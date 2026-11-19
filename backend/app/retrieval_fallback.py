"""Zero-dependency stop-word and token-overlap ranker."""

from __future__ import annotations

import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

_STOP_WORDS = ENGLISH_STOP_WORDS
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(query: str) -> list[str]:
    """Tokenize and lower-case ``query``.

    Args:
        query: The raw query.

    Returns:
        The alphanumeric tokens.
    """
    return _TOKEN_RE.findall(query.lower())


def _has_signal(query: str) -> bool:
    """Return True when ``query`` has a non-stop-word token.

    Args:
        query: The raw query.

    Returns:
        True when the query carries signal.
    """
    return any(token not in _STOP_WORDS for token in _tokens(query))


def _rank_by_token_overlap(
    corpus: list[dict], query: str, top_k: int
) -> list[dict]:
    """Rank documents by token overlap with ``query``.

    Args:
        corpus: The documents to rank.
        query: The raw query.
        top_k: The maximum number of hits.

    Returns:
        The ranked hits with a normalized score.
    """
    query_tokens = {token for token in _tokens(query) if token not in _STOP_WORDS}
    if not query_tokens:
        return []
    scored: list[tuple[float, str, dict]] = []
    for document in corpus:
        text_tokens = set(_tokens(str(document.get("text", ""))))
        overlap = len(query_tokens & text_tokens)
        if overlap:
            scored.append(
                (overlap / len(query_tokens), str(document.get("id", "")), document)
            )
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {**document, "score": score} for score, _, document in scored[:top_k]
    ]
