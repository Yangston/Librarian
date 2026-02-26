"""Schema governance query services."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.predicate_registry_entry import PredicateRegistryEntry
from app.schema.predicate_registry import PredicateKind


def list_predicate_registry_entries(
    db: Session,
    *,
    kind: PredicateKind | None = None,
) -> list[PredicateRegistryEntry]:
    """List predicate registry entries globally, optionally filtered by kind."""

    stmt = select(PredicateRegistryEntry)
    if kind is not None:
        stmt = stmt.where(PredicateRegistryEntry.kind == kind)
    stmt = stmt.order_by(
        PredicateRegistryEntry.kind.asc(),
        PredicateRegistryEntry.frequency.desc(),
        PredicateRegistryEntry.predicate.asc(),
        PredicateRegistryEntry.id.asc(),
    )
    return list(db.scalars(stmt).all())
