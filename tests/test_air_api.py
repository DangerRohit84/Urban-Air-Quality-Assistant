"""Tests for the air context and live AQI routes."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.app.air.provider import LiveAqiReading
from backend.app.aqi import band_from_openweather_index
from backend.app.config import settings

CONTEXT = {"city": "Delhi", "band": "Poor", "season": "winter", "value": 250}


class _FixedProvider:
    """A provider returning a fixed reading."""

    def __init__(self, reading: LiveAqiReading) -> None:
        """Store the reading."""
        self._reading = reading

    def fetch(self, city: object) -> LiveAqiReading:
        """Return the fixed reading."""
        return self._reading


class _RaisingProvider:
    """A provider that always fails."""

    def fetch(self, city: object) -> LiveAqiReading:
        """Raise to simulate a network failure."""
        raise RuntimeError("boom")


def test_context_round_trip_and_get_reflects_it(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A stored context is returned by ``GET /air``."""
    stored = client.post("/air/context", headers=auth_headers, json=CONTEXT)

    assert stored.status_code == 200
    assert stored.json()["band"] == "Poor"
    assert stored.json()["source"] == "user"

    response = client.get("/air?q=Delhi", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["city"] == "Delhi"
    assert body["band"] == "Poor"
    assert body["source"] == "not_configured"
    assert body["fallback"]


def test_get_air_without_key_is_not_configured(
    client: TestClient, auth_headers: dict[str, str], monkeypatch: object
) -> None:
    """Without a key the route degrades gracefully."""
    monkeypatch.setattr(settings, "aqi_api_key", "")

    response = client.get("/air?q=Delhi", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "not_configured"
    assert body["fallback"]


def test_live_reading_is_used_when_key_set(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: object,
) -> None:
    """A configured key yields a live reading."""
    monkeypatch.setattr(settings, "aqi_api_key", "key")
    reading = LiveAqiReading(
        band=band_from_openweather_index(4),
        value=250,
        pm25=150.0,
        pm10=200.0,
        native_index=4,
    )
    monkeypatch.setattr(
        "backend.app.routes.air.OpenWeatherProvider",
        lambda api_key: _FixedProvider(reading),
    )

    response = client.get("/air?q=Delhi", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "live"
    assert body["band"] == "Poor"
    assert body["value"] == 250
    assert body["native_index"] == 4
    assert body["pm25"] == 150.0


def test_live_provider_failure_falls_back(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: object,
) -> None:
    """A raising provider never becomes a 500."""
    monkeypatch.setattr(settings, "aqi_api_key", "key")
    monkeypatch.setattr(
        "backend.app.routes.air.OpenWeatherProvider",
        lambda api_key: _RaisingProvider(),
    )

    response = client.get("/air?q=Delhi", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["source"] == "offline"
    assert "unavailable" in response.json()["fallback"]


def test_live_provider_failure_with_saved_context_is_offline(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: object,
) -> None:
    """A configured provider failure serves the saved band as offline."""
    monkeypatch.setattr(settings, "aqi_api_key", "key")
    client.post("/air/context", headers=auth_headers, json=CONTEXT)
    monkeypatch.setattr(
        "backend.app.routes.air.OpenWeatherProvider",
        lambda api_key: _RaisingProvider(),
    )

    response = client.get("/air?q=Delhi", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "offline"
    assert body["band"] == "Poor"
    assert body["value"] == 250
    assert "unavailable" in body["fallback"]


def test_live_route_uses_official_endpoint_and_payload(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch: object,
) -> None:
    """The route calls the official endpoint and parses ``main.aqi``."""
    monkeypatch.setattr(settings, "aqi_api_key", "key")
    payload = {
        "list": [
            {
                "main": {"aqi": 3},
                "components": {"pm2_5": 80.0, "pm10": 120.0},
            }
        ]
    }
    captured: dict[str, str] = {}

    class _Response:
        def read(self) -> bytes:
            return json.dumps(payload).encode()

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    def fake_urlopen(url: str, timeout: float) -> _Response:
        captured["url"] = url
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    response = client.get("/air?q=Delhi", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "live"
    assert body["band"] == "Moderately Polluted"
    assert body["value"] == 150
    assert body["native_index"] == 3
    assert body["pm25"] == 80.0
    assert "/data/2.5/air_pollution" in captured["url"]
    assert "air-pollution" not in captured["url"]


def test_unknown_city_is_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    """An unknown city is a 404, never a 500."""
    response = client.get("/air?q=Atlantis", headers=auth_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "unknown city"}


def test_context_is_owner_scoped(client: TestClient) -> None:
    """One user's context never leaks into another user's reading."""
    owner = client.post(
        "/auth/register",
        json={"email": "air-owner@example.com", "password": "TestPass123"},
    ).json()
    other = client.post(
        "/auth/register",
        json={"email": "air-other@example.com", "password": "TestPass123"},
    ).json()
    owner_headers = {"Authorization": f"Bearer {owner['token']}"}
    other_headers = {"Authorization": f"Bearer {other['token']}"}
    assert (
        client.post(
            "/air/context", headers=owner_headers, json=CONTEXT
        ).status_code
        == 200
    )

    response = client.get("/air?q=Delhi", headers=other_headers)

    assert response.status_code == 200
    assert response.json()["source"] == "not_configured"
    assert response.json()["band"] != "Poor"


def test_invalid_band_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown band is rejected."""
    response = client.post(
        "/air/context",
        headers=auth_headers,
        json={**CONTEXT, "band": "Purple"},
    )

    assert response.status_code == 422


def test_invalid_season_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """An unknown season is rejected."""
    response = client.post(
        "/air/context",
        headers=auth_headers,
        json={**CONTEXT, "season": "rainbow"},
    )

    assert response.status_code == 422


def test_context_unknown_city_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A city outside the coordinates table is rejected."""
    response = client.post(
        "/air/context",
        headers=auth_headers,
        json={**CONTEXT, "city": "Atlantis"},
    )

    assert response.status_code == 422


def test_oversized_air_city_is_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """A city above 80 characters is rejected."""
    response = client.post(
        "/air/context",
        headers=auth_headers,
        json={**CONTEXT, "city": "x" * 81},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["value", "pm25", "pm10"])
def test_out_of_range_air_values_are_422_without_echo(
    client: TestClient, auth_headers: dict[str, str], field: str
) -> None:
    """Huge numeric readings are rejected and never echoed."""
    huge = 10**30

    response = client.post(
        "/air/context",
        headers=auth_headers,
        json={**CONTEXT, field: huge},
    )

    assert response.status_code == 422
    assert str(huge) not in response.text


def test_openweather_adapter_parses_payload() -> None:
    """The adapter converts the OpenWeather index and components."""
    from backend.app.air.openweather import OpenWeatherProvider
    from backend.app.cities import resolve_city

    payload = {
        "list": [
            {
                "main": {"aqi": 4},
                "components": {"pm2_5": 150.0, "pm10": 210.5},
            }
        ]
    }

    class _Response:
        def read(self) -> bytes:
            return json.dumps(payload).encode()

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    class _Client:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def __call__(self, url: str, timeout: float) -> _Response:
            self.urls.append(url)
            return _Response()

    client = _Client()
    provider = OpenWeatherProvider("key", client=client)
    reading = provider.fetch(resolve_city("Delhi"))

    assert reading.band.name == "Poor"
    assert reading.value == 250
    assert reading.native_index == 4
    assert reading.pm25 == 150.0
    assert reading.pm10 == 210.5
    assert reading.source == "live"
    assert client.urls == [
        "https://api.openweathermap.org/data/2.5/air_pollution"
        "?lat=28.6139&lon=77.209&appid=key"
    ]
