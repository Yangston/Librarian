"""Extraction execution routes."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.extraction.llm_extractor import LLMExtractionError
from app.schemas.common import ApiResponse
from app.schemas.extraction import ExtractionRunResult
from app.services.extraction import run_extraction_for_conversation


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.post("/extract", response_model=ApiResponse[ExtractionRunResult])
def extract_conversation(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[ExtractionRunResult]:
    """Run extraction for a conversation using the configured extractor."""

    try:
        result = run_extraction_for_conversation(db, conversation_id)
    except LLMExtractionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ApiResponse(data=result)
