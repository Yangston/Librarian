"""initial schema

Revision ID: 20260224_0001
Revises:
Create Date: 2026-02-24 00:00:01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260224_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], unique=False)
    op.create_index("ix_messages_timestamp", "messages", ["timestamp"], unique=False)

    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("aliases_json", sa.JSON(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entities_conversation_id", "entities", ["conversation_id"], unique=False)

    op.create_table(
        "facts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("subject_entity_id", sa.Integer(), nullable=False),
        sa.Column("predicate", sa.String(length=255), nullable=False),
        sa.Column("object_value", sa.String(length=1024), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("source_message_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["subject_entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facts_conversation_id", "facts", ["conversation_id"], unique=False)

    op.create_table(
        "relations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("from_entity_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=255), nullable=False),
        sa.Column("to_entity_id", sa.Integer(), nullable=False),
        sa.Column("qualifiers_json", sa.JSON(), nullable=False),
        sa.Column("source_message_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["from_entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_relations_conversation_id", "relations", ["conversation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_relations_conversation_id", table_name="relations")
    op.drop_table("relations")
    op.drop_index("ix_facts_conversation_id", table_name="facts")
    op.drop_table("facts")
    op.drop_index("ix_entities_conversation_id", table_name="entities")
    op.drop_table("entities")
    op.drop_index("ix_messages_timestamp", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
