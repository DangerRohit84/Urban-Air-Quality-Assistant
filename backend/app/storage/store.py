"""Repository locator, lifecycle and health counts."""

from __future__ import annotations

from backend.app.config import settings
from backend.app.storage.memory import InMemoryRepo
from backend.app.storage.protocol import Repository
from backend.app.storage.sqlite_store import SQLiteRepo

_repo: Repository | None = None


def build_repo() -> Repository:
    """Build a repository from ``STORE_BACKEND``.

    Returns:
        The configured repository instance.
    """
    if settings.store_backend == "memory":
        return InMemoryRepo()
    return SQLiteRepo(settings.db_path)


def get_repo() -> Repository:
    """Return the process-wide repository, building it on first use.

    Returns:
        The shared repository instance.
    """
    global _repo
    if _repo is None:
        _repo = build_repo()
    return _repo


def reset_repo(repo: Repository | None = None) -> None:
    """Replace the shared repository, closing the previous one.

    Args:
        repo: The new repository, or None to drop the current one.
    """
    global _repo
    if _repo is not None:
        _repo.close()
    _repo = repo


def store_counts() -> dict[str, int]:
    """Return row counts for the health snapshot.

    Returns:
        A ``users``/``profiles``/``documents`` mapping.
    """
    repo = get_repo()
    return {
        "users": repo.count_users(),
        "profiles": repo.count_profiles(),
        "documents": repo.count_all_documents(),
    }
