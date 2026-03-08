"""Schemas for stable workspace-first v3 APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class WorkspaceSpaceRead(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None
    collection_count: int
    row_count: int
    created_at: datetime
    updated_at: datetime


class WorkspaceSpaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class WorkspaceSpaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "WorkspaceSpaceUpdateRequest":
        if self.name is None and self.description is None:
            raise ValueError("At least one field must be provided.")
        return self


class WorkspaceCollectionRead(BaseModel):
    id: int
    pod_id: int
    parent_id: int | None
    kind: str
    slug: str
    name: str
    description: str | None
    is_auto_generated: bool
    sort_order: int
    column_count: int
    row_count: int
    pending_suggestion_count: int = 0
    has_pending_suggestions: bool = False
    updated_at: datetime


class WorkspaceColumnRead(BaseModel):
    id: int
    collection_id: int
    key: str
    label: str
    data_type: str
    kind: str
    sort_order: int
    required: bool
    is_relation: bool
    relation_target_collection_id: int | None
    origin: str
    planner_locked: bool
    user_locked: bool
    enrichment_policy_json: dict[str, object]
    coverage_count: int = 0
    coverage_ratio: float = 0.0


class WorkspaceSourceRead(BaseModel):
    id: int
    source_kind: str
    title: str | None
    uri: str | None
    snippet: str | None
    confidence: float | None
    created_at: datetime


class WorkspaceCellSuggestionRead(BaseModel):
    id: int
    suggested_display_value: str | None
    source_kind: str
    confidence: float | None
    status: str
    sources: list[WorkspaceSourceRead]


class WorkspaceCellRead(BaseModel):
    id: int | None
    column_id: int
    column_key: str
    label: str
    data_type: str
    value_json: object | None
    display_value: str | None
    source_kind: str | None
    confidence: float | None
    status: str | None
    edited_by_user: bool
    last_verified_at: datetime | None
    sources: list[WorkspaceSourceRead]
    pending_suggestion_count: int = 0
    pending_suggestions: list[WorkspaceCellSuggestionRead] = []


class WorkspaceRowRead(BaseModel):
    id: int
    collection_id: int
    entity_id: int
    primary_entity_id: int | None
    title: str
    summary: str | None
    detail_blurb: str | None
    sort_order: int
    updated_at: datetime
    cells: list[WorkspaceCellRead]


class WorkspaceRowRelationRead(BaseModel):
    id: int
    relation_label: str
    direction: str
    other_row_id: int
    other_row_title: str
    source_kind: str
    confidence: float | None
    status: str
    sources: list[WorkspaceSourceRead]
    suggested: bool = False


class WorkspaceRowDetailRead(BaseModel):
    id: int
    collection_id: int
    collection_name: str
    collection_slug: str
    entity_id: int
    primary_entity_id: int | None
    title: str
    summary: str | None
    detail_blurb: str | None
    notes_markdown: str | None
    sort_order: int
    updated_at: datetime
    cells: list[WorkspaceCellRead]
    relations: list[WorkspaceRowRelationRead]
    pending_relation_suggestion_count: int = 0


class WorkspaceRowsResponse(BaseModel):
    collection: WorkspaceCollectionRead
    columns: list[WorkspaceColumnRead]
    rows: list[WorkspaceRowRead]
    total: int
    limit: int
    offset: int
    pending_suggestion_count: int = 0


class WorkspaceOverviewResponse(BaseModel):
    space: WorkspaceSpaceRead
    collections: list[WorkspaceCollectionRead]


class WorkspaceEnrichmentRunRead(BaseModel):
    id: int
    pod_id: int
    conversation_id: str | None
    collection_id: int | None
    collection_item_id: int | None
    requested_by: str
    run_kind: str
    status: str
    stage: str
    error_message: str | None
    summary_json: dict[str, object]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class WorkspaceSuggestionReviewResult(BaseModel):
    applied: int
    rejected: int


class WorkspaceCollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class WorkspaceCollectionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "WorkspaceCollectionUpdateRequest":
        if self.name is None and self.description is None:
            raise ValueError("At least one field must be provided.")
        return self


class WorkspaceColumnCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    data_type: str = Field(default="text", min_length=1, max_length=32)


class WorkspaceColumnUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int | None = None
    required: bool | None = None
    user_locked: bool | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "WorkspaceColumnUpdateRequest":
        if self.label is None and self.sort_order is None and self.required is None and self.user_locked is None:
            raise ValueError("At least one field must be provided.")
        return self


class WorkspaceRowCreateRequest(BaseModel):
    entity_id: int = Field(ge=1)


class WorkspaceRowUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = None
    detail_blurb: str | None = None
    notes_markdown: str | None = None
    sort_order: int | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "WorkspaceRowUpdateRequest":
        if (
            self.title is None
            and self.summary is None
            and self.detail_blurb is None
            and self.notes_markdown is None
            and self.sort_order is None
        ):
            raise ValueError("At least one field must be provided.")
        return self


class WorkspaceCellUpdateRequest(BaseModel):
    display_value: str | None = None
    value_json: object | None = None
    status: str | None = None


class WorkspaceCatalogRow(BaseModel):
    collection_id: int
    collection_name: str
    collection_slug: str
    space_id: int
    space_name: str
    space_slug: str
    row: WorkspaceRowRead


class WorkspaceLibraryResponse(BaseModel):
    items: list[WorkspaceCatalogRow]
    total: int
    limit: int
    offset: int


class WorkspacePropertyCatalogRow(BaseModel):
    id: int
    collection_id: int
    collection_name: str
    collection_slug: str
    space_id: int
    space_name: str
    key: str
    label: str
    data_type: str
    kind: str
    origin: str
    planner_locked: bool
    user_locked: bool
    coverage_count: int
    row_count: int
    coverage_ratio: float
    updated_at: datetime


class WorkspacePropertyCatalogResponse(BaseModel):
    items: list[WorkspacePropertyCatalogRow]
    total: int


class WorkspaceSyncRunRead(BaseModel):
    conversation_id: str
    pod_id: int
    planner_run_id: int | None
    enrichment_run_id: int | None
    collections_upserted: int
    rows_upserted: int
    values_upserted: int
    relations_upserted: int
