"""add predicate registry for schema governance

Revision ID: 20260226_0003
Revises: 20260226_0002
Create Date: 2026-02-26 00:00:03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260226_0003"
down_revision: str | None = "20260226_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "predicate_registry_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("predicate", sa.String(length=255), nullable=False),
        sa.Column("aliases_json", sa.JSON(), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "predicate", name="uq_predicate_registry_kind_predicate"),
    )
    op.create_index(
        "ix_predicate_registry_entries_kind",
        "predicate_registry_entries",
        ["kind"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_predicate_registry_entries_kind", table_name="predicate_registry_entries")
    op.drop_table("predicate_registry_entries")
