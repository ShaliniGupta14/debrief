"""cost_usd nullable

Revision ID: b7e2f4a1c3d5
Revises: f3a1c9d2e8b4
Create Date: 2026-07-15 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e2f4a1c3d5"
down_revision: str | None = "f3a1c9d2e8b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("llm_calls", "cost_usd", existing_type=sa.Numeric(12, 6), nullable=True)


def downgrade() -> None:
    op.alter_column("llm_calls", "cost_usd", existing_type=sa.Numeric(12, 6), nullable=False)
