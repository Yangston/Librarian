"""Entity resolution event log model."""

from sqlalchemy import JSON, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class ResolutionEvent(Base, IdMixin, CreatedAtMixin):
    """Resolution decisions emitted during extraction persistence."""

    __tablename__ = "resolution_events"

    conversation_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rationale: Mapped[str] = mapped_column(String(255), nullable=False)
    source_message_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
