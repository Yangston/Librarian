"""SQLAlchemy metadata registry import for Alembic."""

from app.models import Entity, Fact, Message, Relation
from app.models.base import Base

__all__ = ["Base", "Message", "Entity", "Fact", "Relation"]

