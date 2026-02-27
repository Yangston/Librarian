"""Entity response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EntityRead(BaseModel):
    """Serialized entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    name: str
    display_name: str
    canonical_name: str
    type: str
    type_label: str
    aliases_json: list[str]
    known_aliases_json: list[str]
    tags_json: list[str]
    first_seen_timestamp: datetime
    resolution_confidence: float
    resolution_reason: str | None
    resolver_version: str | None
    merged_into_id: int | None
    created_at: datetime
    updated_at: datetime
