"""Entity resolution package."""

from app.entity_resolution.resolver import (
    RESOLVER_VERSION,
    EntityResolutionAssignment,
    EntityResolutionPlan,
    EntityResolver,
)

__all__ = [
    "RESOLVER_VERSION",
    "EntityResolutionAssignment",
    "EntityResolutionPlan",
    "EntityResolver",
]
