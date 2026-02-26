"""
Security middleware for the Alithia dashboard.

Blocks automated vulnerability scanners, enforces rate limits per IP,
and injects standard security headers on every response.
"""

import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path-based scanner blocking
# ---------------------------------------------------------------------------

BLOCKED_PREFIXES: Tuple[str, ...] = (
    "/.env",
    "/.git/",
    "/wp-",
    "/wp-content/",
    "/laravel/",
    "/docker/",
    "/backend/.",
    "/admin/.",
    "/api/.",
    "/app/.",
    "/core/.",
    "/assets/.",
    "/stripe/.",
    "/payment/.",
)

BLOCKED_SUFFIXES: Tuple[str, ...] = (
    ".php",
    ".php.bak",
    ".php.old",
    ".php.txt",
    ".php.save",
    ".php~",
)

BLOCKED_EXACT: frozenset = frozenset(
    {
        "/credentials.json",
        "/credentials.json.map",
        "/config.env",
        "/.git/config",
        "/.git/HEAD",
    }
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "X-XSS-Protection": "1; mode=block",
}


def _is_scanner_path(path: str) -> bool:
    if path in BLOCKED_EXACT:
        return True
    lower = path.lower()
    if lower.startswith(BLOCKED_PREFIXES):
        return True
    if lower.endswith(BLOCKED_SUFFIXES):
        return True
    return False


# ---------------------------------------------------------------------------
# Simple in-memory IP rate limiter (sliding-window counter)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Per-IP sliding-window rate limiter.

    Tracks request timestamps in a dict keyed by IP.  Entries older than
    ``window`` seconds are lazily pruned on each check.
    """

    def __init__(self, max_requests: int = 100, window: int = 60) -> None:
        self._max = max_requests
        self._window = window
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, ip: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            timestamps = self._hits[ip]
            timestamps[:] = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self._max:
                return False
            timestamps.append(now)
            return True


_rate_limiter = _RateLimiter(max_requests=100, window=60)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class SecurityMiddleware(BaseHTTPMiddleware):
    """Combined scanner-blocker, rate-limiter, and security-header middleware."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        if _is_scanner_path(path):
            logger.warning("Blocked scanner probe from %s: %s", client_ip, path)
            return Response(status_code=403)

        if not _rate_limiter.is_allowed(client_ip):
            logger.warning("Rate-limited %s", client_ip)
            return Response(
                content="Too Many Requests",
                status_code=429,
                headers={"Retry-After": "60"},
            )

        response: Response = await call_next(request)

        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)

        return response
