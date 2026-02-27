"""SQLAlchemy metadata registry import for Alembic."""

from app.models import (
    ConversationEntityLink,
    Entity,
    EntityMergeAudit,
    ExtractorRun,
    Fact,
    Message,
    PredicateRegistryEntry,
    ResolutionEvent,
    Relation,
    SchemaField,
    SchemaNode,
    SchemaProposal,
    SchemaRelation,
)
from app.models.base import Base

__all__ = [
    "Base",
    "Message",
    "ConversationEntityLink",
    "Entity",
    "EntityMergeAudit",
    "ExtractorRun",
    "PredicateRegistryEntry",
    "ResolutionEvent",
    "SchemaNode",
    "SchemaField",
    "SchemaRelation",
    "SchemaProposal",
    "Fact",
    "Relation",
]
