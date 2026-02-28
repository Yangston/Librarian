"""Knowledge query routes."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.entity import EntityRead
from app.schemas.knowledge import (
    ConversationGraphData,
    ConversationSummaryData,
    EntityGraphData,
    FactTimelineItem,
)
from app.services.knowledge import (
    get_conversation_graph,
    get_conversation_summary,
    get_entity_graph,
    get_entity_record,
    get_entity_timeline,
)

router = APIRouter()


@router.get("/entities/{entity_id}", response_model=ApiResponse[EntityRead])
def get_entity(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[EntityRead]:
    """Return a canonical entity record by ID."""

    entity = get_entity_record(db, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ApiResponse(data=EntityRead.model_validate(entity))


@router.get("/entities/{entity_id}/graph", response_model=ApiResponse[EntityGraphData])
def get_entity_graph_view(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[EntityGraphData]:
    """Return incoming/outgoing relation neighborhood for an entity."""

    payload = get_entity_graph(db, entity_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ApiResponse(data=payload)


@router.get("/entities/{entity_id}/timeline", response_model=ApiResponse[list[FactTimelineItem]])
def get_entity_timeline_view(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[list[FactTimelineItem]]:
    """Return entity facts sorted by source message timestamp."""

    payload = get_entity_timeline(db, entity_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ApiResponse(data=payload)


@router.get(
    "/conversations/{conversation_id}/summary",
    response_model=ApiResponse[ConversationSummaryData],
)
def get_conversation_summary_view(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[ConversationSummaryData]:
    """Return conversation-level knowledge summary."""

    return ApiResponse(data=get_conversation_summary(db, conversation_id))


@router.get(
    "/conversations/{conversation_id}/graph",
    response_model=ApiResponse[ConversationGraphData],
)
def get_conversation_graph_view(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[ConversationGraphData]:
    """Return conversation-wide graph (entities + relations)."""

    return ApiResponse(data=get_conversation_graph(db, conversation_id))
