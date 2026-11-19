"""Tests for chunking, the seed corpus, TF-IDF search and the fallback."""

from __future__ import annotations

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from backend.app import corpus, retrieval, retrieval_fallback, retrieval_index
from backend.app.chunking import chunk_text
from backend.app.storage.memory import InMemoryRepo
from backend.app.storage.store import get_repo


def _owner(document_text: str) -> str:
    """Create a user with one document and return the owner id."""
    repo = get_repo()
    user = repo.create_user(f"owner-{document_text[:8]}@example.com", "hash")
    repo.create_document(
        _document(user.id, document_text),
    )
    return user.id


def _document(owner_id: str, text: str) -> object:
    """Build a document draft for ``owner_id``."""
    from backend.app.models import Document

    return Document(
        id="",
        owner_id=owner_id,
        kind="corpus",
        title="Owner note",
        text=text,
        chunks=chunk_text(text),
        source="user",
        created_at="",
    )


def test_seed_corpus_has_cited_documents() -> None:
    """The seed corpus holds at least eight cited documents."""
    documents = corpus.load_seed_corpus()

    assert len(documents) >= 8
    assert all(document.source.strip() for document in documents)
    assert all(document.chunks for document in documents)


def test_chunk_text_overlaps_and_respects_size() -> None:
    """Chunks overlap and never exceed the requested size."""
    chunks = chunk_text("abcdefghij", size=4, overlap=1)

    assert chunks == ["abcd", "defg", "ghij"]
    assert all(len(chunk) <= 4 for chunk in chunks)


def test_chunk_text_empty() -> None:
    """An empty input produces no chunks."""
    assert chunk_text("   ") == []


def test_search_returns_scored_hits() -> None:
    """A meaningful query returns hits with a score in (0, 1]."""
    hits = retrieval.search("indoor air purifier")

    assert hits
    assert all(0 < hit["score"] <= 1 for hit in hits)
    assert all({"id", "title", "text", "score", "source"} <= set(hit) for hit in hits)


def test_top_k_is_clamped() -> None:
    """``top_k`` never exceeds ten."""
    hits = retrieval.search("air quality", top_k=100)

    assert len(hits) <= 10


def test_stop_word_query_returns_empty() -> None:
    """A stop-word-only query has no signal."""
    assert retrieval.search("the and of to") == []


def test_empty_corpus_returns_empty() -> None:
    """An empty corpus yields no hits."""
    assert retrieval_fallback._rank_by_token_overlap([], "air quality", 5) == []
    _, matrix, documents = retrieval_index._get_index([])
    assert documents == []
    assert matrix is None


def test_owner_isolation() -> None:
    """A document is retrievable only by its owner."""
    owner_id = _owner("zyloflux heuristic guideline for clean rooms")
    other = get_repo().create_user("other-isolation@example.com", "hash")

    owner_hits = retrieval.search("zyloflux", owner_id=owner_id)
    other_hits = retrieval.search("zyloflux", owner_id=other.id)

    assert any(hit["id"] != "seed" for hit in owner_hits)
    assert any("zyloflux" in hit["text"] for hit in owner_hits)
    assert other_hits == []


def test_cache_stats_increment_and_reset() -> None:
    """Repeat queries hit the cache and ``reset_cache`` zeroes it."""
    retrieval.reset_cache()
    before = retrieval.get_cache_stats()

    retrieval.search("indoor air purifier", owner_id="cache-user")
    middle = retrieval.get_cache_stats()
    assert middle["misses"] > before["misses"]

    retrieval.search("indoor air purifier", owner_id="cache-user")
    after = retrieval.get_cache_stats()
    assert after["hits"] > middle["hits"]

    retrieval.reset_cache()
    assert retrieval.get_cache_stats() == {"hits": 0, "misses": 0, "size": 0}


def test_fallback_stop_words_match_sklearn() -> None:
    """The zero-dependency stop-word set matches sklearn's."""
    assert retrieval_fallback._STOP_WORDS == ENGLISH_STOP_WORDS


def test_fallback_ranks_token_overlap() -> None:
    """The fallback ranks a matching document above an unrelated one."""
    documents = [
        {
            "id": "a",
            "title": "A",
            "text": "indoor air purifier with hepa filter",
            "source": "seed",
        },
        {
            "id": "b",
            "title": "B",
            "text": "cooking with lpg",
            "source": "seed",
        },
    ]

    ranked = retrieval_fallback._rank_by_token_overlap(documents, "air purifier", 5)

    assert ranked[0]["id"] == "a"


def test_assemble_corpus_is_owner_scoped() -> None:
    """``assemble_corpus`` returns the seed corpus plus the owner's docs."""
    repo = InMemoryRepo()
    user = repo.create_user("assemble@example.com", "hash")
    repo.create_document(
        _document(user.id, "assemble corpus marker"),
    )

    documents = corpus.assemble_corpus(repo, user.id)

    assert len(documents) >= 9
    assert sum(1 for doc in documents if doc.owner_id == user.id) == 1
