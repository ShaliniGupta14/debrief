"""Sliding-window rate limiting via a Redis sorted set: each request's
timestamp is a member; ZREMRANGEBYSCORE evicts anything outside the window,
ZCARD counts what's left. The check-and-record has to be one atomic Lua
script, not two separate Redis round trips (check, then add) -- otherwise
concurrent requests can each see "under limit" before either records itself,
letting more through than the limit allows. Redis runs Lua scripts
single-threaded and atomically, so this closes that race.
"""

import time
import uuid
from typing import Any

from fastapi import Depends, HTTPException
from redis.asyncio import Redis

from app.config import get_settings
from app.demo_mode import require_writable_project
from app.models import Project

_RATE_LIMIT_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[2])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[3]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[1] .. '-' .. ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[5])
return 1
"""

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(get_settings().redis_url)
    return _redis_client


async def check_and_record(
    redis: Any,
    key: str,
    *,
    limit: int,
    window_seconds: float,
    now: float | None = None,
) -> bool:
    """Returns True if this request is allowed (and records it), False if
    the key is already at its limit within the trailing window_seconds."""
    ts = now if now is not None else time.time()
    window_start = ts - window_seconds
    allowed = await redis.eval(
        _RATE_LIMIT_SCRIPT,
        1,
        key,
        ts,
        window_start,
        limit,
        uuid.uuid4().hex,
        int(window_seconds) + 1,
    )
    return bool(allowed)


async def enforce_ingest_rate_limit(
    project: Project = Depends(require_writable_project),
    redis: Redis = Depends(get_redis_client),
) -> Project:
    settings = get_settings()
    allowed = await check_and_record(
        redis,
        f"ratelimit:ingest:{project.id}",
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"rate limit exceeded: max {settings.rate_limit_requests} requests "
                f"per {settings.rate_limit_window_seconds}s"
            ),
        )
    return project
