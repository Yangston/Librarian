"""Extraction orchestration and persistence services."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.rule_based_extractor import RuleBasedExtractor
from app.extraction.types import ExtractionResult
from app.models.entity import Entity
from app.models.fact import Fact
from app.models.message import Message
from app.models.relation import Relation
from app.schemas.extraction import ExtractionRunResult


def get_default_extractor() -> ExtractorInterface:
    """Return the configured extractor implementation."""

    return RuleBasedExtractor()


def run_extraction_for_conversation(
    db: Session,
    conversation_id: str,
    extractor: ExtractorInterface | None = None,
) -> ExtractionRunResult:
    """Run extraction for a conversation and replace previous extracted data."""

    messages = _get_conversation_messages(db, conversation_id)
    extraction_result = (extractor or get_default_extractor()).extract(messages)
    persisted_counts = _replace_extracted_records(db, conversation_id, extraction_result)

    return ExtractionRunResult(
        conversation_id=conversation_id,
        messages_processed=len(messages),
        entities_created=persisted_counts["entities"],
        facts_created=persisted_counts["facts"],
        relations_created=persisted_counts["relations"],
    )


def _get_conversation_messages(db: Session, conversation_id: str) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc(), Message.id.asc())
    )
    return list(db.scalars(stmt).all())


def _replace_extracted_records(db: Session, conversation_id: str, result: ExtractionResult) -> dict[str, int]:
    """Delete prior records for the conversation and persist the new extraction result."""

    db.execute(delete(Relation).where(Relation.conversation_id == conversation_id))
    db.execute(delete(Fact).where(Fact.conversation_id == conversation_id))
    db.execute(delete(Entity).where(Entity.conversation_id == conversation_id))
    db.flush()

    entity_lookup: dict[tuple[str, str], Entity] = {}
    for extracted_entity in result.entities:
        entity = Entity(
            conversation_id=conversation_id,
            name=extracted_entity.name,
            type=extracted_entity.entity_type,
            aliases_json=sorted(set(extracted_entity.aliases)),
            tags_json=sorted(set(extracted_entity.tags)),
        )
        db.add(entity)
        entity_lookup[(extracted_entity.name.lower(), extracted_entity.entity_type)] = entity
    db.flush()

    facts_created = 0
    for extracted_fact in result.facts:
        subject_entity = entity_lookup.get((extracted_fact.subject_name.lower(), extracted_fact.subject_type))
        if subject_entity is None:
            continue
        db.add(
            Fact(
                conversation_id=conversation_id,
                subject_entity_id=subject_entity.id,
                predicate=extracted_fact.predicate,
                object_value=extracted_fact.object_value,
                confidence=extracted_fact.confidence,
                source_message_ids_json=extracted_fact.source_message_ids,
            )
        )
        facts_created += 1

    relations_created = 0
    for extracted_relation in result.relations:
        from_entity = entity_lookup.get((extracted_relation.from_name.lower(), extracted_relation.from_type))
        to_entity = entity_lookup.get((extracted_relation.to_name.lower(), extracted_relation.to_type))
        if from_entity is None or to_entity is None:
            continue
        db.add(
            Relation(
                conversation_id=conversation_id,
                from_entity_id=from_entity.id,
                relation_type=extracted_relation.relation_type,
                to_entity_id=to_entity.id,
                qualifiers_json=extracted_relation.qualifiers,
                source_message_ids_json=extracted_relation.source_message_ids,
            )
        )
        relations_created += 1

    db.commit()
    return {"entities": len(result.entities), "facts": facts_created, "relations": relations_created}

