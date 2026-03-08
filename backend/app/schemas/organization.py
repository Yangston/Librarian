"""Schemas for pod/collection organization layer."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ScopeMode = Literal["global", "pod", "collection"]


class PodRead(BaseModel):
    """Pod record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class PodCreateRequest(BaseModel):
    """Pod create payload."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class PodDeleteResponse(BaseModel):
    """Pod delete payload."""

    pod_id: int
    deleted: bool
    conversations_deleted: int


class CollectionRead(BaseModel):
    """Collection record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    pod_id: int
    parent_id: int | None
    kind: str
    slug: str
    name: str
    description: str | None
    schema_json: dict[str, object]
    view_config_json: dict[str, object]
    sort_order: int
    is_auto_generated: bool
    created_at: datetime
    updated_at: datetime


class CollectionTreeNode(BaseModel):
    """Collection node with nested children."""

    collection: CollectionRead
    children: list["CollectionTreeNode"] = Field(default_factory=list)


class PodTreeData(BaseModel):
    """Pod tree response payload."""

    pod: PodRead
    tree: list[CollectionTreeNode]


class CollectionItemRead(BaseModel):
    """Entity row in a collection with dynamic fact columns."""

    id: int
    canonical_name: str
    display_name: str
    type_label: str
    alias_count: int
    first_seen: datetime
    last_seen: datetime
    conversation_count: int
    dynamic_fields: dict[str, str]


class CollectionItemsResponse(BaseModel):
    """Paginated collection items response."""

    collection: CollectionRead
    items: list[CollectionItemRead]
    total: int
    limit: int
    offset: int
    selected_fields: list[str]
    available_fields: list[str]


class CollectionItemMutationRequest(BaseModel):
    """Add/update collection membership."""

    entity_id: int
    sort_key: str | None = None


class CollectionItemMutationResponse(BaseModel):
    """Collection item write result."""

    collection_id: int
    entity_id: int
    added: bool


class ScopedGraphNode(BaseModel):
    """Scoped graph node payload."""

    entity_id: int
    canonical_name: str
    display_name: str
    type_label: str
    external: bool = False
    pending_suggestion_count: int = 0


class ScopedGraphEdge(BaseModel):
    """Scoped graph edge payload."""

    relation_id: int
    from_entity_id: int
    to_entity_id: int
    relation_type: str
    confidence: float
    source_kind: str = "conversation"
    status: str = "accepted"
    suggested: bool = False


class ScopedGraphData(BaseModel):
    """Graph view resolved for a workspace scope."""

    scope_mode: ScopeMode
    pod_id: int | None
    collection_id: int | None
    one_hop: bool
    include_external: bool
    nodes: list[ScopedGraphNode]
    edges: list[ScopedGraphEdge]
    pending_suggestion_count: int = 0


CollectionTreeNode.model_rebuild()
