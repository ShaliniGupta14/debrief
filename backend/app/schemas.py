import uuid
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
