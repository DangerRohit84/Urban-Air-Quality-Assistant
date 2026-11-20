"""Tiny local HTTP servers for LLM client tests."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class RecordedRequest:
    """A request observed by the test server."""

    path: str
    authorization: str | None


@dataclass
class Server:
    """A running local server and its observations."""

    base_url: str
    hits: list[RecordedRequest] = field(default_factory=list)


@contextmanager
def serve(
    status: int, body: bytes, location: str | None = None
) -> Iterator[Server]:
    """Serve one canned response and record every request.

    Args:
        status: The HTTP status code to return.
        body: The response body.
        location: The optional ``Location`` header for redirects.

    Yields:
        The running server with its request log.
    """
    hits: list[RecordedRequest] = []

    class Handler(BaseHTTPRequestHandler):
        """Record each POST and return the canned response."""

        def do_POST(self) -> None:  # noqa: N802 - http.server contract
            """Record the request and write the canned response."""
            hits.append(
                RecordedRequest(
                    path=self.path,
                    authorization=self.headers.get("Authorization"),
                )
            )
            self.send_response(status)
            if location is not None:
                self.send_header("Location", location)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            """Silence the default request logging."""
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Server(f"http://127.0.0.1:{server.server_port}", hits)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
