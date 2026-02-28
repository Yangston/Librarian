"""Semantic search routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.search import SemanticSearchData
from app.services.search import semantic_search

router = APIRouter(prefix="/search")


@router.get("", response_model=ApiResponse[SemanticSearchData])
def search(
    q: str = Query(..., min_length=1),
    conversation_id: str | None = Query(default=None, min_length=1),
    type_label: str | None = Query(default=None, min_length=1),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> ApiResponse[SemanticSearchData]:
    """Run semantic search over entities and facts."""

    return ApiResponse(
        data=semantic_search(
            db,
            query=q,
            conversation_id=conversation_id,
            type_label=type_label,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
    )
