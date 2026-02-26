"""Live chat testing routes."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.chat import LiveChatTurnRequest, LiveChatTurnResult
from app.schemas.common import ApiResponse
from app.services.live_chat import LiveChatError, run_live_chat_turn


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.post("/chat/turn", response_model=ApiResponse[LiveChatTurnResult])
def create_live_chat_turn(
    payload: LiveChatTurnRequest,
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[LiveChatTurnResult]:
    """Persist a user message, generate assistant reply, and optionally run extraction."""

    try:
        result = run_live_chat_turn(
            db,
            conversation_id,
            user_content=payload.content,
            auto_extract=payload.auto_extract,
            system_prompt=payload.system_prompt,
        )
    except LiveChatError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ApiResponse(data=result)
