"""Schemas for predicate registry transparency endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PredicateRegistryEntryRead(BaseModel):
    """Serialized predicate registry entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    predicate: str
    aliases_json: list[str]
    frequency: int
    first_seen_at: datetime
    last_seen_at: datetime
