"""Extraction execution routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.conversation import Conversation
from app.extraction.llm_extractor import LLMExtractionError
from app.schemas.common import ApiResponse
from app.schemas.extraction import ExtractionRunResult
from app.services.background_jobs import run_noncritical_post_processing_jobs, run_workspace_enrichment_job
from app.services.extraction import run_extraction_for_conversation
from app.services.workspace_sync import create_workspace_enrichment_run


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.post("/extract", response_model=ApiResponse[ExtractionRunResult])
def extract_conversation(
    background_tasks: BackgroundTasks,
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[ExtractionRunResult]:
    """Run extraction for a conversation using the configured extractor."""

    try:
        result = run_extraction_for_conversation(
            db,
            conversation_id,
            post_processing_mode="none",
        )
    except LLMExtractionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    conversation = db.scalar(select(Conversation).where(Conversation.conversation_id == conversation_id))
    if conversation is not None and conversation.pod_id is not None:
        workspace_run = create_workspace_enrichment_run(
            db,
            pod_id=int(conversation.pod_id),
            conversation_id=conversation_id,
            requested_by="system",
            run_kind="system_chat",
            summary_json={"include_sources": True},
        )
        db.commit()
        background_tasks.add_task(run_workspace_enrichment_job, workspace_run.id)
        background_tasks.add_task(run_noncritical_post_processing_jobs, conversation_id)
    return ApiResponse(data=result)
