"""API router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.routes import auth, profile, system

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(profile.router)
