"""OpenWeather Air Pollution API adapter."""

from __future__ import annotations

import json
import urllib.request
from typing import Protocol, cast

from backend.app.air.provider import LiveAqiReading
from backend.app.aqi import band_from_openweather_index, band_midpoint
from backend.app.cities import City

DEFAULT_BASE_URL = "https://api.openweathermap.org/data/2.5/air_pollution"
TIMEOUT_SECONDS = 5.0


class _Response(Protocol):
    """The minimal response surface the adapter consumes."""

    def read(self) -> bytes:
        """Return the raw body."""
        ...

    def __enter__(self) -> _Response:
        """Enter the context manager."""
        ...

    def __exit__(self, *args: object) -> bool:
        """Exit the context manager."""
        ...


class _Client(Protocol):
    """A ``urlopen``-compatible callable."""

    def __call__(self, url: str, timeout: float) -> _Response:
        """Open ``url``."""
        ...


class OpenWeatherProvider:
    """Fetch and convert an OpenWeather air-pollution reading."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        client: _Client | None = None,
    ) -> None:
        """Store the API key, endpoint and optional HTTP client.

        Args:
            api_key: The OpenWeather API key.
            base_url: The air-pollution endpoint.
            client: An optional ``urlopen``-compatible callable for tests.
        """
        self.api_key = api_key
        self.base_url = base_url
        self._client: _Client = client or cast(_Client, urllib.request.urlopen)

    def fetch(self, city: City) -> LiveAqiReading:
        """Fetch and convert the reading for ``city``.

        Args:
            city: The resolved city.

        Returns:
            The converted reading.

        Raises:
            KeyError: When the payload is malformed.
            ValueError: When the native index is out of range.
        """
        url = f"{self.base_url}?lat={city.lat}&lon={city.lon}" f"&appid={self.api_key}"
        with self._client(url, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        entry = payload["list"][0]
        index = int(entry["main"]["aqi"])
        components = entry.get("components", {})
        pm25_raw = components.get("pm2_5")
        pm10_raw = components.get("pm10")
        band = band_from_openweather_index(index)
        return LiveAqiReading(
            band=band,
            # ``value`` must agree with ``band``: emit a CPCB-equivalent
            # value (the band midpoint), not the native 1-5 index.
            value=band_midpoint(band),
            pm25=float(pm25_raw) if pm25_raw is not None else None,
            pm10=float(pm10_raw) if pm10_raw is not None else None,
            native_index=index,
        )
