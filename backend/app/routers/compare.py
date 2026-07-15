from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_project
from app.evals.compare_stats import bootstrap_compare, worst_regressions
from app.models import EvalDefinition, Project
from app.schemas import CompareResponse, EvalComparison, WorstRegressionOut
from app.services.compare import get_scores_by_prompt

router = APIRouter()

WORST_REGRESSIONS_LIMIT = 10


@router.get("/v1/compare", response_model=CompareResponse)
async def compare_versions(
    version_a: str = Query(..., description="baseline / older prompt version"),
    version_b: str = Query(..., description="candidate / newer prompt version"),
    project: Project = Depends(get_current_project),
    db: AsyncSession = Depends(get_db),
) -> CompareResponse:
    eval_defs = (
        (await db.execute(select(EvalDefinition).where(EvalDefinition.project_id == project.id)))
        .scalars()
        .all()
    )

    eval_comparisons: list[EvalComparison] = []
    all_regressions: list[WorstRegressionOut] = []

    for eval_def in eval_defs:
        scores_by_prompt_a = await get_scores_by_prompt(db, project.id, version_a, eval_def.id)
        scores_by_prompt_b = await get_scores_by_prompt(db, project.id, version_b, eval_def.id)

        flat_a = [s for scores in scores_by_prompt_a.values() for s in scores]
        flat_b = [s for scores in scores_by_prompt_b.values() for s in scores]

        result = bootstrap_compare(flat_a, flat_b)
        eval_comparisons.append(
            EvalComparison(
                eval_definition_id=eval_def.id,
                eval_name=eval_def.name,
                mean_score_a=result.mean_a if result else None,
                mean_score_b=result.mean_b if result else None,
                delta=result.delta if result else None,
                ci_low=result.ci_low if result else None,
                ci_high=result.ci_high if result else None,
                n_calls_a=len(flat_a),
                n_calls_b=len(flat_b),
                regressed=result.regressed if result else False,
            )
        )

        for row in worst_regressions(
            scores_by_prompt_a, scores_by_prompt_b, n=WORST_REGRESSIONS_LIMIT
        ):
            all_regressions.append(
                WorstRegressionOut(
                    eval_definition_id=eval_def.id,
                    eval_name=eval_def.name,
                    prompt=row.prompt,
                    mean_score_a=row.mean_score_a,
                    mean_score_b=row.mean_score_b,
                    delta=row.delta,
                    n_calls_a=row.n_calls_a,
                    n_calls_b=row.n_calls_b,
                )
            )

    all_regressions.sort(key=lambda r: r.delta)

    return CompareResponse(
        version_a=version_a,
        version_b=version_b,
        evals=eval_comparisons,
        worst_regressions=all_regressions[:WORST_REGRESSIONS_LIMIT],
        any_regression=any(e.regressed for e in eval_comparisons),
    )
