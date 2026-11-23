"""Hard-bounded PDF extraction in a killable spawned worker."""

from __future__ import annotations

import multiprocessing
import time
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess

from backend.app.pdf_parser import (
    EXTRACTION_BUDGET_SECONDS,
    MAX_PAGES,
    MAX_STREAM_BYTES,
    PdfTooComplexError,
    parse_pdf_text,
)

__all__ = [
    "EXTRACTION_BUDGET_SECONDS",
    "EXTRACTION_TIMEOUT_SECONDS",
    "MAX_PAGES",
    "MAX_STREAM_BYTES",
    "PdfTooComplexError",
    "extract_pdf_text",
]

EXTRACTION_TIMEOUT_SECONDS = 6.0


def _extract_worker(data: bytes, result: Connection) -> None:
    """Run ``parse_pdf_text`` in the spawned child.

    Args:
        data: The PDF bytes.
        result: The write end of the result pipe.
    """
    try:
        result.send(("ok", parse_pdf_text(data)))
    except PdfTooComplexError as exc:
        result.send(("complex", str(exc)))
    except Exception as exc:  # noqa: BLE001 - report the class only, never data
        result.send(("error", type(exc).__name__))
    finally:
        result.close()


def _stop(process: BaseProcess) -> None:
    """Terminate and reap ``process`` so no worker is left behind.

    Args:
        process: The extraction worker.
    """
    if process.is_alive():
        process.terminate()
    process.join(1.0)
    if process.is_alive():
        process.kill()
        process.join()
    process.close()


def extract_pdf_text(data: bytes) -> str:
    """Extract text from a PDF within a hard wall-clock bound.

    The pypdf work runs in a spawned worker with a hard timeout, so a
    pathological page cannot pin the API worker past the bound even if the
    in-process character and time visitor never fires.

    Args:
        data: The PDF bytes.

    Returns:
        The extracted text, capped at ``MAX_DOCUMENT_CHARS + 1`` characters.

    Raises:
        PdfTooComplexError: When the PDF exceeds the page, resource or
            wall-clock limits, or the worker dies before reporting.
        ValueError: When the PDF is malformed.
    """
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_extract_worker, args=(data, sender), daemon=True)
    deadline = time.monotonic() + EXTRACTION_TIMEOUT_SECONDS
    try:
        process.start()
        sender.close()
        if not receiver.poll(max(0.0, deadline - time.monotonic())):
            raise PdfTooComplexError("PDF too complex")
        try:
            status, payload = receiver.recv()
        except EOFError as exc:
            raise PdfTooComplexError("PDF too complex") from exc
    finally:
        if process.pid is not None:
            _stop(process)
        receiver.close()
    if status == "ok":
        return str(payload)
    if status == "complex":
        raise PdfTooComplexError(str(payload))
    raise ValueError("could not parse PDF")
