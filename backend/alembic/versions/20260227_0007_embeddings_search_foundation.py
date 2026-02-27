"""add embedding/search foundation columns and conversation entity links

Revision ID: 20260227_0007
Revises: 20260227_0006
Create Date: 2026-02-27 00:00:07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_0007"
down_revision: str | None = "20260227_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("embedding", sa.JSON(), nullable=True))

    op.add_column("facts", sa.Column("extractor_run_id", sa.Integer(), nullable=True))
    op.add_column("facts", sa.Column("embedding", sa.JSON(), nullable=True))
    op.create_index("ix_facts_extractor_run_id", "facts", ["extractor_run_id"], unique=False)
    op.create_foreign_key(
        "fk_facts_extractor_run_id_extractor_runs",
        "facts",
        "extractor_runs",
        ["extractor_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("relations", sa.Column("extractor_run_id", sa.Integer(), nullable=True))
    op.create_index("ix_relations_extractor_run_id", "relations", ["extractor_run_id"], unique=False)
    op.create_foreign_key(
        "fk_relations_extractor_run_id_extractor_runs",
        "relations",
        "extractor_runs",
        ["extractor_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "conversation_entity_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("first_seen_message_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "entity_id",
            name="uq_conversation_entity_links_conversation_entity",
        ),
    )
    op.create_index(
        "ix_conversation_entity_links_conversation_id",
        "conversation_entity_links",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_entity_links_entity_id",
        "conversation_entity_links",
        ["entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_entity_links_entity_id", table_name="conversation_entity_links")
    op.drop_index("ix_conversation_entity_links_conversation_id", table_name="conversation_entity_links")
    op.drop_table("conversation_entity_links")

    op.drop_constraint("fk_relations_extractor_run_id_extractor_runs", "relations", type_="foreignkey")
    op.drop_index("ix_relations_extractor_run_id", table_name="relations")
    op.drop_column("relations", "extractor_run_id")

    op.drop_constraint("fk_facts_extractor_run_id_extractor_runs", "facts", type_="foreignkey")
    op.drop_index("ix_facts_extractor_run_id", table_name="facts")
    op.drop_column("facts", "embedding")
    op.drop_column("facts", "extractor_run_id")

    op.drop_column("entities", "embedding")
