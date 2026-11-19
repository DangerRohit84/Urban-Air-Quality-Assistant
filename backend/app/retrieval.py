"""Retrieval orchestration: signal guard, TF-IDF and fallback."""

from __future__ import annotations

from backend.app.corpus import assemble_corpus, load_seed_corpus
from backend.app.retrieval_fallback import _has_signal, _rank_by_token_overlap
from backend.app.retrieval_index import _get_index, get_index_stats, reset_index
from backend.app.storage.store import get_repo

MIN_TOP_K = 1
MAX_TOP_K = 10
DEFAULT_TOP_K = 5


def _clamp_top_k(top_k: int) -> int:
    """Clamp ``top_k`` to the supported range.

    Args:
        top_k: The requested number of hits.

    Returns:
        The clamped value.
    """
    return max(MIN_TOP_K, min(int(top_k), MAX_TOP_K))


def search(
    query: str, top_k: int = DEFAULT_TOP_K, owner_id: str | None = None
) -> list[dict]:
    """Search the corpus for ``query``.

    Args:
        query: The raw query.
        top_k: The maximum number of hits.
        owner_id: The owner whose documents are included.

    Returns:
        The ranked hits, each with id, title, text, score and source.
    """
    limit = _clamp_top_k(top_k)
    if not _has_signal(query):
        return []
    if owner_id is None:
        documents = load_seed_corpus()
    else:
        documents = assemble_corpus(get_repo(), owner_id)
    if not documents:
        return []
    vectorizer, matrix, records = _get_index(documents)
    if matrix is None:
        return []
    try:
        scores = (vectorizer.transform([query]) @ matrix.T).toarray()[0]
    except Exception:  # noqa: BLE001 - degrade to the zero-dep ranker
        return _rank_by_token_overlap(records, query, limit)
    order = sorted(
        range(len(records)),
        key=lambda index: (-scores[index], str(records[index]["id"])),
    )
    hits = [
        {**records[index], "score": round(float(scores[index]), 6)}
        for index in order
    ]
    hits = [hit for hit in hits if hit["score"] > 0]
    if not hits:
        return _rank_by_token_overlap(records, query, limit)
    return hits[:limit]


def get_cache_stats() -> dict[str, int]:
    """Return retrieval cache statistics.

    Returns:
        The ``hits``/``misses``/``size`` mapping.
    """
    return get_index_stats()


def reset_cache() -> None:
    """Reset the retrieval cache."""
    reset_index()
