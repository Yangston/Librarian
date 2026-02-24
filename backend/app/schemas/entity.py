"""Entity response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EntityRead(BaseModel):
    """Serialized entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    name: str
    type: str
    aliases_json: list[str]
    tags_json: list[str]
    created_at: datetime

