"""workspace performance indexes

Revision ID: 20260228_0010
Revises: 20260228_0009
Create Date: 2026-02-28 00:00:10
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260228_0010"
down_revision: str | None = "20260228_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_messages_conversation_timestamp_id",
        "messages",
        ["conversation_id", "timestamp", "id"],
        unique=False,
    )
    op.create_index(
        "ix_entities_merged_updated_id",
        "entities",
        ["merged_into_id", "updated_at", "id"],
        unique=False,
    )
    op.create_index("ix_entities_type_label", "entities", ["type_label"], unique=False)
    op.create_index("ix_facts_predicate", "facts", ["predicate"], unique=False)
    op.create_index(
        "ix_facts_subject_predicate_created_id",
        "facts",
        ["subject_entity_id", "predicate", "created_at", "id"],
        unique=False,
    )
    op.create_index("ix_relations_from_entity_id", "relations", ["from_entity_id"], unique=False)
    op.create_index("ix_relations_to_entity_id", "relations", ["to_entity_id"], unique=False)
    op.create_index(
        "ix_schema_proposals_created_at_id",
        "schema_proposals",
        ["created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_schema_proposals_created_at_id", table_name="schema_proposals")
    op.drop_index("ix_relations_to_entity_id", table_name="relations")
    op.drop_index("ix_relations_from_entity_id", table_name="relations")
    op.drop_index("ix_facts_subject_predicate_created_id", table_name="facts")
    op.drop_index("ix_facts_predicate", table_name="facts")
    op.drop_index("ix_entities_type_label", table_name="entities")
    op.drop_index("ix_entities_merged_updated_id", table_name="entities")
    op.drop_index("ix_messages_conversation_timestamp_id", table_name="messages")
