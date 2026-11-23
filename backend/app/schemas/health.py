"""Health response schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Payload returned by ``GET /health``."""

    status: str = Field(
        description="`ok` when the service is ready to serve requests.",
        examples=["ok"],
    )
    provider: str = Field(
        description="Active LLM provider name, e.g. `local_synth`.",
        examples=["local_synth"],
    )
    cache: dict[str, int] = Field(
        description="In-process response-cache counters.",
        examples=[{"hits": 54, "misses": 4, "size": 10}],
    )
    store: dict[str, int] = Field(
        description="Stored record counts by collection.",
        examples=[{"users": 1, "profiles": 1, "documents": 3, "contexts": 1}],
    )
    uptime_seconds: float = Field(
        description="Process uptime in seconds.",
        examples=[12.5],
    )
