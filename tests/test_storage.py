"""Tests for the storage layer: schema, migrations, memory and SQLite repos."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from backend.app.config import settings
from backend.app.models import AqiContext, Document, Profile
from backend.app.storage.memory import InMemoryRepo
from backend.app.storage.migrations import apply_migrations
from backend.app.storage.protocol import Repository
from backend.app.storage.schema import TABLES
from backend.app.storage.sqlite_store import SQLiteRepo
from backend.app.storage.store import build_repo, get_repo, reset_repo


def _profile(user_id: str, city: str = "Delhi", updated: str = "t1") -> Profile:
    """Build a valid profile for ``user_id``."""
    return Profile(
        user_id=user_id,
        city=city,
        climate_zone="north",
        children=False,
        elderly=False,
        respiratory=False,
        commute_mode="bus",
        commute_km=5.0,
        cooking_fuel="lpg",
        heating_type="none",
        budget_level="medium",
        updated_at=updated,
    )


def _context(user_id: str) -> AqiContext:
    """Build a valid AQI context for ``user_id``."""
    return AqiContext(
        user_id=user_id,
        city="Delhi",
        band="Poor",
        value=250,
        pm25=120.5,
        pm10=200.0,
        season="winter",
        observed_at="2026-11-18T00:00:00+00:00",
        source="user",
    )


def _document(owner_id: str, title: str = "Doc") -> Document:
    """Build a document draft for ``owner_id``."""
    return Document(
        id="",
        owner_id=owner_id,
        kind="corpus",
        title=title,
        text="body",
        chunks=["body"],
        source="seed",
        created_at="",
    )


@pytest.fixture(params=["memory", "sqlite"])
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> Repository:
    """Return a fresh repository of each backend."""
    if request.param == "memory":
        return InMemoryRepo()
    return SQLiteRepo(tmp_path / "store.db")  # type: ignore[operator]


def test_schema_v1_creates_tables_and_version(tmp_path: Path) -> None:
    """Schema v1 creates the four tables and sets ``user_version`` to 1."""
    conn = sqlite3.connect(tmp_path / "schema.db")
    try:
        version = apply_migrations(conn)

        assert version == 1
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert set(TABLES) <= tables
    finally:
        conn.close()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    """Applying v1 twice is a no-op and preserves unrelated rows."""
    conn = sqlite3.connect(tmp_path / "migrate.db")
    try:
        conn.execute("CREATE TABLE sentinel (id INTEGER)")
        conn.execute("INSERT INTO sentinel (id) VALUES (7)")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()

        assert apply_migrations(conn) == 1
        assert apply_migrations(conn) == 1
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert conn.execute("SELECT id FROM sentinel").fetchone()[0] == 7
    finally:
        conn.close()


def test_user_round_trip(repo: Repository) -> None:
    """A created user is retrievable by email and by id."""
    user = repo.create_user("a@b.com", "hash")

    assert user.id
    assert user.email == "a@b.com"
    assert user.password_hash == "hash"
    assert user.created_at
    assert repo.get_user_by_email("a@b.com") == user
    assert repo.get_user_by_id(user.id) == user
    assert repo.get_user_by_email("missing@b.com") is None
    assert repo.get_user_by_id("nope") is None


def test_update_user_password_hash(repo: Repository) -> None:
    """Both backends replace a stored hash and ignore unknown users."""
    user = repo.create_user("legacy@b.com", "old-hash")

    repo.update_user_password_hash(user.id, "new-hash")
    repo.update_user_password_hash("missing", "ignored")

    updated = repo.get_user_by_email("legacy@b.com")
    assert updated is not None
    assert updated.password_hash == "new-hash"
    assert repo.get_user_by_id(user.id) == updated
    assert repo.count_users() == 1


def test_duplicate_email_raises_value_error(repo: Repository) -> None:
    """Both backends reject a second registration for the same email."""
    repo.create_user("dupe@b.com", "hash")

    with pytest.raises(ValueError, match="already registered"):
        repo.create_user("dupe@b.com", "hash")

    assert repo.count_users() == 1


def test_profile_upsert_keeps_latest(repo: Repository) -> None:
    """Saving a profile twice leaves one row with the latest values."""
    user = repo.create_user("p@b.com", "hash")
    first = _profile(user.id, city="Delhi", updated="t1")
    second = replace(first, city="Mumbai", updated_at="t2")

    repo.save_profile(first)
    repo.save_profile(second)

    assert repo.get_profile(user.id) == second
    assert repo.get_profile("nobody") is None


def test_aqi_context_round_trip(repo: Repository) -> None:
    """A stored AQI context round-trips exactly."""
    user = repo.create_user("c@b.com", "hash")
    ctx = _context(user.id)

    repo.save_aqi_context(ctx)

    assert repo.get_aqi_context(user.id) == ctx
    assert repo.get_aqi_context("nobody") is None


def test_document_crud_and_owner_isolation(repo: Repository) -> None:
    """Documents are owner-scoped and deletion is owner-checked."""
    alice = repo.create_user("alice@b.com", "hash")
    bob = repo.create_user("bob@b.com", "hash")
    doc_a = repo.create_document(_document(alice.id, "A"))
    doc_b = repo.create_document(_document(bob.id, "B"))

    assert doc_a.id
    assert doc_a.created_at
    assert repo.list_documents(alice.id) == [doc_a]
    assert repo.list_documents(bob.id) == [doc_b]
    assert repo.get_document(doc_a.id) == doc_a
    assert repo.count_documents(alice.id) == 1
    assert repo.count_documents(bob.id) == 1

    assert repo.delete_document(doc_a.id, bob.id) is False
    assert repo.get_document(doc_a.id) == doc_a
    assert repo.delete_document(doc_a.id, alice.id) is True
    assert repo.get_document(doc_a.id) is None
    assert repo.list_documents(alice.id) == []


def _run_script(repo: Repository) -> dict[str, object]:
    """Run the same operation script against any backend."""
    user = repo.create_user("script@b.com", "hash")
    other = repo.create_user("other@b.com", "hash")
    repo.save_profile(_profile(user.id))
    repo.save_aqi_context(_context(user.id))
    doc = repo.create_document(_document(user.id, "Script"))
    return {
        "profile": replace(repo.get_profile(user.id), user_id=""),
        "context": replace(repo.get_aqi_context(user.id), user_id=""),
        "doc_fields": (doc.kind, doc.title, doc.text, doc.chunks, doc.source),
        "list_titles": [item.title for item in repo.list_documents(user.id)],
        "other_list": repo.list_documents(other.id),
        "delete_foreign": repo.delete_document(doc.id, other.id),
        "delete_own": repo.delete_document(doc.id, user.id),
        "counts": (
            repo.count_documents(user.id),
            repo.count_documents(other.id),
        ),
    }


def test_memory_and_sqlite_parity(tmp_path: Path) -> None:
    """Both backends produce the same observable results."""
    memory = InMemoryRepo()
    sqlite_repo = SQLiteRepo(tmp_path / "parity.db")

    left = _run_script(memory)
    right = _run_script(sqlite_repo)

    assert left == right


def test_concurrent_writes_do_not_500(tmp_path: Path) -> None:
    """Concurrent profile saves and document creates never raise."""
    repo = SQLiteRepo(tmp_path / "race.db")
    user = repo.create_user("race@b.com", "hash")
    other = repo.create_user("other@b.com", "hash")

    def write_profile(index: int) -> None:
        repo.save_profile(_profile(user.id, city=f"city{index}", updated=f"t{index}"))

    def write_own_doc(index: int) -> None:
        repo.create_document(_document(user.id, f"A{index}"))

    def write_other_doc(index: int) -> None:
        repo.create_document(_document(other.id, f"B{index}"))

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = []
        for index in range(20):
            futures.append(pool.submit(write_profile, index))
            futures.append(pool.submit(write_own_doc, index))
            futures.append(pool.submit(write_other_doc, index))
        for future in futures:
            future.result()

    final = repo.get_profile(user.id)
    assert final is not None
    assert final.city in {f"city{i}" for i in range(20)}
    assert repo.count_documents(user.id) == 20
    assert repo.count_documents(other.id) == 20


def test_concurrent_duplicate_registers_admit_one_user(tmp_path: Path) -> None:
    """A SQLite uniqueness race creates exactly one account."""
    repo = SQLiteRepo(tmp_path / "dupe-race.db")

    def register(_: int) -> str:
        try:
            repo.create_user("dupe-race@b.com", "hash")
        except ValueError:
            return "duplicate"
        return "created"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(register, range(8)))

    assert results.count("created") == 1
    assert results.count("duplicate") == 7
    assert repo.count_users() == 1


def test_build_repo_selects_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``STORE_BACKEND`` selects the memory or SQLite implementation."""
    monkeypatch.setattr(settings, "store_backend", "memory")
    assert isinstance(build_repo(), InMemoryRepo)

    monkeypatch.setattr(settings, "store_backend", "sqlite")
    monkeypatch.setattr(
        settings, "database_url", f"sqlite:///{tmp_path}/build.db"
    )
    assert isinstance(build_repo(), SQLiteRepo)


def test_reset_repo_replaces_the_shared_instance() -> None:
    """``reset_repo`` closes the old repo and installs the new one."""
    reset_repo(InMemoryRepo())
    first = get_repo()

    reset_repo(InMemoryRepo())
    second = get_repo()

    assert second is not first
    reset_repo(InMemoryRepo())
