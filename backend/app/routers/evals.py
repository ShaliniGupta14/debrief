import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.anthropic_client import get_anthropic_client
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_project
from app.evals.calibration import compute_calibration_report
from app.evals.judge import run_judge_eval
from app.models import EvalDefinition, LLMCall, Project
from app.schemas import (
    CalibrationRequest,
    EvalDefinitionIn,
    EvalDefinitionListResponse,
    EvalDefinitionOut,
)

router = APIRouter()
settings = get_settings()
CALIBRATION_RUNS_PER_CALL = 3


def _to_out(row: EvalDefinition) -> EvalDefinitionOut:
    return EvalDefinitionOut(
        id=row.id,
        name=row.name,
        type=row.type,
        config=row.config,
        enabled=row.enabled,
        calibration_report=row.calibration_report,
        created_at=row.created_at,
    )


@router.post("/v1/evals", status_code=201, response_model=EvalDefinitionOut)
async def create_eval(
    payload: EvalDefinitionIn,
    project: Project = Depends(get_current_project),
    db: AsyncSession = Depends(get_db),
) -> EvalDefinitionOut:
    row = EvalDefinition(
        project_id=project.id,
        name=payload.name,
        type=payload.type,
        config=payload.config,
        enabled=payload.enabled,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail=f"an eval named '{payload.name}' already exists"
        ) from exc
    await db.refresh(row)
    return _to_out(row)


@router.get("/v1/evals", response_model=EvalDefinitionListResponse)
async def list_evals(
    project: Project = Depends(get_current_project),
    db: AsyncSession = Depends(get_db),
) -> EvalDefinitionListResponse:
    result = await db.execute(
        select(EvalDefinition)
        .where(EvalDefinition.project_id == project.id)
        .order_by(EvalDefinition.created_at)
    )
    return EvalDefinitionListResponse(items=[_to_out(row) for row in result.scalars().all()])


@router.post("/v1/evals/{eval_id}/calibrate", response_model=EvalDefinitionOut)
async def calibrate_eval(
    eval_id: uuid.UUID,
    payload: CalibrationRequest,
    project: Project = Depends(get_current_project),
    db: AsyncSession = Depends(get_db),
    anthropic_client: Any = Depends(get_anthropic_client),
) -> EvalDefinitionOut:
    eval_def = await db.get(EvalDefinition, eval_id)
    if eval_def is None or eval_def.project_id != project.id:
        raise HTTPException(status_code=404, detail="eval definition not found")
    if eval_def.type != "llm_judge":
        raise HTTPException(status_code=400, detail="calibration only applies to llm_judge evals")
    if anthropic_client is None:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured")

    if payload.call_ids:
        calls_result = await db.execute(
            select(LLMCall).where(
                LLMCall.id.in_(payload.call_ids), LLMCall.project_id == project.id
            )
        )
    else:
        calls_result = await db.execute(
            select(LLMCall)
            .where(LLMCall.project_id == project.id)
            .order_by(LLMCall.created_at.desc())
            .limit(payload.sample_size)
        )
    calls = calls_result.scalars().all()
    if not calls:
        raise HTTPException(status_code=400, detail="no calls available to calibrate against")

    async def _score_call(call: LLMCall) -> tuple[str, list[float]]:
        runs = await asyncio.gather(
            *[
                run_judge_eval(
                    anthropic_client.messages,
                    settings.judge_model,
                    eval_def.config,
                    call.prompt,
                    call.response,
                )
                for _ in range(CALIBRATION_RUNS_PER_CALL)
            ]
        )
        return str(call.id), [r.score for r in runs if r is not None]

    per_call_scores = dict(await asyncio.gather(*[_score_call(call) for call in calls]))
    eval_def.calibration_report = compute_calibration_report(per_call_scores)

    await db.commit()
    await db.refresh(eval_def)
    return _to_out(eval_def)
