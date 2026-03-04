"""pod conversation assignment and auto-theme flags

Revision ID: 20260303_0013
Revises: 20260303_0012
Create Date: 2026-03-03 19:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260303_0013"
down_revision: str | None = "20260303_0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SEED_TEMPLATE_SLUGS = (
    "home",
    "stocks",
    "macro",
    "earnings-guidance",
    "news",
    "supply-chain",
    "valuation-models",
    "research-tasks",
)


def _table_exists(table_name: str) -> bool:
    return bool(sa.inspect(op.get_bind()).has_table(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index.get("name") == index_name for index in indexes)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column.get("name") == column_name for column in columns)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _column_exists(table_name, column.name):
        return
    op.add_column(table_name, column)


def upgrade() -> None:
    if not _table_exists("conversations"):
        op.create_table(
            "conversations",
            sa.Column("conversation_id", sa.String(length=255), nullable=False),
            sa.Column("pod_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(["pod_id"], ["pods.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("conversation_id"),
        )
    if not _index_exists("conversations", "ix_conversations_pod_id"):
        op.create_index("ix_conversations_pod_id", "conversations", ["pod_id"], unique=False)

    _add_column_if_missing(
        "collections",
        sa.Column(
            "is_auto_generated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    if not _index_exists("collections", "ix_collections_is_auto_generated"):
        op.create_index(
            "ix_collections_is_auto_generated",
            "collections",
            ["is_auto_generated"],
            unique=False,
        )

    conn = op.get_bind()
    imported_pod_id = conn.execute(
        sa.text("SELECT id FROM pods WHERE slug = 'imported' ORDER BY id ASC LIMIT 1")
    ).scalar()
    if imported_pod_id is None:
        conn.execute(
            sa.text(
                """
                INSERT INTO pods (slug, name, description, is_default)
                VALUES ('imported', 'Imported', 'Backfilled and internal conversations.', true)
                """
            )
        )
        imported_pod_id = conn.execute(
            sa.text("SELECT id FROM pods WHERE slug = 'imported' ORDER BY id ASC LIMIT 1")
        ).scalar()

    if imported_pod_id is not None and _table_exists("messages"):
        conversations = sa.Table("conversations", sa.MetaData(), autoload_with=conn)
        conversation_ids = conn.execute(
            sa.text("SELECT DISTINCT conversation_id FROM messages WHERE conversation_id IS NOT NULL")
        ).scalars()
        for conversation_id in conversation_ids:
            clean_id = str(conversation_id or "").strip()
            if not clean_id:
                continue
            exists = conn.execute(
                sa.select(conversations.c.conversation_id).where(
                    conversations.c.conversation_id == clean_id
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue
            conn.execute(
                sa.insert(conversations).values(
                    conversation_id=clean_id,
                    pod_id=int(imported_pod_id),
                )
            )

    if _table_exists("collections"):
        metadata = sa.MetaData()
        collections = sa.Table("collections", metadata, autoload_with=conn)
        stale_collection_ids = [
            int(value)
            for value in conn.execute(
                sa.select(collections.c.id).where(collections.c.slug.in_(list(_SEED_TEMPLATE_SLUGS)))
            ).scalars()
        ]
        if stale_collection_ids:
            if _table_exists("collection_items"):
                collection_items = sa.Table("collection_items", metadata, autoload_with=conn)
                conn.execute(
                    sa.delete(collection_items).where(
                        collection_items.c.collection_id.in_(stale_collection_ids)
                    )
                )
            if _table_exists("workspace_edges"):
                workspace_edges = sa.Table("workspace_edges", metadata, autoload_with=conn)
                conn.execute(
                    sa.delete(workspace_edges).where(
                        sa.or_(
                            sa.and_(
                                workspace_edges.c.src_kind == "collection",
                                workspace_edges.c.src_id.in_(stale_collection_ids),
                            ),
                            sa.and_(
                                workspace_edges.c.dst_kind == "collection",
                                workspace_edges.c.dst_id.in_(stale_collection_ids),
                            ),
                        )
                    )
                )
            conn.execute(
                sa.delete(collections).where(collections.c.id.in_(stale_collection_ids))
            )


def downgrade() -> None:
    if _index_exists("collections", "ix_collections_is_auto_generated"):
        op.drop_index("ix_collections_is_auto_generated", table_name="collections")
    if _column_exists("collections", "is_auto_generated"):
        op.drop_column("collections", "is_auto_generated")

    if _index_exists("conversations", "ix_conversations_pod_id"):
        op.drop_index("ix_conversations_pod_id", table_name="conversations")
    if _table_exists("conversations"):
        op.drop_table("conversations")
