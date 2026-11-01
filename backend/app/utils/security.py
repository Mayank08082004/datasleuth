import hmac
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Shared-secret API key. Compared in constant time."""
    expected = get_settings().datasleuth_api_key
    if not expected or expected == "change-me":
        # Refuse to run an open API with the placeholder key.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="DATASLEUTH_API_KEY is not configured.")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key.")


_hits: dict[str, deque] = defaultdict(deque)


def _client_key(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    """Sliding one-minute window per client (in-memory; per process)."""
    limit = get_settings().rate_limit_per_minute
    key = _client_key(request)
    now = time.monotonic()
    window = _hits[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded. Try again shortly.")
    window.append(now)
