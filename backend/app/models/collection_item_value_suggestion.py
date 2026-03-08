"""Pending enrichment suggestions for collection row values."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, UpdatedAtMixin


class CollectionItemValueSuggestion(Base, IdMixin, UpdatedAtMixin):
    """Suggested value for one row/column intersection awaiting review."""

    __tablename__ = "collection_item_value_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "collection_item_id",
            "collection_column_id",
            "dedupe_key",
            name="uq_collection_item_value_suggestions_target_key",
        ),
    )

    enrichment_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_enrichment_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    collection_item_id: Mapped[int] = mapped_column(
        ForeignKey("collection_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection_column_id: Mapped[int] = mapped_column(
        ForeignKey("collection_columns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suggested_value_json: Mapped[dict[str, object] | list[object] | str | int | float | bool | None] = mapped_column(
        JSON,
        nullable=True,
    )
    suggested_display_value: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    value_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
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
