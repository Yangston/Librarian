"""Schemas for v2 user-facing workspace endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.explain import SchemaCanonicalizationInfo, SourceMessageEvidence


class SpaceRead(BaseModel):
    """User-facing space card/list row."""

    id: int
    slug: str
    name: str
    description: str | None
    page_count: int
    item_count: int
    created_at: datetime
    updated_at: datetime
    technical_details: dict[str, object] | None = None


class SpaceCreateRequest(BaseModel):
    """Create one user-facing space."""

    name: str = Field(min_length=1)
    description: str | None = None


class SpaceUpdateRequest(BaseModel):
    """Update one user-facing space."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "SpaceUpdateRequest":
        if self.name is None and self.description is None:
            raise ValueError("At least one field must be provided.")
        return self


class SpacePageRead(BaseModel):
    """User-facing page/table row inside one space."""

    id: int
    space_id: int
    parent_id: int | None
    kind: Literal["page", "table"]
    slug: str
    name: str
    description: str | None
    sort_order: int
    item_count: int
    updated_at: datetime
    technical_details: dict[str, object] | None = None


class SpacePagesResponse(BaseModel):
    """Page list payload for one space."""

    space_id: int
    items: list[SpacePageRead]


class LibraryItemPropertyRead(BaseModel):
    """Display-ready property chip for library item rows."""

    property_key: str
    label: str
    value: str
    claim_index_id: int | None = None
    claim_kind: str | None = None
    claim_id: int | None = None
    last_observed_at: datetime | None = None


class LibraryItemListRow(BaseModel):
    """One row/card in library item listing."""

    id: int
    entity_id: int
    name: str
    type_label: str
    summary: str | None
    mention_count: int
    last_seen_at: datetime
    space_id: int | None
    space_name: str | None
    page_id: int | None
    page_name: str | None
    key_properties: list[LibraryItemPropertyRead]
    technical_details: dict[str, object] | None = None


class LibraryItemsResponse(BaseModel):
    """Paginated library item list payload."""

    items: list[LibraryItemListRow]
    total: int
    limit: int
    offset: int


class LibraryItemLinkRead(BaseModel):
    """Connection summary row for item detail pages."""

    relation_type: str
    relation_count: int
    direction: Literal["outgoing", "incoming"]
    other_item_id: int
    other_item_name: str
    last_seen_at: datetime


class LibraryItemActivityRead(BaseModel):
    """Claim-level activity row for item history views."""

    claim_index_id: int
    claim_kind: Literal["fact", "relation"]
    claim_id: int
    label: str
    value_text: str | None
    confidence: float | None
    occurred_at: datetime
    related_item_id: int | None
    related_item_name: str | None
    technical_details: dict[str, object] | None = None


class LibraryItemActivityResponse(BaseModel):
    """Activity feed payload for one library item."""

    item_id: int
    items: list[LibraryItemActivityRead]


class LibraryItemDetailResponse(BaseModel):
    """Detail payload for one library item."""

    id: int
    entity_id: int
    name: str
    type_label: str
    summary: str | None
    mention_count: int
    last_seen_at: datetime
    space_id: int | None
    space_name: str | None
    page_id: int | None
    page_name: str | None
    properties: list[LibraryItemPropertyRead]
    links: list[LibraryItemLinkRead]
    activity_preview: list[LibraryItemActivityRead]
    technical_details: dict[str, object] | None = None


class LibraryItemUpdateRequest(BaseModel):
    """Editable library item fields (delegates to canonical entity update)."""

    canonical_name: str | None = Field(default=None, min_length=1)
    display_name: str | None = Field(default=None, min_length=1)
    type_label: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    known_aliases_json: list[str] | None = None
    aliases_json: list[str] | None = None
    tags_json: list[str] | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "LibraryItemUpdateRequest":
        if not any(
            value is not None
            for value in (
                self.canonical_name,
                self.display_name,
                self.type_label,
                self.type,
                self.known_aliases_json,
                self.aliases_json,
                self.tags_json,
            )
        ):
            raise ValueError("At least one field must be provided.")
        return self


class PropertyCatalogRead(BaseModel):
    """User-facing property/type catalog row."""

    id: int
    display_label: str
    kind: Literal["field", "relation"]
    status: Literal["stable", "emerging", "deprecated"]
    mention_count: int
    last_seen_at: datetime | None
    technical_details: dict[str, object] | None = None


class PropertyCatalogResponse(BaseModel):
    """Property catalog payload."""

    items: list[PropertyCatalogRead]
    total: int


class PropertyCatalogUpdateRequest(BaseModel):
    """Editable fields for user-facing property catalog entries."""

    display_label: str | None = Field(default=None, min_length=1)
    status: Literal["stable", "emerging", "deprecated"] | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "PropertyCatalogUpdateRequest":
        if self.display_label is None and self.status is None:
            raise ValueError("At least one field must be provided.")
        return self


class UnifiedClaimExplainResponse(BaseModel):
    """Unified explain payload for both facts and relations."""

    claim_index_id: int
    claim_kind: Literal["fact", "relation"]
    claim_id: int
    title: str
    why_this_exists: str
    evidence_snippets: list[str]
    source_messages: list[SourceMessageEvidence]
    canonicalization: SchemaCanonicalizationInfo | None
    technical_details: dict[str, object] | None = None


class SearchResultCard(BaseModel):
    """Normalized card payload for v2 grouped search results."""

    id: str
    kind: Literal["item", "claim"]
    title: str
    subtitle: str | None
    score: float
    href: str
    technical_details: dict[str, object] | None = None


class SearchResultGroup(BaseModel):
    """One named group in v2 search results."""

    key: Literal["items", "claims"]
    label: str
    count: int
    items: list[SearchResultCard]


class SearchV2Response(BaseModel):
    """Grouped search payload optimized for UI cards."""

    query: str
    groups: list[SearchResultGroup]
