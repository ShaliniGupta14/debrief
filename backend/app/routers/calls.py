import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_project
from app.models import EvalResult, LLMCall, Project
from app.pagination import decode_cursor, encode_cursor
from app.schemas import CallDetail, CallListResponse, CallSummary, EvalResultOut
from app.services.calls import get_call_by_id, list_calls

router = APIRouter()

PROMPT_PREVIEW_LENGTH = 150


def _to_summary(row: LLMCall) -> CallSummary:
    preview = (
        row.prompt
        if len(row.prompt) <= PROMPT_PREVIEW_LENGTH
        else row.prompt[:PROMPT_PREVIEW_LENGTH] + "..."
    )
    return CallSummary(
        id=row.id,
        model=row.model,
        prompt_preview=preview,
        prompt_version=row.prompt_version,
        status=row.status,
        error_message=row.error_message,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cost_usd=row.cost_usd,
        latency_ms=row.latency_ms,
        trace_id=row.trace_id,
        created_at=row.created_at,
    )


@router.get("/v1/calls", response_model=CallListResponse)
async def list_calls_endpoint(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    status: Literal["ok", "error"] | None = None,
    metadata: str | None = None,
    q: str | None = None,
    project: Project = Depends(get_current_project),
    db: AsyncSession = Depends(get_db),
) -> CallListResponse:
    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_cursor(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="invalid cursor") from exc

    metadata_filter = None
    if metadata is not None:
        try:
            metadata_filter = json.loads(metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="metadata must be valid JSON") from exc

    rows = await list_calls(
        db,
        project.id,
        cursor=decoded_cursor,
        limit=limit,
        start_time=start_time,
        end_time=end_time,
        model=model,
        prompt_version=prompt_version,
        status=status,
        metadata_filter=metadata_filter,
        q=q,
    )

    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None

    return CallListResponse(items=[_to_summary(row) for row in rows], next_cursor=next_cursor)


@router.get("/v1/calls/{call_id}", response_model=CallDetail)
async def get_call_detail(
    call_id: uuid.UUID,
    project: Project = Depends(get_current_project),
    db: AsyncSession = Depends(get_db),
) -> CallDetail:
    row = await get_call_by_id(db, project.id, call_id)
    if row is None:
        raise HTTPException(status_code=404, detail="call not found")

    eval_rows = (
        (await db.execute(select(EvalResult).where(EvalResult.call_id == call_id))).scalars().all()
    )

    return CallDetail(
        id=row.id,
        project_id=row.project_id,
        trace_id=row.trace_id,
        client_call_id=row.client_call_id,
        model=row.model,
        prompt=row.prompt,
        response=row.response,
        prompt_version=row.prompt_version,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        cost_usd=row.cost_usd,
        latency_ms=row.latency_ms,
        status=row.status,
        error_message=row.error_message,
        metadata=row.metadata_,
        created_at=row.created_at,
        eval_results=[
            EvalResultOut(
                id=e.id,
                eval_definition_id=e.eval_definition_id,
                score=e.score,
                passed=e.passed,
                judge_rationale=e.judge_rationale,
                created_at=e.created_at,
            )
            for e in eval_rows
        ],
    )
