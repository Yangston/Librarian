"""Message ingestion and retrieval routes."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.message import MessageRead, MessagesIngestRequest
from app.services.messages import create_messages, list_messages


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.post("/messages", response_model=ApiResponse[list[MessageRead]], status_code=201)
def ingest_messages(
    payload: MessagesIngestRequest,
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[list[MessageRead]]:
    """Store a conversation message batch."""

    created = create_messages(db, conversation_id, payload.messages)
    return ApiResponse(data=[MessageRead.model_validate(message) for message in created])


@router.get("/messages", response_model=ApiResponse[list[MessageRead]])
def get_messages(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[list[MessageRead]]:
    """List messages for a conversation."""

    records = list_messages(db, conversation_id)
    return ApiResponse(data=[MessageRead.model_validate(message) for message in records])

