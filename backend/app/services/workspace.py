"""Phase 3 workspace query services."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

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
from app.schemas.entity_listing import EntityListItem, EntityListingResponse
from app.schemas.workspace import (
    ConversationListItem,
    ConversationsListResponse,
    RecentEntitiesResponse,
    RecentEntityItem,
    SchemaFieldOverview,
    SchemaNodeOverview,
    SchemaOverviewData,
    SchemaProposalOverview,
    SchemaRelationOverview,
)

_empty_state_verified = False
_empty_state_lock = Lock()


def list_conversations(
    db: Session,
    *,
    limit: int,
    offset: int,
    query: str | None = None,
) -> ConversationsListResponse:
    """Return paginated conversations ordered by latest activity."""

    _ensure_workspace_empty_state_consistent(db)

    message_stats = (
        select(
            Message.conversation_id.label("conversation_id"),
            func.count(Message.id).label("message_count"),
            func.min(Message.timestamp).label("first_message_at"),
            func.max(Message.timestamp).label("last_message_at"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )
    entity_counts = (
        select(
            ConversationEntityLink.conversation_id.label("conversation_id"),
            func.count(ConversationEntityLink.entity_id).label("entity_count"),
        )
        .group_by(ConversationEntityLink.conversation_id)
        .subquery()
    )
    fact_counts = (
        select(Fact.conversation_id.label("conversation_id"), func.count(Fact.id).label("fact_count"))
        .group_by(Fact.conversation_id)
        .subquery()
    )
    relation_counts = (
        select(Relation.conversation_id.label("conversation_id"), func.count(Relation.id).label("relation_count"))
        .group_by(Relation.conversation_id)
        .subquery()
    )
    run_counts = (
        select(
            ExtractorRun.conversation_id.label("conversation_id"),
            func.count(ExtractorRun.id).label("extractor_run_count"),
        )
        .group_by(ExtractorRun.conversation_id)
        .subquery()
    )

    filter_term = (query or "").strip()
    base = select(message_stats.c.conversation_id)
    if filter_term:
        base = base.where(message_stats.c.conversation_id.ilike(f"%{filter_term}%"))
    total = int(db.scalar(select(func.count()).select_from(base.subquery())) or 0)

    stmt = (
        select(
            message_stats.c.conversation_id,
            message_stats.c.first_message_at,
            message_stats.c.last_message_at,
            message_stats.c.message_count,
            func.coalesce(entity_counts.c.entity_count, 0).label("entity_count"),
            func.coalesce(fact_counts.c.fact_count, 0).label("fact_count"),
            func.coalesce(relation_counts.c.relation_count, 0).label("relation_count"),
            func.coalesce(run_counts.c.extractor_run_count, 0).label("extractor_run_count"),
        )
        .outerjoin(entity_counts, entity_counts.c.conversation_id == message_stats.c.conversation_id)
        .outerjoin(fact_counts, fact_counts.c.conversation_id == message_stats.c.conversation_id)
        .outerjoin(relation_counts, relation_counts.c.conversation_id == message_stats.c.conversation_id)
        .outerjoin(run_counts, run_counts.c.conversation_id == message_stats.c.conversation_id)
        .order_by(message_stats.c.last_message_at.desc(), message_stats.c.conversation_id.desc())
        .limit(limit)
        .offset(offset)
    )
    if filter_term:
        stmt = stmt.where(message_stats.c.conversation_id.ilike(f"%{filter_term}%"))

    rows = db.execute(stmt).all()
    items = [
        ConversationListItem(
            conversation_id=row.conversation_id,
            first_message_at=row.first_message_at,
            last_message_at=row.last_message_at,
            message_count=int(row.message_count or 0),
            entity_count=int(row.entity_count or 0),
            fact_count=int(row.fact_count or 0),
            relation_count=int(row.relation_count or 0),
            extractor_run_count=int(row.extractor_run_count or 0),
        )
        for row in rows
    ]
    return ConversationsListResponse(items=items, total=total, limit=limit, offset=offset)


def list_recent_entities(db: Session, *, limit: int) -> RecentEntitiesResponse:
    """Return recently updated canonical entities."""

    _ensure_workspace_empty_state_consistent(db)

    conversation_counts = (
        select(
            ConversationEntityLink.entity_id.label("entity_id"),
            func.count(ConversationEntityLink.id).label("conversation_count"),
        )
        .group_by(ConversationEntityLink.entity_id)
        .subquery()
    )
    stmt = (
        select(
            Entity,
            func.coalesce(conversation_counts.c.conversation_count, 0).label("conversation_count"),
        )
        .outerjoin(conversation_counts, conversation_counts.c.entity_id == Entity.id)
        .where(Entity.merged_into_id.is_(None))
        .order_by(Entity.updated_at.desc(), Entity.id.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    items = [
        RecentEntityItem(
            entity_id=entity.id,
            canonical_name=entity.canonical_name,
            display_name=entity.display_name,
            type_label=entity.type_label,
            alias_count=_alias_count(entity),
            first_seen=entity.first_seen_timestamp,
            last_seen=entity.updated_at,
            conversation_count=int(conversation_count or 0),
        )
        for entity, conversation_count in rows
    ]
    return RecentEntitiesResponse(items=items)


def list_entities_catalog(
    db: Session,
    *,
    limit: int,
    offset: int,
    sort: str,
    order: str,
    query: str | None = None,
    type_label: str | None = None,
    selected_fields: list[str] | None = None,
) -> EntityListingResponse:
    """Return global entities table rows with optional dynamic fact columns."""

    _ensure_workspace_empty_state_consistent(db)

    selected = _normalize_fields(selected_fields or [])
    available_fields = _list_available_dynamic_fields(db, limit=40)

    conversation_counts = (
        select(
            ConversationEntityLink.entity_id.label("entity_id"),
            func.count(ConversationEntityLink.id).label("conversation_count"),
        )
        .group_by(ConversationEntityLink.entity_id)
        .subquery()
    )
    conversation_count_expr = func.coalesce(conversation_counts.c.conversation_count, 0)
    alias_count_expr = func.coalesce(func.json_array_length(Entity.known_aliases_json), 0)

    filters = [Entity.merged_into_id.is_(None)]
    search_term = (query or "").strip()
    if search_term:
        filters.append(Entity.canonical_name.ilike(f"%{search_term}%"))
    clean_type = (type_label or "").strip()
    if clean_type:
        filters.append(Entity.type_label == clean_type)

    total_stmt = select(func.count()).select_from(select(Entity.id).where(*filters).subquery())
    total = int(db.scalar(total_stmt) or 0)

    sort_map = {
        "canonical_name": Entity.canonical_name,
        "type_label": Entity.type_label,
        "last_seen": Entity.updated_at,
        "conversation_count": conversation_count_expr,
        "alias_count": alias_count_expr,
    }
    sort_expr = sort_map.get(sort, Entity.updated_at)
    sort_expr = sort_expr.asc() if order == "asc" else sort_expr.desc()

    stmt = (
        select(
            Entity,
            conversation_count_expr.label("conversation_count"),
        )
        .outerjoin(conversation_counts, conversation_counts.c.entity_id == Entity.id)
        .where(*filters)
        .order_by(sort_expr, Entity.id.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).all()
    entity_ids = [entity.id for entity, _ in rows]
    dynamic_values = _lookup_dynamic_field_values(db, entity_ids=entity_ids, fields=selected)

    items = [
        EntityListItem(
            id=entity.id,
            canonical_name=entity.canonical_name,
            display_name=entity.display_name,
            type_label=entity.type_label,
            alias_count=_alias_count(entity),
            first_seen=entity.first_seen_timestamp,
            last_seen=entity.updated_at,
            conversation_count=int(conversation_count or 0),
            dynamic_fields=dynamic_values.get(entity.id, {}),
        )
        for entity, conversation_count in rows
    ]
    return EntityListingResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        selected_fields=selected,
        available_fields=available_fields,
    )


def get_schema_overview(db: Session, *, per_section_limit: int = 200, proposal_limit: int = 100) -> SchemaOverviewData:
    """Return schema nodes/fields/relations/proposals in one payload."""

    _ensure_workspace_empty_state_consistent(db)

    nodes_raw = list(db.scalars(select(SchemaNode).order_by(SchemaNode.label.asc())).all())
    fields_raw = list(db.scalars(select(SchemaField).order_by(SchemaField.label.asc())).all())
    relations_raw = list(db.scalars(select(SchemaRelation).order_by(SchemaRelation.label.asc())).all())
    proposals_raw = list(
        db.scalars(
            select(SchemaProposal)
            .order_by(SchemaProposal.created_at.desc(), SchemaProposal.id.desc())
            .limit(proposal_limit)
        ).all()
    )

    nodes = sorted(
        (
            SchemaNodeOverview(
                id=node.id,
                label=node.label,
                description=node.description,
                examples=list(node.examples_json or []),
                frequency=_stat_count(node.stats_json, "observations"),
                last_seen_conversation_id=_stat_text(node.stats_json, "last_seen_conversation_id"),
            )
            for node in nodes_raw
        ),
        key=lambda item: (-item.frequency, item.label),
    )[:per_section_limit]

    field_label_by_id = {field.id: field.label for field in fields_raw}
    fields = sorted(
        (
            SchemaFieldOverview(
                id=field.id,
                label=field.label,
                canonical_label=field_label_by_id.get(field.canonical_of_id),
                description=field.description,
                examples=list(field.examples_json or []),
                frequency=_stat_count(field.stats_json, "observations"),
                last_seen_conversation_id=_stat_text(field.stats_json, "last_seen_conversation_id"),
            )
            for field in fields_raw
        ),
        key=lambda item: (-item.frequency, item.label),
    )[:per_section_limit]

    relation_label_by_id = {relation.id: relation.label for relation in relations_raw}
    relations = sorted(
        (
            SchemaRelationOverview(
                id=relation.id,
                label=relation.label,
                canonical_label=relation_label_by_id.get(relation.canonical_of_id),
                description=relation.description,
                examples=list(relation.examples_json or []),
                frequency=_stat_count(relation.stats_json, "observations"),
                last_seen_conversation_id=_stat_text(relation.stats_json, "last_seen_conversation_id"),
            )
            for relation in relations_raw
        ),
        key=lambda item: (-item.frequency, item.label),
    )[:per_section_limit]

    proposals = [
        SchemaProposalOverview(
            id=proposal.id,
            proposal_type=proposal.proposal_type,
            status=proposal.status,
            confidence=proposal.confidence,
            payload=dict(proposal.payload_json or {}),
            evidence=dict(proposal.evidence_json or {}),
            created_at=proposal.created_at,
        )
        for proposal in proposals_raw
    ]

    return SchemaOverviewData(
        nodes=nodes,
        fields=fields,
        relations=relations,
        proposals=proposals,
    )


def _lookup_dynamic_field_values(
    db: Session,
    *,
    entity_ids: list[int],
    fields: list[str],
) -> dict[int, dict[str, str]]:
    by_entity: dict[int, dict[str, str]] = defaultdict(dict)
    if not entity_ids or not fields:
        return by_entity

    stmt = (
        select(
            Fact.subject_entity_id,
            Fact.predicate,
            Fact.object_value,
            Fact.created_at,
            Fact.id,
        )
        .where(Fact.subject_entity_id.in_(entity_ids), Fact.predicate.in_(fields))
        .order_by(
            Fact.subject_entity_id.asc(),
            Fact.predicate.asc(),
            Fact.created_at.desc(),
            Fact.id.desc(),
        )
    )
    for row in db.execute(stmt).all():
        bucket = by_entity[int(row.subject_entity_id)]
        key = str(row.predicate)
        if key not in bucket:
            bucket[key] = str(row.object_value)
    return by_entity


def _list_available_dynamic_fields(db: Session, *, limit: int) -> list[str]:
    stmt = (
        select(Fact.predicate, func.count(Fact.id).label("frequency"))
        .group_by(Fact.predicate)
        .order_by(func.count(Fact.id).desc(), Fact.predicate.asc())
        .limit(limit)
    )
    return [str(row.predicate) for row in db.execute(stmt).all()]


def _normalize_fields(fields: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for field in fields:
        clean = field.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        ordered.append(clean)
    return ordered


def _alias_count(entity: Entity) -> int:
    aliases = {alias.strip() for alias in (entity.known_aliases_json or []) if alias and alias.strip()}
    aliases.update(
        alias.strip() for alias in (entity.aliases_json or []) if alias and alias.strip()
    )
    aliases.discard(entity.canonical_name.strip())
    return len(aliases)


def _stat_count(stats: dict[str, object] | None, key: str) -> int:
    if not isinstance(stats, dict):
        return 0
    return int(stats.get(key, 0) or 0)


def _stat_text(stats: dict[str, object] | None, key: str) -> str | None:
    if not isinstance(stats, dict):
        return None
    value = stats.get(key)
    return value if isinstance(value, str) and value else None


def _ensure_workspace_empty_state_consistent(db: Session) -> None:
    global _empty_state_verified

    if db.scalar(select(Message.id).limit(1)) is not None:
        _empty_state_verified = False
        return

    if _empty_state_verified:
        return

    with _empty_state_lock:
        if _empty_state_verified:
            return

        has_stale_state = any(
            [
                db.scalar(select(Entity.id).limit(1)) is not None,
                db.scalar(select(Fact.id).limit(1)) is not None,
                db.scalar(select(Relation.id).limit(1)) is not None,
                db.scalar(select(ConversationEntityLink.id).limit(1)) is not None,
                db.scalar(select(ExtractorRun.id).limit(1)) is not None,
                db.scalar(select(ResolutionEvent.id).limit(1)) is not None,
                db.scalar(select(EntityMergeAudit.id).limit(1)) is not None,
                db.scalar(select(SchemaNode.id).limit(1)) is not None,
                db.scalar(select(SchemaField.id).limit(1)) is not None,
                db.scalar(select(SchemaRelation.id).limit(1)) is not None,
                db.scalar(select(SchemaProposal.id).limit(1)) is not None,
                db.scalar(select(PredicateRegistryEntry.id).limit(1)) is not None,
            ]
        )
        if not has_stale_state:
            _empty_state_verified = True
            return

        db.execute(delete(SchemaProposal))
        db.execute(delete(SchemaRelation))
        db.execute(delete(SchemaField))
        db.execute(delete(SchemaNode))
        db.execute(delete(PredicateRegistryEntry))
        db.execute(delete(ConversationEntityLink))
        db.execute(delete(Relation))
        db.execute(delete(Fact))
        db.execute(delete(ExtractorRun))
        db.execute(delete(ResolutionEvent))
        db.execute(delete(EntityMergeAudit))
        db.execute(delete(Entity))
        db.commit()
        _empty_state_verified = True
