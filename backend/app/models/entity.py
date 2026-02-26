"""Entity ORM model."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class Entity(Base, IdMixin, CreatedAtMixin):
    """Extracted entity."""

    __tablename__ = "entities"

    conversation_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    aliases_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    known_aliases_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    first_seen_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolution_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    resolution_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolver_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    merged_into_id: Mapped[int | None] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
