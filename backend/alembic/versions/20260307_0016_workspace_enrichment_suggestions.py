"""workspace enrichment suggestion tables

Revision ID: 20260307_0016
Revises: 20260306_0015
Create Date: 2026-03-07 11:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260307_0016"
down_revision: str | None = "20260306_0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_enrichment_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pod_id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=True),
        sa.Column("collection_item_id", sa.Integer(), nullable=True),
        sa.Column("requested_by", sa.String(length=32), nullable=False, server_default="system"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["pod_id"], ["pods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["collection_item_id"], ["collection_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspace_enrichment_runs_pod_id", "workspace_enrichment_runs", ["pod_id"], unique=False)
    op.create_index("ix_workspace_enrichment_runs_collection_id", "workspace_enrichment_runs", ["collection_id"], unique=False)
    op.create_index("ix_workspace_enrichment_runs_collection_item_id", "workspace_enrichment_runs", ["collection_item_id"], unique=False)
    op.create_index("ix_workspace_enrichment_runs_status", "workspace_enrichment_runs", ["status"], unique=False)

    op.create_table(
        "collection_item_value_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enrichment_run_id", sa.Integer(), nullable=True),
        sa.Column("collection_item_id", sa.Integer(), nullable=False),
        sa.Column("collection_column_id", sa.Integer(), nullable=False),
        sa.Column("suggested_value_json", sa.JSON(), nullable=True),
        sa.Column("suggested_display_value", sa.String(length=2048), nullable=True),
        sa.Column("value_type", sa.String(length=32), nullable=False, server_default="text"),
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="external"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("source_ids_json", sa.JSON(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["enrichment_run_id"], ["workspace_enrichment_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["collection_item_id"], ["collection_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_column_id"], ["collection_columns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "collection_item_id",
            "collection_column_id",
            "dedupe_key",
            name="uq_collection_item_value_suggestions_target_key",
        ),
    )
    op.create_index("ix_collection_item_value_suggestions_enrichment_run_id", "collection_item_value_suggestions", ["enrichment_run_id"], unique=False)
    op.create_index("ix_collection_item_value_suggestions_collection_item_id", "collection_item_value_suggestions", ["collection_item_id"], unique=False)
    op.create_index("ix_collection_item_value_suggestions_collection_column_id", "collection_item_value_suggestions", ["collection_column_id"], unique=False)
    op.create_index("ix_collection_item_value_suggestions_source_kind", "collection_item_value_suggestions", ["source_kind"], unique=False)
    op.create_index("ix_collection_item_value_suggestions_status", "collection_item_value_suggestions", ["status"], unique=False)
    op.create_index("ix_collection_item_value_suggestions_dedupe_key", "collection_item_value_suggestions", ["dedupe_key"], unique=False)

    op.create_table(
        "collection_item_relation_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enrichment_run_id", sa.Integer(), nullable=True),
        sa.Column("from_collection_item_id", sa.Integer(), nullable=False),
        sa.Column("to_collection_item_id", sa.Integer(), nullable=False),
        sa.Column("relation_label", sa.String(length=255), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="external"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("source_ids_json", sa.JSON(), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["enrichment_run_id"], ["workspace_enrichment_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["from_collection_item_id"], ["collection_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_collection_item_id"], ["collection_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_collection_item_id",
            "to_collection_item_id",
            "relation_label",
            "dedupe_key",
            name="uq_collection_item_relation_suggestions_target_key",
        ),
    )
    op.create_index("ix_collection_item_relation_suggestions_enrichment_run_id", "collection_item_relation_suggestions", ["enrichment_run_id"], unique=False)
    op.create_index("ix_collection_item_relation_suggestions_from_collection_item_id", "collection_item_relation_suggestions", ["from_collection_item_id"], unique=False)
    op.create_index("ix_collection_item_relation_suggestions_to_collection_item_id", "collection_item_relation_suggestions", ["to_collection_item_id"], unique=False)
    op.create_index("ix_collection_item_relation_suggestions_relation_label", "collection_item_relation_suggestions", ["relation_label"], unique=False)
    op.create_index("ix_collection_item_relation_suggestions_source_kind", "collection_item_relation_suggestions", ["source_kind"], unique=False)
    op.create_index("ix_collection_item_relation_suggestions_status", "collection_item_relation_suggestions", ["status"], unique=False)
    op.create_index("ix_collection_item_relation_suggestions_dedupe_key", "collection_item_relation_suggestions", ["dedupe_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_collection_item_relation_suggestions_dedupe_key", table_name="collection_item_relation_suggestions")
    op.drop_index("ix_collection_item_relation_suggestions_status", table_name="collection_item_relation_suggestions")
    op.drop_index("ix_collection_item_relation_suggestions_source_kind", table_name="collection_item_relation_suggestions")
    op.drop_index("ix_collection_item_relation_suggestions_relation_label", table_name="collection_item_relation_suggestions")
    op.drop_index("ix_collection_item_relation_suggestions_to_collection_item_id", table_name="collection_item_relation_suggestions")
    op.drop_index("ix_collection_item_relation_suggestions_from_collection_item_id", table_name="collection_item_relation_suggestions")
    op.drop_index("ix_collection_item_relation_suggestions_enrichment_run_id", table_name="collection_item_relation_suggestions")
    op.drop_table("collection_item_relation_suggestions")

    op.drop_index("ix_collection_item_value_suggestions_dedupe_key", table_name="collection_item_value_suggestions")
    op.drop_index("ix_collection_item_value_suggestions_status", table_name="collection_item_value_suggestions")
    op.drop_index("ix_collection_item_value_suggestions_source_kind", table_name="collection_item_value_suggestions")
    op.drop_index("ix_collection_item_value_suggestions_collection_column_id", table_name="collection_item_value_suggestions")
    op.drop_index("ix_collection_item_value_suggestions_collection_item_id", table_name="collection_item_value_suggestions")
    op.drop_index("ix_collection_item_value_suggestions_enrichment_run_id", table_name="collection_item_value_suggestions")
    op.drop_table("collection_item_value_suggestions")

    op.drop_index("ix_workspace_enrichment_runs_status", table_name="workspace_enrichment_runs")
    op.drop_index("ix_workspace_enrichment_runs_collection_item_id", table_name="workspace_enrichment_runs")
    op.drop_index("ix_workspace_enrichment_runs_collection_id", table_name="workspace_enrichment_runs")
    op.drop_index("ix_workspace_enrichment_runs_pod_id", table_name="workspace_enrichment_runs")
    op.drop_table("workspace_enrichment_runs")
