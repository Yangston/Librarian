"""Unified claim index across facts and relations for v2 UX."""

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class ClaimIndex(Base, IdMixin):
    """Materialized claim row used by v2 library/activity/explain surfaces."""

    __tablename__ = "claim_index"
    __table_args__ = (
        UniqueConstraint("claim_kind", "claim_id", name="uq_claim_index_kind_id"),
    )

    claim_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    claim_id: Mapped[int] = mapped_column(nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    space_id: Mapped[int | None] = mapped_column(
        ForeignKey("spaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    page_id: Mapped[int | None] = mapped_column(
        ForeignKey("space_pages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    library_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("library_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    related_library_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("library_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    property_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    relation_type: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    value_text: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    occurred_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    extractor_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("extractor_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_message_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
