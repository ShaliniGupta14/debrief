import pytest

from app.models import Project
from app.security import hash_api_key


@pytest.fixture
async def demo_project(db_session):
    raw_key = "sk_demo_test_key"
    p = Project(
        name="demo-project",
        api_key_hash=hash_api_key(raw_key),
        api_key_prefix=raw_key[:12],
        is_demo=True,
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p, raw_key


VALID_CALL = {
    "model": "claude-sonnet-5",
    "prompt": "hello",
    "response": "hi there",
    "input_tokens": 10,
    "output_tokens": 5,
    "latency_ms": 100,
}


async def test_demo_project_cannot_ingest(client, demo_project):
    _, raw_key = demo_project
    response = await client.post("/v1/ingest", json=[VALID_CALL], headers={"X-API-Key": raw_key})
    assert response.status_code == 403
    assert "read-only" in response.json()["detail"]


async def test_demo_project_cannot_create_eval(client, demo_project):
    _, raw_key = demo_project
    response = await client.post(
        "/v1/evals",
        json={"name": "x", "type": "contains", "config": {"text": "x"}},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 403


async def test_demo_project_can_read_calls(client, demo_project):
    _, raw_key = demo_project
    response = await client.get("/v1/calls", headers={"X-API-Key": raw_key})
    assert response.status_code == 200


async def test_demo_project_can_read_stats(client, demo_project):
    _, raw_key = demo_project
    response = await client.get("/v1/stats", headers={"X-API-Key": raw_key})
    assert response.status_code == 200


async def test_demo_project_can_list_evals(client, demo_project):
    _, raw_key = demo_project
    response = await client.get("/v1/evals", headers={"X-API-Key": raw_key})
    assert response.status_code == 200


async def test_non_demo_project_can_still_ingest(client, project, db_session):
    _, raw_key = project
    response = await client.post("/v1/ingest", json=[VALID_CALL], headers={"X-API-Key": raw_key})
    assert response.status_code == 202
