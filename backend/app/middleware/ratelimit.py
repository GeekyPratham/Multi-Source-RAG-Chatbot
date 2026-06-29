"""middleware/ratelimit.py — API rate limiting using Redis (Upstash or local).

Uses the unified Redis service — if Redis is not available, rate limiting is
disabled gracefully with a warning log.
"""
from __future__ import annotations
import time
from typing import Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.redis_service import (
    incr as redis_incr,
    expire as redis_expire,
    is_available as redis_available,
    get_client_type,
)
from app.utils.logger import log

# ── Config ────────────────────────────────────────────────────────────────────
RATE_LIMIT_WINDOW_SECONDS = 60       # 1 minute window
RATE_LIMIT_MAX_REQUESTS = 60         # max 60 requests per window per user


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that rate-limits requests per user (based on JWT user_id or IP).

    Uses Redis counters — if Redis is unavailable, rate limiting is skipped
    and a warning is logged once.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._warned = False

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip rate limiting for health checks and static paths
        path = request.url.path
        if path in ("/", "/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # If Redis is not available, skip rate limiting (with warning)
        if not redis_available():
            if not self._warned:
                log.warning(
                    "⚠️  Rate limiting DISABLED — Redis is not available. "
                    "Set UPSTASH_REDIS_REST_URL/TOKEN in .env"
                )
                self._warned = True
            return await call_next(request)

        # Determine the identifier for rate limiting
        # Prefer user_id from JWT, fall back to IP address
        user_id = None
        if hasattr(request.state, "user") and request.state.user:
            user_id = str(request.state.user.id)
        
        identifier = user_id or request.client.host if request.client else "anonymous"
        rate_key = f"ratelimit:{identifier}:{int(time.time() // RATE_LIMIT_WINDOW_SECONDS)}"

        try:
            count = await redis_incr(rate_key)
            if count is None:
                # Redis error, allow the request through
                return await call_next(request)

            # Set expiry on first request in this window
            if count == 1:
                await redis_expire(rate_key, RATE_LIMIT_WINDOW_SECONDS + 5)

            # Check if over limit
            if count > RATE_LIMIT_MAX_REQUESTS:
                log.warning(
                    "Rate limit exceeded for %s — %d requests in window",
                    identifier[:50], count,
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "rate_limit_exceeded",
                        "message": f"Too many requests. Limit: {RATE_LIMIT_MAX_REQUESTS} per {RATE_LIMIT_WINDOW_SECONDS}s",
                    },
                    headers={
                        "Retry-After": str(RATE_LIMIT_WINDOW_SECONDS),
                        "X-RateLimit-Limit": str(RATE_LIMIT_MAX_REQUESTS),
                    },
                )
        except Exception as e:
            log.warning("Rate limit check failed: %s — allowing request through", e)
            # Don't block requests on rate limiter errors

        return await call_next(request)