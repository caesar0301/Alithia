"""
Cloudflare Turnstile verification dependency for FastAPI.

When ``turnstile.enabled`` is ``false`` in config (the default), verification
is skipped entirely so local / self-hosted deployments work without any
Cloudflare account.
"""

from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, Request

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _get_turnstile_config(request: Request) -> Dict[str, Any]:
    return request.app.state.config.get("turnstile", {})


async def verify_turnstile(request: Request) -> None:
    """FastAPI dependency that verifies a Turnstile token when enabled."""
    ts_config = _get_turnstile_config(request)
    if not ts_config.get("enabled", False):
        return

    secret_key = ts_config.get("secret_key", "")
    if not secret_key:
        return

    token: Optional[str] = request.headers.get("cf-turnstile-response")
    if not token:
        raise HTTPException(status_code=403, detail="Missing Turnstile token")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            SITEVERIFY_URL,
            data={"secret": secret_key, "response": token},
        )

    result = resp.json()
    if not result.get("success", False):
        raise HTTPException(status_code=403, detail="Turnstile verification failed")
