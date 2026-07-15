from datetime import UTC, datetime
from decimal import Decimal

from app.models import EvalDefinition, EvalResult, LLMCall


async def _make_call(db_session, project, *, prompt, prompt_version) -> LLMCall:
    row = LLMCall(
        project_id=project.id,
        model="claude-sonnet-5",
        prompt=prompt,
        response="a response",
        prompt_version=prompt_version,
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


async def _make_eval_def(db_session, project, name="quality") -> EvalDefinition:
    row = EvalDefinition(project_id=project.id, name=name, type="llm_judge", config={"rubric": "x"})
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def _score(db_session, call, eval_def, score) -> None:
    db_session.add(
        EvalResult(call_id=call.id, eval_definition_id=eval_def.id, score=Decimal(str(score)))
    )
    await db_session.commit()


async def test_compare_detects_a_clear_regression(client, project, db_session):
    proj, raw_key = project
    eval_def = await _make_eval_def(db_session, proj)

    for i in range(15):
        call_a = await _make_call(db_session, proj, prompt=f"prompt-{i}", prompt_version="v1")
        await _score(db_session, call_a, eval_def, 0.9)
        call_b = await _make_call(db_session, proj, prompt=f"prompt-{i}", prompt_version="v2")
        await _score(db_session, call_b, eval_def, 0.3)

    response = await client.get(
        "/v1/compare", params={"version_a": "v1", "version_b": "v2"}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["any_regression"] is True
    ev = body["evals"][0]
    assert ev["regressed"] is True
    assert ev["delta"] < -0.5
    assert len(body["worst_regressions"]) > 0
    assert body["worst_regressions"][0]["delta"] < 0


async def test_compare_no_regression_for_similar_scores(client, project, db_session):
    proj, raw_key = project
    eval_def = await _make_eval_def(db_session, proj)

    for i in range(15):
        call_a = await _make_call(db_session, proj, prompt=f"prompt-{i}", prompt_version="v1")
        await _score(db_session, call_a, eval_def, 0.8)
        call_b = await _make_call(db_session, proj, prompt=f"prompt-{i}", prompt_version="v2")
        await _score(db_session, call_b, eval_def, 0.81)

    response = await client.get(
        "/v1/compare", params={"version_a": "v1", "version_b": "v2"}, headers={"X-API-Key": raw_key}
    )
    body = response.json()
    assert body["any_regression"] is False
    assert body["evals"][0]["regressed"] is False


async def test_compare_handles_version_with_no_data(client, project, db_session):
    proj, raw_key = project
    await _make_eval_def(db_session, proj)

    response = await client.get(
        "/v1/compare",
        params={"version_a": "nonexistent-a", "version_b": "nonexistent-b"},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evals"][0]["mean_score_a"] is None
    assert body["evals"][0]["regressed"] is False
    assert body["worst_regressions"] == []


async def test_compare_covers_every_eval_definition_for_the_project(client, project, db_session):
    proj, raw_key = project
    eval_def_1 = await _make_eval_def(db_session, proj, name="quality")
    eval_def_2 = await _make_eval_def(db_session, proj, name="safety")

    call_a = await _make_call(db_session, proj, prompt="p1", prompt_version="v1")
    call_b = await _make_call(db_session, proj, prompt="p1", prompt_version="v2")
    await _score(db_session, call_a, eval_def_1, 0.8)
    await _score(db_session, call_b, eval_def_1, 0.8)
    await _score(db_session, call_a, eval_def_2, 0.9)
    await _score(db_session, call_b, eval_def_2, 0.9)

    response = await client.get(
        "/v1/compare", params={"version_a": "v1", "version_b": "v2"}, headers={"X-API-Key": raw_key}
    )
    body = response.json()
    assert {e["eval_name"] for e in body["evals"]} == {"quality", "safety"}


async def test_compare_rejects_missing_auth(client):
    response = await client.get("/v1/compare", params={"version_a": "v1", "version_b": "v2"})
    assert response.status_code == 401


async def test_compare_rejects_missing_query_params(client, project):
    _, raw_key = project
    response = await client.get(
        "/v1/compare", params={"version_a": "v1"}, headers={"X-API-Key": raw_key}
    )
    assert response.status_code == 422
