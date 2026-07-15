import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    """An instrumented app. Doubles as the auth boundary: one API key per project."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    api_key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LLMCall(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("ix_llm_calls_project_created", "project_id", "created_at"),
        Index(
            "ix_llm_calls_metadata_gin",
            "metadata",
            postgresql_using="gin",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
        Index("ix_llm_calls_search_vector_gin", "search_vector", postgresql_using="gin"),
        UniqueConstraint("project_id", "client_call_id", name="uq_llm_calls_project_client_call_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    client_call_id: Mapped[str | None] = mapped_column(String, nullable=True)

    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(prompt, '') || ' ' || coalesce(response, ''))",
            persisted=True,
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalDefinition(Base):
    __tablename__ = "eval_definitions"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_eval_definitions_project_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Populated by a one-off calibration run (judge x3 on a fixed sample), not per-call.
    # See DECISIONS.md: keeping this off eval_results avoids breaking its unique constraint.
    calibration_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = (UniqueConstraint("call_id", "eval_definition_id", name="uq_eval_results_call_eval"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_calls.id"), nullable=False)
    eval_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("eval_definitions.id"), nullable=False
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    judge_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelPrice(Base):
    __tablename__ = "model_prices"
    __table_args__ = (
        UniqueConstraint("model", "effective_date", name="uq_model_prices_model_effective_date"),
        Index("ix_model_prices_model_effective_date", "model", "effective_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    model: Mapped[str] = mapped_column(String, nullable=False)
    input_price_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    output_price_per_mtok: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
