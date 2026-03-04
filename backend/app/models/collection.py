"""Collection ORM model."""

from sqlalchemy import Boolean, JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin, UpdatedAtMixin


class Collection(Base, IdMixin, CreatedAtMixin, UpdatedAtMixin):
    """Notion-like page/table/folder container inside a pod."""

    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("pod_id", "slug", name="uq_collections_pod_slug"),)

    pod_id: Mapped[int] = mapped_column(
        ForeignKey("pods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    view_config_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
