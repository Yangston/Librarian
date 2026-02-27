"""Semantic search response schemas."""

from pydantic import BaseModel

from app.schemas.entity import EntityRead
from app.schemas.fact import FactWithSubjectRead


class EntitySearchHit(BaseModel):
    """Entity search hit with similarity score."""

    entity: EntityRead
    similarity: float


class FactSearchHit(BaseModel):
    """Fact search hit with similarity score."""

    fact: FactWithSubjectRead
    similarity: float


class SemanticSearchData(BaseModel):
    """Search response payload."""

    query: str
    conversation_id: str | None
    entities: list[EntitySearchHit]
    facts: list[FactSearchHit]
