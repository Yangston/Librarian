"""workspace v3 stable schema

Revision ID: 20260306_0015
Revises: 20260305_0014
Create Date: 2026-03-06 09:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260306_0015"
down_revision: str | None = "20260305_0014"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    return bool(sa.inspect(op.get_bind()).has_table(table_name))


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column.get("name") == column_name for column in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index.get("name") == index_name for index in indexes)


def _foreign_key_exists(
    table_name: str,
    constraint_name: str,
    *,
    local_columns: Sequence[str] | None = None,
    referred_table: str | None = None,
    remote_columns: Sequence[str] | None = None,
) -> bool:
    if not _table_exists(table_name):
        return False
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys(table_name)
    for foreign_key in foreign_keys:
        if foreign_key.get("name") == constraint_name:
            return True
        if local_columns is not None and tuple(foreign_key.get("constrained_columns") or ()) != tuple(local_columns):
            continue
        if referred_table is not None and foreign_key.get("referred_table") != referred_table:
            continue
        if remote_columns is not None and tuple(foreign_key.get("referred_columns") or ()) != tuple(remote_columns):
            continue
        return True
    return False


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if _column_exists(table_name, column.name):
        return
    op.add_column(table_name, column)


def _create_index_safe(name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if not all(_column_exists(table_name, column_name) for column_name in columns):
        return
    if _index_exists(table_name, name):
        return
    op.create_index(name, table_name, columns, unique=unique)


def _create_foreign_key_safe(
    name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str | None = None,
) -> None:
    if not all(_column_exists(source_table, column_name) for column_name in local_cols):
        return
    if _foreign_key_exists(
        source_table,
        name,
        local_columns=local_cols,
        referred_table=referent_table,
        remote_columns=remote_cols,
    ):
        return
    op.create_foreign_key(name, source_table, referent_table, local_cols, remote_cols, ondelete=ondelete)


def upgrade() -> None:
    _add_column_if_missing("entities", sa.Column("pod_id", sa.Integer(), nullable=True))
    _create_foreign_key_safe("fk_entities_pod_id", "entities", "pods", ["pod_id"], ["id"], ondelete="SET NULL")
    _create_index_safe("ix_entities_pod_id", "entities", ["pod_id"], unique=False)

    _add_column_if_missing("facts", sa.Column("pod_id", sa.Integer(), nullable=True))
    _create_foreign_key_safe("fk_facts_pod_id", "facts", "pods", ["pod_id"], ["id"], ondelete="SET NULL")
    _create_index_safe("ix_facts_pod_id", "facts", ["pod_id"], unique=False)

    _add_column_if_missing("relations", sa.Column("pod_id", sa.Integer(), nullable=True))
    _create_foreign_key_safe("fk_relations_pod_id", "relations", "pods", ["pod_id"], ["id"], ondelete="SET NULL")
    _create_index_safe("ix_relations_pod_id", "relations", ["pod_id"], unique=False)

    _add_column_if_missing("extractor_runs", sa.Column("pod_id", sa.Integer(), nullable=True))
    _add_column_if_missing(
        "extractor_runs",
        sa.Column("run_kind", sa.String(length=32), server_default="conversation_extract", nullable=False),
    )
    _create_foreign_key_safe(
        "fk_extractor_runs_pod_id",
        "extractor_runs",
        "pods",
        ["pod_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_index_safe("ix_extractor_runs_pod_id", "extractor_runs", ["pod_id"], unique=False)
    _create_index_safe("ix_extractor_runs_run_kind", "extractor_runs", ["run_kind"], unique=False)

    _add_column_if_missing("collection_items", sa.Column("primary_entity_id", sa.Integer(), nullable=True))
    _add_column_if_missing("collection_items", sa.Column("title", sa.String(length=255), nullable=True))
    _add_column_if_missing("collection_items", sa.Column("summary", sa.Text(), nullable=True))
    _add_column_if_missing("collection_items", sa.Column("detail_blurb", sa.Text(), nullable=True))
    _add_column_if_missing("collection_items", sa.Column("notes_markdown", sa.Text(), nullable=True))
    _add_column_if_missing("collection_items", sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False))
    _add_column_if_missing(
        "collection_items",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    _create_foreign_key_safe(
        "fk_collection_items_primary_entity_id",
        "collection_items",
        "entities",
        ["primary_entity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_index_safe("ix_collection_items_primary_entity_id", "collection_items", ["primary_entity_id"], unique=False)

    op.create_table(
        "collection_columns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_relation", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("relation_target_collection_id", sa.Integer(), nullable=True),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("planner_locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("user_locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("enrichment_policy_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relation_target_collection_id"], ["collections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id", "key", name="uq_collection_columns_collection_key"),
    )
    op.create_index("ix_collection_columns_collection_id", "collection_columns", ["collection_id"], unique=False)
    op.create_index("ix_collection_columns_kind", "collection_columns", ["kind"], unique=False)
    op.create_index("ix_collection_columns_relation_target_collection_id", "collection_columns", ["relation_target_collection_id"], unique=False)

    op.create_table(
        "collection_item_values",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("collection_item_id", sa.Integer(), nullable=False),
        sa.Column("collection_column_id", sa.Integer(), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("display_value", sa.String(length=2048), nullable=True),
        sa.Column("value_type", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edited_by_user", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["collection_column_id"], ["collection_columns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_item_id"], ["collection_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_item_id", "collection_column_id", name="uq_collection_item_values_row_column"),
    )
    op.create_index("ix_collection_item_values_collection_item_id", "collection_item_values", ["collection_item_id"], unique=False)
    op.create_index("ix_collection_item_values_collection_column_id", "collection_item_values", ["collection_column_id"], unique=False)
    op.create_index("ix_collection_item_values_source_kind", "collection_item_values", ["source_kind"], unique=False)
    op.create_index("ix_collection_item_values_status", "collection_item_values", ["status"], unique=False)

    op.create_table(
        "collection_item_relations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_collection_item_id", sa.Integer(), nullable=False),
        sa.Column("to_collection_item_id", sa.Integer(), nullable=False),
        sa.Column("relation_label", sa.String(length=255), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["from_collection_item_id"], ["collection_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_collection_item_id"], ["collection_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_collection_item_id", "to_collection_item_id", "relation_label", name="uq_collection_item_relations_tuple"),
    )
    op.create_index("ix_collection_item_relations_from_collection_item_id", "collection_item_relations", ["from_collection_item_id"], unique=False)
    op.create_index("ix_collection_item_relations_to_collection_item_id", "collection_item_relations", ["to_collection_item_id"], unique=False)
    op.create_index("ix_collection_item_relations_relation_label", "collection_item_relations", ["relation_label"], unique=False)
    op.create_index("ix_collection_item_relations_source_kind", "collection_item_relations", ["source_kind"], unique=False)
    op.create_index("ix_collection_item_relations_status", "collection_item_relations", ["status"], unique=False)

    _add_column_if_missing("evidence", sa.Column("collection_item_value_id", sa.Integer(), nullable=True))
    _add_column_if_missing("evidence", sa.Column("collection_item_relation_id", sa.Integer(), nullable=True))
    op.drop_constraint("ck_evidence_has_claim", "evidence", type_="check")
    _create_foreign_key_safe(
        "fk_evidence_collection_item_value_id",
        "evidence",
        "collection_item_values",
        ["collection_item_value_id"],
        ["id"],
        ondelete="CASCADE",
    )
    _create_foreign_key_safe(
        "fk_evidence_collection_item_relation_id",
        "evidence",
        "collection_item_relations",
        ["collection_item_relation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_evidence_has_claim",
        "evidence",
        "fact_id IS NOT NULL OR relation_id IS NOT NULL OR collection_item_value_id IS NOT NULL OR collection_item_relation_id IS NOT NULL",
    )
    _create_index_safe("ix_evidence_collection_item_value_id", "evidence", ["collection_item_value_id"], unique=False)
    _create_index_safe("ix_evidence_collection_item_relation_id", "evidence", ["collection_item_relation_id"], unique=False)

    op.execute(
        """
        UPDATE entities
        SET pod_id = conversations.pod_id
        FROM conversations
        WHERE conversations.conversation_id = entities.conversation_id
          AND entities.pod_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE facts
        SET pod_id = conversations.pod_id
        FROM conversations
        WHERE conversations.conversation_id = facts.conversation_id
          AND facts.pod_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE relations
        SET pod_id = conversations.pod_id
        FROM conversations
        WHERE conversations.conversation_id = relations.conversation_id
          AND relations.pod_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE extractor_runs
        SET pod_id = conversations.pod_id
        FROM conversations
        WHERE conversations.conversation_id = extractor_runs.conversation_id
          AND extractor_runs.pod_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_collection_item_relation_id", table_name="evidence")
    op.drop_index("ix_evidence_collection_item_value_id", table_name="evidence")
    op.drop_constraint("ck_evidence_has_claim", "evidence", type_="check")
    op.drop_constraint("fk_evidence_collection_item_relation_id", "evidence", type_="foreignkey")
    op.drop_constraint("fk_evidence_collection_item_value_id", "evidence", type_="foreignkey")
    op.drop_column("evidence", "collection_item_relation_id")
    op.drop_column("evidence", "collection_item_value_id")
    op.create_check_constraint(
        "ck_evidence_has_claim",
        "evidence",
        "fact_id IS NOT NULL OR relation_id IS NOT NULL",
    )

    op.drop_index("ix_collection_item_relations_status", table_name="collection_item_relations")
    op.drop_index("ix_collection_item_relations_source_kind", table_name="collection_item_relations")
    op.drop_index("ix_collection_item_relations_relation_label", table_name="collection_item_relations")
    op.drop_index("ix_collection_item_relations_to_collection_item_id", table_name="collection_item_relations")
    op.drop_index("ix_collection_item_relations_from_collection_item_id", table_name="collection_item_relations")
    op.drop_table("collection_item_relations")

    op.drop_index("ix_collection_item_values_status", table_name="collection_item_values")
    op.drop_index("ix_collection_item_values_source_kind", table_name="collection_item_values")
    op.drop_index("ix_collection_item_values_collection_column_id", table_name="collection_item_values")
    op.drop_index("ix_collection_item_values_collection_item_id", table_name="collection_item_values")
    op.drop_table("collection_item_values")

    op.drop_index("ix_collection_columns_relation_target_collection_id", table_name="collection_columns")
    op.drop_index("ix_collection_columns_kind", table_name="collection_columns")
    op.drop_index("ix_collection_columns_collection_id", table_name="collection_columns")
    op.drop_table("collection_columns")

    op.drop_index("ix_collection_items_primary_entity_id", table_name="collection_items")
    op.drop_constraint("fk_collection_items_primary_entity_id", "collection_items", type_="foreignkey")
    op.drop_column("collection_items", "updated_at")
    op.drop_column("collection_items", "sort_order")
    op.drop_column("collection_items", "notes_markdown")
    op.drop_column("collection_items", "detail_blurb")
    op.drop_column("collection_items", "summary")
    op.drop_column("collection_items", "title")
    op.drop_column("collection_items", "primary_entity_id")

    op.drop_index("ix_extractor_runs_run_kind", table_name="extractor_runs")
    op.drop_index("ix_extractor_runs_pod_id", table_name="extractor_runs")
    op.drop_constraint("fk_extractor_runs_pod_id", "extractor_runs", type_="foreignkey")
    op.drop_column("extractor_runs", "run_kind")
    op.drop_column("extractor_runs", "pod_id")

    op.drop_index("ix_relations_pod_id", table_name="relations")
    op.drop_constraint("fk_relations_pod_id", "relations", type_="foreignkey")
    op.drop_column("relations", "pod_id")

    op.drop_index("ix_facts_pod_id", table_name="facts")
    op.drop_constraint("fk_facts_pod_id", "facts", type_="foreignkey")
    op.drop_column("facts", "pod_id")

    op.drop_index("ix_entities_pod_id", table_name="entities")
    op.drop_constraint("fk_entities_pod_id", "entities", type_="foreignkey")
    op.drop_column("entities", "pod_id")
