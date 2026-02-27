"""Resolution event response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResolutionEventRead(BaseModel):
    """Serialized resolution event record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    event_type: str
    entity_ids_json: list[int]
    similarity_score: float | None
    rationale: str
    source_message_ids_json: list[int]
    created_at: datetime
