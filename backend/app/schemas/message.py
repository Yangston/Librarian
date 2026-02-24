"""Message request/response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    """Single message payload for ingestion."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    timestamp: datetime | None = None


class MessagesIngestRequest(BaseModel):
    """Conversation ingestion payload."""

    messages: list[MessageCreate] = Field(default_factory=list, min_length=1)


class MessageRead(BaseModel):
    """Serialized message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    role: str
    content: str
    timestamp: datetime

