from datetime import UTC, datetime

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.metrics import llm_calls_ingested_total
from app.models import LLMCall, Project
from app.queue import get_arq_pool
from app.rate_limit import enforce_ingest_rate_limit
from app.schemas import CallIn, IngestResponse, IngestResultItem
from app.services.pricing import compute_cost

router = APIRouter()

MAX_BATCH_SIZE = 100


async def _ingest_one(db: AsyncSession, project: Project, call_in: CallIn) -> tuple[LLMCall, bool]:
    now = datetime.now(UTC)
    cost = await compute_cost(db, call_in.model, call_in.input_tokens, call_in.output_tokens, now)
    row = LLMCall(
        project_id=project.id,
        trace_id=call_in.trace_id,
        client_call_id=call_in.client_call_id,
        model=call_in.model,
        prompt=call_in.prompt,
        response=call_in.response,
        prompt_version=call_in.prompt_version,
        input_tokens=call_in.input_tokens,
        output_tokens=call_in.output_tokens,
        cost_usd=cost,
        latency_ms=call_in.latency_ms,
        status=call_in.status,
        error_message=call_in.error_message,
        metadata_=call_in.metadata,
    )
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
        return row, False
    except IntegrityError:
        # Only reachable via the (project_id, client_call_id) unique constraint —
        # anything else re-raises rather than silently masking a real error.
        if call_in.client_call_id is None:
            raise
        result = await db.execute(
            select(LLMCall).where(
                LLMCall.project_id == project.id,
                LLMCall.client_call_id == call_in.client_call_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            raise
        return existing, True


@router.post("/v1/ingest", status_code=202, response_model=IngestResponse)
async def ingest(
    payload: list[CallIn],
    project: Project = Depends(enforce_ingest_rate_limit),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> IngestResponse:
    if not payload:
        raise HTTPException(status_code=422, detail="at least one call is required")
    if len(payload) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=422, detail=f"batch size cannot exceed {MAX_BATCH_SIZE}")

    results = []
    for call_in in payload:
        row, duplicate = await _ingest_one(db, project, call_in)
        results.append(
            IngestResultItem(id=row.id, client_call_id=row.client_call_id, duplicate=duplicate)
        )
        if not duplicate:
            llm_calls_ingested_total.labels(status=row.status).inc()

    await db.commit()

    # Only enqueue for genuinely new rows -- an idempotent replay of an
    # already-evaluated call shouldn't re-trigger (and re-cost) a judge call.
    for result_item in results:
        if not result_item.duplicate:
            await arq_pool.enqueue_job("run_evals_for_call", str(result_item.id))

    return IngestResponse(accepted=results, count=len(results))
