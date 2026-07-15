"""initial schema

Revision ID: f3a1c9d2e8b4
Revises:
Create Date: 2026-07-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a1c9d2e8b4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "projects",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("api_key_hash", sa.String(), nullable=False),
        sa.Column("api_key_prefix", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("api_key_hash", name="uq_projects_api_key_hash"),
    )

    op.create_table(
        "llm_calls",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_call_id", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', coalesce(prompt, '') || ' ' || coalesce(response, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "client_call_id", name="uq_llm_calls_project_client_call_id"),
    )
    op.create_index("ix_llm_calls_project_created", "llm_calls", ["project_id", "created_at"])
    op.create_index(
        "ix_llm_calls_metadata_gin",
        "llm_calls",
        ["metadata"],
        postgresql_using="gin",
        postgresql_ops={"metadata": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_llm_calls_search_vector_gin",
        "llm_calls",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.create_table(
        "eval_definitions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("calibration_report", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_eval_definitions_project_name"),
    )

    op.create_table(
        "eval_results",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("llm_calls.id"), nullable=False),
        sa.Column(
            "eval_definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_definitions.id"),
            nullable=False,
        ),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("judge_rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("call_id", "eval_definition_id", name="uq_eval_results_call_eval"),
    )

    op.create_table(
        "model_prices",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_price_per_mtok", sa.Numeric(12, 6), nullable=False),
        sa.Column("output_price_per_mtok", sa.Numeric(12, 6), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("model", "effective_date", name="uq_model_prices_model_effective_date"),
    )
    op.create_index("ix_model_prices_model_effective_date", "model_prices", ["model", "effective_date"])


def downgrade() -> None:
    op.drop_table("model_prices")
    op.drop_table("eval_results")
    op.drop_table("eval_definitions")
    op.drop_index("ix_llm_calls_search_vector_gin", table_name="llm_calls")
    op.drop_index("ix_llm_calls_metadata_gin", table_name="llm_calls")
    op.drop_index("ix_llm_calls_project_created", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_table("projects")
