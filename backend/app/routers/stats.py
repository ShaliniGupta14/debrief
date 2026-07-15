from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_project
from app.models import Project
from app.schemas import StatsResponse
from app.services.stats import get_stats

router = APIRouter()


@router.get("/v1/stats", response_model=StatsResponse)
async def get_stats_endpoint(
    bucket: Literal["hour", "day"] = "day",
    group_by: Literal["model", "prompt_version"] = "model",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    project: Project = Depends(get_current_project),
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    buckets = await get_stats(
        db,
        project.id,
        bucket=bucket,
        group_by=group_by,
        start_time=start_time,
        end_time=end_time,
    )
    return StatsResponse(buckets=buckets)
