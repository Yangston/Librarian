"""Typed extraction outputs independent of persistence."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExtractedEntity:
    """Entity extracted from one or more messages."""

    name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_message_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ExtractedFact:
    """Fact extracted from messages."""

    subject_name: str
    subject_type: str
    predicate: str
    object_value: str
    confidence: float
    source_message_ids: list[int]
    snippet: str | None = None


@dataclass(slots=True)
class ExtractedRelation:
    """Relation extracted from messages."""

    from_name: str
    from_type: str
    relation_type: str
    to_name: str
    to_type: str
    qualifiers: dict[str, object]
    source_message_ids: list[int]
    snippet: str | None = None


@dataclass(slots=True)
class ExtractionResult:
    """Container for extractor outputs."""

    entities: list[ExtractedEntity] = field(default_factory=list)
    facts: list[ExtractedFact] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)

