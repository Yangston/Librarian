"""Entity merge audit response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EntityMergeAuditRead(BaseModel):
    """Serialized entity merge audit record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    survivor_entity_id: int
    merged_entity_ids_json: list[int]
    reason_for_merge: str
    confidence: float
    resolver_version: str
    details_json: dict[str, object]
    timestamp: datetime
