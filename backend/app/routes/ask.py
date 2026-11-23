"""Grounded ask route."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.auth.dependencies import load_profile_or_default, require_user_id
from backend.app.llm.factory import build_provider
from backend.app.plans import PROFILE_NOTE
from backend.app.prompting import OUT_OF_DOMAIN, build_prompt, build_sources
from backend.app.retrieval import search
from backend.app.routes.common import AUTH_RESPONSES, BODY_LIMIT_RESPONSE
from backend.app.schemas.ask import AskIn, AskResponse
from backend.app.storage.store import get_repo

router = APIRouter(tags=["ask"])

ASK_RESPONSES: dict[int | str, dict[str, object]] = {
    **AUTH_RESPONSES,
    **BODY_LIMIT_RESPONSE,
}


@router.post("/ask", response_model=AskResponse, responses=ASK_RESPONSES)
def ask(
    payload: AskIn,
    user_id: Annotated[str, Depends(require_user_id)],
) -> AskResponse:
    """Answer a question from the owner's corpus.

    Args:
        payload: The question and plain-language flag.
        user_id: The verified owner id.

    Returns:
        The grounded answer, or a refusal when nothing supports it.
    """
    repo = get_repo()
    profile = load_profile_or_default(repo, user_id)
    context = repo.get_aqi_context(user_id)
    hits = search(payload.question, owner_id=user_id)
    mode = "plain" if payload.plain_language else "standard"
    if not hits:
        return AskResponse(
            answer=OUT_OF_DOMAIN, citations=[], mode=mode, grounded=False
        )
    prompt = build_prompt(
        payload.question, profile, context, hits, payload.plain_language
    )
    answer = build_provider().answer(
        prompt,
        plain_language=payload.plain_language,
        sources=build_sources(hits),
    )
    if not profile.city:
        answer = f"{PROFILE_NOTE} {answer}"
    citations = [str(hit["id"]) for hit in hits[:3]]
    return AskResponse(answer=answer, citations=citations, mode=mode, grounded=True)
