"""Materialized relation links between library items."""

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class ItemLink(Base, IdMixin):
    """Aggregated directed relation edges between library items."""

    __tablename__ = "item_links"
    __table_args__ = (
        UniqueConstraint(
            "from_library_item_id",
            "to_library_item_id",
            "relation_type",
            name="uq_item_links_tuple",
        ),
    )

    from_library_item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_library_item_id: Mapped[int] = mapped_column(
        ForeignKey("library_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    relation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
