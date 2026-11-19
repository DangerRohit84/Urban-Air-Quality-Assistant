"""Export routes for the personalized plan."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from backend.app.auth.dependencies import require_user_id
from backend.app.plans import PlansPayload
from backend.app.routes.plans import payload_for_user
from backend.app.schemas.plans import to_response

router = APIRouter(tags=["export"])

FORMATS = frozenset({"md", "json"})

_SECTIONS: tuple[tuple[str, str], ...] = (
    ("Routines", "routines"),
    ("Indoor hacks", "hacks"),
    ("Alternatives", "alternatives"),
)


def _markdown(payload: PlansPayload) -> str:
    """Render the plans payload as Markdown.

    Args:
        payload: The plans payload.

    Returns:
        The Markdown document.
    """
    lines = ["# Your air quality plan", ""]
    if payload.profile_note:
        lines += [payload.profile_note, ""]
    for heading, attribute in _SECTIONS:
        lines += [f"## {heading}", ""]
        for item in getattr(payload, attribute):
            lines.append(f"- **{item.title}** - {item.detail}")
            lines.append(
                f"  CO2e {item.impact.co2e_kg_week} kg/week; exposure "
                f"{item.impact.exposure_reduction_pct}%; cost "
                f"{item.impact.cost_delta_inr_month} INR/month"
            )
            lines.append(f"  Sources: {', '.join(item.citations)}")
        lines.append("")
    return "\n".join(lines)


@router.get("/export")
def export(
    user_id: Annotated[str, Depends(require_user_id)],
    format: str = "md",
) -> object:
    """Export the caller's plan as Markdown or JSON.

    Args:
        user_id: The verified owner id.
        format: The export format, ``md`` or ``json``.

    Returns:
        The exported document.

    Raises:
        HTTPException: 422 when the format is unknown.
    """
    if format not in FORMATS:
        raise HTTPException(status_code=422, detail="unknown format")
    payload = payload_for_user(user_id)
    if format == "json":
        return to_response(payload).model_dump()
    return PlainTextResponse(_markdown(payload), media_type="text/markdown")
