"""Explainability response schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.fact import FactWithSubjectRead
from app.schemas.relation import RelationWithEntitiesRead


class SourceMessageEvidence(BaseModel):
    """Source message payload used for explainability."""

    id: int
    role: str
    content: str
    timestamp: datetime


class FactExplainData(BaseModel):
    """Explain response for a fact."""

    fact: FactWithSubjectRead
    source_messages: list[SourceMessageEvidence]
    snippets: list[str]


class RelationExplainData(BaseModel):
    """Explain response for a relation."""

    relation: RelationWithEntitiesRead
    source_messages: list[SourceMessageEvidence]
    snippets: list[str]

