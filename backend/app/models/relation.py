"""Relation ORM model."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class Relation(Base, IdMixin, CreatedAtMixin):
    """Extracted relation."""

    __tablename__ = "relations"

    conversation_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    from_entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(255), nullable=False)
    to_entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), default="conversation", nullable=False, index=True)
    qualifiers_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    source_message_ids_json: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    extractor_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("extractor_runs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
