import random
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.evals.judge import run_judge_eval
from app.evals.rules import run_rule_eval
from app.metrics import eval_jobs_processed_total
from app.models import EvalDefinition, EvalResult, LLMCall

settings = get_settings()


async def _save_result(
    db: AsyncSession,
    call_id: uuid.UUID,
    eval_definition_id: uuid.UUID,
    score: float,
    passed: bool | None,
    rationale: str | None,
) -> None:
    # Upsert, not a plain insert: arq can retry a job after a partial failure,
    # and re-running evals for the same call must not violate the
    # (call_id, eval_definition_id) unique constraint.
    stmt = pg_insert(EvalResult).values(
        call_id=call_id,
        eval_definition_id=eval_definition_id,
        score=score,
        passed=passed,
        judge_rationale=rationale,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["call_id", "eval_definition_id"],
        set_={
            "score": stmt.excluded.score,
            "passed": stmt.excluded.passed,
            "judge_rationale": stmt.excluded.judge_rationale,
        },
    )
    await db.execute(stmt)


async def run_evals_for_call(ctx: dict[str, Any], call_id: str) -> None:
    session_factory = ctx["session_factory"]
    anthropic_client: Any | None = ctx.get("anthropic_client")
    call_uuid = uuid.UUID(call_id)

    async with session_factory() as db:
        call = await db.get(LLMCall, call_uuid)
        if call is None:
            return

        eval_defs = (
            (
                await db.execute(
                    select(EvalDefinition).where(
                        EvalDefinition.project_id == call.project_id,
                        EvalDefinition.enabled.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        rule_defs = [d for d in eval_defs if d.type != "llm_judge"]
        judge_defs = [d for d in eval_defs if d.type == "llm_judge"]

        any_rule_failed = False
        for definition in rule_defs:
            score, passed = run_rule_eval(
                definition.type, definition.config, call.prompt, call.response
            )
            await _save_result(db, call.id, definition.id, score, passed, None)
            if not passed:
                any_rule_failed = True

        # 100% of calls flagged by a rule failure get judged, regardless of
        # sample_rate -- the cost-guard is for routine sampling, not for
        # calls we already suspect are bad.
        if judge_defs and anthropic_client is not None:
            for definition in judge_defs:
                sample_rate = definition.config.get("sample_rate", settings.judge_sample_rate)
                if not (any_rule_failed or random.random() < sample_rate):
                    continue
                result = await run_judge_eval(
                    anthropic_client.messages,
                    settings.judge_model,
                    definition.config,
                    call.prompt,
                    call.response,
                )
                if result is not None:
                    await _save_result(
                        db, call.id, definition.id, result.score, result.passed, result.rationale
                    )

        await db.commit()
        eval_jobs_processed_total.inc()
