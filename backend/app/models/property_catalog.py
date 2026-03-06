"""User-facing property/type catalog materialized from schema + claims."""

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, UpdatedAtMixin


class PropertyCatalog(Base, IdMixin, UpdatedAtMixin):
    """Catalog entry for a property or relation label."""

    __tablename__ = "property_catalog"

    property_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_label: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
