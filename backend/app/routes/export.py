"""Export routes for the personalized plan."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from backend.app.auth.dependencies import require_user_id
from backend.app.plans import PlansPayload
from backend.app.routes.common import AUTH_RESPONSES
from backend.app.routes.plans import payload_for_user
from backend.app.schemas.plans import to_response

router = APIRouter(tags=["export"])

MARKDOWN_EXAMPLE = "# Your air quality plan\n\n## Routines\n\n- **Filter swap** - ..."

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


@router.get(
    "/export",
    response_class=Response,
    responses={
        200: {
            "description": "The caller's plan as Markdown (default) or JSON.",
            "content": {
                "text/markdown": {
                    "schema": {"type": "string"},
                    "example": MARKDOWN_EXAMPLE,
                },
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PlansResponse"},
                },
            },
        },
        **AUTH_RESPONSES,
    },
)
def export(
    user_id: Annotated[str, Depends(require_user_id)],
    export_format: Annotated[str, Query(alias="format", pattern="^(md|json)$")] = "md",
) -> Response:
    """Export the caller's plan as Markdown or JSON.

    Args:
        user_id: The verified owner id.
        export_format: The export format, ``md`` or ``json``.

    Returns:
        The exported document with its matching media type.
    """
    payload = payload_for_user(user_id)
    if export_format == "json":
        return JSONResponse(to_response(payload).model_dump())
    return PlainTextResponse(_markdown(payload), media_type="text/markdown")
