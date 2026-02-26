"""
GET /api/config/public — Public (non-secret) configuration for the frontend.
POST /api/config/verify — Verify Turnstile token for initial page access.
"""

from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

router = APIRouter(prefix="/api/config", tags=["config"])


class PublicConfig(BaseModel):
    turnstile_enabled: bool = False
    turnstile_site_key: str = ""


class VerifyRequest(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    success: bool
    message: str = ""


@router.get("/public", response_model=PublicConfig)
async def get_public_config(request: Request):
    ts = request.app.state.config.get("turnstile", {})
    return PublicConfig(
        turnstile_enabled=ts.get("enabled", False),
        turnstile_site_key=ts.get("site_key", "") if ts.get("enabled", False) else "",
    )


@router.post("/verify", response_model=VerifyResponse)
async def verify_turnstile_token(request: Request, body: VerifyRequest):
    """Verify a Turnstile token for initial page access."""
    ts_config: Dict[str, Any] = request.app.state.config.get("turnstile", {})

    if not ts_config.get("enabled", False):
        return VerifyResponse(success=True, message="Turnstile is disabled")

    secret_key = ts_config.get("secret_key", "")
    if not secret_key:
        return VerifyResponse(success=True, message="No secret key configured")

    if not body.token:
        raise HTTPException(status_code=400, detail="Missing token")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            SITEVERIFY_URL,
            data={"secret": secret_key, "response": body.token},
        )

    result = resp.json()
    if not result.get("success", False):
        return VerifyResponse(success=False, message="Verification failed")

    return VerifyResponse(success=True, message="Verification successful")
