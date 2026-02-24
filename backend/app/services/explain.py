"""Explainability helpers for facts and relations."""

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.entity import Entity
from app.models.fact import Fact
from app.models.message import Message
from app.models.relation import Relation
from app.schemas.explain import FactExplainData, RelationExplainData, SourceMessageEvidence
from app.schemas.fact import FactRead, FactWithSubjectRead
from app.schemas.relation import RelationRead, RelationWithEntitiesRead


def get_fact_explain(db: Session, conversation_id: str, fact_id: int) -> FactExplainData | None:
    """Return fact explainability details."""

    stmt = (
        select(Fact, Entity.name.label("subject_entity_name"))
        .join(Entity, Entity.id == Fact.subject_entity_id)
        .where(Fact.conversation_id == conversation_id, Fact.id == fact_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None

    fact, subject_name = row
    source_messages = _get_source_messages(db, conversation_id, fact.source_message_ids_json)
    return FactExplainData(
        fact=FactWithSubjectRead(
            **FactRead.model_validate(fact).model_dump(),
            subject_entity_name=subject_name,
        ),
        source_messages=source_messages,
        snippets=_fact_snippets(fact, source_messages),
    )


def get_relation_explain(db: Session, conversation_id: str, relation_id: int) -> RelationExplainData | None:
    """Return relation explainability details."""

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

    relation, from_name, to_name = row
    source_messages = _get_source_messages(db, conversation_id, relation.source_message_ids_json)
    snippets = []
    qualifier_snippet = relation.qualifiers_json.get("snippet") if relation.qualifiers_json else None
    if isinstance(qualifier_snippet, str):
        snippets.append(qualifier_snippet)
    snippets.extend([m.content for m in source_messages if relation.relation_type.lower() in m.content.lower()])
    return RelationExplainData(
        relation=RelationWithEntitiesRead(
            **RelationRead.model_validate(relation).model_dump(),
            from_entity_name=from_name,
            to_entity_name=to_name,
        ),
        source_messages=source_messages,
        snippets=list(dict.fromkeys(snippets)),
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
