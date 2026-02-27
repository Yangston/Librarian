"""Conversation-to-entity link model."""

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class ConversationEntityLink(Base, IdMixin, CreatedAtMixin):
    """Tracks where canonical entities appear across conversations."""

    __tablename__ = "conversation_entity_links"
    __table_args__ = (
        UniqueConstraint("conversation_id", "entity_id", name="uq_conversation_entity_links_conversation_entity"),
    )

    conversation_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    first_seen_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
