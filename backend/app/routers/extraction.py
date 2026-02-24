"""Extraction execution routes."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.extraction import ExtractionRunResult
from app.services.extraction import run_extraction_for_conversation


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.post("/extract", response_model=ApiResponse[ExtractionRunResult])
def extract_conversation(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[ExtractionRunResult]:
    """Run deterministic extraction for a conversation."""

    return ApiResponse(data=run_extraction_for_conversation(db, conversation_id))

