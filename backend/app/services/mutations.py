"""Mutation services for editable/deletable workspace records."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.fact import Fact
from app.models.message import Message
from app.models.relation import Relation
from app.models.schema_field import SchemaField
from app.models.schema_node import SchemaNode
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
    """Delete a single message row."""

    message = db.scalar(select(Message).where(Message.id == message_id))
    if message is None:
        return False
    db.delete(message)
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
