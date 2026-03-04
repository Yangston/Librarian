"""phase 3.8 organization layer and evidence provenance

Revision ID: 20260303_0011
Revises: 20260228_0010
Create Date: 2026-03-03 00:11:00
"""

from __future__ import annotations

from collections.abc import Sequence
import re

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260303_0011"
down_revision: str | None = "20260228_0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SNIPPET_MAX_LEN = 280


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


def _create_table_safe(name: str, *columns, **kwargs) -> None:
    if _table_exists(name):
        return
    op.create_table(name, *columns, **kwargs)


def _create_index_safe(name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if not all(_column_exists(table_name, column_name) for column_name in columns):
        return
    if _index_exists(table_name, name):
        return
    op.create_index(name, table_name, columns, unique=unique)


def _stock_table_schema() -> dict[str, object]:
    return {
        "columns": [
            {"name": "name", "type": "title"},
            {"name": "ticker", "type": "text"},
            {"name": "exchange", "type": "select", "options": ["NASDAQ", "NYSE", "TSX", "Other"]},
            {
                "name": "sector",
                "type": "select",
                "options": ["Semis", "Cloud", "Software", "Hardware", "Services", "Other"],
            },
            {"name": "market_cap_usd", "type": "number"},
            {"name": "thesis", "type": "rich_text"},
            {"name": "status", "type": "select", "options": ["Watch", "Researching", "Owned", "Avoid"]},
            {"name": "conviction", "type": "select", "options": ["Low", "Medium", "High"]},
            {"name": "tags", "type": "multi_select"},
            {"name": "last_updated", "type": "datetime"},
        ]
    }


def _macro_table_schema() -> dict[str, object]:
    return {
        "columns": [
            {"name": "event", "type": "title"},
            {
                "name": "category",
                "type": "select",
                "options": ["Rates", "Inflation", "Liquidity", "Trade", "FX", "Geopolitics"],
            },
            {"name": "date", "type": "date"},
            {"name": "summary", "type": "rich_text"},
            {"name": "impacted_entities", "type": "relation_multi", "target": "Entity"},
            {"name": "status", "type": "select", "options": ["Monitor", "Active", "Resolved"]},
            {"name": "sources", "type": "relation_multi", "target": "Source"},
        ]
    }


def _earnings_table_schema() -> dict[str, object]:
    return {
        "columns": [
            {"name": "company", "type": "relation", "target": "Company"},
            {"name": "quarter", "type": "select", "options": ["Q1", "Q2", "Q3", "Q4"]},
            {"name": "fiscal_year", "type": "number"},
            {"name": "report_date", "type": "date"},
            {"name": "beat_miss", "type": "select", "options": ["Beat", "Meet", "Miss", "Mixed"]},
            {
                "name": "guidance_change",
                "type": "select",
                "options": ["Raised", "Maintained", "Lowered", "N/A"],
            },
            {"name": "key_highlights", "type": "rich_text"},
            {"name": "transcript", "type": "relation", "target": "Source"},
        ]
    }


def _news_table_schema() -> dict[str, object]:
    return {
        "columns": [
            {"name": "headline", "type": "title"},
            {"name": "datetime", "type": "datetime"},
            {"name": "related_entities", "type": "relation_multi", "target": "Entity"},
            {
                "name": "topic",
                "type": "select",
                "options": ["Earnings", "Product", "Regulation", "Supply Chain", "M&A", "Security"],
            },
            {"name": "sentiment", "type": "select", "options": ["Positive", "Neutral", "Negative", "Mixed"]},
            {"name": "source", "type": "relation", "target": "Source"},
            {"name": "summary", "type": "rich_text"},
        ]
    }


def _supply_chain_table_schema() -> dict[str, object]:
    return {
        "columns": [
            {"name": "from_entity", "type": "relation", "target": "Entity"},
            {
                "name": "relationship",
                "type": "select",
                "options": ["SUPPLIER_OF", "CUSTOMER_OF", "DEPENDS_ON", "PARTNER_OF"],
            },
            {"name": "to_entity", "type": "relation", "target": "Entity"},
            {"name": "criticality", "type": "select", "options": ["Low", "Medium", "High"]},
            {"name": "notes", "type": "rich_text"},
            {"name": "evidence", "type": "relation_multi", "target": "Evidence"},
        ]
    }


def _valuation_table_schema() -> dict[str, object]:
    return {
        "columns": [
            {"name": "company", "type": "relation", "target": "Company"},
            {"name": "method", "type": "select", "options": ["DCF", "Comps", "SOTP", "PEG", "Rule-of-40"]},
            {"name": "base_case_fmv", "type": "currency", "currency": "USD"},
            {"name": "bull_case_fmv", "type": "currency", "currency": "USD"},
            {"name": "bear_case_fmv", "type": "currency", "currency": "USD"},
            {"name": "key_assumptions", "type": "rich_text"},
            {"name": "model_link", "type": "url"},
            {"name": "last_reviewed", "type": "date"},
        ]
    }


def _research_tasks_table_schema() -> dict[str, object]:
    return {
        "columns": [
            {"name": "task", "type": "title"},
            {"name": "due", "type": "date"},
            {"name": "priority", "type": "select", "options": ["Low", "Medium", "High"]},
            {"name": "related_entities", "type": "relation_multi", "target": "Entity"},
            {"name": "status", "type": "select", "options": ["Not started", "In progress", "Done"]},
        ]
    }


def _normalize_type_label(label: str | None) -> str:
    if not label:
        return ""
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def _target_collection_slug(type_label: str | None) -> str:
    normalized = _normalize_type_label(type_label)
    if normalized in {"company", "issuer", "stock"}:
        return "stocks"
    if normalized in {"macroevent", "macro"}:
        return "macro"
    if normalized in {"earningsreport", "earnings"}:
        return "earnings-guidance"
    if normalized in {"newsitem", "news"}:
        return "news"
    if normalized in {"supplychainlink", "supplychain"}:
        return "supply-chain"
    if normalized in {"valuation", "valuationmodel", "model"}:
        return "valuation-models"
    return "research-tasks"


def _truncate_snippet(content: str | None) -> str | None:
    if not content:
        return None
    trimmed = " ".join(content.strip().split())
    if len(trimmed) <= SNIPPET_MAX_LEN:
        return trimmed
    return f"{trimmed[: SNIPPET_MAX_LEN - 3]}..."


def upgrade() -> None:
    _create_table_safe(
        "pods",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_pods_slug"),
    )
    _add_column_if_missing("pods", sa.Column("slug", sa.String(length=128), nullable=False))
    _add_column_if_missing("pods", sa.Column("name", sa.String(length=255), nullable=False))
    _add_column_if_missing("pods", sa.Column("description", sa.Text(), nullable=True))
    _add_column_if_missing("pods", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing(
        "pods",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _add_column_if_missing(
        "pods",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _create_index_safe("ix_pods_slug", "pods", ["slug"], unique=False)
    _create_index_safe("ix_pods_is_default", "pods", ["is_default"], unique=False)

    _create_table_safe(
        "collections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pod_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("view_config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["parent_id"], ["collections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pod_id"], ["pods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pod_id", "slug", name="uq_collections_pod_slug"),
    )
    _add_column_if_missing("collections", sa.Column("pod_id", sa.Integer(), nullable=False))
    _add_column_if_missing("collections", sa.Column("parent_id", sa.Integer(), nullable=True))
    _add_column_if_missing("collections", sa.Column("kind", sa.String(length=16), nullable=False))
    _add_column_if_missing("collections", sa.Column("slug", sa.String(length=128), nullable=False))
    _add_column_if_missing("collections", sa.Column("name", sa.String(length=255), nullable=False))
    _add_column_if_missing("collections", sa.Column("description", sa.Text(), nullable=True))
    _add_column_if_missing(
        "collections",
        sa.Column("schema_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    _add_column_if_missing(
        "collections",
        sa.Column("view_config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    _add_column_if_missing(
        "collections",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    _add_column_if_missing(
        "collections",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _add_column_if_missing(
        "collections",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _create_index_safe("ix_collections_pod_id", "collections", ["pod_id"], unique=False)
    _create_index_safe("ix_collections_parent_id", "collections", ["parent_id"], unique=False)

    _create_table_safe(
        "collection_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("sort_key", sa.String(length=255), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id", "entity_id", name="uq_collection_items_collection_entity"),
    )
    _add_column_if_missing("collection_items", sa.Column("collection_id", sa.Integer(), nullable=False))
    _add_column_if_missing("collection_items", sa.Column("entity_id", sa.Integer(), nullable=False))
    _add_column_if_missing("collection_items", sa.Column("sort_key", sa.String(length=255), nullable=True))
    _add_column_if_missing(
        "collection_items",
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _create_index_safe("ix_collection_items_collection_id", "collection_items", ["collection_id"], unique=False)
    _create_index_safe("ix_collection_items_entity_id", "collection_items", ["entity_id"], unique=False)

    _create_table_safe(
        "workspace_edges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("src_kind", sa.String(length=16), nullable=False),
        sa.Column("src_id", sa.Integer(), nullable=False),
        sa.Column("dst_kind", sa.String(length=16), nullable=False),
        sa.Column("dst_id", sa.Integer(), nullable=False),
        sa.Column("edge_type", sa.String(length=32), nullable=False, server_default="CONTAINS"),
        sa.Column("namespace", sa.String(length=32), nullable=False, server_default="workspace"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "src_kind",
            "src_id",
            "dst_kind",
            "dst_id",
            "edge_type",
            "namespace",
            name="uq_workspace_edges_tuple",
        ),
    )
    _add_column_if_missing("workspace_edges", sa.Column("src_kind", sa.String(length=16), nullable=False))
    _add_column_if_missing("workspace_edges", sa.Column("src_id", sa.Integer(), nullable=False))
    _add_column_if_missing("workspace_edges", sa.Column("dst_kind", sa.String(length=16), nullable=False))
    _add_column_if_missing("workspace_edges", sa.Column("dst_id", sa.Integer(), nullable=False))
    _add_column_if_missing(
        "workspace_edges",
        sa.Column("edge_type", sa.String(length=32), nullable=False, server_default="CONTAINS"),
    )
    _add_column_if_missing(
        "workspace_edges",
        sa.Column("namespace", sa.String(length=32), nullable=False, server_default="workspace"),
    )
    _add_column_if_missing(
        "workspace_edges",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _create_index_safe("ix_workspace_edges_src_kind", "workspace_edges", ["src_kind"], unique=False)
    _create_index_safe("ix_workspace_edges_src_id", "workspace_edges", ["src_id"], unique=False)
    _create_index_safe("ix_workspace_edges_dst_kind", "workspace_edges", ["dst_kind"], unique=False)
    _create_index_safe("ix_workspace_edges_dst_id", "workspace_edges", ["dst_id"], unique=False)
    _create_index_safe("ix_workspace_edges_namespace", "workspace_edges", ["namespace"], unique=False)

    _create_table_safe(
        "sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=True),
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="message"),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("uri", sa.String(length=2048), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_sources_message_id"),
    )
    _add_column_if_missing("sources", sa.Column("conversation_id", sa.String(length=255), nullable=True))
    _add_column_if_missing(
        "sources",
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="message"),
    )
    _add_column_if_missing("sources", sa.Column("message_id", sa.Integer(), nullable=True))
    _add_column_if_missing("sources", sa.Column("title", sa.String(length=255), nullable=True))
    _add_column_if_missing("sources", sa.Column("uri", sa.String(length=2048), nullable=True))
    _add_column_if_missing(
        "sources",
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    _add_column_if_missing(
        "sources",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _create_index_safe("ix_sources_message_id", "sources", ["message_id"], unique=False)
    _create_index_safe("ix_sources_conversation_id", "sources", ["conversation_id"], unique=False)
    _create_index_safe("ix_sources_source_kind", "sources", ["source_kind"], unique=False)

    _create_table_safe(
        "evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("fact_id", sa.Integer(), nullable=True),
        sa.Column("relation_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("fact_id IS NOT NULL OR relation_id IS NOT NULL", name="ck_evidence_has_claim"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fact_id"], ["facts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relation_id"], ["relations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    _add_column_if_missing("evidence", sa.Column("source_id", sa.Integer(), nullable=False))
    _add_column_if_missing("evidence", sa.Column("fact_id", sa.Integer(), nullable=True))
    _add_column_if_missing("evidence", sa.Column("relation_id", sa.Integer(), nullable=True))
    _add_column_if_missing("evidence", sa.Column("message_id", sa.Integer(), nullable=True))
    _add_column_if_missing("evidence", sa.Column("snippet", sa.Text(), nullable=True))
    _add_column_if_missing("evidence", sa.Column("confidence", sa.Float(), nullable=True))
    _add_column_if_missing(
        "evidence",
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    _add_column_if_missing(
        "evidence",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    _create_index_safe("ix_evidence_source_id", "evidence", ["source_id"], unique=False)
    _create_index_safe("ix_evidence_fact_id", "evidence", ["fact_id"], unique=False)
    _create_index_safe("ix_evidence_relation_id", "evidence", ["relation_id"], unique=False)
    _create_index_safe("ix_evidence_message_id", "evidence", ["message_id"], unique=False)

    conn = op.get_bind()
    metadata = sa.MetaData()
    pods = sa.Table("pods", metadata, autoload_with=conn)
    collections = sa.Table("collections", metadata, autoload_with=conn)
    collection_items = sa.Table("collection_items", metadata, autoload_with=conn)
    workspace_edges = sa.Table("workspace_edges", metadata, autoload_with=conn)
    messages = sa.Table("messages", metadata, autoload_with=conn)
    entities = sa.Table("entities", metadata, autoload_with=conn)
    facts = sa.Table("facts", metadata, autoload_with=conn)
    relations = sa.Table("relations", metadata, autoload_with=conn)
    sources = sa.Table("sources", metadata, autoload_with=conn)
    evidence = sa.Table("evidence", metadata, autoload_with=conn)

    legacy_id = conn.execute(sa.select(pods.c.id).where(pods.c.slug == "legacy")).scalar_one_or_none()
    if legacy_id is None:
        conn.execute(
            sa.insert(pods).values(
                slug="legacy",
                name="Legacy",
                description="Default pod for existing knowledge",
                is_default=True,
            )
        )
        legacy_id = conn.execute(sa.select(pods.c.id).where(pods.c.slug == "legacy")).scalar_one()

    collection_specs = [
        {
            "slug": "home",
            "kind": "PAGE",
            "name": "AI Tech Stock Research - Home",
            "description": "Root home page for the default workspace pod.",
            "schema_json": {},
            "parent_slug": None,
            "sort_order": 0,
        },
        {
            "slug": "stocks",
            "kind": "TABLE",
            "name": "Stocks",
            "description": "Company entities tracked in this pod.",
            "schema_json": _stock_table_schema(),
            "parent_slug": "home",
            "sort_order": 10,
        },
        {
            "slug": "macro",
            "kind": "TABLE",
            "name": "Macro",
            "description": "Macro events and impacts.",
            "schema_json": _macro_table_schema(),
            "parent_slug": "home",
            "sort_order": 20,
        },
        {
            "slug": "earnings-guidance",
            "kind": "TABLE",
            "name": "Earnings & Guidance",
            "description": "Earnings reports and guidance updates.",
            "schema_json": _earnings_table_schema(),
            "parent_slug": "home",
            "sort_order": 30,
        },
        {
            "slug": "news",
            "kind": "TABLE",
            "name": "News",
            "description": "News items and linked entities.",
            "schema_json": _news_table_schema(),
            "parent_slug": "home",
            "sort_order": 40,
        },
        {
            "slug": "supply-chain",
            "kind": "TABLE",
            "name": "Supply Chain",
            "description": "Supply chain relationships and evidence.",
            "schema_json": _supply_chain_table_schema(),
            "parent_slug": "home",
            "sort_order": 50,
        },
        {
            "slug": "valuation-models",
            "kind": "TABLE",
            "name": "Valuation & Models",
            "description": "Valuation methods and assumptions.",
            "schema_json": _valuation_table_schema(),
            "parent_slug": "home",
            "sort_order": 60,
        },
        {
            "slug": "research-tasks",
            "kind": "TABLE",
            "name": "Research Tasks",
            "description": "General tasks and uncategorized entities.",
            "schema_json": _research_tasks_table_schema(),
            "parent_slug": "home",
            "sort_order": 70,
        },
    ]

    collection_id_by_slug: dict[str, int] = {}
    for spec in collection_specs:
        existing_id = conn.execute(
            sa.select(collections.c.id).where(
                collections.c.pod_id == legacy_id,
                collections.c.slug == spec["slug"],
            )
        ).scalar_one_or_none()
        if existing_id is not None:
            collection_id_by_slug[spec["slug"]] = int(existing_id)
            continue
        parent_id = None
        if spec["parent_slug"] is not None:
            parent_id = collection_id_by_slug[spec["parent_slug"]]
        conn.execute(
            sa.insert(collections).values(
                pod_id=legacy_id,
                parent_id=parent_id,
                kind=spec["kind"],
                slug=spec["slug"],
                name=spec["name"],
                description=spec["description"],
                schema_json=spec["schema_json"],
                view_config_json={},
                sort_order=spec["sort_order"],
            )
        )
        created_id = conn.execute(
            sa.select(collections.c.id).where(
                collections.c.pod_id == legacy_id,
                collections.c.slug == spec["slug"],
            )
        ).scalar_one()
        collection_id_by_slug[spec["slug"]] = int(created_id)

    existing_memberships = {
        (int(row.collection_id), int(row.entity_id))
        for row in conn.execute(
            sa.select(collection_items.c.collection_id, collection_items.c.entity_id)
        ).all()
    }
    active_entities = conn.execute(
        sa.select(entities.c.id, entities.c.type_label).where(entities.c.merged_into_id.is_(None))
    ).all()
    for row in active_entities:
        target_slug = _target_collection_slug(row.type_label)
        collection_id = collection_id_by_slug[target_slug]
        key = (collection_id, int(row.id))
        if key in existing_memberships:
            continue
        conn.execute(
            sa.insert(collection_items).values(
                collection_id=collection_id,
                entity_id=int(row.id),
                sort_key=None,
            )
        )
        existing_memberships.add(key)

    existing_edges = {
        (
            row.src_kind,
            int(row.src_id),
            row.dst_kind,
            int(row.dst_id),
            row.edge_type,
            row.namespace,
        )
        for row in conn.execute(
            sa.select(
                workspace_edges.c.src_kind,
                workspace_edges.c.src_id,
                workspace_edges.c.dst_kind,
                workspace_edges.c.dst_id,
                workspace_edges.c.edge_type,
                workspace_edges.c.namespace,
            )
        ).all()
    }

    def _insert_edge(src_kind: str, src_id: int, dst_kind: str, dst_id: int) -> None:
        key = (src_kind, src_id, dst_kind, dst_id, "CONTAINS", "workspace")
        if key in existing_edges:
            return
        conn.execute(
            sa.insert(workspace_edges).values(
                src_kind=src_kind,
                src_id=src_id,
                dst_kind=dst_kind,
                dst_id=dst_id,
                edge_type="CONTAINS",
                namespace="workspace",
            )
        )
        existing_edges.add(key)

    home_id = collection_id_by_slug["home"]
    _insert_edge("pod", int(legacy_id), "collection", int(home_id))
    for slug, collection_id in collection_id_by_slug.items():
        if slug == "home":
            continue
        _insert_edge("collection", int(home_id), "collection", int(collection_id))

    memberships = conn.execute(
        sa.select(collection_items.c.collection_id, collection_items.c.entity_id)
    ).all()
    for row in memberships:
        _insert_edge("collection", int(row.collection_id), "entity", int(row.entity_id))

    existing_source_message_ids = {
        int(message_id)
        for message_id in conn.execute(
            sa.select(sources.c.message_id).where(sources.c.message_id.is_not(None))
        ).scalars()
    }
    message_rows = conn.execute(
        sa.select(messages.c.id, messages.c.conversation_id, messages.c.role, messages.c.timestamp, messages.c.content)
    ).all()
    content_by_message_id = {int(row.id): row.content for row in message_rows}
    for row in message_rows:
        message_id = int(row.id)
        if message_id in existing_source_message_ids:
            continue
        conn.execute(
            sa.insert(sources).values(
                conversation_id=row.conversation_id,
                source_kind="message",
                message_id=message_id,
                title=f"{row.role} message #{message_id}",
                uri=None,
                payload_json={
                    "role": row.role,
                    "timestamp": row.timestamp.isoformat() if row.timestamp is not None else None,
                },
            )
        )
        existing_source_message_ids.add(message_id)

    source_id_by_message_id = {
        int(row.message_id): int(row.id)
        for row in conn.execute(sa.select(sources.c.id, sources.c.message_id).where(sources.c.message_id.is_not(None))).all()
    }
    existing_evidence_keys = {
        (
            row.fact_id if row.fact_id is None else int(row.fact_id),
            row.relation_id if row.relation_id is None else int(row.relation_id),
            row.message_id if row.message_id is None else int(row.message_id),
            int(row.source_id),
        )
        for row in conn.execute(
            sa.select(evidence.c.fact_id, evidence.c.relation_id, evidence.c.message_id, evidence.c.source_id)
        ).all()
    }

    fact_rows = conn.execute(
        sa.select(facts.c.id, facts.c.source_message_ids_json, facts.c.confidence)
    ).all()
    for row in fact_rows:
        fact_id = int(row.id)
        source_message_ids = row.source_message_ids_json or []
        for message_id in source_message_ids:
            if not isinstance(message_id, int):
                continue
            source_id = source_id_by_message_id.get(message_id)
            if source_id is None:
                continue
            key = (fact_id, None, message_id, source_id)
            if key in existing_evidence_keys:
                continue
            conn.execute(
                sa.insert(evidence).values(
                    source_id=source_id,
                    fact_id=fact_id,
                    relation_id=None,
                    message_id=message_id,
                    snippet=_truncate_snippet(content_by_message_id.get(message_id)),
                    confidence=float(row.confidence) if row.confidence is not None else None,
                    meta_json={"origin": "fact_source_message_ids_json_backfill"},
                )
            )
            existing_evidence_keys.add(key)

    relation_rows = conn.execute(
        sa.select(relations.c.id, relations.c.source_message_ids_json, relations.c.confidence)
    ).all()
    for row in relation_rows:
        relation_id = int(row.id)
        source_message_ids = row.source_message_ids_json or []
        for message_id in source_message_ids:
            if not isinstance(message_id, int):
                continue
            source_id = source_id_by_message_id.get(message_id)
            if source_id is None:
                continue
            key = (None, relation_id, message_id, source_id)
            if key in existing_evidence_keys:
                continue
            conn.execute(
                sa.insert(evidence).values(
                    source_id=source_id,
                    fact_id=None,
                    relation_id=relation_id,
                    message_id=message_id,
                    snippet=_truncate_snippet(content_by_message_id.get(message_id)),
                    confidence=float(row.confidence) if row.confidence is not None else None,
                    meta_json={"origin": "relation_source_message_ids_json_backfill"},
                )
            )
            existing_evidence_keys.add(key)


def downgrade() -> None:
    op.drop_index("ix_evidence_message_id", table_name="evidence")
    op.drop_index("ix_evidence_relation_id", table_name="evidence")
    op.drop_index("ix_evidence_fact_id", table_name="evidence")
    op.drop_index("ix_evidence_source_id", table_name="evidence")
    op.drop_table("evidence")

    op.drop_index("ix_sources_source_kind", table_name="sources")
    op.drop_index("ix_sources_conversation_id", table_name="sources")
    op.drop_index("ix_sources_message_id", table_name="sources")
    op.drop_table("sources")

    op.drop_index("ix_workspace_edges_namespace", table_name="workspace_edges")
    op.drop_index("ix_workspace_edges_dst_id", table_name="workspace_edges")
    op.drop_index("ix_workspace_edges_dst_kind", table_name="workspace_edges")
    op.drop_index("ix_workspace_edges_src_id", table_name="workspace_edges")
    op.drop_index("ix_workspace_edges_src_kind", table_name="workspace_edges")
    op.drop_table("workspace_edges")

    op.drop_index("ix_collection_items_entity_id", table_name="collection_items")
    op.drop_index("ix_collection_items_collection_id", table_name="collection_items")
    op.drop_table("collection_items")

    op.drop_index("ix_collections_parent_id", table_name="collections")
    op.drop_index("ix_collections_pod_id", table_name="collections")
    op.drop_table("collections")

    op.drop_index("ix_pods_is_default", table_name="pods")
    op.drop_index("ix_pods_slug", table_name="pods")
    op.drop_table("pods")
