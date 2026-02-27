"""Fact ORM model."""

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin
from app.models.embedding_type import EMBEDDING_COLUMN_TYPE


class Fact(Base, IdMixin, CreatedAtMixin):
    """Extracted fact."""

    __tablename__ = "facts"

    conversation_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    subject_entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    predicate: Mapped[str] = mapped_column(String(255), nullable=False)
    object_value: Mapped[str] = mapped_column(String(1024), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), default="conversation", nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_message_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    extractor_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("extractor_runs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(EMBEDDING_COLUMN_TYPE, nullable=True)
