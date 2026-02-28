"""Knowledge query services for entities and conversation summaries."""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.entity import Entity
from app.models.fact import Fact
from app.models.message import Message
from app.models.relation import Relation
from app.models.schema_field import SchemaField
from app.models.schema_node import SchemaNode
from app.models.schema_relation import SchemaRelation
from app.schemas.entity import EntityRead
from app.schemas.fact import FactRead, FactWithSubjectRead
from app.schemas.knowledge import (
    ConversationGraphData,
    ConversationSchemaChanges,
    ConversationSummaryData,
    EntityGraphData,
    FactTimelineItem,
    RelationCluster,
)
from app.schemas.relation import RelationRead, RelationWithEntitiesRead
from app.services.database import list_facts, list_relations


def get_entity_record(db: Session, entity_id: int) -> Entity | None:
    """Fetch a single entity record by ID."""

    return db.scalar(select(Entity).where(Entity.id == entity_id))


def get_entity_graph(db: Session, entity_id: int) -> EntityGraphData | None:
    """Return incoming/outgoing relation graph and local facts for an entity."""

    entity = get_entity_record(db, entity_id)
    if entity is None:
        return None

    outgoing = _list_relations_for_entity(db, entity_id=entity_id, direction="outgoing")
    incoming = _list_relations_for_entity(db, entity_id=entity_id, direction="incoming")
    supporting_facts = _list_facts_for_entity(db, entity_id=entity_id)

    related_ids: set[int] = set()
    for relation in outgoing:
        related_ids.add(relation.to_entity_id)
    for relation in incoming:
        related_ids.add(relation.from_entity_id)
    related_ids.discard(entity_id)

    related_entities = []
    if related_ids:
        rows = list(db.scalars(select(Entity).where(Entity.id.in_(sorted(related_ids))).order_by(Entity.id.asc())))
        related_entities = [EntityRead.model_validate(row) for row in rows]

    return EntityGraphData(
        entity=EntityRead.model_validate(entity),
        outgoing_relations=outgoing,
        incoming_relations=incoming,
        related_entities=related_entities,
        supporting_facts=supporting_facts,
    )


def get_entity_timeline(db: Session, entity_id: int) -> list[FactTimelineItem] | None:
    """Return supporting facts for an entity ordered by source message timestamp."""

    entity = get_entity_record(db, entity_id)
    if entity is None:
        return None

    facts = _list_fact_rows_for_entity(db, entity_id=entity_id)
    source_ids = {
        message_id
        for fact in facts
        for message_id in (fact.source_message_ids_json or [])
        if isinstance(message_id, int)
    }
    message_by_id = {}
    if source_ids:
        messages = list(db.scalars(select(Message).where(Message.id.in_(sorted(source_ids)))))
        message_by_id = {message.id: message for message in messages}

    timeline: list[FactTimelineItem] = []
    for fact in facts:
        timestamp = _first_message_timestamp(fact.source_message_ids_json, message_by_id)
        timeline.append(
            FactTimelineItem(
                fact=FactWithSubjectRead(
                    **FactRead.model_validate(fact).model_dump(),
                    subject_entity_name=entity.name,
                ),
                timestamp=timestamp,
            )
        )
    timeline.sort(key=lambda item: (item.timestamp is None, item.timestamp, item.fact.id))
    return timeline


def get_conversation_summary(db: Session, conversation_id: str) -> ConversationSummaryData:
    """Return key entities/facts/schema deltas and relation clusters for a conversation."""

    entities = list(
        db.scalars(
            select(Entity)
            .where(Entity.conversation_id == conversation_id, Entity.merged_into_id.is_(None))
            .order_by(Entity.id.asc())
        )
    )
    entity_by_id = {entity.id: entity for entity in entities}
    facts = list_facts(db, conversation_id)
    relations = list_relations(db, conversation_id)

    support_counter: Counter[int] = Counter()
    for fact in facts:
        support_counter[fact.subject_entity_id] += 1
    for relation in relations:
        support_counter[relation.from_entity_id] += 1
        support_counter[relation.to_entity_id] += 1

    sorted_entities = sorted(
        entities,
        key=lambda entity: (-support_counter.get(entity.id, 0), entity.id),
    )
    key_entities = [EntityRead.model_validate(entity) for entity in sorted_entities[:10]]
    key_facts = sorted(facts, key=lambda fact: (-fact.confidence, fact.id))[:10]

    schema_changes = ConversationSchemaChanges(
        node_labels=_schema_labels_for_conversation(db, SchemaNode, conversation_id),
        field_labels=_schema_labels_for_conversation(db, SchemaField, conversation_id),
        relation_labels=_schema_labels_for_conversation(db, SchemaRelation, conversation_id),
    )

    relation_clusters = _build_relation_clusters(relations, entity_by_id)
    return ConversationSummaryData(
        conversation_id=conversation_id,
        key_entities=key_entities,
        key_facts=key_facts,
        schema_changes_triggered=schema_changes,
        relation_clusters=relation_clusters,
    )


def get_conversation_graph(db: Session, conversation_id: str) -> ConversationGraphData:
    """Return all entities/relations observed in a conversation."""

    entities = list(
        db.scalars(
            select(Entity)
            .where(Entity.conversation_id == conversation_id, Entity.merged_into_id.is_(None))
            .order_by(Entity.canonical_name.asc(), Entity.id.asc())
        )
    )
    entity_by_id = {entity.id: entity for entity in entities}
    relations = list_relations(db, conversation_id)

    # Keep graph complete even if old rows reference entities outside the filtered set.
    missing_entity_ids = {
        relation.from_entity_id
        for relation in relations
        if relation.from_entity_id not in entity_by_id
    }
    missing_entity_ids.update(
        relation.to_entity_id for relation in relations if relation.to_entity_id not in entity_by_id
    )
    if missing_entity_ids:
        for row in db.scalars(select(Entity).where(Entity.id.in_(sorted(missing_entity_ids)))):
            entity_by_id[row.id] = row

    ordered_entities = [EntityRead.model_validate(entity) for entity in sorted(entity_by_id.values(), key=lambda item: item.id)]
    return ConversationGraphData(
        conversation_id=conversation_id,
        entities=ordered_entities,
        relations=relations,
    )


def _list_fact_rows_for_entity(db: Session, *, entity_id: int) -> list[Fact]:
    return list(
        db.scalars(
            select(Fact)
            .where(Fact.subject_entity_id == entity_id)
            .order_by(Fact.created_at.asc(), Fact.id.asc())
        )
    )


def _list_facts_for_entity(db: Session, *, entity_id: int) -> list[FactWithSubjectRead]:
    subject_entity = db.scalar(select(Entity).where(Entity.id == entity_id))
    if subject_entity is None:
        return []
    facts = _list_fact_rows_for_entity(db, entity_id=entity_id)
    return [
        FactWithSubjectRead(
            **FactRead.model_validate(fact).model_dump(),
            subject_entity_name=subject_entity.name,
        )
        for fact in facts
    ]


def _list_relations_for_entity(
    db: Session,
    *,
    entity_id: int,
    direction: str,
) -> list[RelationWithEntitiesRead]:
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
        .order_by(Relation.id.asc())
    )
    if direction == "outgoing":
        stmt = stmt.where(Relation.from_entity_id == entity_id)
    else:
        stmt = stmt.where(Relation.to_entity_id == entity_id)
    rows = db.execute(stmt).all()
    return [
        RelationWithEntitiesRead(
            **RelationRead.model_validate(relation).model_dump(),
            from_entity_name=from_name,
            to_entity_name=to_name,
        )
        for relation, from_name, to_name in rows
    ]


def _schema_labels_for_conversation(
    db: Session,
    model_cls: type[SchemaNode] | type[SchemaField] | type[SchemaRelation],
    conversation_id: str,
) -> list[str]:
    labels = []
    rows = list(db.scalars(select(model_cls).order_by(model_cls.label.asc())))
    for row in rows:
        stats = row.stats_json or {}
        if stats.get("last_seen_conversation_id") == conversation_id:
            labels.append(row.label)
    return labels


def _build_relation_clusters(
    relations: list[RelationWithEntitiesRead],
    entity_by_id: dict[int, Entity],
) -> list[RelationCluster]:
    grouped: dict[str, list[RelationWithEntitiesRead]] = defaultdict(list)
    for relation in relations:
        grouped[relation.relation_type].append(relation)

    clusters: list[RelationCluster] = []
    for label, items in grouped.items():
        sample_edges: list[str] = []
        for relation in items[:5]:
            from_name = entity_by_id.get(relation.from_entity_id, None)
            to_name = entity_by_id.get(relation.to_entity_id, None)
            sample_edges.append(
                f"{from_name.canonical_name if from_name else relation.from_entity_name} -> "
                f"{to_name.canonical_name if to_name else relation.to_entity_name}"
            )
        clusters.append(
            RelationCluster(
                relation_label=label,
                relation_count=len(items),
                sample_edges=sample_edges,
            )
        )
    clusters.sort(key=lambda cluster: (-cluster.relation_count, cluster.relation_label))
    return clusters


def _first_message_timestamp(source_message_ids: list[int], message_by_id: dict[int, Message]):
    timestamps = []
    for message_id in source_message_ids or []:
        message = message_by_id.get(message_id)
        if message is not None:
            timestamps.append(message.timestamp)
    if not timestamps:
        return None
    return min(timestamps)
