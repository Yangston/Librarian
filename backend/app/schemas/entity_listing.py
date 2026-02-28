"""Schemas for global entity listing and dynamic table columns."""

from datetime import datetime

from pydantic import BaseModel


class EntityListItem(BaseModel):
    """Entity row for Phase 3 global entities table."""

    id: int
    canonical_name: str
    display_name: str
    type_label: str
    alias_count: int
    first_seen: datetime
    last_seen: datetime
    conversation_count: int
    dynamic_fields: dict[str, str]


class EntityListingResponse(BaseModel):
    """Paginated entities listing payload."""

    items: list[EntityListItem]
    total: int
    limit: int
    offset: int
    selected_fields: list[str]
    available_fields: list[str]

