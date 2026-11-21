"""Fixed-window request limits stored in Redis.

Redis errors do not block the API. Health checks already report Redis as down.
"""

import logging
import time

from redis import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_client: Redis | None = None


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled or request.url.path in {"/health", "/api/v1/health", "/api/v1/ready"}:
            return await call_next(request)
        limit = _limit_for(request.method, request.url.path, settings)
        identity = request.client.host if request.client else "unknown"
        try:
            allowed = consume(f"{identity}:{request.url.path}", limit)
        except RedisError:
            logger.warning("Rate limit check skipped because Redis is unavailable")
            return await call_next(request)
        if allowed:
            return await call_next(request)
        return JSONResponse(
            status_code=429,
            content={
                "error": "too_many_requests",
                "message": "Too many requests. Wait a moment and try again.",
                "details": None,
            },
        )


def consume(identity: str, limit: int, *, now: int | None = None, client: Redis | None = None) -> bool:
    """Return False when this identity is over the per-minute limit."""

    window = int(now if now is not None else time.time()) // 60
    key = f"proposalgenie:rate:{window}:{identity}"
    connection = client or _redis()
    count = int(connection.incr(key))
    if count == 1:
        connection.expire(key, 120)
    return count <= limit


def _limit_for(method: str, path: str, settings) -> int:
    if path.startswith("/api/v1/auth"):
        return settings.rate_limit_auth_per_minute
    expensive = ("/generate", "/export/", "/run", "/resume", "/rag/query", "/rag/search", "/costs/suggest", "/regenerate")
    if any(part in path for part in expensive):
        return settings.rate_limit_expensive_per_minute
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return settings.rate_limit_write_per_minute
    return settings.rate_limit_read_per_minute


def _redis() -> Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Redis.from_url(settings.redis_dsn, socket_connect_timeout=0.3, socket_timeout=0.3)
    return _client
