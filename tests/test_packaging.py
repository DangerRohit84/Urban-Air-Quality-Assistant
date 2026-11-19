"""Clean-checkout packaging gates for the versioned seed corpus."""

from __future__ import annotations

import subprocess
from pathlib import Path

from backend.app.corpus import SEED_CORPUS_PATH, load_seed_corpus

ROOT = Path(__file__).resolve().parents[1]
SEED_RELATIVE = "backend/data/seed_corpus.json"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run git in the repository root.

    Args:
        args: The git arguments.

    Returns:
        The completed process.
    """
    return subprocess.run(  # noqa: S603 - fixed argv, no untrusted input
        [  # noqa: S607 - fixed argv, no untrusted input
            "git",
            "-C",
            str(ROOT),
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_seed_corpus_is_tracked_by_git() -> None:
    """The seed corpus is part of the branch, not only the local tree."""
    result = _git("ls-files", "--error-unmatch", "--", SEED_RELATIVE)

    assert result.returncode == 0, (
        f"{SEED_RELATIVE} is not tracked by git; "
        "a clean clone cannot load the corpus"
    )


def test_seed_corpus_is_not_gitignored() -> None:
    """No ignore rule hides ``backend/data/seed_corpus.json``."""
    result = _git("check-ignore", "-v", "--", SEED_RELATIVE)

    assert result.returncode != 0, result.stdout.strip()


def test_seed_corpus_loads_from_the_checked_out_tree() -> None:
    """The committed corpus parses into unique seed documents."""
    documents = load_seed_corpus()

    assert len(documents) >= 8
    assert SEED_CORPUS_PATH.is_file()
    assert len({document.id for document in documents}) == len(documents)
