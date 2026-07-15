from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_project
from app.models import EvalDefinition, Project
from app.schemas import EvalDefinitionIn, EvalDefinitionListResponse, EvalDefinitionOut

router = APIRouter()


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
