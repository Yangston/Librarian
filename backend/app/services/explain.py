"""Explainability helpers for facts and relations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.entity import Entity
from app.models.fact import Fact
from app.models.message import Message
from app.models.relation import Relation
from app.models.resolution_event import ResolutionEvent
from app.models.schema_field import SchemaField
from app.models.schema_relation import SchemaRelation
from app.schemas.explain import (
    FactExplainData,
    RelationExplainData,
    SchemaCanonicalizationInfo,
    SourceMessageEvidence,
)
from app.schemas.fact import FactRead, FactWithSubjectRead
from app.schemas.relation import RelationRead, RelationWithEntitiesRead
from app.schemas.resolution_event import ResolutionEventRead


def get_fact_explain(db: Session, conversation_id: str, fact_id: int) -> FactExplainData | None:
    """Return fact explainability details scoped to a conversation."""

    stmt = (
        select(Fact, Entity.name.label("subject_entity_name"))
        .join(Entity, Entity.id == Fact.subject_entity_id)
        .where(Fact.conversation_id == conversation_id, Fact.id == fact_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return _build_fact_explain_payload(db, row[0], row[1])


def get_fact_explain_by_id(db: Session, fact_id: int) -> FactExplainData | None:
    """Return fact explainability details by ID across all conversations."""

    stmt = (
        select(Fact, Entity.name.label("subject_entity_name"))
        .join(Entity, Entity.id == Fact.subject_entity_id)
        .where(Fact.id == fact_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return _build_fact_explain_payload(db, row[0], row[1])


def get_relation_explain(db: Session, conversation_id: str, relation_id: int) -> RelationExplainData | None:
    """Return relation explainability details scoped to a conversation."""

    from_entity = aliased(Entity)
    to_entity = aliased(Entity)
    stmt = (
        select(
            Relation,
            from_entity.name.label("from_entity_name"),
            to_entity.name.label("to_entity_name"),
        )
        .join(from_entity, from_entity.id == Relation.from_entity_id)
        .join(to_entity, to_entity.id == Relation.to_entity_id)
        .where(Relation.conversation_id == conversation_id, Relation.id == relation_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return _build_relation_explain_payload(db, row[0], row[1], row[2])


def get_relation_explain_by_id(db: Session, relation_id: int) -> RelationExplainData | None:
    """Return relation explainability details by ID across all conversations."""

    from_entity = aliased(Entity)
    to_entity = aliased(Entity)
    stmt = (
        select(
            Relation,
            from_entity.name.label("from_entity_name"),
            to_entity.name.label("to_entity_name"),
        )
        .join(from_entity, from_entity.id == Relation.from_entity_id)
        .join(to_entity, to_entity.id == Relation.to_entity_id)
        .where(Relation.id == relation_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return _build_relation_explain_payload(db, row[0], row[1], row[2])


def _build_fact_explain_payload(db: Session, fact: Fact, subject_name: str) -> FactExplainData:
    source_messages = _get_source_messages(db, fact.conversation_id, fact.source_message_ids_json)
    resolution_events = _list_resolution_events(
        db,
        conversation_id=fact.conversation_id,
        entity_ids=[fact.subject_entity_id],
    )
    return FactExplainData(
        fact=FactWithSubjectRead(
            **FactRead.model_validate(fact).model_dump(),
            subject_entity_name=subject_name,
        ),
        extractor_run_id=fact.extractor_run_id,
        source_messages=source_messages,
        resolution_events=resolution_events,
        schema_canonicalization=_schema_info_for_fact(db, fact),
        snippets=_fact_snippets(fact, source_messages),
    )


def _build_relation_explain_payload(
    db: Session,
    relation: Relation,
    from_name: str,
    to_name: str,
) -> RelationExplainData:
    source_messages = _get_source_messages(db, relation.conversation_id, relation.source_message_ids_json)
    snippets = []
    qualifier_snippet = relation.qualifiers_json.get("snippet") if relation.qualifiers_json else None
    if isinstance(qualifier_snippet, str):
        snippets.append(qualifier_snippet)
    snippets.extend([m.content for m in source_messages if relation.relation_type.lower() in m.content.lower()])
    resolution_events = _list_resolution_events(
        db,
        conversation_id=relation.conversation_id,
        entity_ids=[relation.from_entity_id, relation.to_entity_id],
    )
    return RelationExplainData(
        relation=RelationWithEntitiesRead(
            **RelationRead.model_validate(relation).model_dump(),
            from_entity_name=from_name,
            to_entity_name=to_name,
        ),
        extractor_run_id=relation.extractor_run_id,
        source_messages=source_messages,
        resolution_events=resolution_events,
        schema_canonicalization=_schema_info_for_relation(db, relation),
        snippets=list(dict.fromkeys(snippets)),
    )


def _list_resolution_events(
    db: Session,
    *,
    conversation_id: str,
    entity_ids: list[int],
) -> list[ResolutionEventRead]:
    event_rows = list(
        db.scalars(
            select(ResolutionEvent)
            .where(ResolutionEvent.conversation_id == conversation_id)
            .order_by(ResolutionEvent.id.asc())
        )
    )
    target_ids = set(entity_ids)
    relevant = []
    for event in event_rows:
        event_ids = set(event.entity_ids_json or [])
        if event_ids.intersection(target_ids):
            relevant.append(event)
    return [ResolutionEventRead.model_validate(event) for event in relevant]


def _schema_info_for_fact(db: Session, fact: Fact) -> SchemaCanonicalizationInfo:
    return _schema_info(
        db,
        table_name="schema_fields",
        label=fact.predicate,
        model_cls=SchemaField,
    )


def _schema_info_for_relation(db: Session, relation: Relation) -> SchemaCanonicalizationInfo:
    return _schema_info(
        db,
        table_name="schema_relations",
        label=relation.relation_type,
        model_cls=SchemaRelation,
    )


def _schema_info(
    db: Session,
    *,
    table_name: str,
    label: str,
    model_cls: type[SchemaField] | type[SchemaRelation],
) -> SchemaCanonicalizationInfo:
    row = db.scalar(select(model_cls).where(model_cls.label == label))
    if row is None:
        return SchemaCanonicalizationInfo(
            registry_table=table_name,
            observed_label=label,
            canonical_label=None,
            canonical_id=None,
            status="unregistered",
        )
    canonical_of_id = row.canonical_of_id
    if canonical_of_id is None:
        return SchemaCanonicalizationInfo(
            registry_table=table_name,
            observed_label=label,
            canonical_label=row.label,
            canonical_id=row.id,
            status="canonical",
        )
    canonical_row = db.scalar(select(model_cls).where(model_cls.id == canonical_of_id))
    return SchemaCanonicalizationInfo(
        registry_table=table_name,
        observed_label=label,
        canonical_label=canonical_row.label if canonical_row is not None else None,
        canonical_id=canonical_of_id,
        status="canonicalized",
    )


def _get_source_messages(db: Session, conversation_id: str, source_message_ids: list[int]) -> list[SourceMessageEvidence]:
    if not source_message_ids:
        return []
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.id.in_(source_message_ids))
        .order_by(Message.timestamp.asc(), Message.id.asc())
    )
    messages = list(db.scalars(stmt).all())
    return [SourceMessageEvidence.model_validate(message, from_attributes=True) for message in messages]


def _fact_snippets(fact: Fact, source_messages: list[SourceMessageEvidence]) -> list[str]:
    snippets: list[str] = []
    for message in source_messages:
        content_lower = message.content.lower()
        if fact.object_value.lower() in content_lower or fact.predicate.lower() in content_lower:
            snippets.append(message.content)
    return list(dict.fromkeys(snippets))
