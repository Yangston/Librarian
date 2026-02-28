"""phase3 add relation confidence

Revision ID: 20260228_0009
Revises: 20260227_0008
Create Date: 2026-02-28 00:00:09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260228_0009"
down_revision: str | None = "20260227_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "relations",
        sa.Column("confidence", sa.Float(), server_default=sa.text("1.0"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("relations", "confidence")

