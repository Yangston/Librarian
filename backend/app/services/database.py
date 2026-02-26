"""Query services for transparent database views."""

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.entity import Entity
from app.models.entity_merge_audit import EntityMergeAudit
from app.models.fact import Fact
from app.models.relation import Relation
from app.schemas.fact import FactRead, FactWithSubjectRead
from app.schemas.relation import RelationRead, RelationWithEntitiesRead


def list_entities(db: Session, conversation_id: str) -> list[Entity]:
    """List entities for a conversation."""

    stmt = (
        select(Entity)
        .where(Entity.conversation_id == conversation_id)
        .order_by(Entity.type.asc(), Entity.name.asc(), Entity.id.asc())
    )
    return list(db.scalars(stmt).all())


def list_entity_merge_audits(db: Session, conversation_id: str) -> list[EntityMergeAudit]:
    """List entity merge audits for a conversation."""

    stmt = (
        select(EntityMergeAudit)
        .where(EntityMergeAudit.conversation_id == conversation_id)
        .order_by(EntityMergeAudit.id.asc())
    )
    return list(db.scalars(stmt).all())


def list_facts(db: Session, conversation_id: str) -> list[FactWithSubjectRead]:
    """List facts with subject entity names for a conversation."""

    stmt = (
        select(Fact, Entity.name.label("subject_entity_name"))
        .join(Entity, Entity.id == Fact.subject_entity_id)
        .where(Fact.conversation_id == conversation_id)
        .order_by(Fact.id.asc())
    )
    rows = db.execute(stmt).all()
    return [
        FactWithSubjectRead(
            **FactRead.model_validate(fact).model_dump(),
            subject_entity_name=subject_entity_name,
        )
        for fact, subject_entity_name in rows
    ]


def list_relations(db: Session, conversation_id: str) -> list[RelationWithEntitiesRead]:
    """List relations with endpoint names for a conversation."""

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
        .where(Relation.conversation_id == conversation_id)
        .order_by(Relation.id.asc())
    )
    rows = db.execute(stmt).all()
    return [
        RelationWithEntitiesRead(
            **RelationRead.model_validate(relation).model_dump(),
            from_entity_name=from_name,
            to_entity_name=to_name,
        )
        for relation, from_name, to_name in rows
    ]
