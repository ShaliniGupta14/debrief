import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

EvalType = Literal["regex", "json_schema", "length", "contains", "llm_judge"]

# Required config keys per eval type -- checked at creation time so a bad
# definition fails fast with a 422, not silently at eval-run time in the worker.
_REQUIRED_CONFIG_KEYS: dict[str, tuple[str, ...]] = {
    "regex": ("pattern",),
    "json_schema": ("schema",),
    "length": (),  # validated separately: needs at least one of min/max
    "contains": ("text",),
    "llm_judge": ("rubric",),
}


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


class StatsBucket(BaseModel):
    bucket: datetime
    group_key: str | None
    volume: int
    spend_usd: Decimal
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float


class StatsResponse(BaseModel):
    buckets: list[StatsBucket]


class EvalDefinitionIn(BaseModel):
    name: str
    type: EvalType
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    @model_validator(mode="after")
    def _check_config_shape(self) -> "EvalDefinitionIn":
        missing = [k for k in _REQUIRED_CONFIG_KEYS[self.type] if k not in self.config]
        if missing:
            raise ValueError(f"{self.type} config missing required key(s): {', '.join(missing)}")
        if self.type == "length" and "min" not in self.config and "max" not in self.config:
            raise ValueError("length config needs at least one of 'min' or 'max'")
        return self


class EvalDefinitionOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    config: dict[str, Any]
    enabled: bool
    calibration_report: dict[str, Any] | None
    created_at: datetime


class EvalDefinitionListResponse(BaseModel):
    items: list[EvalDefinitionOut]


class CalibrationRequest(BaseModel):
    call_ids: list[uuid.UUID] | None = None
    sample_size: int = Field(default=5, ge=1, le=20)
