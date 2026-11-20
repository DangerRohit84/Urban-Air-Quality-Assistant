"""Tests for bounded PDF text extraction."""

from __future__ import annotations

import time

import pytest

from backend.app.pdf_text import MAX_PAGES, PdfTooComplexError, extract_pdf_text
from tests.pdf_fixtures import flate_bomb_pdf, many_pages_pdf, text_pdf


def test_extracts_text_from_a_normal_pdf() -> None:
    """A small text PDF still extracts normally."""
    assert "zyloflux" in extract_pdf_text(text_pdf("zyloflux marker"))


def test_flate_bomb_is_rejected_quickly() -> None:
    """A tiny PDF that expands past the stream cap fails fast."""
    started = time.monotonic()

    with pytest.raises(PdfTooComplexError, match="too complex"):
        extract_pdf_text(flate_bomb_pdf())

    assert time.monotonic() - started < 3.0


def test_pdf_over_the_page_limit_is_rejected() -> None:
    """A PDF with more than ``MAX_PAGES`` pages is rejected before extraction."""
    with pytest.raises(PdfTooComplexError, match=f"more than {MAX_PAGES} pages"):
        extract_pdf_text(many_pages_pdf(MAX_PAGES + 1))
