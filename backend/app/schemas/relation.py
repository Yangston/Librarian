"""Relation response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RelationRead(BaseModel):
    """Serialized relation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    from_entity_id: int
    relation_type: str
    to_entity_id: int
    scope: str
    qualifiers_json: dict[str, object]
    source_message_ids_json: list[int]
    extractor_run_id: int | None
    created_at: datetime


class RelationWithEntitiesRead(RelationRead):
    """Relation plus denormalized endpoint names."""

    from_entity_name: str
    to_entity_name: str
