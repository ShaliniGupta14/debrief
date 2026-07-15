import uuid
from datetime import UTC, datetime, timedelta

from app.models import LLMCall, Project

BASE_CALL = {
    "model": "claude-sonnet-5",
    "prompt": "hello",
    "response": "hi there",
    "input_tokens": 10,
    "output_tokens": 5,
    "latency_ms": 100,
}


async def _make_call(db_session, project: Project, *, created_at: datetime, **overrides) -> LLMCall:
    row = LLMCall(
        project_id=project.id,
        model=overrides.get("model", BASE_CALL["model"]),
        prompt=overrides.get("prompt", BASE_CALL["prompt"]),
        response=overrides.get("response", BASE_CALL["response"]),
        prompt_version=overrides.get("prompt_version"),
        input_tokens=overrides.get("input_tokens", BASE_CALL["input_tokens"]),
        output_tokens=overrides.get("output_tokens", BASE_CALL["output_tokens"]),
        cost_usd=overrides.get("cost_usd"),
        latency_ms=overrides.get("latency_ms", BASE_CALL["latency_ms"]),
        status=overrides.get("status", "ok"),
        error_message=overrides.get("error_message"),
        metadata_=overrides.get("metadata", {}),
        created_at=created_at,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def test_list_calls_paginates_with_cursor(client, project, db_session):
    proj, raw_key = project
    now = datetime.now(UTC)
    for i in range(3):
        await _make_call(db_session, proj, created_at=now - timedelta(minutes=i))
    headers = {"X-API-Key": raw_key}

    first_page = await client.get("/v1/calls", params={"limit": 2}, headers=headers)
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second_page = await client.get(
        "/v1/calls", params={"limit": 2, "cursor": first_body["next_cursor"]}, headers=headers
    )
    second_body = second_page.json()
    assert len(second_body["items"]) == 1
    assert second_body["next_cursor"] is None

    seen_ids = {item["id"] for item in first_body["items"]} | {
        item["id"] for item in second_body["items"]
    }
    assert len(seen_ids) == 3


async def test_list_calls_filters_by_model_and_status(client, project, db_session):
    proj, raw_key = project
    now = datetime.now(UTC)
    await _make_call(db_session, proj, created_at=now, model="claude-sonnet-5", status="ok")
    await _make_call(db_session, proj, created_at=now, model="claude-haiku-4-5", status="error")
    headers = {"X-API-Key": raw_key}

    response = await client.get("/v1/calls", params={"model": "claude-haiku-4-5"}, headers=headers)
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["model"] == "claude-haiku-4-5"

    response = await client.get("/v1/calls", params={"status": "error"}, headers=headers)
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "error"


async def test_list_calls_filters_by_metadata_containment(client, project, db_session):
    proj, raw_key = project
    now = datetime.now(UTC)
    await _make_call(db_session, proj, created_at=now, metadata={"env": "prod", "team": "growth"})
    await _make_call(db_session, proj, created_at=now, metadata={"env": "staging"})
    headers = {"X-API-Key": raw_key}

    response = await client.get(
        "/v1/calls", params={"metadata": '{"env": "prod"}'}, headers=headers
    )
    body = response.json()
    assert len(body["items"]) == 1


async def test_list_calls_full_text_search(client, project, db_session):
    proj, raw_key = project
    now = datetime.now(UTC)
    await _make_call(db_session, proj, created_at=now, prompt="what is the refund policy")
    await _make_call(db_session, proj, created_at=now, prompt="write a haiku about autumn")
    headers = {"X-API-Key": raw_key}

    response = await client.get("/v1/calls", params={"q": "refund"}, headers=headers)
    body = response.json()
    assert len(body["items"]) == 1
    assert "refund" in body["items"][0]["prompt_preview"]


async def test_list_calls_rejects_invalid_cursor(client, project):
    _, raw_key = project
    response = await client.get(
        "/v1/calls", params={"cursor": "not-valid-base64!!"}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 422


async def test_list_calls_rejects_missing_auth(client):
    response = await client.get("/v1/calls")
    assert response.status_code == 401


async def test_get_call_detail_returns_full_call(client, project, db_session):
    proj, raw_key = project
    row = await _make_call(db_session, proj, created_at=datetime.now(UTC))

    response = await client.get(f"/v1/calls/{row.id}", headers={"X-API-Key": raw_key})
    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "hi there"
    assert body["eval_results"] == []


async def test_get_call_detail_404_for_unknown_id(client, project):
    _, raw_key = project
    response = await client.get(f"/v1/calls/{uuid.uuid4()}", headers={"X-API-Key": raw_key})
    assert response.status_code == 404


async def test_get_call_detail_404_for_other_projects_call(client, project, db_session):
    proj, raw_key = project
    other_project = Project(name="other", api_key_hash="other-hash", api_key_prefix="other")
    db_session.add(other_project)
    await db_session.commit()
    await db_session.refresh(other_project)

    row = await _make_call(db_session, other_project, created_at=datetime.now(UTC))

    response = await client.get(f"/v1/calls/{row.id}", headers={"X-API-Key": raw_key})
    assert response.status_code == 404
