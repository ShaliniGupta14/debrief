import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EvalResult, LLMCall


async def get_scores_by_prompt(
    db: AsyncSession,
    project_id: uuid.UUID,
    prompt_version: str,
    eval_definition_id: uuid.UUID,
) -> dict[str, list[float]]:
    stmt = (
        select(LLMCall.prompt, EvalResult.score)
        .join(EvalResult, EvalResult.call_id == LLMCall.id)
        .where(
            LLMCall.project_id == project_id,
            LLMCall.prompt_version == prompt_version,
            EvalResult.eval_definition_id == eval_definition_id,
        )
    )
    result = await db.execute(stmt)
    scores_by_prompt: dict[str, list[float]] = defaultdict(list)
    for prompt, score in result.all():
        scores_by_prompt[prompt].append(float(score))
    return scores_by_prompt
