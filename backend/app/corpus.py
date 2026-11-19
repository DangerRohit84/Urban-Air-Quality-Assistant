"""Seed corpus loading and per-owner corpus assembly."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.chunking import chunk_text
from backend.app.models import Document
from backend.app.storage.protocol import Repository

SEED_CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_corpus.json"


def load_seed_corpus() -> list[Document]:
    """Load the seeded knowledge base.

    Returns:
        The seed documents with chunked text.
    """
    payload = json.loads(SEED_CORPUS_PATH.read_text(encoding="utf-8"))
    documents: list[Document] = []
    for item in payload:
        text = str(item["text"])
        documents.append(
            Document(
                id=str(item["id"]),
                owner_id="seed",
                kind="seed",
                title=str(item["title"]),
                text=text,
                chunks=chunk_text(text),
                source=str(item["source"]),
                created_at="",
            )
        )
    return documents


def assemble_corpus(repo: Repository, owner_id: str) -> list[Document]:
    """Return the seed corpus plus ``owner_id``'s documents.

    Args:
        repo: The repository.
        owner_id: The owner.

    Returns:
        The combined corpus.
    """
    return load_seed_corpus() + repo.list_documents(owner_id)
