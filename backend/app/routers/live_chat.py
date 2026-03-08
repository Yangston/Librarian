"""Live chat testing routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.conversation import Conversation
from app.schemas.chat import LiveChatTurnRequest, LiveChatTurnResult
from app.schemas.common import ApiResponse
from app.services.background_jobs import run_noncritical_post_processing_jobs, run_workspace_enrichment_job
from app.services.conversations import (
    ConversationPodConflictError,
    ConversationPodNotFoundError,
    ConversationPodRequiredError,
    ensure_conversation_assignment,
)
from app.services.live_chat import LiveChatError, run_live_chat_turn
from app.services.workspace_sync import create_workspace_enrichment_run


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.post("/chat/turn", response_model=ApiResponse[LiveChatTurnResult])
def create_live_chat_turn(
    background_tasks: BackgroundTasks,
    payload: LiveChatTurnRequest,
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[LiveChatTurnResult]:
    """Persist a user message, generate assistant reply, and optionally run extraction."""

    try:
        ensure_conversation_assignment(
            db,
            conversation_id=conversation_id,
            pod_id=payload.pod_id,
            require_pod_for_new=True,
        )
    except ConversationPodRequiredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConversationPodNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationPodConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        result = run_live_chat_turn(
            db,
            conversation_id,
            user_content=payload.content,
            pod_id=payload.pod_id,
            auto_extract=payload.auto_extract,
            system_prompt=payload.system_prompt,
        )
    except LiveChatError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if payload.auto_extract and result.extraction is not None:
        conversation = db.scalar(
            select(Conversation).where(Conversation.conversation_id == conversation_id)
        )
        if conversation is not None and conversation.pod_id is not None:
            workspace_run = create_workspace_enrichment_run(
                db,
                pod_id=int(conversation.pod_id),
                conversation_id=conversation_id,
                requested_by="system",
                run_kind="system_chat",
                summary_json={"include_sources": payload.workspace_enrichment_include_sources},
            )
            db.commit()
            background_tasks.add_task(run_workspace_enrichment_job, workspace_run.id)
            background_tasks.add_task(run_noncritical_post_processing_jobs, conversation_id)
            result = result.model_copy(update={"workspace_enrichment_run_id": int(workspace_run.id)})
    return ApiResponse(data=result)
