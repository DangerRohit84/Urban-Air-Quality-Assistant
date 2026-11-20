"""Retrieval orchestration: signal guard, TF-IDF and fallback."""

from __future__ import annotations

from backend.app.corpus import assemble_corpus, load_seed_corpus
from backend.app.retrieval_fallback import (
    _coverage,
    _has_signal,
    _rank_by_token_overlap,
)
from backend.app.retrieval_index import (
    _get_index,
    get_index_stats,
    invalidate_index,
    reset_index,
)
from backend.app.storage.store import get_repo

MIN_TOP_K = 1
MAX_TOP_K = 10
DEFAULT_TOP_K = 5

# A candidate hit counts as support only when it clears BOTH gates:
#   * MIN_RELEVANCE - a TF-IDF cosine floor. 0.15 sits below the weakest
#     legitimate seed query observed (~0.17) and above matches that share only
#     a negligible slice of the query's term weight.
#   * MIN_COVERAGE - at least 30% of the query's content tokens must appear in
#     the hit's text/title. Content tokens exclude stop words, generic filler
#     ("best", "top", ...) and are lightly normalized ("children" -> "child",
#     "smoggy" -> "smog", plurals -> singular). This generalises "at least one
#     content token": a one- or two-word query still needs a single match,
#     while "best pizza in Naples" now has no content-token match at all.
MIN_RELEVANCE = 0.15
MIN_COVERAGE = 0.3


def _clamp_top_k(top_k: int) -> int:
    """Clamp ``top_k`` to the supported range.

    Args:
        top_k: The requested number of hits.

    Returns:
        The clamped value.
    """
    return max(MIN_TOP_K, min(int(top_k), MAX_TOP_K))


def _is_relevant(query: str, hit: dict) -> bool:
    """Return True when ``hit`` is relevant enough to ground ``query``.

    Args:
        query: The raw query.
        hit: The candidate hit.

    Returns:
        True when the score floor and the content-coverage floor both hold.
    """
    return (
        float(hit.get("score", 0.0)) >= MIN_RELEVANCE
        and _coverage(query, hit) >= MIN_COVERAGE
    )


def _relevant(hits: list[dict], query: str) -> list[dict]:
    """Filter ``hits`` down to the ones that ground ``query``.

    Args:
        hits: The candidate hits.
        query: The raw query.

    Returns:
        The hits that clear both relevance gates.
    """
    return [hit for hit in hits if _is_relevant(query, hit)]


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
    vectorizer, matrix, records = _get_index(documents, owner_id or "")
    if matrix is None:
        return []
    try:
        scores = (vectorizer.transform([query]) @ matrix.T).toarray()[0]
    except Exception:  # noqa: BLE001 - degrade to the zero-dep ranker
        return _relevant(_rank_by_token_overlap(records, query, limit), query)
    order = sorted(
        range(len(records)),
        key=lambda index: (-scores[index], str(records[index]["id"])),
    )
    hits = [
        {**records[index], "score": round(float(scores[index]), 6)}
        for index in order
    ]
    hits = _relevant(hits, query)
    if not hits:
        # Zero-dependency path: the fallback score IS the token coverage, so
        # applying the same filter keeps both paths on one rule.
        hits = _relevant(_rank_by_token_overlap(records, query, limit), query)
    return hits[:limit]


def get_cache_stats() -> dict[str, int]:
    """Return retrieval cache statistics.

    Returns:
        The ``hits``/``misses``/``size`` mapping.
    """
    return get_index_stats()


def invalidate_cache(owner_id: str) -> None:
    """Invalidate only ``owner_id``'s retrieval cache entries.

    Args:
        owner_id: The owner whose documents changed.
    """
    invalidate_index(owner_id)


def reset_cache() -> None:
    """Reset the entire retrieval cache and statistics."""
    reset_index()
