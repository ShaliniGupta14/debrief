import uuid

import pytest
from redis.asyncio import Redis

from app.config import get_settings
from app.rate_limit import check_and_record


@pytest.fixture
async def redis_client():
    client = Redis.from_url(get_settings().redis_url)
    yield client
    await client.aclose()


def _unique_key() -> str:
    return f"ratelimit:test:{uuid.uuid4().hex}"


async def test_allows_requests_under_the_limit(redis_client):
    key = _unique_key()
    for _ in range(3):
        assert await check_and_record(redis_client, key, limit=5, window_seconds=60) is True


async def test_rejects_requests_once_limit_is_reached(redis_client):
    key = _unique_key()
    for _ in range(3):
        assert await check_and_record(redis_client, key, limit=3, window_seconds=60) is True
    assert await check_and_record(redis_client, key, limit=3, window_seconds=60) is False


async def test_old_requests_fall_out_of_the_sliding_window(redis_client):
    key = _unique_key()
    base = 1_000_000.0
    # Fill the limit at t=0.
    for _ in range(3):
        assert (
            await check_and_record(redis_client, key, limit=3, window_seconds=10, now=base) is True
        )
    # Still within the window (t=5) -- still full.
    assert (
        await check_and_record(redis_client, key, limit=3, window_seconds=10, now=base + 5) is False
    )
    # Past the window (t=11) -- the original 3 have aged out, so this succeeds.
    assert (
        await check_and_record(redis_client, key, limit=3, window_seconds=10, now=base + 11) is True
    )


async def test_different_keys_have_independent_limits(redis_client):
    key_a, key_b = _unique_key(), _unique_key()
    for _ in range(3):
        assert await check_and_record(redis_client, key_a, limit=3, window_seconds=60) is True
    # key_b's own limit is untouched by key_a's usage.
    assert await check_and_record(redis_client, key_b, limit=3, window_seconds=60) is True


async def test_concurrent_requests_never_exceed_the_limit(redis_client):
    import asyncio

    key = _unique_key()
    results = await asyncio.gather(
        *[check_and_record(redis_client, key, limit=5, window_seconds=60) for _ in range(20)]
    )
    assert sum(results) == 5


async def test_ingest_returns_429_when_rate_limited(client, project):
    from app.main import app
    from app.rate_limit import enforce_ingest_rate_limit

    async def _deny(project=None):
        from fastapi import HTTPException

        raise HTTPException(status_code=429, detail="rate limit exceeded")

    _, raw_key = project
    app.dependency_overrides[enforce_ingest_rate_limit] = _deny
    try:
        response = await client.post(
            "/v1/ingest",
            json=[
                {
                    "model": "x",
                    "prompt": "a",
                    "response": "b",
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "latency_ms": 1,
                }
            ],
            headers={"X-API-Key": raw_key},
        )
        assert response.status_code == 429
    finally:
        app.dependency_overrides.pop(enforce_ingest_rate_limit, None)
