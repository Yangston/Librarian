"""Schema governance transparency routes."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.predicate_registry import PredicateRegistryEntryRead
from app.services.schema import list_predicate_registry_entries

PredicateKindParam = Literal["fact_predicate", "relation_type"]

router = APIRouter(prefix="/schema")


@router.get("/predicates", response_model=ApiResponse[list[PredicateRegistryEntryRead]])
def get_predicate_registry(
    kind: PredicateKindParam | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[list[PredicateRegistryEntryRead]]:
    """List registered predicates/relation types and their frequency."""

    entries = list_predicate_registry_entries(db, kind=kind)
    return ApiResponse(data=[PredicateRegistryEntryRead.model_validate(entry) for entry in entries])
