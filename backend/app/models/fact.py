"""Fact ORM model."""

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class Fact(Base, IdMixin, CreatedAtMixin):
    """Extracted fact."""

    __tablename__ = "facts"

    conversation_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    subject_entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False)
    object_value: Mapped[str] = mapped_column(String(1024), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_message_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)

