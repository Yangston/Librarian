"""Entity merge audit log model."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class EntityMergeAudit(Base, IdMixin):
    """Immutable-ish merge audit records for transparent entity resolution."""

    __tablename__ = "entity_merge_audits"

    conversation_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    survivor_entity_id: Mapped[int] = mapped_column(nullable=False)
    merged_entity_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    reason_for_merge: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    resolver_version: Mapped[str] = mapped_column(String(64), nullable=False)
    details_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
