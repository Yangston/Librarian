"""Transparent database view routes."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.entity import EntityRead
from app.schemas.fact import FactWithSubjectRead
from app.schemas.relation import RelationWithEntitiesRead
from app.services.database import list_entities, list_facts, list_relations


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.get("/entities", response_model=ApiResponse[list[EntityRead]])
def get_entities(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[list[EntityRead]]:
    """List extracted entities for a conversation."""

    return ApiResponse(data=[EntityRead.model_validate(entity) for entity in list_entities(db, conversation_id)])


@router.get("/facts", response_model=ApiResponse[list[FactWithSubjectRead]])
def get_facts(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[list[FactWithSubjectRead]]:
    """List extracted facts for a conversation."""

    return ApiResponse(data=list_facts(db, conversation_id))


@router.get("/relations", response_model=ApiResponse[list[RelationWithEntitiesRead]])
def get_relations(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[list[RelationWithEntitiesRead]]:
    """List extracted relations for a conversation."""

    return ApiResponse(data=list_relations(db, conversation_id))

