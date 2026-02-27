"""phase2 strict completion schema updates

Revision ID: 20260227_0008
Revises: 20260227_0007
Create Date: 2026-02-27 00:00:08
"""

from collections.abc import Sequence
import os

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260227_0008"
down_revision: str | None = "20260227_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_EMBEDDING_DIMENSIONS = 1536
_ENABLE_PGVECTOR = os.getenv("ENABLE_PGVECTOR", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def upgrade() -> None:
    op.add_column("entities", sa.Column("display_name", sa.String(length=255), nullable=True))
    op.add_column("entities", sa.Column("type_label", sa.String(length=64), nullable=True))
    op.add_column(
        "entities",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.execute("UPDATE entities SET display_name = name WHERE display_name IS NULL")
    op.execute("UPDATE entities SET type_label = type WHERE type_label IS NULL")
    op.execute("UPDATE entities SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("entities", "display_name", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("entities", "type_label", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("entities", "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    op.add_column(
        "facts",
        sa.Column("scope", sa.String(length=32), server_default=sa.text("'conversation'"), nullable=False),
    )
    op.create_index("ix_facts_scope", "facts", ["scope"], unique=False)
    op.add_column(
        "relations",
        sa.Column("scope", sa.String(length=32), server_default=sa.text("'conversation'"), nullable=False),
    )
    op.create_index("ix_relations_scope", "relations", ["scope"], unique=False)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and _ENABLE_PGVECTOR and _is_pgvector_available(bind):
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        _convert_embedding_columns_to_vector()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and _ENABLE_PGVECTOR and _is_pgvector_available(bind):
        _convert_embedding_columns_to_json()

    op.drop_index("ix_relations_scope", table_name="relations")
    op.drop_column("relations", "scope")
    op.drop_index("ix_facts_scope", table_name="facts")
    op.drop_column("facts", "scope")

    op.drop_column("entities", "updated_at")
    op.drop_column("entities", "type_label")
    op.drop_column("entities", "display_name")


def _convert_embedding_columns_to_vector() -> None:
    for table_name in ("entities", "facts", "schema_nodes", "schema_fields", "schema_relations"):
        op.execute(
            f"ALTER TABLE {table_name} "
            f"ALTER COLUMN embedding TYPE vector({_EMBEDDING_DIMENSIONS}) USING NULL"
        )


def _convert_embedding_columns_to_json() -> None:
    for table_name in ("entities", "facts", "schema_nodes", "schema_fields", "schema_relations"):
        op.execute(
            f"ALTER TABLE {table_name} "
            "ALTER COLUMN embedding TYPE jsonb USING to_jsonb(embedding)"
        )


def _is_pgvector_available(bind) -> bool:
    try:
        row = bind.execute(
            sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector' LIMIT 1")
        ).first()
        return row is not None
    except Exception:
        return False
