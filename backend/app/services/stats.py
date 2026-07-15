import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LLMCall
from app.schemas import StatsBucket


async def get_stats(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    bucket: Literal["hour", "day"],
    group_by: Literal["model", "prompt_version"],
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[StatsBucket]:
    bucket_expr = func.date_trunc(bucket, LLMCall.created_at).label("bucket")
    group_col = LLMCall.model if group_by == "model" else LLMCall.prompt_version
    group_expr = group_col.label("group_key")

    stmt = select(
        bucket_expr,
        group_expr,
        func.count().label("volume"),
        func.coalesce(func.sum(LLMCall.cost_usd), 0).label("spend_usd"),
        func.percentile_cont(0.5).within_group(LLMCall.latency_ms.asc()).label("latency_p50_ms"),
        func.percentile_cont(0.95).within_group(LLMCall.latency_ms.asc()).label("latency_p95_ms"),
        func.percentile_cont(0.99).within_group(LLMCall.latency_ms.asc()).label("latency_p99_ms"),
    ).where(LLMCall.project_id == project_id)

    if start_time is not None:
        stmt = stmt.where(LLMCall.created_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(LLMCall.created_at <= end_time)

    stmt = stmt.group_by(bucket_expr, group_expr).order_by(bucket_expr.asc())

    result = await db.execute(stmt)
    return [
        StatsBucket(
            bucket=row.bucket,
            group_key=row.group_key,
            volume=row.volume,
            spend_usd=row.spend_usd,
            latency_p50_ms=row.latency_p50_ms,
            latency_p95_ms=row.latency_p95_ms,
            latency_p99_ms=row.latency_p99_ms,
        )
        for row in result.all()
    ]
