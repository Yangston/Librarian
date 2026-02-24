"""Explainability routes for facts and relations."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.explain import FactExplainData, RelationExplainData
from app.services.explain import get_fact_explain, get_relation_explain


router = APIRouter(prefix="/conversations/{conversation_id}")


@router.get("/facts/{fact_id}/explain", response_model=ApiResponse[FactExplainData])
def explain_fact(
    conversation_id: str = Path(..., min_length=1),
    fact_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[FactExplainData]:
    """Return traceability details for a fact."""

    payload = get_fact_explain(db, conversation_id, fact_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    return ApiResponse(data=payload)


@router.get("/relations/{relation_id}/explain", response_model=ApiResponse[RelationExplainData])
def explain_relation(
    conversation_id: str = Path(..., min_length=1),
    relation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[RelationExplainData]:
    """Return traceability details for a relation."""

    payload = get_relation_explain(db, conversation_id, relation_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Relation not found")
    return ApiResponse(data=payload)

