"""Extraction orchestration and persistence services."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.entity_resolution import RESOLVER_VERSION, EntityResolver
from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.llm_extractor import LLMExtractionError, LLMExtractor, OpenAIChatCompletionsClient
from app.extraction.types import ExtractionResult
from app.models.entity import Entity
from app.models.entity_merge_audit import EntityMergeAudit
from app.models.fact import Fact
from app.models.message import Message
from app.models.relation import Relation
from app.schema.entity_types import normalize_entity_type
from app.schema.predicate_registry import PredicateRegistry
from app.schemas.extraction import ExtractionRunResult


def get_default_extractor() -> ExtractorInterface:
    """Return the LLM extractor implementation."""

    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMExtractionError(
            "OPENAI_API_KEY is not configured. Set it in backend/.env before running extraction."
        )
    return LLMExtractor(
        OpenAIChatCompletionsClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    )


def run_extraction_for_conversation(
    db: Session,
    conversation_id: str,
    extractor: ExtractorInterface | None = None,
) -> ExtractionRunResult:
    """Run extraction for a conversation and replace previous extracted data."""

    messages = _get_conversation_messages(db, conversation_id)
    extraction_result = (extractor or get_default_extractor()).extract(messages)
    persisted_counts = _replace_extracted_records(db, conversation_id, extraction_result, messages)

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


def _replace_extracted_records(
    db: Session,
    conversation_id: str,
    result: ExtractionResult,
    messages: list[Message],
) -> dict[str, int]:
    """Delete prior records for the conversation and persist the new extraction result."""

    _apply_schema_governance_normalization(result)

    db.execute(delete(Relation).where(Relation.conversation_id == conversation_id))
    db.execute(delete(Fact).where(Fact.conversation_id == conversation_id))
    db.execute(delete(Entity).where(Entity.conversation_id == conversation_id))
    db.execute(delete(EntityMergeAudit).where(EntityMergeAudit.conversation_id == conversation_id))
    db.flush()

    message_timestamps = {message.id: message.timestamp for message in messages}
    resolution_plan = EntityResolver().resolve(
        result.entities,
        observed_message_timestamps=message_timestamps,
    )
    assignments_by_index = {
        assignment.extracted_index: assignment for assignment in resolution_plan.assignments
    }

    entities_by_index: dict[int, Entity] = {}
    for extracted_index, extracted_entity in enumerate(result.entities):
        assignment = assignments_by_index[extracted_index]
        first_seen_timestamp = _first_seen_timestamp(extracted_entity.source_message_ids, message_timestamps)
        entity = Entity(
            conversation_id=conversation_id,
            name=extracted_entity.name,
            canonical_name=assignment.canonical_name,
            type=extracted_entity.entity_type,
            aliases_json=sorted(set(extracted_entity.aliases)),
            known_aliases_json=assignment.known_aliases,
            tags_json=sorted(set(extracted_entity.tags)),
            first_seen_timestamp=first_seen_timestamp or datetime.now(timezone.utc),
            resolution_confidence=assignment.confidence,
            resolution_reason=assignment.reason_for_merge,
            resolver_version=RESOLVER_VERSION,
        )
        db.add(entity)
        entities_by_index[extracted_index] = entity
    db.flush()

    canonical_entity_by_cluster: dict[int, Entity] = {}
    for assignment in resolution_plan.assignments:
        if assignment.merged:
            continue
        canonical_entity_by_cluster[assignment.canonical_cluster_index] = entities_by_index[
            assignment.extracted_index
        ]

    for assignment in resolution_plan.assignments:
        if not assignment.merged:
            continue
        merged_entity = entities_by_index[assignment.extracted_index]
        canonical_entity = canonical_entity_by_cluster.get(assignment.canonical_cluster_index)
        if canonical_entity is None:
            continue
        merged_entity.merged_into_id = canonical_entity.id
        db.add(
            EntityMergeAudit(
                conversation_id=conversation_id,
                survivor_entity_id=canonical_entity.id,
                merged_entity_ids_json=[merged_entity.id],
                reason_for_merge=assignment.reason_for_merge or "unknown",
                confidence=assignment.confidence,
                resolver_version=RESOLVER_VERSION,
                details_json={
                    "entity_type": assignment.entity_type,
                    "survivor_canonical_name": assignment.canonical_name,
                    "merged_name": merged_entity.name,
                },
            )
        )
    db.flush()

    predicate_registry = PredicateRegistry()

    facts_created = 0
    for extracted_fact in result.facts:
        cluster_index = resolution_plan.resolve_reference(
            extracted_fact.subject_name,
            extracted_fact.subject_type,
        )
        subject_entity = canonical_entity_by_cluster.get(cluster_index) if cluster_index is not None else None
        if subject_entity is None:
            continue
        predicate_decision = predicate_registry.register(
            db,
            value=extracted_fact.predicate,
            kind="fact_predicate",
        )
        db.add(
            Fact(
                conversation_id=conversation_id,
                subject_entity_id=subject_entity.id,
                predicate=predicate_decision.canonical_predicate,
                object_value=extracted_fact.object_value,
                confidence=extracted_fact.confidence,
                source_message_ids_json=extracted_fact.source_message_ids,
            )
        )
        facts_created += 1

    relations_created = 0
    for extracted_relation in result.relations:
        from_cluster_index = resolution_plan.resolve_reference(
            extracted_relation.from_name,
            extracted_relation.from_type,
        )
        to_cluster_index = resolution_plan.resolve_reference(
            extracted_relation.to_name,
            extracted_relation.to_type,
        )
        from_entity = (
            canonical_entity_by_cluster.get(from_cluster_index)
            if from_cluster_index is not None
            else None
        )
        to_entity = canonical_entity_by_cluster.get(to_cluster_index) if to_cluster_index is not None else None
        if from_entity is None or to_entity is None:
            continue
        relation_type_decision = predicate_registry.register(
            db,
            value=extracted_relation.relation_type,
            kind="relation_type",
        )
        db.add(
            Relation(
                conversation_id=conversation_id,
                from_entity_id=from_entity.id,
                relation_type=relation_type_decision.canonical_predicate,
                to_entity_id=to_entity.id,
                qualifiers_json=extracted_relation.qualifiers,
                source_message_ids_json=extracted_relation.source_message_ids,
            )
        )
        relations_created += 1

    db.commit()
    return {"entities": len(result.entities), "facts": facts_created, "relations": relations_created}


def _first_seen_timestamp(
    source_message_ids: list[int],
    message_timestamps: dict[int, datetime],
) -> datetime | None:
    timestamps = [
        message_timestamps[message_id]
        for message_id in source_message_ids
        if message_id in message_timestamps
    ]
    if not timestamps:
        return None
    return min(timestamps)


def _apply_schema_governance_normalization(result: ExtractionResult) -> None:
    """Enforce controlled entity types on extracted outputs before persistence."""

    for entity in result.entities:
        entity.entity_type = normalize_entity_type(entity.entity_type)
    for fact in result.facts:
        fact.subject_type = normalize_entity_type(fact.subject_type)
    for relation in result.relations:
        relation.from_type = normalize_entity_type(relation.from_type)
        relation.to_type = normalize_entity_type(relation.to_type)
