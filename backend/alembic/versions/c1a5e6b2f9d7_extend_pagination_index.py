"""extend project_created index for keyset pagination

Revision ID: c1a5e6b2f9d7
Revises: b7e2f4a1c3d5
Create Date: 2026-07-15 01:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c1a5e6b2f9d7"
down_revision: str | None = "b7e2f4a1c3d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_llm_calls_project_created", table_name="llm_calls")
    op.create_index(
        "ix_llm_calls_project_created_id",
        "llm_calls",
        ["project_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_calls_project_created_id", table_name="llm_calls")
    op.create_index("ix_llm_calls_project_created", "llm_calls", ["project_id", "created_at"])
