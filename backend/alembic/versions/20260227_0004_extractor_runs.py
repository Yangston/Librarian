"""add extractor run logging table

Revision ID: 20260227_0004
Revises: 20260226_0003
Create Date: 2026-02-27 00:00:04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_0004"
down_revision: str | None = "20260226_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extractor_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("input_message_ids_json", sa.JSON(), nullable=False),
        sa.Column("raw_output_json", sa.JSON(), nullable=False),
        sa.Column("validated_output_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extractor_runs_conversation_id", "extractor_runs", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_extractor_runs_conversation_id", table_name="extractor_runs")
    op.drop_table("extractor_runs")
