"""Cell values for collection rows."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, UpdatedAtMixin


class CollectionItemValue(Base, IdMixin, UpdatedAtMixin):
    """Latest value for one row/column intersection."""

    __tablename__ = "collection_item_values"
    __table_args__ = (
        UniqueConstraint(
            "collection_item_id",
            "collection_column_id",
            name="uq_collection_item_values_row_column",
        ),
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
    value_json: Mapped[dict[str, object] | list[object] | str | int | float | bool | None] = mapped_column(
        JSON,
        nullable=True,
    )
    display_value: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    value_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), default="conversation", nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="confirmed", nullable=False, index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    edited_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
