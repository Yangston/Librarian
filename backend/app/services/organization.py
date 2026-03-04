"""Organization-layer services for pods, themes, and scoped graph views."""

from __future__ import annotations

from collections import defaultdict
import json
import logging
import re
from typing import Any, Literal
from urllib import error as urllib_error
from urllib import request as urllib_request

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.collection import Collection
from app.models.collection_item import CollectionItem
from app.models.conversation import Conversation
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.fact import Fact
from app.models.pod import Pod
from app.models.relation import Relation
from app.models.workspace_edge import WorkspaceEdge
from app.schemas.organization import (
    CollectionItemMutationResponse,
    CollectionItemRead,
    CollectionItemsResponse,
    CollectionRead,
    CollectionTreeNode,
    PodDeleteResponse,
    PodRead,
    PodTreeData,
    ScopedGraphData,
    ScopedGraphEdge,
    ScopedGraphNode,
    ScopeMode,
)

logger = logging.getLogger(__name__)

_SEED_TEMPLATE_SLUGS = {
    "home",
    "stocks",
    "macro",
    "earnings-guidance",
    "news",
    "supply-chain",
    "valuation-models",
    "research-tasks",
}
_THEME_SYNTHESIS_PROMPT_VERSION = "pod_theme_v1"
_THEME_SYNTHESIS_JSON_SCHEMA: dict[str, Any] = {
    "name": "librarian_pod_themes",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "themes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": ["string", "null"]},
                        "columns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                                "required": ["name", "type"],
                            },
                        },
                        "inclusion": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "type_labels": {"type": "array", "items": {"type": "string"}},
                                "predicates": {"type": "array", "items": {"type": "string"}},
                                "relation_labels": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["type_labels", "predicates", "relation_labels"],
                        },
                    },
                    "required": ["name", "description", "columns", "inclusion"],
                },
            }
        },
        "required": ["themes"],
    },
}


def create_pod(db: Session, *, name: str, description: str | None = None) -> PodRead:
    """Create one pod with a unique slug."""

    base_slug = _slugify(name) or "pod"
    slug = base_slug
    suffix = 2
    while db.scalar(select(Pod.id).where(Pod.slug == slug)) is not None:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    pod = Pod(
        slug=slug,
        name=name.strip(),
        description=(description or "").strip() or None,
        is_default=False,
    )
    db.add(pod)
    db.commit()
    db.refresh(pod)
    return PodRead.model_validate(pod)


def delete_pod_with_conversations(db: Session, *, pod_id: int) -> PodDeleteResponse | None:
    """Delete one pod and every conversation assigned to it."""

    pod = db.scalar(select(Pod).where(Pod.id == pod_id))
    if pod is None:
        return None
    if pod.slug == "imported":
        raise ValueError("Imported pod is system-managed and cannot be deleted.")
    if pod.slug.startswith("compat-pod-"):
        raise ValueError("Compatibility pods are system-managed and cannot be deleted.")

    conversation_ids = list(
        db.scalars(
            select(Conversation.conversation_id)
            .where(Conversation.pod_id == pod_id)
            .order_by(Conversation.conversation_id.asc())
        ).all()
    )
    conversations_deleted = 0
    if conversation_ids:
        # Local import avoids module-load cycles with mutation services.
        from app.services.mutations import delete_conversation

        for conversation_id in conversation_ids:
            if delete_conversation(db, conversation_id):
                conversations_deleted += 1

    collection_ids = list(
        db.scalars(select(Collection.id).where(Collection.pod_id == pod_id)).all()
    )
    if collection_ids:
        db.execute(
            delete(WorkspaceEdge).where(
                or_(
                    and_(
                        WorkspaceEdge.src_kind == "collection",
                        WorkspaceEdge.src_id.in_(collection_ids),
                    ),
                    and_(
                        WorkspaceEdge.dst_kind == "collection",
                        WorkspaceEdge.dst_id.in_(collection_ids),
                    ),
                )
            )
        )
    db.execute(
        delete(WorkspaceEdge).where(
            WorkspaceEdge.src_kind == "pod",
            WorkspaceEdge.src_id == pod_id,
        )
    )
    db.delete(pod)
    db.commit()
    return PodDeleteResponse(
        pod_id=pod_id,
        deleted=True,
        conversations_deleted=conversations_deleted,
    )


def list_pods(db: Session) -> list[PodRead]:
    """List all pods."""

    pods = list(
        db.scalars(
            select(Pod)
            .where(~Pod.slug.like("compat-pod-%"), Pod.slug != "imported")
            .order_by(Pod.is_default.desc(), Pod.name.asc(), Pod.id.asc())
        ).all()
    )
    return [PodRead.model_validate(pod) for pod in pods]


def get_pod(db: Session, pod_id: int) -> PodRead | None:
    """Fetch a pod by id."""

    pod = db.scalar(select(Pod).where(Pod.id == pod_id))
    if pod is None:
        return None
    return PodRead.model_validate(pod)


def get_pod_tree(db: Session, pod_id: int) -> PodTreeData | None:
    """Return pod with nested collection tree."""

    pod = db.scalar(select(Pod).where(Pod.id == pod_id))
    if pod is None:
        return None
    collections = list(
        db.scalars(
            select(Collection)
            .where(Collection.pod_id == pod_id)
            .order_by(Collection.sort_order.asc(), Collection.id.asc())
        ).all()
    )
    children_by_parent: dict[int | None, list[Collection]] = defaultdict(list)
    for collection in collections:
        children_by_parent[collection.parent_id].append(collection)

    def build(parent_id: int | None) -> list[CollectionTreeNode]:
        nodes = []
        for collection in children_by_parent.get(parent_id, []):
            nodes.append(
                CollectionTreeNode(
                    collection=CollectionRead.model_validate(collection),
                    children=build(collection.id),
                )
            )
        return nodes

    return PodTreeData(pod=PodRead.model_validate(pod), tree=build(None))


def get_collection(db: Session, collection_id: int) -> CollectionRead | None:
    """Fetch one collection."""

    collection = db.scalar(select(Collection).where(Collection.id == collection_id))
    if collection is None:
        return None
    return CollectionRead.model_validate(collection)


def list_collection_items(
    db: Session,
    *,
    collection_id: int,
    limit: int,
    offset: int,
    sort: str,
    order: str,
    query: str | None = None,
    selected_fields: list[str] | None = None,
) -> CollectionItemsResponse | None:
    """Return paginated entity rows for a collection."""

    collection = db.scalar(select(Collection).where(Collection.id == collection_id))
    if collection is None:
        return None

    selected = _normalize_fields(selected_fields or [])
    entity_ids_query = select(CollectionItem.entity_id).where(CollectionItem.collection_id == collection_id)
    entity_ids_subquery = entity_ids_query.subquery()
    available_fields = _list_available_dynamic_fields(
        db,
        entity_ids_query=entity_ids_query,
        limit=40,
    )

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

    filters = [Entity.id.in_(select(entity_ids_subquery.c.entity_id)), Entity.merged_into_id.is_(None)]
    search_term = (query or "").strip()
    if search_term:
        filters.append(Entity.canonical_name.ilike(f"%{search_term}%"))

    total = int(db.scalar(select(func.count()).select_from(select(Entity.id).where(*filters).subquery())) or 0)

    sort_map = {
        "canonical_name": Entity.canonical_name,
        "type_label": Entity.type_label,
        "last_seen": Entity.updated_at,
        "conversation_count": conversation_count_expr,
        "alias_count": alias_count_expr,
    }
    sort_expr = sort_map.get(sort, Entity.updated_at)
    sort_expr = sort_expr.asc() if order == "asc" else sort_expr.desc()

    rows = db.execute(
        select(Entity, conversation_count_expr.label("conversation_count"))
        .outerjoin(conversation_counts, conversation_counts.c.entity_id == Entity.id)
        .where(*filters)
        .order_by(sort_expr, Entity.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()

    entity_ids = [entity.id for entity, _ in rows]
    dynamic_values = _lookup_dynamic_field_values(db, entity_ids=entity_ids, fields=selected)

    items = [
        CollectionItemRead(
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
    return CollectionItemsResponse(
        collection=CollectionRead.model_validate(collection),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        selected_fields=selected,
        available_fields=available_fields,
    )


def upsert_collection_item(
    db: Session,
    *,
    collection_id: int,
    entity_id: int,
    sort_key: str | None = None,
) -> CollectionItemMutationResponse | None:
    """Add entity membership to collection and ensure workspace edge."""

    collection = db.scalar(select(Collection).where(Collection.id == collection_id))
    entity = db.scalar(select(Entity).where(Entity.id == entity_id, Entity.merged_into_id.is_(None)))
    if collection is None or entity is None:
        return None
    row = db.scalar(
        select(CollectionItem).where(
            CollectionItem.collection_id == collection_id,
            CollectionItem.entity_id == entity_id,
        )
    )
    added = False
    if row is None:
        row = CollectionItem(collection_id=collection_id, entity_id=entity_id, sort_key=sort_key)
        db.add(row)
        added = True
    elif sort_key is not None:
        row.sort_key = sort_key

    _ensure_workspace_edge(
        db,
        src_kind="collection",
        src_id=collection_id,
        dst_kind="entity",
        dst_id=entity_id,
    )
    db.flush()
    return CollectionItemMutationResponse(collection_id=collection_id, entity_id=entity_id, added=added)


def remove_collection_item(db: Session, *, collection_id: int, entity_id: int) -> bool:
    """Remove entity membership from collection and prune workspace edge."""

    row = db.scalar(
        select(CollectionItem).where(
            CollectionItem.collection_id == collection_id,
            CollectionItem.entity_id == entity_id,
        )
    )
    if row is None:
        return False
    db.delete(row)
    edge = db.scalar(
        select(WorkspaceEdge).where(
            WorkspaceEdge.src_kind == "collection",
            WorkspaceEdge.src_id == collection_id,
            WorkspaceEdge.dst_kind == "entity",
            WorkspaceEdge.dst_id == entity_id,
            WorkspaceEdge.edge_type == "CONTAINS",
            WorkspaceEdge.namespace == "workspace",
        )
    )
    if edge is not None:
        db.delete(edge)
    db.flush()
    return True


def rebuild_pod_themes_for_conversation(db: Session, *, conversation_id: str) -> None:
    """Regenerate one pod's auto-generated theme tables for a conversation update."""

    row = db.scalar(select(Conversation).where(Conversation.conversation_id == conversation_id))
    if row is None:
        return
    rebuild_pod_themes(db, pod_id=int(row.pod_id))


def rebuild_pod_themes(db: Session, *, pod_id: int) -> None:
    """Regenerate one pod's auto-generated theme tables and memberships."""

    pod = db.scalar(select(Pod).where(Pod.id == pod_id))
    if pod is None:
        return
    _remove_seeded_templates(db, pod_id=pod_id)

    entity_rows = list(
        db.scalars(
            select(Entity).where(
                Entity.merged_into_id.is_(None),
                Entity.id.in_(
                    select(ConversationEntityLink.entity_id)
                    .join(
                        Conversation,
                        Conversation.conversation_id == ConversationEntityLink.conversation_id,
                    )
                    .where(Conversation.pod_id == pod_id)
                ),
            )
        ).all()
    )
    specs_by_slug = _derive_theme_specs(db, pod_id=pod_id, entity_rows=entity_rows)
    auto_collections = list(
        db.scalars(
            select(Collection).where(
                Collection.pod_id == pod_id,
                Collection.is_auto_generated.is_(True),
            )
        ).all()
    )
    auto_by_slug = {row.slug: row for row in auto_collections}

    desired_collection_ids: dict[str, int] = {}
    for idx, spec in enumerate(specs_by_slug.values()):
        existing = auto_by_slug.get(spec["slug"])
        if existing is None:
            existing = Collection(
                pod_id=pod_id,
                parent_id=None,
                kind="TABLE",
                slug=spec["slug"],
                name=spec["name"],
                description=spec["description"],
                schema_json=spec["schema_json"],
                view_config_json={},
                sort_order=(idx + 1) * 10,
                is_auto_generated=True,
            )
            db.add(existing)
            db.flush()
        else:
            existing.kind = "TABLE"
            existing.name = spec["name"]
            existing.description = spec["description"]
            existing.schema_json = spec["schema_json"]
            existing.sort_order = (idx + 1) * 10
            existing.is_auto_generated = True
            db.add(existing)
            db.flush()
        desired_collection_ids[spec["slug"]] = int(existing.id)

    desired_slugs = set(desired_collection_ids.keys())
    stale_collection_ids = [
        int(row.id) for row in auto_collections if row.slug not in desired_slugs
    ]
    if stale_collection_ids:
        db.execute(delete(CollectionItem).where(CollectionItem.collection_id.in_(stale_collection_ids)))
        db.execute(
            delete(WorkspaceEdge).where(
                or_(
                    and_(
                        WorkspaceEdge.src_kind == "collection",
                        WorkspaceEdge.src_id.in_(stale_collection_ids),
                    ),
                    and_(
                        WorkspaceEdge.dst_kind == "collection",
                        WorkspaceEdge.dst_id.in_(stale_collection_ids),
                    ),
                )
            )
        )
        db.execute(delete(Collection).where(Collection.id.in_(stale_collection_ids)))

    collection_ids = list(desired_collection_ids.values())
    if collection_ids:
        db.execute(delete(CollectionItem).where(CollectionItem.collection_id.in_(collection_ids)))
        db.execute(
            delete(WorkspaceEdge).where(
                WorkspaceEdge.src_kind == "collection",
                WorkspaceEdge.src_id.in_(collection_ids),
                WorkspaceEdge.dst_kind == "entity",
                WorkspaceEdge.namespace == "workspace",
            )
        )
        db.execute(
            delete(WorkspaceEdge).where(
                WorkspaceEdge.src_kind == "pod",
                WorkspaceEdge.src_id == pod_id,
                WorkspaceEdge.dst_kind == "collection",
                WorkspaceEdge.dst_id.in_(collection_ids),
                WorkspaceEdge.namespace == "workspace",
            )
        )

    for slug, spec in specs_by_slug.items():
        collection_id = desired_collection_ids[slug]
        _ensure_workspace_edge(
            db,
            src_kind="pod",
            src_id=pod_id,
            dst_kind="collection",
            dst_id=collection_id,
        )
        for entity_id in spec["entity_ids"]:
            db.add(CollectionItem(collection_id=collection_id, entity_id=entity_id, sort_key=None))
            _ensure_workspace_edge(
                db,
                src_kind="collection",
                src_id=collection_id,
                dst_kind="entity",
                dst_id=entity_id,
            )

    db.flush()


def resolve_scope_entity_ids(
    db: Session,
    *,
    scope_mode: ScopeMode,
    pod_id: int | None = None,
    collection_id: int | None = None,
) -> set[int]:
    """Resolve in-scope entity IDs for global/pod/collection views."""

    if scope_mode == "global":
        return {int(value) for value in db.scalars(select(Entity.id).where(Entity.merged_into_id.is_(None))).all()}
    if scope_mode == "pod":
        if pod_id is None:
            return set()
        rows = db.scalars(
            select(CollectionItem.entity_id)
            .join(Collection, Collection.id == CollectionItem.collection_id)
            .where(Collection.pod_id == pod_id)
        ).all()
        return {int(value) for value in rows}
    if collection_id is None:
        return set()
    rows = db.scalars(select(CollectionItem.entity_id).where(CollectionItem.collection_id == collection_id)).all()
    return {int(value) for value in rows}


def get_scoped_graph(
    db: Session,
    *,
    scope_mode: ScopeMode,
    pod_id: int | None = None,
    collection_id: int | None = None,
    one_hop: bool = False,
    include_external: bool = False,
) -> ScopedGraphData:
    """Return graph payload scoped to global/pod/collection membership."""

    seed_ids = resolve_scope_entity_ids(
        db,
        scope_mode=scope_mode,
        pod_id=pod_id,
        collection_id=collection_id,
    )
    in_scope_ids = set(seed_ids)
    if not seed_ids and scope_mode != "global":
        return ScopedGraphData(
            scope_mode=scope_mode,
            pod_id=pod_id,
            collection_id=collection_id,
            one_hop=one_hop,
            include_external=include_external,
            nodes=[],
            edges=[],
        )

    relation_rows = list(
        db.scalars(
            select(Relation).where(
                and_(
                    Relation.from_entity_id.in_(seed_ids if seed_ids else [-1]),
                    Relation.to_entity_id.in_(seed_ids if seed_ids else [-1]),
                )
            )
        ).all()
    )
    if scope_mode != "global":
        relation_rows = list(
            db.scalars(
                select(Relation).where(
                    or_(
                        Relation.from_entity_id.in_(seed_ids if seed_ids else [-1]),
                        Relation.to_entity_id.in_(seed_ids if seed_ids else [-1]),
                    )
                )
            ).all()
        )

    if one_hop and scope_mode == "collection":
        for relation in relation_rows:
            if relation.from_entity_id in seed_ids or relation.to_entity_id in seed_ids:
                in_scope_ids.add(int(relation.from_entity_id))
                in_scope_ids.add(int(relation.to_entity_id))

    if scope_mode == "global":
        in_scope_ids = {
            int(value)
            for value in db.scalars(select(Entity.id).where(Entity.merged_into_id.is_(None))).all()
        }

    graph_edges: list[ScopedGraphEdge] = []
    for relation in relation_rows:
        from_in_scope = relation.from_entity_id in in_scope_ids
        to_in_scope = relation.to_entity_id in in_scope_ids
        if scope_mode == "global":
            if not (from_in_scope and to_in_scope):
                continue
        elif include_external:
            if not (relation.from_entity_id in seed_ids or relation.to_entity_id in seed_ids):
                continue
        else:
            if not (from_in_scope and to_in_scope):
                continue
        graph_edges.append(
            ScopedGraphEdge(
                relation_id=relation.id,
                from_entity_id=relation.from_entity_id,
                to_entity_id=relation.to_entity_id,
                relation_type=relation.relation_type,
                confidence=relation.confidence,
            )
        )

    node_ids = set(in_scope_ids)
    if include_external and scope_mode != "global":
        for edge in graph_edges:
            node_ids.add(edge.from_entity_id)
            node_ids.add(edge.to_entity_id)

    entities = list(
        db.scalars(
            select(Entity).where(
                Entity.id.in_(node_ids if node_ids else [-1]),
                Entity.merged_into_id.is_(None),
            )
        ).all()
    )
    nodes = [
        ScopedGraphNode(
            entity_id=entity.id,
            canonical_name=entity.canonical_name,
            display_name=entity.display_name,
            type_label=entity.type_label,
            external=scope_mode != "global" and entity.id not in seed_ids,
        )
        for entity in sorted(entities, key=lambda item: item.id)
    ]
    return ScopedGraphData(
        scope_mode=scope_mode,
        pod_id=pod_id,
        collection_id=collection_id,
        one_hop=one_hop,
        include_external=include_external,
        nodes=nodes,
        edges=sorted(graph_edges, key=lambda item: item.relation_id),
    )


def _derive_theme_specs(
    db: Session,
    *,
    pod_id: int,
    entity_rows: list[Entity],
) -> dict[str, dict[str, object]]:
    llm_specs = _derive_theme_specs_with_llm(db, pod_id=pod_id, entity_rows=entity_rows)
    if llm_specs:
        return llm_specs
    return _derive_theme_specs_fallback(db, entity_rows=entity_rows)


def _derive_theme_specs_with_llm(
    db: Session,
    *,
    pod_id: int,
    entity_rows: list[Entity],
) -> dict[str, dict[str, object]] | None:
    if not entity_rows:
        return {}
    synthesis = _synthesize_themes_with_llm(
        _build_theme_synthesis_input(db, pod_id=pod_id, entity_rows=entity_rows)
    )
    if not synthesis:
        return None

    entity_by_id = {int(entity.id): entity for entity in entity_rows}
    entity_ids = sorted(entity_by_id.keys())
    if not entity_ids:
        return {}

    facts_rows = list(
        db.execute(
            select(Fact.subject_entity_id, Fact.predicate).where(Fact.subject_entity_id.in_(entity_ids))
        ).all()
    )
    pod_conversation_ids = select(Conversation.conversation_id).where(Conversation.pod_id == pod_id)
    relation_rows = list(
        db.execute(
            select(Relation.from_entity_id, Relation.to_entity_id, Relation.relation_type).where(
                Relation.conversation_id.in_(pod_conversation_ids)
            )
        ).all()
    )

    type_to_ids: dict[str, set[int]] = defaultdict(set)
    for entity in entity_rows:
        key = _normalize_type_label(entity.type_label or entity.type)
        if key:
            type_to_ids[key].add(int(entity.id))
    predicate_to_ids: dict[str, set[int]] = defaultdict(set)
    for subject_entity_id, predicate in facts_rows:
        key = _normalize_type_label(str(predicate or ""))
        if key and subject_entity_id is not None:
            predicate_to_ids[key].add(int(subject_entity_id))
    relation_to_ids: dict[str, set[int]] = defaultdict(set)
    for from_entity_id, to_entity_id, relation_type in relation_rows:
        key = _normalize_type_label(str(relation_type or ""))
        if not key:
            continue
        if from_entity_id in entity_by_id:
            relation_to_ids[key].add(int(from_entity_id))
        if to_entity_id in entity_by_id:
            relation_to_ids[key].add(int(to_entity_id))

    specs: dict[str, dict[str, object]] = {}
    slug_counts: dict[str, int] = defaultdict(int)
    for theme in synthesis:
        name = str(theme.get("name") or "").strip()
        if not name:
            continue
        raw_slug = _slugify(name) or "theme"
        if raw_slug in _SEED_TEMPLATE_SLUGS:
            raw_slug = f"{raw_slug}-theme"
        slug_counts[raw_slug] += 1
        slug = raw_slug if slug_counts[raw_slug] == 1 else f"{raw_slug}-{slug_counts[raw_slug]}"

        inclusion_raw = theme.get("inclusion")
        inclusion = inclusion_raw if isinstance(inclusion_raw, dict) else {}
        type_labels = _clean_str_list(inclusion.get("type_labels"))
        predicates = _clean_str_list(inclusion.get("predicates"))
        relation_labels = _clean_str_list(inclusion.get("relation_labels"))

        matching_entity_ids: set[int] = set()
        for label in type_labels:
            matching_entity_ids.update(type_to_ids.get(_normalize_type_label(label), set()))
        for label in predicates:
            matching_entity_ids.update(predicate_to_ids.get(_normalize_type_label(label), set()))
        for label in relation_labels:
            matching_entity_ids.update(relation_to_ids.get(_normalize_type_label(label), set()))
        if not type_labels and not predicates and not relation_labels:
            matching_entity_ids.update(entity_ids)
        if not matching_entity_ids:
            continue

        columns = _normalize_theme_columns(theme.get("columns"))
        if not any(column.get("name") == "canonical_name" for column in columns):
            columns = [{"name": "canonical_name", "type": "title"}, *columns]
        columns = _dedupe_columns(columns)

        specs[slug] = {
            "slug": slug,
            "name": name,
            "description": str(theme.get("description") or "").strip()
            or f"Auto-generated theme for {name} in this pod.",
            "schema_json": {
                "columns": columns,
                "source": _THEME_SYNTHESIS_PROMPT_VERSION,
                "inclusion": {
                    "type_labels": type_labels,
                    "predicates": predicates,
                    "relation_labels": relation_labels,
                },
            },
            "entity_ids": sorted(matching_entity_ids),
        }
    return specs


def _derive_theme_specs_fallback(db: Session, *, entity_rows: list[Entity]) -> dict[str, dict[str, object]]:
    grouped_entity_ids: dict[str, set[int]] = defaultdict(set)
    grouped_types: dict[str, set[str]] = defaultdict(set)
    grouped_display_name: dict[str, str] = {}
    for entity in entity_rows:
        label = (entity.type_label or "").strip()
        normalized = _normalize_type_label(label)
        if not normalized:
            slug = "general"
            theme_name = "General"
        else:
            if normalized.endswith("y") and len(normalized) > 1:
                plural = f"{normalized[:-1]}ies"
            elif normalized.endswith("s"):
                plural = normalized
            else:
                plural = f"{normalized}s"
            slug = _slugify(plural) or "theme"
            if slug in _SEED_TEMPLATE_SLUGS:
                slug = f"{slug}-theme"
            theme_name = _title_case_label(plural)
        grouped_entity_ids[slug].add(int(entity.id))
        if label:
            grouped_types[slug].add(label)
        grouped_display_name[slug] = theme_name

    specs: dict[str, dict[str, object]] = {}
    for slug in sorted(grouped_entity_ids.keys()):
        entity_ids = sorted(grouped_entity_ids[slug])
        predicates = _top_predicates_for_entity_ids(db, entity_ids=entity_ids, limit=12)
        columns = [{"name": "canonical_name", "type": "title"}]
        columns.extend({"name": predicate, "type": "text"} for predicate in predicates)
        specs[slug] = {
            "slug": slug,
            "name": grouped_display_name[slug],
            "description": f"Auto-generated theme for {grouped_display_name[slug]} in this pod.",
            "schema_json": {
                "columns": _dedupe_columns(columns),
                "source": "auto_theme_fallback_v1",
                "inclusion": {"type_labels": sorted(grouped_types.get(slug, set()))},
            },
            "entity_ids": entity_ids,
        }
    return specs


def _top_predicates_for_entity_ids(db: Session, *, entity_ids: list[int], limit: int) -> list[str]:
    if not entity_ids:
        return []
    rows = db.execute(
        select(Fact.predicate, func.count(Fact.id).label("frequency"))
        .where(Fact.subject_entity_id.in_(entity_ids))
        .group_by(Fact.predicate)
        .order_by(func.count(Fact.id).desc(), Fact.predicate.asc())
        .limit(limit)
    ).all()
    return [str(row.predicate) for row in rows]


def _build_theme_synthesis_input(
    db: Session,
    *,
    pod_id: int,
    entity_rows: list[Entity],
) -> dict[str, Any]:
    entity_ids = [int(entity.id) for entity in entity_rows]
    type_counts: dict[str, int] = defaultdict(int)
    for entity in entity_rows:
        label = str(entity.type_label or entity.type or "Unspecified").strip() or "Unspecified"
        type_counts[label] += 1

    facts_rows = list(
        db.execute(
            select(Fact.subject_entity_id, Fact.predicate, Fact.object_value).where(
                Fact.subject_entity_id.in_(entity_ids if entity_ids else [-1])
            )
        ).all()
    )
    predicate_counts: dict[str, int] = defaultdict(int)
    sample_facts: list[dict[str, str]] = []
    entity_name_by_id = {int(entity.id): entity.canonical_name for entity in entity_rows}
    for subject_entity_id, predicate, object_value in facts_rows:
        clean_predicate = str(predicate or "").strip()
        if not clean_predicate:
            continue
        predicate_counts[clean_predicate] += 1
        if len(sample_facts) < 30:
            sample_facts.append(
                {
                    "entity": entity_name_by_id.get(int(subject_entity_id or 0), ""),
                    "predicate": clean_predicate,
                    "value": str(object_value or "").strip(),
                }
            )

    pod_conversation_ids = select(Conversation.conversation_id).where(Conversation.pod_id == pod_id)
    relation_rows = list(
        db.execute(
            select(Relation.from_entity_id, Relation.relation_type, Relation.to_entity_id).where(
                Relation.conversation_id.in_(pod_conversation_ids)
            )
        ).all()
    )
    relation_counts: dict[str, int] = defaultdict(int)
    sample_relations: list[dict[str, str]] = []
    for from_entity_id, relation_type, to_entity_id in relation_rows:
        clean_relation = str(relation_type or "").strip()
        if not clean_relation:
            continue
        relation_counts[clean_relation] += 1
        if len(sample_relations) < 20:
            sample_relations.append(
                {
                    "from": entity_name_by_id.get(int(from_entity_id or 0), ""),
                    "relation": clean_relation,
                    "to": entity_name_by_id.get(int(to_entity_id or 0), ""),
                }
            )

    sample_entities = [
        {
            "name": entity.canonical_name,
            "type_label": entity.type_label,
            "aliases": list(entity.known_aliases_json or [])[:4],
        }
        for entity in entity_rows[:40]
    ]

    return {
        "pod_id": pod_id,
        "entity_count": len(entity_rows),
        "type_counts": dict(sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))),
        "predicate_counts": dict(sorted(predicate_counts.items(), key=lambda item: (-item[1], item[0]))),
        "relation_counts": dict(sorted(relation_counts.items(), key=lambda item: (-item[1], item[0]))),
        "sample_entities": sample_entities,
        "sample_facts": sample_facts,
        "sample_relations": sample_relations,
    }


def _synthesize_themes_with_llm(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    system_prompt = (
        "Design pod-local workspace themes from extracted graph signals. "
        "Return concise, useful table themes with inclusion criteria based on "
        "type_labels, predicates, and relation_labels. Keep names short."
    )
    user_prompt = json.dumps(payload, ensure_ascii=True)
    request_payload = {
        "model": settings.openai_model,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": _THEME_SYNTHESIS_JSON_SCHEMA,
        },
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = urllib_request.Request(
        url=f"{settings.openai_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=settings.openai_timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
        decoded = json.loads(raw)
        content = decoded["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else {}
        themes = parsed.get("themes")
        if isinstance(themes, list):
            return [item for item in themes if isinstance(item, dict)]
    except (urllib_error.URLError, urllib_error.HTTPError, json.JSONDecodeError, KeyError, TypeError, IndexError):
        logger.warning("pod.theme_synthesis_llm_failed_using_fallback", exc_info=True)
    return None


def _normalize_theme_columns(raw_columns: Any) -> list[dict[str, str]]:
    if not isinstance(raw_columns, list):
        return [{"name": "canonical_name", "type": "title"}]
    columns: list[dict[str, str]] = []
    for raw in raw_columns:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        col_type = str(raw.get("type") or "text").strip().lower()
        if col_type not in {"title", "text", "number", "date", "boolean", "json"}:
            col_type = "text"
        columns.append({"name": _slugify(name).replace("-", "_") or name, "type": col_type})
    return columns


def _dedupe_columns(columns: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for column in columns:
        name = str(column.get("name") or "").strip()
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        deduped.append({"name": name, "type": str(column.get("type") or "text")})
    return deduped


def _clean_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in value:
        clean = str(raw or "").strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def _remove_seeded_templates(db: Session, *, pod_id: int) -> None:
    seeded_ids = list(
        db.scalars(
            select(Collection.id).where(
                Collection.pod_id == pod_id,
                Collection.slug.in_(sorted(_SEED_TEMPLATE_SLUGS)),
            )
        ).all()
    )
    if not seeded_ids:
        return
    db.execute(delete(CollectionItem).where(CollectionItem.collection_id.in_(seeded_ids)))
    db.execute(
        delete(WorkspaceEdge).where(
            or_(
                and_(WorkspaceEdge.src_kind == "collection", WorkspaceEdge.src_id.in_(seeded_ids)),
                and_(WorkspaceEdge.dst_kind == "collection", WorkspaceEdge.dst_id.in_(seeded_ids)),
            )
        )
    )
    db.execute(delete(Collection).where(Collection.id.in_(seeded_ids)))
    db.flush()


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _normalize_type_label(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _title_case_label(value: str) -> str:
    return " ".join(token.capitalize() for token in re.split(r"[_\-\s]+", value) if token)


def _ensure_workspace_edge(
    db: Session,
    *,
    src_kind: Literal["pod", "collection"],
    src_id: int,
    dst_kind: Literal["collection", "entity"],
    dst_id: int,
) -> None:
    edge = db.scalar(
        select(WorkspaceEdge).where(
            WorkspaceEdge.src_kind == src_kind,
            WorkspaceEdge.src_id == src_id,
            WorkspaceEdge.dst_kind == dst_kind,
            WorkspaceEdge.dst_id == dst_id,
            WorkspaceEdge.edge_type == "CONTAINS",
            WorkspaceEdge.namespace == "workspace",
        )
    )
    if edge is None:
        db.add(
            WorkspaceEdge(
                src_kind=src_kind,
                src_id=src_id,
                dst_kind=dst_kind,
                dst_id=dst_id,
                edge_type="CONTAINS",
                namespace="workspace",
            )
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

    rows = db.execute(
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
    ).all()
    for row in rows:
        bucket = by_entity[int(row.subject_entity_id)]
        key = str(row.predicate)
        if key not in bucket:
            bucket[key] = str(row.object_value)
    return by_entity


def _list_available_dynamic_fields(
    db: Session,
    *,
    entity_ids_query,
    limit: int,
) -> list[str]:
    rows = db.execute(
        select(Fact.predicate, func.count(Fact.id).label("frequency"))
        .where(Fact.subject_entity_id.in_(entity_ids_query))
        .group_by(Fact.predicate)
        .order_by(func.count(Fact.id).desc(), Fact.predicate.asc())
        .limit(limit)
    ).all()
    return [str(row.predicate) for row in rows]


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
    aliases.update(alias.strip() for alias in (entity.aliases_json or []) if alias and alias.strip())
    aliases.discard(entity.canonical_name.strip())
    return len(aliases)
