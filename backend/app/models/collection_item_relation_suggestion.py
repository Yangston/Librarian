"""Pending enrichment suggestions for relations between collection rows."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, UpdatedAtMixin


class CollectionItemRelationSuggestion(Base, IdMixin, UpdatedAtMixin):
    """Suggested row relation awaiting review."""

    __tablename__ = "collection_item_relation_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "from_collection_item_id",
            "to_collection_item_id",
            "relation_label",
            "dedupe_key",
            name="uq_collection_item_relation_suggestions_target_key",
        ),
    )

    enrichment_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_enrichment_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    from_collection_item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_collection_item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_label: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(32), default="external", nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    meta_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
