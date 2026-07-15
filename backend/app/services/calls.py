import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LLMCall


async def list_calls(
    db: AsyncSession,
    project_id: uuid.UUID,
    *,
    cursor: tuple[datetime, uuid.UUID] | None,
    limit: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    status: str | None = None,
    metadata_filter: dict[str, Any] | None = None,
    q: str | None = None,
) -> list[LLMCall]:
    stmt = select(LLMCall).where(LLMCall.project_id == project_id)

    if start_time is not None:
        stmt = stmt.where(LLMCall.created_at >= start_time)
    if end_time is not None:
        stmt = stmt.where(LLMCall.created_at <= end_time)
    if model is not None:
        stmt = stmt.where(LLMCall.model == model)
    if prompt_version is not None:
        stmt = stmt.where(LLMCall.prompt_version == prompt_version)
    if status is not None:
        stmt = stmt.where(LLMCall.status == status)
    if metadata_filter is not None:
        stmt = stmt.where(LLMCall.metadata_.op("@>")(metadata_filter))
    if q is not None:
        stmt = stmt.where(LLMCall.search_vector.op("@@")(func.plainto_tsquery("english", q)))
    if cursor is not None:
        cursor_created_at, cursor_id = cursor
        stmt = stmt.where(
            or_(
                LLMCall.created_at < cursor_created_at,
                and_(LLMCall.created_at == cursor_created_at, LLMCall.id < cursor_id),
            )
        )

    # Fetch one extra row to know whether a next page exists without a second query.
    stmt = stmt.order_by(LLMCall.created_at.desc(), LLMCall.id.desc()).limit(limit + 1)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_call_by_id(
    db: AsyncSession, project_id: uuid.UUID, call_id: uuid.UUID
) -> LLMCall | None:
    result = await db.execute(
        select(LLMCall).where(LLMCall.id == call_id, LLMCall.project_id == project_id)
    )
    return result.scalar_one_or_none()
