"""Tests for the application-wide error handlers."""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_unknown_route_returns_404_json() -> None:
    """An unknown route returns a JSON 404 body."""
    client = TestClient(create_app())

    response = client.get("/definitely-not-a-route")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_value_error_maps_to_400() -> None:
    """A handler raising ``ValueError`` is rendered as a 400."""
    app = create_app()

    @app.get("/bad")
    def bad() -> None:
        raise ValueError("bad input")

    client = TestClient(app)

    response = client.get("/bad")

    assert response.status_code == 400
    assert response.json() == {"detail": "bad input"}


def test_http_exception_passthrough_keeps_status_and_detail() -> None:
    """``HTTPException`` keeps its status code and detail."""
    app = create_app()

    @app.get("/conflict")
    def conflict() -> None:
        raise HTTPException(status_code=409, detail="conflict")

    client = TestClient(app)

    response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {"detail": "conflict"}


def test_error_bodies_never_leak_tracebacks() -> None:
    """No error body contains traceback text."""
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret stack detail")

    client = TestClient(app, raise_server_exceptions=False)

    for path in ("/definitely-not-a-route", "/boom"):
        body = client.get(path).text.lower()
        assert "traceback" not in body
        assert "secret stack detail" not in body
        assert "file \"" not in body
