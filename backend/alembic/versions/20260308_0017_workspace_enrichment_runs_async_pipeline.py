"""extend workspace enrichment runs for async staged pipeline

Revision ID: 20260308_0017
Revises: 20260307_0016
Create Date: 2026-03-08 01:05:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260308_0017"
down_revision: str | None = "20260307_0016"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace_enrichment_runs",
        sa.Column("conversation_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "workspace_enrichment_runs",
        sa.Column("run_kind", sa.String(length=32), nullable=False, server_default="manual_space"),
    )
    op.add_column(
        "workspace_enrichment_runs",
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="queued"),
    )
    op.create_foreign_key(
        "fk_workspace_enrichment_runs_conversation_id",
        "workspace_enrichment_runs",
        "conversations",
        ["conversation_id"],
        ["conversation_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_workspace_enrichment_runs_conversation_id",
        "workspace_enrichment_runs",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_enrichment_runs_run_kind",
        "workspace_enrichment_runs",
        ["run_kind"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_enrichment_runs_stage",
        "workspace_enrichment_runs",
        ["stage"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_enrichment_runs_stage", table_name="workspace_enrichment_runs")
    op.drop_index("ix_workspace_enrichment_runs_run_kind", table_name="workspace_enrichment_runs")
    op.drop_index("ix_workspace_enrichment_runs_conversation_id", table_name="workspace_enrichment_runs")
    op.drop_constraint("fk_workspace_enrichment_runs_conversation_id", "workspace_enrichment_runs", type_="foreignkey")
    op.drop_column("workspace_enrichment_runs", "stage")
    op.drop_column("workspace_enrichment_runs", "run_kind")
    op.drop_column("workspace_enrichment_runs", "conversation_id")
