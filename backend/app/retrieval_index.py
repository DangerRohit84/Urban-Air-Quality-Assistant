"""Cached TF-IDF index fitted once per corpus."""

from __future__ import annotations

import hashlib
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer

from backend.app.models import Document

_CACHE: dict[str, tuple[Any, Any, list[dict]]] = {}
_STATS = {"hits": 0, "misses": 0}


def _cache_key(owner_id: str, corpus: list[Document]) -> str:
    """Build the cache key for one owner's corpus.

    Args:
        owner_id: The owner whose corpus is indexed (empty for the seed-only
            corpus).
        corpus: The documents.

    Returns:
        The ``owner:corpus-hash`` key.
    """
    return f"{owner_id}:{_corpus_hash(corpus)}"


def _corpus_hash(corpus: list[Document]) -> str:
    """Hash the corpus identity.

    Args:
        corpus: The documents.

    Returns:
        The hex digest.
    """
    payload = "|".join(f"{doc.id}:{doc.text}" for doc in corpus)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _records(corpus: list[Document]) -> list[dict]:
    """Convert documents to index records.

    Args:
        corpus: The documents.

    Returns:
        The records.
    """
    return [
        {
            "id": doc.id,
            "title": doc.title,
            "text": f"{doc.title}\n{doc.text}",
            "source": doc.source,
        }
        for doc in corpus
    ]


def _get_index(
    corpus: list[Document], owner_id: str = ""
) -> tuple[Any, Any, list[dict]]:
    """Return a cached ``(vectorizer, matrix, records)`` triple.

    Args:
        corpus: The documents to index.
        owner_id: The owner whose corpus is indexed (empty for seed-only).

    Returns:
        The vectorizer, the term matrix (or None) and the records.
    """
    key = _cache_key(owner_id, corpus)
    cached = _CACHE.get(key)
    if cached is not None:
        _STATS["hits"] += 1
        return cached
    _STATS["misses"] += 1
    records = _records(corpus)
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = None
    if records:
        matrix = vectorizer.fit_transform([record["text"] for record in records])
    result = (vectorizer, matrix, records)
    _CACHE[key] = result
    return result


def get_index_stats() -> dict[str, int]:
    """Return cache statistics.

    Returns:
        The ``hits``/``misses``/``size`` mapping.
    """
    return {
        "hits": _STATS["hits"],
        "misses": _STATS["misses"],
        "size": len(_CACHE),
    }


def invalidate_index(owner_id: str) -> int:
    """Drop every cached index belonging to ``owner_id``.

    Args:
        owner_id: The owner whose cache entries are dropped.

    Returns:
        The number of dropped entries.
    """
    prefix = f"{owner_id}:"
    keys = [key for key in _CACHE if key.startswith(prefix)]
    for key in keys:
        del _CACHE[key]
    return len(keys)


def reset_index() -> None:
    """Clear the index cache and statistics."""
    _CACHE.clear()
    _STATS["hits"] = 0
    _STATS["misses"] = 0
