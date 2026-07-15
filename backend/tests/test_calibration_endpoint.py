import uuid
from datetime import UTC, datetime

import pytest

from app.anthropic_client import get_anthropic_client
from app.main import app
from app.models import LLMCall
from tests.test_judge import FakeMessagesClient, _scored_message


class FakeAnthropicClient:
    def __init__(self, messages: FakeMessagesClient) -> None:
        self.messages = messages


@pytest.fixture
def fake_judge_client():
    """A fake client that returns a slightly different score each call, so
    calibration reports a real (nonzero) variance -- more representative
    than a client that always returns the same canned score."""
    scores = iter([0.7, 0.8, 0.75, 0.72, 0.78, 0.74] * 10)
    responses_client = FakeMessagesClient(responses=[])

    async def create(**kwargs):
        return _scored_message(next(scores), "Calibration run.")

    responses_client.create = create  # type: ignore[method-assign]
    fake_client = FakeAnthropicClient(responses_client)
    app.dependency_overrides[get_anthropic_client] = lambda: fake_client
    yield fake_client
    app.dependency_overrides.pop(get_anthropic_client, None)


async def _make_call(db_session, project) -> LLMCall:
    row = LLMCall(
        project_id=project.id,
        model="claude-sonnet-5",
        prompt="hello",
        response="hi there",
        input_tokens=10,
        output_tokens=5,
        latency_ms=100,
        status="ok",
        metadata_={},
        created_at=datetime.now(UTC),
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def _create_judge_eval(client, raw_key):
    response = await client.post(
        "/v1/evals",
        json={"name": "quality", "type": "llm_judge", "config": {"rubric": "Be helpful."}},
        headers={"X-API-Key": raw_key},
    )
    return response.json()["id"]


async def test_calibrate_happy_path(client, project, db_session, fake_judge_client):
    proj, raw_key = project
    eval_id = await _create_judge_eval(client, raw_key)
    call1 = await _make_call(db_session, proj)
    call2 = await _make_call(db_session, proj)

    response = await client.post(
        f"/v1/evals/{eval_id}/calibrate",
        json={"call_ids": [str(call1.id), str(call2.id)]},
        headers={"X-API-Key": raw_key},
    )

    assert response.status_code == 200
    report = response.json()["calibration_report"]
    assert report["n_calls"] == 2
    assert report["n_runs_per_call"] == 3
    assert all(len(c["scores"]) == 3 for c in report["calls"])
    assert "small calibration set" in report["note"]


async def test_calibrate_defaults_to_recent_calls_when_no_ids_given(
    client, project, db_session, fake_judge_client
):
    proj, raw_key = project
    eval_id = await _create_judge_eval(client, raw_key)
    await _make_call(db_session, proj)
    await _make_call(db_session, proj)

    response = await client.post(
        f"/v1/evals/{eval_id}/calibrate", json={"sample_size": 2}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 200
    assert response.json()["calibration_report"]["n_calls"] == 2


async def test_calibrate_404_for_unknown_eval(client, project, fake_judge_client):
    _, raw_key = project
    response = await client.post(
        f"/v1/evals/{uuid.uuid4()}/calibrate",
        json={},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 404


async def test_calibrate_rejects_non_judge_eval_type(client, project, fake_judge_client):
    _, raw_key = project
    create_response = await client.post(
        "/v1/evals",
        json={"name": "regex-check", "type": "regex", "config": {"pattern": "x"}},
        headers={"X-API-Key": raw_key},
    )
    eval_id = create_response.json()["id"]

    response = await client.post(
        f"/v1/evals/{eval_id}/calibrate", json={}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 400


async def test_calibrate_503_when_no_api_key_configured(client, project):
    # No fake_judge_client override here -- get_anthropic_client falls through
    # to the real (unconfigured) settings-based lookup.
    _, raw_key = project
    eval_id = await _create_judge_eval(client, raw_key)

    response = await client.post(
        f"/v1/evals/{eval_id}/calibrate", json={}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 503


async def test_calibrate_400_when_no_calls_available(client, project, fake_judge_client):
    _, raw_key = project
    eval_id = await _create_judge_eval(client, raw_key)

    response = await client.post(
        f"/v1/evals/{eval_id}/calibrate", json={}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 400
