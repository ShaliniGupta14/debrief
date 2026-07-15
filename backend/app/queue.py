"""Lazy singleton arq pool for enqueueing jobs from the API process.

A module-level lazy singleton (rather than FastAPI lifespan + app.state) so
tests don't need lifespan-triggering machinery (httpx's ASGITransport doesn't
run ASGI lifespan events by default) -- the pool is created on first actual
use and is trivially overridable via FastAPI's dependency_overrides, same
pattern as get_db.
"""

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

_pool: ArqRedis | None = None
_lock = asyncio.Lock()


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        async with _lock:
            if _pool is None:
                settings = get_settings()
                _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool
