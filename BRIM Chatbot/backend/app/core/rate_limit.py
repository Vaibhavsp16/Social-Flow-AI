"""
Minimal in-process rate limiting for the endpoints that are expensive or brute-forceable.

Deliberately not a distributed limiter: it protects a single-process deployment (uvicorn, one
worker) and is documented as such. Behind multiple workers or instances this must move to Redis —
the call sites already funnel through ``RATE_LIMITED_PREFIXES`` so the swap is local.
"""

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# (method, path fragment) -> (limit, window seconds)
RATE_LIMITED_PREFIXES: Tuple[Tuple[str, str, int, int], ...] = (
    ("POST", "/api/auth/login", 10, 60),
    ("POST", "/api/auth/signup", 5, 300),
    ("POST", "/api/conversations/", 60, 60),   # message turns
    ("POST", "/api/bots/", 30, 60),            # chat + knowledge ingestion
)


class RateLimiter:
    def __init__(self) -> None:
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window: int) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        # Avoid unbounded growth from one-off keys (e.g. many IPs).
        if len(self._hits) > 10_000:
            self._hits.clear()
        return True


limiter = RateLimiter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Read per request so tests (and local demos) can switch it off without re-importing.
        if os.getenv("RATE_LIMIT_ENABLED", "true").lower() not in ("1", "true", "yes"):
            return await call_next(request)
        for method, fragment, limit, window in RATE_LIMITED_PREFIXES:
            if request.method == method and fragment in request.url.path:
                key = f"{_client_ip(request)}:{fragment}:{method}"
                if not limiter.check(key, limit, window):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests. Please wait a moment and try again."},
                        headers={"Retry-After": str(window)},
                    )
                break
        return await call_next(request)
