from datetime import UTC, datetime

from sqlalchemy import select

from app.models import EvalDefinition, EvalResult, LLMCall
from app.workers.tasks import run_evals_for_call
from tests.test_judge import FakeMessagesClient, _scored_message


async def _make_call(db_session, project, *, prompt="hello", response="hi there") -> LLMCall:
    row = LLMCall(
        project_id=project.id,
        model="claude-sonnet-5",
        prompt=prompt,
        response=response,
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


async def _make_eval(db_session, project, *, name, type_, config, enabled=True) -> EvalDefinition:
    row = EvalDefinition(
        project_id=project.id, name=name, type=type_, config=config, enabled=enabled
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def test_worker_runs_all_enabled_rule_evals_for_a_call(db_session, project, worker_ctx):
    proj, _ = project
    call = await _make_call(db_session, proj, response="your refund is on the way")
    await _make_eval(
        db_session, proj, name="mentions-refund", type_="contains", config={"text": "refund"}
    )
    await _make_eval(db_session, proj, name="not-too-long", type_="length", config={"max": 500})

    await run_evals_for_call(worker_ctx, str(call.id))

    results = (
        (await db_session.execute(select(EvalResult).where(EvalResult.call_id == call.id)))
        .scalars()
        .all()
    )
    assert len(results) == 2
    assert all(r.passed for r in results)


async def test_worker_skips_disabled_evals(db_session, project, worker_ctx):
    proj, _ = project
    call = await _make_call(db_session, proj)
    await _make_eval(
        db_session,
        proj,
        name="disabled-eval",
        type_="contains",
        config={"text": "x"},
        enabled=False,
    )

    await run_evals_for_call(worker_ctx, str(call.id))

    results = (
        (await db_session.execute(select(EvalResult).where(EvalResult.call_id == call.id)))
        .scalars()
        .all()
    )
    assert results == []


async def test_worker_is_idempotent_on_rerun(db_session, project, worker_ctx):
    proj, _ = project
    call = await _make_call(db_session, proj, response="short")
    await _make_eval(db_session, proj, name="length-check", type_="length", config={"min": 100})

    await run_evals_for_call(worker_ctx, str(call.id))
    await run_evals_for_call(worker_ctx, str(call.id))

    results = (
        (await db_session.execute(select(EvalResult).where(EvalResult.call_id == call.id)))
        .scalars()
        .all()
    )
    assert len(results) == 1  # upsert, not a second row
    assert results[0].passed is False


async def test_worker_judges_100_percent_when_a_rule_eval_fails(db_session, project, worker_ctx):
    proj, _ = project
    call = await _make_call(db_session, proj, response="short")
    await _make_eval(db_session, proj, name="length-check", type_="length", config={"min": 999})
    judge_def = await _make_eval(
        db_session,
        proj,
        name="quality-judge",
        type_="llm_judge",
        # sample_rate 0 would normally never fire -- but a rule failure forces it to 100%.
        config={"rubric": "Be helpful.", "sample_rate": 0.0},
    )

    fake_client = FakeMessagesClient(responses=[_scored_message(0.8, "Decent.")])
    worker_ctx["anthropic_client"] = type("C", (), {"messages": fake_client})()

    await run_evals_for_call(worker_ctx, str(call.id))

    judge_result = (
        await db_session.execute(
            select(EvalResult).where(
                EvalResult.call_id == call.id, EvalResult.eval_definition_id == judge_def.id
            )
        )
    ).scalar_one_or_none()
    assert judge_result is not None
    assert judge_result.judge_rationale == "Decent."


async def test_worker_skips_judge_when_no_anthropic_client_configured(
    db_session, project, worker_ctx
):
    proj, _ = project
    call = await _make_call(db_session, proj, response="short")
    await _make_eval(db_session, proj, name="length-check", type_="length", config={"min": 999})
    await _make_eval(
        db_session,
        proj,
        name="quality-judge",
        type_="llm_judge",
        config={"rubric": "Be helpful.", "sample_rate": 1.0},
    )
    # worker_ctx["anthropic_client"] is None by default -- no key configured.

    await run_evals_for_call(worker_ctx, str(call.id))

    results = (
        (await db_session.execute(select(EvalResult).where(EvalResult.call_id == call.id)))
        .scalars()
        .all()
    )
    assert len(results) == 1  # only the rule eval; judge silently skipped, not crashed
