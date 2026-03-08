"""Stable collection column definitions for workspace tables."""

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin, UpdatedAtMixin


class CollectionColumn(Base, IdMixin, CreatedAtMixin, UpdatedAtMixin):
    """One standardized column within a collection."""

    __tablename__ = "collection_columns"
    __table_args__ = (
        UniqueConstraint("collection_id", "key", name="uq_collection_columns_collection_key"),
    )

    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="property", nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_relation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    relation_target_collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    origin: Mapped[str] = mapped_column(String(32), default="planner", nullable=False, index=True)
    planner_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enrichment_policy_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
