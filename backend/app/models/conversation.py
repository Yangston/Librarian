"""Conversation-to-pod assignment model."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UpdatedAtMixin


class Conversation(Base, CreatedAtMixin, UpdatedAtMixin):
    """Conversation record that binds one conversation id to one pod."""

    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    pod_id: Mapped[int] = mapped_column(
        ForeignKey("pods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
