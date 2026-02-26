"""add entity resolution metadata and merge audit log

Revision ID: 20260226_0002
Revises: 20260224_0001
Create Date: 2026-02-26 00:00:02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260226_0002"
down_revision: str | None = "20260224_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("canonical_name", sa.String(length=255), nullable=True))
    op.add_column("entities", sa.Column("known_aliases_json", sa.JSON(), nullable=True))
    op.add_column("entities", sa.Column("first_seen_timestamp", sa.DateTime(timezone=True), nullable=True))
    op.add_column("entities", sa.Column("resolution_confidence", sa.Float(), nullable=True))
    op.add_column("entities", sa.Column("resolution_reason", sa.String(length=128), nullable=True))
    op.add_column("entities", sa.Column("resolver_version", sa.String(length=64), nullable=True))
    op.add_column("entities", sa.Column("merged_into_id", sa.Integer(), nullable=True))

    op.execute("UPDATE entities SET canonical_name = name WHERE canonical_name IS NULL")
    op.execute("UPDATE entities SET known_aliases_json = aliases_json WHERE known_aliases_json IS NULL")
    op.execute("UPDATE entities SET first_seen_timestamp = created_at WHERE first_seen_timestamp IS NULL")
    op.execute("UPDATE entities SET resolution_confidence = 1.0 WHERE resolution_confidence IS NULL")
    op.execute(
        "UPDATE entities SET resolver_version = 'legacy-pre-resolution' WHERE resolver_version IS NULL"
    )

    op.alter_column("entities", "canonical_name", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("entities", "known_aliases_json", existing_type=sa.JSON(), nullable=False)
    op.alter_column(
        "entities",
        "first_seen_timestamp",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column("entities", "resolution_confidence", existing_type=sa.Float(), nullable=False)

    op.create_index("ix_entities_canonical_name", "entities", ["canonical_name"], unique=False)
    op.create_index("ix_entities_merged_into_id", "entities", ["merged_into_id"], unique=False)
    op.create_foreign_key(
        "fk_entities_merged_into_id_entities",
        "entities",
        "entities",
        ["merged_into_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "entity_merge_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("survivor_entity_id", sa.Integer(), nullable=False),
        sa.Column("merged_entity_ids_json", sa.JSON(), nullable=False),
        sa.Column("reason_for_merge", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("resolver_version", sa.String(length=64), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_entity_merge_audits_conversation_id",
        "entity_merge_audits",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_entity_merge_audits_conversation_id", table_name="entity_merge_audits")
    op.drop_table("entity_merge_audits")

    op.drop_constraint("fk_entities_merged_into_id_entities", "entities", type_="foreignkey")
    op.drop_index("ix_entities_merged_into_id", table_name="entities")
    op.drop_index("ix_entities_canonical_name", table_name="entities")

    op.drop_column("entities", "merged_into_id")
    op.drop_column("entities", "resolver_version")
    op.drop_column("entities", "resolution_reason")
    op.drop_column("entities", "resolution_confidence")
    op.drop_column("entities", "first_seen_timestamp")
    op.drop_column("entities", "known_aliases_json")
    op.drop_column("entities", "canonical_name")
