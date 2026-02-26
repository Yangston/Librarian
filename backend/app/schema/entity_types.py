"""Controlled entity type system (Phase 2 v1)."""

from __future__ import annotations


ENTITY_TYPE_VALUES: tuple[str, ...] = (
    "Company",
    "Person",
    "Event",
    "Concept",
    "Metric",
    "Location",
    "Other",
)
ENTITY_TYPE_SET = set(ENTITY_TYPE_VALUES)

_ENTITY_TYPE_SYNONYMS: dict[str, str] = {
    "organization": "Company",
    "org": "Company",
    "business": "Company",
    "ticker": "Company",
    "stock": "Company",
    "company": "Company",
    "person": "Person",
    "people": "Person",
    "individual": "Person",
    "executive": "Person",
    "event": "Event",
    "news": "Event",
    "announcement": "Event",
    "decision": "Event",
    "meeting": "Event",
    "concept": "Concept",
    "theme": "Concept",
    "topic": "Concept",
    "technology": "Concept",
    "metric": "Metric",
    "kpi": "Metric",
    "measure": "Metric",
    "indicator": "Metric",
    "location": "Location",
    "place": "Location",
    "country": "Location",
    "city": "Location",
    "region": "Location",
    "other": "Other",
}


def normalize_entity_type(raw_type: str | None) -> str:
    """Normalize to the controlled entity type list."""

    cleaned = _clean_text(raw_type)
    if not cleaned:
        return "Other"
    normalized = _ENTITY_TYPE_SYNONYMS.get(cleaned.lower())
    if normalized:
        return normalized
    titled = cleaned.title()
    return titled if titled in ENTITY_TYPE_SET else "Other"


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().split())
