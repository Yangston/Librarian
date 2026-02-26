"""SQLAlchemy metadata registry import for Alembic."""

from app.models import Entity, EntityMergeAudit, Fact, Message, PredicateRegistryEntry, Relation
from app.models.base import Base

__all__ = ["Base", "Message", "Entity", "EntityMergeAudit", "PredicateRegistryEntry", "Fact", "Relation"]
