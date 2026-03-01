"""Mutation services for editable/deletable workspace records."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractedFact, ExtractedRelation, ExtractionResult
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.entity_merge_audit import EntityMergeAudit
from app.models.extractor_run import ExtractorRun
from app.models.fact import Fact
from app.models.message import Message
from app.models.predicate_registry_entry import PredicateRegistryEntry
from app.models.resolution_event import ResolutionEvent
from app.models.relation import Relation
from app.models.schema_field import SchemaField
from app.models.schema_node import SchemaNode
from app.models.schema_proposal import SchemaProposal
from app.models.schema_relation import SchemaRelation
from app.schemas.entity import EntityRead
from app.schemas.fact import FactRead, FactWithSubjectRead
from app.schemas.mutations import (
    EntityUpdateRequest,
    FactUpdateRequest,
    MessageUpdateRequest,
    RelationUpdateRequest,
    SchemaFieldMutationRead,
    SchemaFieldUpdateRequest,
    SchemaNodeMutationRead,
    SchemaNodeUpdateRequest,
    SchemaRelationMutationRead,
    SchemaRelationUpdateRequest,
)
from app.schemas.relation import RelationRead, RelationWithEntitiesRead
from app.services.extraction import run_extraction_for_conversation


def update_message(db: Session, message_id: int, payload: MessageUpdateRequest) -> Message | None:
    """Update editable fields for one message."""

    message = db.scalar(select(Message).where(Message.id == message_id))
    if message is None:
        return None
    if payload.role is not None:
        message.role = payload.role
    if payload.content is not None:
        message.content = payload.content.strip()
    db.commit()
    db.refresh(message)
    return message


def delete_message(db: Session, message_id: int) -> bool:
    """Delete one message and rederive conversation knowledge from remaining messages."""

    message = db.scalar(select(Message).where(Message.id == message_id))
    if message is None:
        return False
    conversation_id = message.conversation_id
    db.delete(message)
    db.flush()

    remaining_message_ids = set(
        db.scalars(select(Message.id).where(Message.conversation_id == conversation_id)).all()
    )
    replay_result = _build_filtered_replay_result(db, conversation_id, remaining_message_ids)

    _clear_conversation_derived_state(db, conversation_id, clear_messages=False)
    if remaining_message_ids and replay_result is not None:
        run_extraction_for_conversation(
            db,
            conversation_id,
            extractor=_ReplayExtractor(replay_result),
            post_processing_mode="inline",
        )

    _rebuild_global_derived_state(db)
    db.commit()
    return True


def delete_conversation(db: Session, conversation_id: str) -> bool:
    """Delete a conversation and all derived records tied to it."""

    clean_conversation_id = conversation_id.strip()
    if not clean_conversation_id:
        return False

    has_records = _conversation_has_any_records(db, clean_conversation_id)
    if not has_records:
        return False

    _clear_conversation_derived_state(db, clean_conversation_id, clear_messages=True)
    _rebuild_global_derived_state(db)
    db.commit()
    return True


def update_entity(db: Session, entity_id: int, payload: EntityUpdateRequest) -> EntityRead | None:
    """Update editable fields for one entity record."""

    entity = db.scalar(select(Entity).where(Entity.id == entity_id))
    if entity is None:
        return None

    if payload.canonical_name is not None:
        entity.canonical_name = payload.canonical_name.strip()
        if payload.display_name is None:
            entity.display_name = entity.canonical_name
    if payload.display_name is not None:
        entity.display_name = payload.display_name.strip()
    if payload.type_label is not None:
        clean = payload.type_label.strip()
        entity.type_label = clean
        if payload.type is None:
            entity.type = clean
    if payload.type is not None:
        clean_type = payload.type.strip()
        entity.type = clean_type
        if payload.type_label is None:
            entity.type_label = clean_type
    if payload.known_aliases_json is not None:
        entity.known_aliases_json = _clean_string_list(payload.known_aliases_json)
    if payload.aliases_json is not None:
        entity.aliases_json = _clean_string_list(payload.aliases_json)
    if payload.tags_json is not None:
        entity.tags_json = _clean_string_list(payload.tags_json)

    db.commit()
    db.refresh(entity)
    return EntityRead.model_validate(entity)


def delete_entity(db: Session, entity_id: int) -> bool:
    """Delete an entity and dependent rows used by the workspace."""

    entity = db.scalar(select(Entity).where(Entity.id == entity_id))
    if entity is None:
        return False

    db.execute(delete(Fact).where(Fact.subject_entity_id == entity_id))
    db.execute(
        delete(Relation).where(
            or_(Relation.from_entity_id == entity_id, Relation.to_entity_id == entity_id)
        )
    )
    db.execute(delete(ConversationEntityLink).where(ConversationEntityLink.entity_id == entity_id))
    db.execute(update(Entity).where(Entity.merged_into_id == entity_id).values(merged_into_id=None))
    db.delete(entity)
    db.commit()
    return True


def update_fact(db: Session, fact_id: int, payload: FactUpdateRequest) -> FactWithSubjectRead | None:
    """Update editable fields for a fact row."""

    fact = db.scalar(select(Fact).where(Fact.id == fact_id))
    if fact is None:
        return None
    if payload.subject_entity_id is not None:
        subject = db.scalar(select(Entity).where(Entity.id == payload.subject_entity_id))
        if subject is None:
            return None
        fact.subject_entity_id = payload.subject_entity_id
    if payload.predicate is not None:
        fact.predicate = payload.predicate.strip()
    if payload.object_value is not None:
        fact.object_value = payload.object_value.strip()
    if payload.scope is not None:
        fact.scope = payload.scope.strip()
    if payload.confidence is not None:
        fact.confidence = payload.confidence

    db.commit()
    db.refresh(fact)
    return _fact_with_subject(db, fact)


def delete_fact(db: Session, fact_id: int) -> bool:
    """Delete one fact row."""

    fact = db.scalar(select(Fact).where(Fact.id == fact_id))
    if fact is None:
        return False
    db.delete(fact)
    db.commit()
    return True


def update_relation(
    db: Session,
    relation_id: int,
    payload: RelationUpdateRequest,
) -> RelationWithEntitiesRead | None:
    """Update editable fields for one relation row."""

    relation = db.scalar(select(Relation).where(Relation.id == relation_id))
    if relation is None:
        return None

    if payload.from_entity_id is not None:
        from_entity = db.scalar(select(Entity).where(Entity.id == payload.from_entity_id))
        if from_entity is None:
            return None
        relation.from_entity_id = payload.from_entity_id
    if payload.to_entity_id is not None:
        to_entity = db.scalar(select(Entity).where(Entity.id == payload.to_entity_id))
        if to_entity is None:
            return None
        relation.to_entity_id = payload.to_entity_id
    if payload.relation_type is not None:
        relation.relation_type = payload.relation_type.strip()
    if payload.scope is not None:
        relation.scope = payload.scope.strip()
    if payload.confidence is not None:
        relation.confidence = payload.confidence
    if payload.qualifiers_json is not None:
        relation.qualifiers_json = payload.qualifiers_json

    db.commit()
    db.refresh(relation)
    return _relation_with_entities(db, relation.id)


def delete_relation(db: Session, relation_id: int) -> bool:
    """Delete one relation row."""

    relation = db.scalar(select(Relation).where(Relation.id == relation_id))
    if relation is None:
        return False
    db.delete(relation)
    db.commit()
    return True


def update_schema_node(
    db: Session,
    schema_node_id: int,
    payload: SchemaNodeUpdateRequest,
) -> SchemaNodeMutationRead | None:
    """Update one schema node row."""

    row = db.scalar(select(SchemaNode).where(SchemaNode.id == schema_node_id))
    if row is None:
        return None
    if payload.label is not None:
        row.label = payload.label.strip()
    if payload.description is not None:
        row.description = payload.description.strip() or None
    if payload.examples_json is not None:
        row.examples_json = _clean_string_list(payload.examples_json)
    db.commit()
    db.refresh(row)
    return SchemaNodeMutationRead.model_validate(row)


def delete_schema_node(db: Session, schema_node_id: int) -> bool:
    """Delete one schema node row."""

    row = db.scalar(select(SchemaNode).where(SchemaNode.id == schema_node_id))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def update_schema_field(
    db: Session,
    schema_field_id: int,
    payload: SchemaFieldUpdateRequest,
) -> SchemaFieldMutationRead | None:
    """Update one schema field row."""

    row = db.scalar(select(SchemaField).where(SchemaField.id == schema_field_id))
    if row is None:
        return None
    if payload.label is not None:
        row.label = payload.label.strip()
    if payload.description is not None:
        row.description = payload.description.strip() or None
    if payload.examples_json is not None:
        row.examples_json = _clean_string_list(payload.examples_json)
    if payload.canonical_of_id is not None:
        canonical = db.scalar(select(SchemaField).where(SchemaField.id == payload.canonical_of_id))
        if canonical is None:
            return None
        row.canonical_of_id = payload.canonical_of_id
    db.commit()
    db.refresh(row)
    return SchemaFieldMutationRead.model_validate(row)


def delete_schema_field(db: Session, schema_field_id: int) -> bool:
    """Delete one schema field row."""

    row = db.scalar(select(SchemaField).where(SchemaField.id == schema_field_id))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def update_schema_relation(
    db: Session,
    schema_relation_id: int,
    payload: SchemaRelationUpdateRequest,
) -> SchemaRelationMutationRead | None:
    """Update one schema relation row."""

    row = db.scalar(select(SchemaRelation).where(SchemaRelation.id == schema_relation_id))
    if row is None:
        return None
    if payload.label is not None:
        row.label = payload.label.strip()
    if payload.description is not None:
        row.description = payload.description.strip() or None
    if payload.examples_json is not None:
        row.examples_json = _clean_string_list(payload.examples_json)
    if payload.canonical_of_id is not None:
        canonical = db.scalar(select(SchemaRelation).where(SchemaRelation.id == payload.canonical_of_id))
        if canonical is None:
            return None
        row.canonical_of_id = payload.canonical_of_id
    db.commit()
    db.refresh(row)
    return SchemaRelationMutationRead.model_validate(row)


def delete_schema_relation(db: Session, schema_relation_id: int) -> bool:
    """Delete one schema relation row."""

    row = db.scalar(select(SchemaRelation).where(SchemaRelation.id == schema_relation_id))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def _fact_with_subject(db: Session, fact: Fact) -> FactWithSubjectRead:
    subject = db.scalar(select(Entity).where(Entity.id == fact.subject_entity_id))
    subject_name = subject.name if subject is not None else ""
    return FactWithSubjectRead(
        **FactRead.model_validate(fact).model_dump(),
        subject_entity_name=subject_name,
    )


def _relation_with_entities(db: Session, relation_id: int) -> RelationWithEntitiesRead | None:
    from_entity = aliased(Entity)
    to_entity = aliased(Entity)
    row = db.execute(
        select(
            Relation,
            from_entity.name.label("from_entity_name"),
            to_entity.name.label("to_entity_name"),
        )
        .join(from_entity, from_entity.id == Relation.from_entity_id)
        .join(to_entity, to_entity.id == Relation.to_entity_id)
        .where(Relation.id == relation_id)
    ).one_or_none()
    if row is None:
        return None
    relation, from_name, to_name = row
    return RelationWithEntitiesRead(
        **RelationRead.model_validate(relation).model_dump(),
        from_entity_name=from_name,
        to_entity_name=to_name,
    )


def _clean_string_list(values: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def _find_replacement_conversation_for_entity(
    db: Session, entity_id: int, conversation_id: str
) -> str | None:
    linked_conversation = db.scalar(
        select(ConversationEntityLink.conversation_id)
        .where(
            ConversationEntityLink.entity_id == entity_id,
            ConversationEntityLink.conversation_id != conversation_id,
        )
        .order_by(ConversationEntityLink.id.asc())
        .limit(1)
    )
    if linked_conversation is not None:
        return linked_conversation

    fact_conversation = db.scalar(
        select(Fact.conversation_id)
        .where(Fact.subject_entity_id == entity_id, Fact.conversation_id != conversation_id)
        .order_by(Fact.id.asc())
        .limit(1)
    )
    if fact_conversation is not None:
        return fact_conversation

    relation_conversation = db.scalar(
        select(Relation.conversation_id)
        .where(
            Relation.conversation_id != conversation_id,
            or_(Relation.from_entity_id == entity_id, Relation.to_entity_id == entity_id),
        )
        .order_by(Relation.id.asc())
        .limit(1)
    )
    if relation_conversation is not None:
        return relation_conversation

    merged_reference = db.scalar(
        select(Entity.conversation_id)
        .where(Entity.merged_into_id == entity_id, Entity.conversation_id != conversation_id)
        .order_by(Entity.id.asc())
        .limit(1)
    )
    return merged_reference


def _conversation_has_any_records(db: Session, conversation_id: str) -> bool:
    return any(
        [
            db.scalar(select(Message.id).where(Message.conversation_id == conversation_id).limit(1))
            is not None,
            db.scalar(select(Fact.id).where(Fact.conversation_id == conversation_id).limit(1))
            is not None,
            db.scalar(select(Relation.id).where(Relation.conversation_id == conversation_id).limit(1))
            is not None,
            db.scalar(
                select(ConversationEntityLink.id)
                .where(ConversationEntityLink.conversation_id == conversation_id)
                .limit(1)
            )
            is not None,
            db.scalar(select(ResolutionEvent.id).where(ResolutionEvent.conversation_id == conversation_id).limit(1))
            is not None,
            db.scalar(
                select(EntityMergeAudit.id).where(EntityMergeAudit.conversation_id == conversation_id).limit(1)
            )
            is not None,
            db.scalar(select(ExtractorRun.id).where(ExtractorRun.conversation_id == conversation_id).limit(1))
            is not None,
            db.scalar(select(Entity.id).where(Entity.conversation_id == conversation_id).limit(1))
            is not None,
        ]
    )


def _clear_conversation_derived_state(db: Session, conversation_id: str, *, clear_messages: bool) -> None:
    db.execute(delete(Relation).where(Relation.conversation_id == conversation_id))
    db.execute(delete(Fact).where(Fact.conversation_id == conversation_id))
    db.execute(delete(ConversationEntityLink).where(ConversationEntityLink.conversation_id == conversation_id))
    db.execute(delete(ResolutionEvent).where(ResolutionEvent.conversation_id == conversation_id))
    db.execute(delete(EntityMergeAudit).where(EntityMergeAudit.conversation_id == conversation_id))
    db.execute(delete(ExtractorRun).where(ExtractorRun.conversation_id == conversation_id))
    if clear_messages:
        db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    db.flush()

    origin_entities = list(db.scalars(select(Entity).where(Entity.conversation_id == conversation_id)).all())
    for entity in origin_entities:
        replacement_conversation = _find_replacement_conversation_for_entity(db, entity.id, conversation_id)
        if replacement_conversation is not None:
            entity.conversation_id = replacement_conversation
            continue
        db.execute(update(Entity).where(Entity.merged_into_id == entity.id).values(merged_into_id=None))
        db.execute(delete(ConversationEntityLink).where(ConversationEntityLink.entity_id == entity.id))
        db.delete(entity)
    db.flush()


def _rebuild_global_derived_state(db: Session) -> None:
    # Schema proposals do not carry durable provenance; clear and allow regeneration.
    db.execute(delete(SchemaProposal))
    db.execute(delete(SchemaRelation))
    db.execute(delete(SchemaField))
    db.execute(delete(SchemaNode))
    db.execute(delete(PredicateRegistryEntry))
    db.flush()
    active_entities = list(
        db.execute(
            select(
                Entity.type_label,
                Entity.canonical_name,
                Entity.conversation_id,
            ).where(Entity.merged_into_id.is_(None))
        ).all()
    )
    node_examples: dict[str, list[str]] = defaultdict(list)
    node_counts: dict[str, int] = defaultdict(int)
    node_last_seen: dict[str, str] = {}
    for type_label, canonical_name, conversation_id in active_entities:
        label = str(type_label or "").strip()
        if not label:
            continue
        node_counts[label] += 1
        node_last_seen[label] = str(conversation_id)
        example = str(canonical_name or "").strip()
        if example and example not in node_examples[label] and len(node_examples[label]) < 8:
            node_examples[label].append(example)
    for label in sorted(node_counts.keys()):
        db.add(
            SchemaNode(
                label=label,
                examples_json=node_examples[label],
                stats_json={
                    "observations": node_counts[label],
                    "last_seen_conversation_id": node_last_seen.get(label),
                },
            )
        )

    fact_rows = list(
        db.execute(
            select(
                Fact.predicate,
                Fact.object_value,
                Fact.conversation_id,
                Entity.canonical_name,
            ).join(Entity, Entity.id == Fact.subject_entity_id)
        ).all()
    )
    field_examples: dict[str, list[str]] = defaultdict(list)
    field_counts: dict[str, int] = defaultdict(int)
    field_last_seen: dict[str, str] = {}
    fact_predicate_counts: dict[str, int] = defaultdict(int)
    for predicate, object_value, conversation_id, canonical_name in fact_rows:
        label = str(predicate or "").strip()
        if not label:
            continue
        field_counts[label] += 1
        field_last_seen[label] = str(conversation_id)
        fact_predicate_counts[label] += 1
        subject = str(canonical_name or "").strip()
        value = str(object_value or "").strip()
        example = f"{subject}: {value}".strip(": ")
        if example and example not in field_examples[label] and len(field_examples[label]) < 8:
            field_examples[label].append(example)
    for label in sorted(field_counts.keys()):
        db.add(
            SchemaField(
                label=label,
                examples_json=field_examples[label],
                stats_json={
                    "observations": field_counts[label],
                    "last_seen_conversation_id": field_last_seen.get(label),
                },
            )
        )
    for predicate, frequency in fact_predicate_counts.items():
        db.add(
            PredicateRegistryEntry(
                kind="fact_predicate",
                predicate=predicate,
                aliases_json=[predicate],
                frequency=int(frequency),
            )
        )

    from_entity = aliased(Entity)
    to_entity = aliased(Entity)
    relation_rows = list(
        db.execute(
            select(
                Relation.relation_type,
                Relation.conversation_id,
                from_entity.canonical_name.label("from_name"),
                to_entity.canonical_name.label("to_name"),
            )
            .join(from_entity, from_entity.id == Relation.from_entity_id)
            .join(to_entity, to_entity.id == Relation.to_entity_id)
        ).all()
    )
    relation_examples: dict[str, list[str]] = defaultdict(list)
    relation_counts: dict[str, int] = defaultdict(int)
    relation_last_seen: dict[str, str] = {}
    relation_type_counts: dict[str, int] = defaultdict(int)
    for relation_type, conversation_id, from_name, to_name in relation_rows:
        label = str(relation_type or "").strip()
        if not label:
            continue
        relation_counts[label] += 1
        relation_last_seen[label] = str(conversation_id)
        relation_type_counts[label] += 1
        source = str(from_name or "").strip()
        target = str(to_name or "").strip()
        example = f"{source} {label} {target}".strip()
        if example and example not in relation_examples[label] and len(relation_examples[label]) < 8:
            relation_examples[label].append(example)
    for label in sorted(relation_counts.keys()):
        db.add(
            SchemaRelation(
                label=label,
                examples_json=relation_examples[label],
                stats_json={
                    "observations": relation_counts[label],
                    "last_seen_conversation_id": relation_last_seen.get(label),
                },
            )
        )
    for relation_type, frequency in relation_type_counts.items():
        db.add(
            PredicateRegistryEntry(
                kind="relation_type",
                predicate=relation_type,
                aliases_json=[relation_type],
                frequency=int(frequency),
            )
        )

    db.flush()


def _build_filtered_replay_result(
    db: Session, conversation_id: str, allowed_message_ids: set[int]
) -> ExtractionResult | None:
    if not allowed_message_ids:
        return ExtractionResult()
    latest_run = db.scalar(
        select(ExtractorRun)
        .where(ExtractorRun.conversation_id == conversation_id)
        .order_by(ExtractorRun.id.desc())
        .limit(1)
    )
    if latest_run is None or not isinstance(latest_run.validated_output_json, dict):
        return None
    payload = latest_run.validated_output_json

    entities: list[ExtractedEntity] = []
    for row in _coerce_dict_list(payload.get("entities")):
        source_ids = _coerce_int_list(row.get("source_message_ids"))
        if source_ids:
            source_ids = [message_id for message_id in source_ids if message_id in allowed_message_ids]
            if not source_ids:
                continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        entities.append(
            ExtractedEntity(
                name=name,
                type_label=str(row.get("type_label")).strip() if row.get("type_label") is not None else None,
                confidence=float(row.get("confidence", 0.0) or 0.0),
                source_message_ids=source_ids,
                aliases=_coerce_str_list(row.get("aliases")),
                tags=_coerce_str_list(row.get("tags")),
            )
        )

    facts: list[ExtractedFact] = []
    for row in _coerce_dict_list(payload.get("facts")):
        source_ids = [
            message_id
            for message_id in _coerce_int_list(row.get("source_message_ids"))
            if message_id in allowed_message_ids
        ]
        if not source_ids:
            continue
        entity_name = str(row.get("entity_name") or "").strip()
        field_label = str(row.get("field_label") or "").strip()
        value_text = str(row.get("value_text") or "").strip()
        if not entity_name or not field_label or not value_text:
            continue
        facts.append(
            ExtractedFact(
                entity_name=entity_name,
                field_label=field_label,
                value_text=value_text,
                confidence=float(row.get("confidence", 0.0) or 0.0),
                source_message_ids=source_ids,
                snippet=str(row.get("snippet")).strip() if row.get("snippet") is not None else None,
            )
        )

    relations: list[ExtractedRelation] = []
    for row in _coerce_dict_list(payload.get("relations")):
        source_ids = [
            message_id
            for message_id in _coerce_int_list(row.get("source_message_ids"))
            if message_id in allowed_message_ids
        ]
        if not source_ids:
            continue
        from_entity = str(row.get("from_entity") or "").strip()
        relation_label = str(row.get("relation_label") or "").strip()
        to_entity = str(row.get("to_entity") or "").strip()
        if not from_entity or not relation_label or not to_entity:
            continue
        qualifiers_raw = row.get("qualifiers")
        qualifiers = qualifiers_raw if isinstance(qualifiers_raw, dict) else {}
        relations.append(
            ExtractedRelation(
                from_entity=from_entity,
                relation_label=relation_label,
                to_entity=to_entity,
                qualifiers=dict(qualifiers),
                confidence=float(row.get("confidence", 0.0) or 0.0),
                source_message_ids=source_ids,
                snippet=str(row.get("snippet")).strip() if row.get("snippet") is not None else None,
            )
        )

    return ExtractionResult(entities=entities, facts=facts, relations=relations)


def _coerce_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        cleaned.append(text)
    return cleaned


def _coerce_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    items: list[int] = []
    for item in value:
        try:
            number = int(item)
        except (TypeError, ValueError):
            continue
        items.append(number)
    return items


class _ReplayExtractor(ExtractorInterface):
    def __init__(self, result: ExtractionResult):
        self._result = result
        self.model_name = "replay_extractor"
        self.prompt_version = "replay/latest_extractor_run"

    def extract(self, messages: list[Message]) -> ExtractionResult:
        return self._result
