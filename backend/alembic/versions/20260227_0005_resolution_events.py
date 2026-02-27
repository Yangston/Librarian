"""add resolution event log table

Revision ID: 20260227_0005
Revises: 20260227_0004
Create Date: 2026-02-27 00:00:05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_0005"
down_revision: str | None = "20260227_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resolution_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("entity_ids_json", sa.JSON(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("rationale", sa.String(length=255), nullable=False),
        sa.Column("source_message_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resolution_events_conversation_id", "resolution_events", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_resolution_events_conversation_id", table_name="resolution_events")
    op.drop_table("resolution_events")
