"""add schema registry tables

Revision ID: 20260227_0006
Revises: 20260227_0005
Create Date: 2026-02-27 00:00:06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_0006"
down_revision: str | None = "20260227_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schema_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("examples_json", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("stats_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
    )
    op.create_index("ix_schema_nodes_label", "schema_nodes", ["label"], unique=True)

    op.create_table(
        "schema_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("canonical_of_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("examples_json", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("stats_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["canonical_of_id"], ["schema_fields.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
    )
    op.create_index("ix_schema_fields_label", "schema_fields", ["label"], unique=True)
    op.create_index("ix_schema_fields_canonical_of_id", "schema_fields", ["canonical_of_id"], unique=False)

    op.create_table(
        "schema_relations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("canonical_of_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("examples_json", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("stats_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["canonical_of_id"], ["schema_relations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
    )
    op.create_index("ix_schema_relations_label", "schema_relations", ["label"], unique=True)
    op.create_index(
        "ix_schema_relations_canonical_of_id",
        "schema_relations",
        ["canonical_of_id"],
        unique=False,
    )

    op.create_table(
        "schema_proposals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("proposal_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'proposed'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schema_proposals_proposal_type", "schema_proposals", ["proposal_type"], unique=False)
    op.create_index("ix_schema_proposals_status", "schema_proposals", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_schema_proposals_status", table_name="schema_proposals")
    op.drop_index("ix_schema_proposals_proposal_type", table_name="schema_proposals")
    op.drop_table("schema_proposals")

    op.drop_index("ix_schema_relations_canonical_of_id", table_name="schema_relations")
    op.drop_index("ix_schema_relations_label", table_name="schema_relations")
    op.drop_table("schema_relations")

    op.drop_index("ix_schema_fields_canonical_of_id", table_name="schema_fields")
    op.drop_index("ix_schema_fields_label", table_name="schema_fields")
    op.drop_table("schema_fields")

    op.drop_index("ix_schema_nodes_label", table_name="schema_nodes")
    op.drop_table("schema_nodes")
