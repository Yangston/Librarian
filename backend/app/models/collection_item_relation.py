"""Workspace-level relations between collection rows."""

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin, UpdatedAtMixin


class CollectionItemRelation(Base, IdMixin, CreatedAtMixin, UpdatedAtMixin):
    """Stable row-level relation for workspace rendering."""

    __tablename__ = "collection_item_relations"
    __table_args__ = (
        UniqueConstraint(
            "from_collection_item_id",
            "to_collection_item_id",
            "relation_label",
            name="uq_collection_item_relations_tuple",
        ),
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
    source_kind: Mapped[str] = mapped_column(String(32), default="conversation", nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="confirmed", nullable=False, index=True)
