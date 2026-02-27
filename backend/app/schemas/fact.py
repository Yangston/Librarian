"""Fact response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FactRead(BaseModel):
    """Serialized fact."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    subject_entity_id: int
    predicate: str
    object_value: str
    scope: str
    confidence: float
    source_message_ids_json: list[int]
    extractor_run_id: int | None
    created_at: datetime


class FactWithSubjectRead(FactRead):
    """Fact plus denormalized subject entity name."""

    subject_entity_name: str
