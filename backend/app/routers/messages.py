"""Message ingestion and retrieval routes."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.message import MessageRead, MessagesIngestRequest
from app.services.conversations import (
    ConversationPodConflictError,
    ConversationPodNotFoundError,
    ConversationPodRequiredError,
)
from app.services.messages import create_messages, list_messages


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.post("/messages", response_model=ApiResponse[list[MessageRead]], status_code=201)
def ingest_messages(
    payload: MessagesIngestRequest,
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[list[MessageRead]]:
    """Store a conversation message batch."""

    try:
        created = create_messages(
            db,
            conversation_id,
            payload.messages,
            pod_id=payload.pod_id,
            require_pod_for_new=True,
        )
    except ConversationPodRequiredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConversationPodNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationPodConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(data=[MessageRead.model_validate(message) for message in created])


@router.get("/messages", response_model=ApiResponse[list[MessageRead]])
def get_messages(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[list[MessageRead]]:
    """List messages for a conversation."""

    records = list_messages(db, conversation_id)
    return ApiResponse(data=[MessageRead.model_validate(message) for message in records])
