"""Schemas for live chat testing endpoints."""

from pydantic import BaseModel, Field

from app.schemas.extraction import ExtractionRunResult
from app.schemas.message import MessageRead


class LiveChatTurnRequest(BaseModel):
    """Request payload for one live chat turn."""

    content: str = Field(min_length=1)
    auto_extract: bool = True
    system_prompt: str | None = None


class LiveChatTurnResult(BaseModel):
    """Response payload for one live chat turn."""

    conversation_id: str
    user_message: MessageRead
    assistant_message: MessageRead
    extraction: ExtractionRunResult | None = None
