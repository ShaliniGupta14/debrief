import datetime
import uuid
from decimal import Decimal

from app.models import LLMCall, ModelPrice

VALID_CALL = {
    "model": "claude-sonnet-5",
    "prompt": "hello",
    "response": "hi there",
    "input_tokens": 1000,
    "output_tokens": 500,
    "latency_ms": 250,
}


async def _seed_price(db_session):
    db_session.add(
        ModelPrice(
            model="claude-sonnet-5",
            input_price_per_mtok=Decimal("3"),
            output_price_per_mtok=Decimal("15"),
            effective_date=datetime.date(2026, 1, 1),
        )
    )
    await db_session.commit()


async def test_ingest_single_call_computes_cost(client, project, db_session):
    _, raw_key = project
    await _seed_price(db_session)

    response = await client.post("/v1/ingest", json=[VALID_CALL], headers={"X-API-Key": raw_key})

    assert response.status_code == 202
    body = response.json()
    assert body["count"] == 1
    assert body["accepted"][0]["duplicate"] is False

    row = await db_session.get(LLMCall, uuid.UUID(body["accepted"][0]["id"]))
    assert row is not None
    assert row.cost_usd == Decimal("0.010500")


async def test_ingest_idempotent_replay_returns_same_row(client, project, db_session):
    _, raw_key = project
    await _seed_price(db_session)
    call = {**VALID_CALL, "client_call_id": "req-123"}
    headers = {"X-API-Key": raw_key}

    first = await client.post("/v1/ingest", json=[call], headers=headers)
    second = await client.post("/v1/ingest", json=[call], headers=headers)

    assert first.json()["accepted"][0]["duplicate"] is False
    assert second.json()["accepted"][0]["duplicate"] is True
    assert first.json()["accepted"][0]["id"] == second.json()["accepted"][0]["id"]


async def test_ingest_unknown_model_is_still_accepted_with_null_cost(client, project, db_session):
    _, raw_key = project
    response = await client.post(
        "/v1/ingest",
        json=[{**VALID_CALL, "model": "some-unpriced-model"}],
        headers={"X-API-Key": raw_key},
    )

    assert response.status_code == 202
    row = await db_session.get(LLMCall, uuid.UUID(response.json()["accepted"][0]["id"]))
    assert row.cost_usd is None


async def test_ingest_batch_of_multiple_calls(client, project, db_session):
    _, raw_key = project
    await _seed_price(db_session)
    response = await client.post(
        "/v1/ingest",
        json=[VALID_CALL, {**VALID_CALL, "client_call_id": "req-2"}],
        headers={"X-API-Key": raw_key},
    )

    assert response.status_code == 202
    assert response.json()["count"] == 2


async def test_ingest_rejects_invalid_api_key(client):
    response = await client.post(
        "/v1/ingest", json=[VALID_CALL], headers={"X-API-Key": "not-a-real-key"}
    )
    assert response.status_code == 401


async def test_ingest_rejects_batch_over_max_size(client, project):
    _, raw_key = project
    response = await client.post(
        "/v1/ingest", json=[VALID_CALL] * 101, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 422


async def test_ingest_rejects_missing_required_field(client, project):
    _, raw_key = project
    bad_call = {k: v for k, v in VALID_CALL.items() if k != "model"}
    response = await client.post("/v1/ingest", json=[bad_call], headers={"X-API-Key": raw_key})
    assert response.status_code == 422
