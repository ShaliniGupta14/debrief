import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class CallIn(BaseModel):
    model: str
    prompt: str
    response: str
    prompt_version: str | None = None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    status: Literal["ok", "error"] = "ok"
    error_message: str | None = None
    trace_id: uuid.UUID | None = None
    client_call_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResultItem(BaseModel):
    id: uuid.UUID
    client_call_id: str | None
    duplicate: bool


class IngestResponse(BaseModel):
    accepted: list[IngestResultItem]
    count: int


class CallSummary(BaseModel):
    id: uuid.UUID
    model: str
    prompt_preview: str
    prompt_version: str | None
    status: str
    error_message: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None
    latency_ms: int
    trace_id: uuid.UUID | None
    created_at: datetime


class CallListResponse(BaseModel):
    items: list[CallSummary]
    next_cursor: str | None


class EvalResultOut(BaseModel):
    id: uuid.UUID
    eval_definition_id: uuid.UUID
    score: Decimal
    passed: bool | None
    judge_rationale: str | None
    created_at: datetime


class CallDetail(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    trace_id: uuid.UUID | None
    client_call_id: str | None
    model: str
    prompt: str
    response: str
    prompt_version: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None
    latency_ms: int
    status: str
    error_message: str | None
    metadata: dict[str, Any]
    created_at: datetime
    eval_results: list[EvalResultOut]
