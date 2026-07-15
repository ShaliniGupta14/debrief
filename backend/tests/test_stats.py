from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models import LLMCall, Project


async def _make_call(
    db_session, project: Project, *, created_at: datetime, latency_ms: int, **overrides
):
    row = LLMCall(
        project_id=project.id,
        model=overrides.get("model", "claude-sonnet-5"),
        prompt="hello",
        response="hi",
        prompt_version=overrides.get("prompt_version"),
        input_tokens=10,
        output_tokens=5,
        cost_usd=overrides.get("cost_usd", Decimal("0.01")),
        latency_ms=latency_ms,
        status="ok",
        metadata_={},
        created_at=created_at,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def test_stats_computes_volume_spend_and_percentiles(client, project, db_session):
    proj, raw_key = project
    day = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    # 11 values: p50's rank (0.5*(11-1)=5) lands exactly on index 5 -> 600, no
    # interpolation needed there; p95/p99 do interpolate, checked with approx.
    for latency in range(100, 1101, 100):
        await _make_call(
            db_session, proj, created_at=day, latency_ms=latency, cost_usd=Decimal("0.10")
        )

    response = await client.get(
        "/v1/stats", params={"bucket": "day", "group_by": "model"}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 200
    buckets = response.json()["buckets"]
    assert len(buckets) == 1

    b = buckets[0]
    assert b["group_key"] == "claude-sonnet-5"
    assert b["volume"] == 11
    assert Decimal(b["spend_usd"]) == Decimal("1.10")
    assert b["latency_p50_ms"] == pytest.approx(600.0)
    assert b["latency_p95_ms"] == pytest.approx(1050.0)
    assert b["latency_p99_ms"] == pytest.approx(1090.0)


async def test_stats_groups_by_prompt_version(client, project, db_session):
    proj, raw_key = project
    day = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    await _make_call(db_session, proj, created_at=day, latency_ms=100, prompt_version="v1")
    await _make_call(db_session, proj, created_at=day, latency_ms=200, prompt_version="v1")
    await _make_call(db_session, proj, created_at=day, latency_ms=300, prompt_version="v2")

    response = await client.get(
        "/v1/stats",
        params={"bucket": "day", "group_by": "prompt_version"},
        headers={"X-API-Key": raw_key},
    )
    buckets = {b["group_key"]: b for b in response.json()["buckets"]}
    assert buckets["v1"]["volume"] == 2
    assert buckets["v2"]["volume"] == 1


async def test_stats_buckets_separate_days(client, project, db_session):
    proj, raw_key = project
    day1 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    day2 = day1 + timedelta(days=1)
    await _make_call(db_session, proj, created_at=day1, latency_ms=100)
    await _make_call(db_session, proj, created_at=day2, latency_ms=200)

    response = await client.get(
        "/v1/stats", params={"bucket": "day", "group_by": "model"}, headers={"X-API-Key": raw_key}
    )
    buckets = response.json()["buckets"]
    assert len(buckets) == 2


async def test_stats_does_not_leak_across_projects(client, project, db_session):
    proj, raw_key = project
    other = Project(name="other", api_key_hash="other-hash-2", api_key_prefix="other2")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    await _make_call(db_session, other, created_at=datetime.now(UTC), latency_ms=500)

    response = await client.get("/v1/stats", headers={"X-API-Key": raw_key})
    assert response.json()["buckets"] == []


async def test_stats_rejects_invalid_bucket(client, project):
    _, raw_key = project
    response = await client.get(
        "/v1/stats", params={"bucket": "week"}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 422


async def test_stats_rejects_missing_auth(client):
    response = await client.get("/v1/stats")
    assert response.status_code == 401
