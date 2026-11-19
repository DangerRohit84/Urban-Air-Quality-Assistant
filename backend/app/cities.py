"""Major Indian city coordinates and resolution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class City:
    """A city with its coordinates."""

    name: str
    lat: float
    lon: float


_CITY_DATA: tuple[tuple[str, float, float], ...] = (
    ("Delhi", 28.6139, 77.209),
    ("Mumbai", 19.076, 72.8777),
    ("Bengaluru", 12.9716, 77.5946),
    ("Chennai", 13.0827, 80.2707),
    ("Kolkata", 22.5726, 88.3639),
    ("Hyderabad", 17.385, 78.4867),
    ("Pune", 18.5204, 73.8567),
    ("Ahmedabad", 23.0225, 72.5714),
    ("Jaipur", 26.9124, 75.7873),
    ("Lucknow", 26.8467, 80.9462),
    ("Chandigarh", 30.7333, 76.7794),
    ("Patna", 25.5941, 85.1376),
    ("Bhopal", 23.2599, 77.4126),
    ("Indore", 22.7196, 75.8577),
    ("Guwahati", 26.1445, 91.7362),
    ("Srinagar", 34.0837, 74.7973),
    ("Shimla", 31.1048, 77.1734),
    ("Kochi", 9.9312, 76.2673),
    ("Thiruvananthapuram", 8.5241, 76.9366),
    ("Bhubaneswar", 20.2961, 85.8245),
)

_CITIES: dict[str, City] = {
    name.casefold(): City(name, lat, lon) for name, lat, lon in _CITY_DATA
}


def resolve_city(name: str) -> City | None:
    """Resolve a city name to its coordinates.

    Args:
        name: The raw city name.

    Returns:
        The city, or None when it is not in the table.
    """
    return _CITIES.get(name.strip().casefold())
