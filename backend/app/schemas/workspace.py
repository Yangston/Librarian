"""Schemas for Phase 3 workspace-oriented endpoints."""

from datetime import datetime

from pydantic import BaseModel


class ConversationListItem(BaseModel):
    """Conversation list row with activity counters."""

    conversation_id: str
    first_message_at: datetime | None
    last_message_at: datetime | None
    message_count: int
    entity_count: int
    fact_count: int
    relation_count: int
    extractor_run_count: int


class ConversationsListResponse(BaseModel):
    """Paginated conversation list payload."""

    items: list[ConversationListItem]
    total: int
    limit: int
    offset: int


class RecentEntityItem(BaseModel):
    """Entity card data for recent activity feed."""

    entity_id: int
    canonical_name: str
    display_name: str
    type_label: str
    alias_count: int
    first_seen: datetime
    last_seen: datetime
    conversation_count: int


class RecentEntitiesResponse(BaseModel):
    """Recent entities response payload."""

    items: list[RecentEntityItem]


class SchemaNodeOverview(BaseModel):
    """Learned type row for schema explorer overview."""

    id: int
    label: str
    description: str | None
    examples: list[str]
    frequency: int
    last_seen_conversation_id: str | None


class SchemaFieldOverview(BaseModel):
    """Learned field row for schema explorer overview."""

    id: int
    label: str
    canonical_label: str | None
    description: str | None
    examples: list[str]
    frequency: int
    last_seen_conversation_id: str | None


class SchemaRelationOverview(BaseModel):
    """Learned relation row for schema explorer overview."""

    id: int
    label: str
    canonical_label: str | None
    description: str | None
    examples: list[str]
    frequency: int
    last_seen_conversation_id: str | None


class SchemaProposalOverview(BaseModel):
    """Schema proposal row for transparency feeds."""

    id: int
    proposal_type: str
    status: str
    confidence: float
    payload: dict[str, object]
    evidence: dict[str, object]
    created_at: datetime


class SchemaOverviewData(BaseModel):
    """Schema overview payload for dashboard + schema page."""

    nodes: list[SchemaNodeOverview]
    fields: list[SchemaFieldOverview]
    relations: list[SchemaRelationOverview]
    proposals: list[SchemaProposalOverview]

