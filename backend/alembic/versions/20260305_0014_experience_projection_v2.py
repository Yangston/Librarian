"""add experience projection v2 tables

Revision ID: 20260305_0014
Revises: 20260303_0013
Create Date: 2026-03-05 00:14:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260305_0014"
down_revision: str | None = "20260303_0013"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pod_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["pod_id"], ["pods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pod_id", name="uq_spaces_pod_id"),
        sa.UniqueConstraint("slug", name="uq_spaces_slug"),
    )
    op.create_index("ix_spaces_pod_id", "spaces", ["pod_id"], unique=True)
    op.create_index("ix_spaces_slug", "spaces", ["slug"], unique=True)

    op.create_table(
        "space_pages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("space_id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["space_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("space_id", "slug", name="uq_space_pages_space_slug"),
        sa.UniqueConstraint("collection_id", name="uq_space_pages_collection_id"),
    )
    op.create_index("ix_space_pages_space_id", "space_pages", ["space_id"], unique=False)
    op.create_index("ix_space_pages_collection_id", "space_pages", ["collection_id"], unique=True)
    op.create_index("ix_space_pages_parent_id", "space_pages", ["parent_id"], unique=False)

    op.create_table(
        "library_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("space_id", sa.Integer(), nullable=True),
        sa.Column("page_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type_label", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["space_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", name="uq_library_items_entity_id"),
    )
    op.create_index("ix_library_items_entity_id", "library_items", ["entity_id"], unique=True)
    op.create_index("ix_library_items_space_id", "library_items", ["space_id"], unique=False)
    op.create_index("ix_library_items_page_id", "library_items", ["page_id"], unique=False)
    op.create_index("ix_library_items_name", "library_items", ["name"], unique=False)
    op.create_index("ix_library_items_type_label", "library_items", ["type_label"], unique=False)
    op.create_index("ix_library_items_last_seen_at", "library_items", ["last_seen_at"], unique=False)

    op.create_table(
        "item_properties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("library_item_id", sa.Integer(), nullable=False),
        sa.Column("property_key", sa.String(length=255), nullable=False),
        sa.Column("property_label", sa.String(length=255), nullable=False),
        sa.Column("property_value", sa.String(length=2048), nullable=False),
        sa.Column("claim_kind", sa.String(length=16), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["library_item_id"], ["library_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("library_item_id", "property_key", name="uq_item_properties_item_key"),
    )
    op.create_index("ix_item_properties_library_item_id", "item_properties", ["library_item_id"], unique=False)
    op.create_index("ix_item_properties_property_key", "item_properties", ["property_key"], unique=False)
    op.create_index("ix_item_properties_claim_id", "item_properties", ["claim_id"], unique=False)
    op.create_index("ix_item_properties_last_observed_at", "item_properties", ["last_observed_at"], unique=False)

    op.create_table(
        "item_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_library_item_id", sa.Integer(), nullable=False),
        sa.Column("to_library_item_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", sa.String(length=255), nullable=False),
        sa.Column("relation_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["from_library_item_id"], ["library_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_library_item_id"], ["library_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_library_item_id",
            "to_library_item_id",
            "relation_type",
            name="uq_item_links_tuple",
        ),
    )
    op.create_index("ix_item_links_from_library_item_id", "item_links", ["from_library_item_id"], unique=False)
    op.create_index("ix_item_links_to_library_item_id", "item_links", ["to_library_item_id"], unique=False)
    op.create_index("ix_item_links_relation_type", "item_links", ["relation_type"], unique=False)
    op.create_index("ix_item_links_last_seen_at", "item_links", ["last_seen_at"], unique=False)

    op.create_table(
        "property_catalog",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("property_key", sa.String(length=255), nullable=False),
        sa.Column("display_label", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_key", name="uq_property_catalog_property_key"),
    )
    op.create_index("ix_property_catalog_property_key", "property_catalog", ["property_key"], unique=True)
    op.create_index("ix_property_catalog_kind", "property_catalog", ["kind"], unique=False)
    op.create_index("ix_property_catalog_status", "property_catalog", ["status"], unique=False)
    op.create_index("ix_property_catalog_last_seen_at", "property_catalog", ["last_seen_at"], unique=False)

    op.create_table(
        "claim_index",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("claim_kind", sa.String(length=16), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("space_id", sa.Integer(), nullable=True),
        sa.Column("page_id", sa.Integer(), nullable=True),
        sa.Column("library_item_id", sa.Integer(), nullable=True),
        sa.Column("related_library_item_id", sa.Integer(), nullable=True),
        sa.Column("property_key", sa.String(length=255), nullable=True),
        sa.Column("relation_type", sa.String(length=255), nullable=True),
        sa.Column("value_text", sa.String(length=2048), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extractor_run_id", sa.Integer(), nullable=True),
        sa.Column("source_message_ids_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["extractor_run_id"], ["extractor_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["library_item_id"], ["library_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["page_id"], ["space_pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_library_item_id"], ["library_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_kind", "claim_id", name="uq_claim_index_kind_id"),
    )
    op.create_index("ix_claim_index_claim_kind", "claim_index", ["claim_kind"], unique=False)
    op.create_index("ix_claim_index_claim_id", "claim_index", ["claim_id"], unique=False)
    op.create_index("ix_claim_index_conversation_id", "claim_index", ["conversation_id"], unique=False)
    op.create_index("ix_claim_index_space_id", "claim_index", ["space_id"], unique=False)
    op.create_index("ix_claim_index_page_id", "claim_index", ["page_id"], unique=False)
    op.create_index("ix_claim_index_library_item_id", "claim_index", ["library_item_id"], unique=False)
    op.create_index(
        "ix_claim_index_related_library_item_id",
        "claim_index",
        ["related_library_item_id"],
        unique=False,
    )
    op.create_index("ix_claim_index_property_key", "claim_index", ["property_key"], unique=False)
    op.create_index("ix_claim_index_relation_type", "claim_index", ["relation_type"], unique=False)
    op.create_index("ix_claim_index_occurred_at", "claim_index", ["occurred_at"], unique=False)
    op.create_index("ix_claim_index_extractor_run_id", "claim_index", ["extractor_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_claim_index_extractor_run_id", table_name="claim_index")
    op.drop_index("ix_claim_index_occurred_at", table_name="claim_index")
    op.drop_index("ix_claim_index_relation_type", table_name="claim_index")
    op.drop_index("ix_claim_index_property_key", table_name="claim_index")
    op.drop_index("ix_claim_index_related_library_item_id", table_name="claim_index")
    op.drop_index("ix_claim_index_library_item_id", table_name="claim_index")
    op.drop_index("ix_claim_index_page_id", table_name="claim_index")
    op.drop_index("ix_claim_index_space_id", table_name="claim_index")
    op.drop_index("ix_claim_index_conversation_id", table_name="claim_index")
    op.drop_index("ix_claim_index_claim_id", table_name="claim_index")
    op.drop_index("ix_claim_index_claim_kind", table_name="claim_index")
    op.drop_table("claim_index")

    op.drop_index("ix_property_catalog_last_seen_at", table_name="property_catalog")
    op.drop_index("ix_property_catalog_status", table_name="property_catalog")
    op.drop_index("ix_property_catalog_kind", table_name="property_catalog")
    op.drop_index("ix_property_catalog_property_key", table_name="property_catalog")
    op.drop_table("property_catalog")

    op.drop_index("ix_item_links_last_seen_at", table_name="item_links")
    op.drop_index("ix_item_links_relation_type", table_name="item_links")
    op.drop_index("ix_item_links_to_library_item_id", table_name="item_links")
    op.drop_index("ix_item_links_from_library_item_id", table_name="item_links")
    op.drop_table("item_links")

    op.drop_index("ix_item_properties_last_observed_at", table_name="item_properties")
    op.drop_index("ix_item_properties_claim_id", table_name="item_properties")
    op.drop_index("ix_item_properties_property_key", table_name="item_properties")
    op.drop_index("ix_item_properties_library_item_id", table_name="item_properties")
    op.drop_table("item_properties")

    op.drop_index("ix_library_items_last_seen_at", table_name="library_items")
    op.drop_index("ix_library_items_type_label", table_name="library_items")
    op.drop_index("ix_library_items_name", table_name="library_items")
    op.drop_index("ix_library_items_page_id", table_name="library_items")
    op.drop_index("ix_library_items_space_id", table_name="library_items")
    op.drop_index("ix_library_items_entity_id", table_name="library_items")
    op.drop_table("library_items")

    op.drop_index("ix_space_pages_parent_id", table_name="space_pages")
    op.drop_index("ix_space_pages_collection_id", table_name="space_pages")
    op.drop_index("ix_space_pages_space_id", table_name="space_pages")
    op.drop_table("space_pages")

    op.drop_index("ix_spaces_slug", table_name="spaces")
    op.drop_index("ix_spaces_pod_id", table_name="spaces")
    op.drop_table("spaces")
