"""
GET /api/config/public — Public (non-secret) configuration for the frontend.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/config", tags=["config"])


class PublicConfig(BaseModel):
    turnstile_enabled: bool = False
    turnstile_site_key: str = ""


@router.get("/public", response_model=PublicConfig)
async def get_public_config(request: Request):
    ts = request.app.state.config.get("turnstile", {})
    return PublicConfig(
        turnstile_enabled=ts.get("enabled", False),
        turnstile_site_key=ts.get("site_key", "") if ts.get("enabled", False) else "",
    )
