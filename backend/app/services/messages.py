"""Message ingestion and retrieval services."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message
from app.schemas.message import MessageCreate
from app.services.conversations import ensure_conversation_assignment


def create_messages(
    db: Session,
    conversation_id: str,
    message_inputs: list[MessageCreate],
    *,
    pod_id: int | None = None,
    require_pod_for_new: bool = False,
) -> list[Message]:
    """Persist a batch of messages for a conversation."""

    clean_conversation_id = conversation_id.strip()
    ensure_conversation_assignment(
        db,
        conversation_id=clean_conversation_id,
        pod_id=pod_id,
        require_pod_for_new=require_pod_for_new,
    )
    created: list[Message] = []
    for message_input in message_inputs:
        message = Message(
            conversation_id=clean_conversation_id,
            role=message_input.role,
            content=message_input.content,
            timestamp=message_input.timestamp or datetime.now(timezone.utc),
        )
        db.add(message)
        created.append(message)
    db.commit()
    for message in created:
        db.refresh(message)
    return created


def list_messages(db: Session, conversation_id: str) -> list[Message]:
    """Return messages for a conversation ordered deterministically."""

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc(), Message.id.asc())
    )
    return list(db.scalars(stmt).all())

