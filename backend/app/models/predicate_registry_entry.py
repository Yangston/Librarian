"""Predicate registry ORM model."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class PredicateRegistryEntry(Base, IdMixin):
    """Registry entries for normalized fact predicates and relation types."""

    __tablename__ = "predicate_registry_entries"
    __table_args__ = (UniqueConstraint("kind", "predicate", name="uq_predicate_registry_kind_predicate"),)

    kind: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
