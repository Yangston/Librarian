"""Extraction endpoint schemas."""

from pydantic import BaseModel


class ExtractionRunResult(BaseModel):
    """Extraction execution summary."""

    conversation_id: str
    messages_processed: int
    entities_created: int
    facts_created: int
    relations_created: int

