"""Domain dataclasses shared by storage, domain logic and API schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.app.impact import Impact


@dataclass(slots=True)
class User:
    """An authenticated account."""

    id: str
    email: str
    password_hash: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe mapping of the user.

        Returns:
            A dictionary with every field.
        """
        return asdict(self)


@dataclass(slots=True)
class Profile:
    """A user's household and lifestyle profile."""

    user_id: str
    city: str
    climate_zone: str
    children: bool
    elderly: bool
    respiratory: bool
    commute_mode: str
    commute_km: float
    cooking_fuel: str
    heating_type: str
    budget_level: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe mapping of the profile.

        Returns:
            A dictionary with every field.
        """
        return asdict(self)


@dataclass(slots=True)
class Document:
    """A seed, corpus or uploaded document."""

    id: str
    owner_id: str
    kind: str
    title: str
    text: str
    chunks: list[str]
    source: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe mapping of the document.

        Returns:
            A dictionary with every field.
        """
        return asdict(self)


@dataclass(slots=True)
class AqiContext:
    """A user's stored air-quality context."""

    user_id: str
    city: str
    band: str
    value: int | None
    pm25: float | None
    pm10: float | None
    season: str
    observed_at: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe mapping of the context.

        Returns:
            A dictionary with every field.
        """
        return asdict(self)


@dataclass(slots=True)
class Recommendation:
    """One personalized recommendation with its computed impact."""

    key: str
    area: str
    title: str
    detail: str
    action_key: str
    baseline_key: str
    impact: Impact
    citations: list[str]
    approximate: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe mapping of the recommendation.

        Returns:
            A dictionary with every field.
        """
        return asdict(self)
