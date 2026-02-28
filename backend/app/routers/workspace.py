"""Phase 3 workspace routes."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.entity_listing import EntityListingResponse
from app.schemas.workspace import ConversationsListResponse, RecentEntitiesResponse
from app.services.workspace import list_conversations, list_entities_catalog, list_recent_entities

ConversationLimitParam = Query(default=20, ge=1, le=200)
ConversationOffsetParam = Query(default=0, ge=0)
EntitySortParam = Literal["canonical_name", "type_label", "last_seen", "conversation_count", "alias_count"]
SortOrderParam = Literal["asc", "desc"]

router = APIRouter()


@router.get("/conversations", response_model=ApiResponse[ConversationsListResponse])
def get_conversations(
    limit: int = ConversationLimitParam,
    offset: int = ConversationOffsetParam,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[ConversationsListResponse]:
    """List known conversations ordered by most recent activity."""

    payload = list_conversations(
        db,
        limit=limit,
        offset=offset,
        query=q,
    )
    return ApiResponse(data=payload)


@router.get("/recent/entities", response_model=ApiResponse[RecentEntitiesResponse])
def get_recent_entities(
    limit: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[RecentEntitiesResponse]:
    """Return recently updated entities for dashboard activity cards."""

    return ApiResponse(data=list_recent_entities(db, limit=limit))


@router.get("/entities", response_model=ApiResponse[EntityListingResponse])
def get_entities_catalog(
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = ConversationOffsetParam,
    sort: EntitySortParam = Query(default="last_seen"),
    order: SortOrderParam = Query(default="desc"),
    q: str | None = Query(default=None),
    type_label: str | None = Query(default=None),
    fields: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[EntityListingResponse]:
    """Return global entity table rows with optional dynamic field columns."""

    selected_fields = [segment.strip() for segment in (fields or "").split(",") if segment.strip()]
    payload = list_entities_catalog(
        db,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
        query=q,
        type_label=type_label,
        selected_fields=selected_fields,
    )
    return ApiResponse(data=payload)

