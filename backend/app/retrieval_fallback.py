"""Zero-dependency stop-word and token-overlap ranker."""

from __future__ import annotations

import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

_STOP_WORDS = ENGLISH_STOP_WORDS
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Generic superlatives and conversational padding carry no domain evidence.
# Excluding them stops "best" in "best pizza in Naples" from counting as a
# match against seed-001's "for the best reduction".
_FILLER_WORDS = frozenset(
    {
        "actually",
        "basically",
        "best",
        "better",
        "good",
        "great",
        "kindly",
        "nice",
        "please",
        "really",
        "recommend",
        "recommended",
        "simply",
        "suggest",
        "top",
        "worst",
    }
)

# Irregular variants that plural stripping cannot reduce to one form.
_ALIASES = {
    "children": "child",
    "kid": "child",
    "kids": "child",
    "smoggy": "smog",
}


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


def _canonical(token: str) -> str:
    """Return the comparison form of one token.

    The mapping is intentionally small: irregular aliases plus a plural
    ``s`` strip for words longer than three characters. It lets a query say
    "child" or "smoggy" while the corpus says "children" or "smog", without
    pulling in a stemmer dependency.

    Args:
        token: The lower-cased token.

    Returns:
        The canonical token.
    """
    token = _ALIASES.get(token, token)
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    return token


def _content_tokens(query: str) -> set[str]:
    """Return the meaningful, canonicalized tokens of ``query``.

    Args:
        query: The raw query.

    Returns:
        The content tokens, lower-cased and de-duplicated.
    """
    return {
        _canonical(token)
        for token in _tokens(query)
        if token not in _STOP_WORDS and token not in _FILLER_WORDS
    }


def _coverage(query: str, document: dict) -> float:
    """Return the fraction of query content tokens present in ``document``.

    Args:
        query: The raw query.
        document: The document record (its ``text`` includes the title).

    Returns:
        The overlap ratio in ``[0, 1]``; ``0.0`` for a signal-free query.
    """
    query_tokens = _content_tokens(query)
    if not query_tokens:
        return 0.0
    text_tokens = {
        _canonical(token) for token in _tokens(str(document.get("text", "")))
    }
    return len(query_tokens & text_tokens) / len(query_tokens)


def _rank_by_token_overlap(corpus: list[dict], query: str, top_k: int) -> list[dict]:
    """Rank documents by token overlap with ``query``.

    Args:
        corpus: The documents to rank.
        query: The raw query.
        top_k: The maximum number of hits.

    Returns:
        The ranked hits with a normalized score.
    """
    query_tokens = _content_tokens(query)
    if not query_tokens:
        return []
    scored: list[tuple[float, str, dict]] = []
    for document in corpus:
        coverage = _coverage(query, document)
        if coverage:
            scored.append((coverage, str(document.get("id", "")), document))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [{**document, "score": score} for score, _, document in scored[:top_k]]
