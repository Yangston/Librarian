"""compatibility defaults for legacy pod_id columns

Revision ID: 20260303_0012
Revises: 20260303_0011
Create Date: 2026-03-03 15:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260303_0012"
down_revision: str | None = "20260303_0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_LEGACY_POD_DEFAULT_TABLES = [
    "messages",
    "extractor_runs",
    "predicate_registry_entries",
    "schema_nodes",
    "schema_fields",
    "schema_relations",
    "schema_proposals",
]


def _table_exists(table_name: str) -> bool:
    return bool(sa.inspect(op.get_bind()).has_table(table_name))


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column.get("name") == column_name for column in columns)


def _get_or_create_default_pod_id() -> int | None:
    conn = op.get_bind()
    if not _table_exists("pods"):
        return None

    default_id = conn.execute(sa.text("SELECT id FROM pods WHERE is_default = true ORDER BY id ASC LIMIT 1")).scalar()
    if default_id is not None:
        return int(default_id)

    legacy_row = conn.execute(sa.text("SELECT id FROM pods WHERE slug = 'legacy' ORDER BY id ASC LIMIT 1")).scalar()
    if legacy_row is not None:
        legacy_id = int(legacy_row)
        conn.execute(sa.text("UPDATE pods SET is_default = true WHERE id = :pod_id"), {"pod_id": legacy_id})
        return legacy_id

    conn.execute(
        sa.text(
            """
            INSERT INTO pods (slug, name, description, is_default)
            VALUES ('legacy', 'Legacy', 'Default pod for existing knowledge', true)
            """
        )
    )
    inserted = conn.execute(sa.text("SELECT id FROM pods WHERE slug = 'legacy' ORDER BY id ASC LIMIT 1")).scalar()
    if inserted is None:
        return None
    return int(inserted)


def _set_pod_default(table_name: str, pod_id: int) -> None:
    conn = op.get_bind()
    if not _column_exists(table_name, "pod_id"):
        return
    conn.execute(sa.text(f'UPDATE "{table_name}" SET pod_id = :pod_id WHERE pod_id IS NULL'), {"pod_id": pod_id})
    conn.execute(sa.text(f'ALTER TABLE "{table_name}" ALTER COLUMN pod_id SET DEFAULT {int(pod_id)}'))


def _drop_pod_default(table_name: str) -> None:
    conn = op.get_bind()
    if not _column_exists(table_name, "pod_id"):
        return
    conn.execute(sa.text(f'ALTER TABLE "{table_name}" ALTER COLUMN pod_id DROP DEFAULT'))


def upgrade() -> None:
    """Set safe defaults for required pod_id columns in legacy tables."""

    default_pod_id = _get_or_create_default_pod_id()
    if default_pod_id is None:
        return

    for table_name in _LEGACY_POD_DEFAULT_TABLES:
        _set_pod_default(table_name, default_pod_id)


def downgrade() -> None:
    """Remove server defaults introduced for pod_id compatibility."""

    for table_name in _LEGACY_POD_DEFAULT_TABLES:
        _drop_pod_default(table_name)
