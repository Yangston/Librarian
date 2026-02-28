"""Explainability response schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.fact import FactWithSubjectRead
from app.schemas.relation import RelationWithEntitiesRead
from app.schemas.resolution_event import ResolutionEventRead


class SourceMessageEvidence(BaseModel):
    """Source message payload used for explainability."""

    id: int
    role: str
    content: str
    timestamp: datetime


class SchemaCanonicalizationInfo(BaseModel):
    """Canonicalization context for a schema label."""

    registry_table: str
    observed_label: str
    canonical_label: str | None
    canonical_id: int | None
    status: str
    proposal: "SchemaProposalLink | None" = None


class SchemaProposalLink(BaseModel):
    """Schema proposal metadata relevant to canonicalization."""

    proposal_id: int
    proposal_type: str
    status: str
    confidence: float
    created_at: datetime


class ExtractionMetadata(BaseModel):
    """Extractor run metadata attached to explain responses."""

    extractor_run_id: int
    model_name: str
    prompt_version: str
    created_at: datetime


class FactExplainData(BaseModel):
    """Explain response for a fact."""

    fact: FactWithSubjectRead
    extractor_run_id: int | None
    extraction_metadata: ExtractionMetadata | None
    source_messages: list[SourceMessageEvidence]
    resolution_events: list[ResolutionEventRead]
    schema_canonicalization: SchemaCanonicalizationInfo
    snippets: list[str]


class RelationExplainData(BaseModel):
    """Explain response for a relation."""

    relation: RelationWithEntitiesRead
    extractor_run_id: int | None
    extraction_metadata: ExtractionMetadata | None
    source_messages: list[SourceMessageEvidence]
    resolution_events: list[ResolutionEventRead]
    schema_canonicalization: SchemaCanonicalizationInfo
    snippets: list[str]
