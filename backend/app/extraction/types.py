"""Typed extraction outputs independent of persistence."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExtractedEntity:
    """Entity extracted from one or more messages."""

    name: str
    type_label: str | None = None
    confidence: float = 0.0
    source_message_ids: list[int] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExtractedFact:
    """Fact extracted from messages."""

    entity_name: str
    field_label: str
    value_text: str
    confidence: float
    source_message_ids: list[int]
    snippet: str | None = None


@dataclass(slots=True)
class ExtractedRelation:
    """Relation extracted from messages."""

    from_entity: str
    relation_label: str
    to_entity: str
    qualifiers: dict[str, object]
    confidence: float
    source_message_ids: list[int]
    snippet: str | None = None


@dataclass(slots=True)
class ExtractionResult:
    """Container for extractor outputs."""

    entities: list[ExtractedEntity] = field(default_factory=list)
    facts: list[ExtractedFact] = field(default_factory=list)
    relations: list[ExtractedRelation] = field(default_factory=list)
