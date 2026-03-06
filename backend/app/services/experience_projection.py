"""Experience projection layer for user-facing v2 workspace APIs."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.claim_index import ClaimIndex
from app.models.collection import Collection
from app.models.collection_item import CollectionItem
from app.models.conversation import Conversation
from app.models.entity import Entity
from app.models.fact import Fact
from app.models.item_link import ItemLink
from app.models.item_property import ItemProperty
from app.models.library_item import LibraryItem
from app.models.pod import Pod
from app.models.property_catalog import PropertyCatalog
from app.models.relation import Relation
from app.models.schema_field import SchemaField
from app.models.schema_relation import SchemaRelation
from app.models.space import Space
from app.models.space_page import SpacePage


def rebuild_experience_projection(
    db: Session,
    *,
    conversation_id: str | None = None,
    space_id: int | None = None,
) -> None:
    """Rebuild materialized v2 experience projection tables.

    The first implementation intentionally rebuilds globally for deterministic
    behavior. Scope arguments are accepted for future optimization.
    """

    _ = (conversation_id, space_id)  # Reserved for scoped rebuilds.
    _clear_projection_tables(db)
    spaces_by_pod = _rebuild_spaces(db)
    pages_by_collection = _rebuild_space_pages(db, spaces_by_pod=spaces_by_pod)
    library_item_by_entity = _rebuild_library_items(
        db,
        spaces_by_pod=spaces_by_pod,
        pages_by_collection=pages_by_collection,
    )
    _rebuild_item_properties(db, library_item_by_entity=library_item_by_entity)
    _rebuild_item_links(db, library_item_by_entity=library_item_by_entity)
    _rebuild_property_catalog(db)
    _rebuild_claim_index(db, library_item_by_entity=library_item_by_entity)
    db.flush()


def rebuild_experience_projection_all(db: Session) -> None:
    """Explicit full rebuild entrypoint for migration/backfill flows."""

    rebuild_experience_projection(db, conversation_id=None, space_id=None)


def _clear_projection_tables(db: Session) -> None:
    db.execute(delete(ClaimIndex))
    db.execute(delete(ItemLink))
    db.execute(delete(ItemProperty))
    db.execute(delete(LibraryItem))
    db.execute(delete(PropertyCatalog))
    db.execute(delete(SpacePage))
    db.execute(delete(Space))
    db.flush()


def _rebuild_spaces(db: Session) -> dict[int, Space]:
    spaces_by_pod: dict[int, Space] = {}
    pods = list(
        db.scalars(
            select(Pod)
            .where(~Pod.slug.like("compat-pod-%"), Pod.slug != "imported")
            .order_by(Pod.is_default.desc(), Pod.name.asc(), Pod.id.asc())
        ).all()
    )
    used_slugs: set[str] = set()
    for pod in pods:
        base_slug = _slugify(pod.slug or pod.name) or f"space-{pod.id}"
        slug = base_slug
        suffix = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        used_slugs.add(slug)
        row = Space(
            pod_id=pod.id,
            slug=slug,
            name=pod.name,
            description=pod.description,
        )
        db.add(row)
        db.flush()
        spaces_by_pod[pod.id] = row
    return spaces_by_pod


def _rebuild_space_pages(db: Session, *, spaces_by_pod: dict[int, Space]) -> dict[int, SpacePage]:
    pages_by_collection: dict[int, SpacePage] = {}
    collections = list(
        db.scalars(
            select(Collection)
            .where(Collection.pod_id.in_(list(spaces_by_pod.keys()) or [-1]))
            .order_by(Collection.sort_order.asc(), Collection.id.asc())
        ).all()
    )
    pending_parent_by_page: dict[int, int | None] = {}
    slug_seen_by_space: dict[int, set[str]] = defaultdict(set)

    for collection in collections:
        space = spaces_by_pod.get(collection.pod_id)
        if space is None:
            continue
        base_slug = _slugify(collection.slug or collection.name) or f"page-{collection.id}"
        slug = base_slug
        suffix = 2
        while slug in slug_seen_by_space[space.id]:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        slug_seen_by_space[space.id].add(slug)
        page = SpacePage(
            space_id=space.id,
            collection_id=collection.id,
            parent_id=None,
            kind=_normalize_page_kind(collection.kind),
            slug=slug,
            name=collection.name,
            description=collection.description,
            sort_order=collection.sort_order,
        )
        db.add(page)
        db.flush()
        pages_by_collection[collection.id] = page
        pending_parent_by_page[page.id] = collection.parent_id

    if pending_parent_by_page:
        page_by_collection_id = {key: value.id for key, value in pages_by_collection.items()}
        for page in pages_by_collection.values():
            parent_collection_id = pending_parent_by_page.get(page.id)
            if parent_collection_id is None:
                continue
            page.parent_id = page_by_collection_id.get(parent_collection_id)
            db.add(page)
    db.flush()
    return pages_by_collection


def _rebuild_library_items(
    db: Session,
    *,
    spaces_by_pod: dict[int, Space],
    pages_by_collection: dict[int, SpacePage],
) -> dict[int, LibraryItem]:
    entities = list(
        db.scalars(
            select(Entity)
            .where(Entity.merged_into_id.is_(None))
            .order_by(Entity.updated_at.desc(), Entity.id.asc())
        ).all()
    )

    conversation_pod: dict[str, int] = {
        row.conversation_id: int(row.pod_id)
        for row in db.execute(select(Conversation.conversation_id, Conversation.pod_id)).all()
    }
    memberships_by_entity: dict[int, list[int]] = defaultdict(list)
    for entity_id, collection_id in db.execute(
        select(CollectionItem.entity_id, CollectionItem.collection_id)
    ).all():
        memberships_by_entity[int(entity_id)].append(int(collection_id))

    facts_by_entity: dict[int, list[Fact]] = defaultdict(list)
    for fact in db.scalars(
        select(Fact).order_by(Fact.created_at.desc(), Fact.id.desc())
    ).all():
        facts_by_entity[int(fact.subject_entity_id)].append(fact)

    relation_counts: dict[int, int] = defaultdict(int)
    for from_id, to_id in db.execute(select(Relation.from_entity_id, Relation.to_entity_id)).all():
        relation_counts[int(from_id)] += 1
        relation_counts[int(to_id)] += 1

    collection_to_page_id = {collection_id: page.id for collection_id, page in pages_by_collection.items()}
    collection_to_space_id = {collection_id: page.space_id for collection_id, page in pages_by_collection.items()}

    library_item_by_entity: dict[int, LibraryItem] = {}
    for entity in entities:
        pod_id = conversation_pod.get(entity.conversation_id)
        mapped_space = spaces_by_pod.get(pod_id) if pod_id is not None else None
        membership_collections = memberships_by_entity.get(entity.id, [])
        page_id = None
        if membership_collections:
            sorted_collections = sorted(membership_collections)
            for collection_id in sorted_collections:
                candidate_page = collection_to_page_id.get(collection_id)
                candidate_space = collection_to_space_id.get(collection_id)
                if candidate_page is None:
                    continue
                if mapped_space is None or mapped_space.id == candidate_space:
                    page_id = candidate_page
                    if mapped_space is None and candidate_space is not None:
                        mapped_space = next(
                            (space for space in spaces_by_pod.values() if space.id == candidate_space),
                            None,
                        )
                    break

        mention_count = len(facts_by_entity.get(entity.id, [])) + relation_counts.get(entity.id, 0)
        summary = _build_entity_summary(facts_by_entity.get(entity.id, []))
        row = LibraryItem(
            entity_id=entity.id,
            space_id=mapped_space.id if mapped_space is not None else None,
            page_id=page_id,
            name=entity.canonical_name,
            type_label=entity.type_label,
            summary=summary,
            mention_count=mention_count,
            last_seen_at=entity.updated_at,
        )
        db.add(row)
        db.flush()
        library_item_by_entity[entity.id] = row
    return library_item_by_entity


def _rebuild_item_properties(db: Session, *, library_item_by_entity: dict[int, LibraryItem]) -> None:
    facts = list(
        db.scalars(
            select(Fact).order_by(Fact.subject_entity_id.asc(), Fact.created_at.desc(), Fact.id.desc())
        ).all()
    )
    latest_by_entity_predicate: dict[tuple[int, str], Fact] = {}
    for fact in facts:
        key = (int(fact.subject_entity_id), str(fact.predicate))
        if key not in latest_by_entity_predicate:
            latest_by_entity_predicate[key] = fact

    for (entity_id, predicate), fact in latest_by_entity_predicate.items():
        item = library_item_by_entity.get(entity_id)
        if item is None:
            continue
        db.add(
            ItemProperty(
                library_item_id=item.id,
                property_key=predicate,
                property_label=_display_label(predicate),
                property_value=fact.object_value,
                claim_kind="fact",
                claim_id=fact.id,
                last_observed_at=fact.created_at,
            )
        )
    db.flush()


def _rebuild_item_links(db: Session, *, library_item_by_entity: dict[int, LibraryItem]) -> None:
    grouped: dict[tuple[int, int, str], tuple[int, datetime]] = {}
    for relation in db.scalars(select(Relation).order_by(Relation.id.asc())).all():
        from_item = library_item_by_entity.get(int(relation.from_entity_id))
        to_item = library_item_by_entity.get(int(relation.to_entity_id))
        if from_item is None or to_item is None:
            continue
        key = (from_item.id, to_item.id, str(relation.relation_type))
        current = grouped.get(key)
        if current is None:
            grouped[key] = (1, relation.created_at)
        else:
            grouped[key] = (current[0] + 1, max(current[1], relation.created_at))

    for (from_item_id, to_item_id, relation_type), (count, last_seen) in grouped.items():
        db.add(
            ItemLink(
                from_library_item_id=from_item_id,
                to_library_item_id=to_item_id,
                relation_type=relation_type,
                relation_count=count,
                last_seen_at=last_seen,
            )
        )
    db.flush()


def _rebuild_property_catalog(db: Session) -> None:
    for field in db.scalars(select(SchemaField).order_by(SchemaField.label.asc())).all():
        observations = _stat_count(field.stats_json, "observations")
        status = "deprecated" if field.canonical_of_id is not None else ("stable" if observations >= 5 else "emerging")
        db.add(
            PropertyCatalog(
                property_key=f"field:{field.label}",
                display_label=_display_label(field.label),
                kind="field",
                status=status,
                mention_count=observations,
                last_seen_at=field.created_at,
            )
        )

    for relation in db.scalars(select(SchemaRelation).order_by(SchemaRelation.label.asc())).all():
        observations = _stat_count(relation.stats_json, "observations")
        status = (
            "deprecated"
            if relation.canonical_of_id is not None
            else ("stable" if observations >= 5 else "emerging")
        )
        db.add(
            PropertyCatalog(
                property_key=f"relation:{relation.label}",
                display_label=_display_label(relation.label),
                kind="relation",
                status=status,
                mention_count=observations,
                last_seen_at=relation.created_at,
            )
        )
    db.flush()


def _rebuild_claim_index(db: Session, *, library_item_by_entity: dict[int, LibraryItem]) -> None:
    entity_name_by_id = {
        int(entity_id): str(name)
        for entity_id, name in db.execute(select(Entity.id, Entity.canonical_name)).all()
    }
    for fact in db.scalars(select(Fact).order_by(Fact.id.asc())).all():
        item = library_item_by_entity.get(int(fact.subject_entity_id))
        db.add(
            ClaimIndex(
                claim_kind="fact",
                claim_id=fact.id,
                conversation_id=fact.conversation_id,
                space_id=item.space_id if item is not None else None,
                page_id=item.page_id if item is not None else None,
                library_item_id=item.id if item is not None else None,
                related_library_item_id=None,
                property_key=fact.predicate,
                relation_type=None,
                value_text=fact.object_value,
                confidence=fact.confidence,
                occurred_at=fact.created_at,
                extractor_run_id=fact.extractor_run_id,
                source_message_ids_json=list(fact.source_message_ids_json or []),
            )
        )

    for relation in db.scalars(select(Relation).order_by(Relation.id.asc())).all():
        from_item = library_item_by_entity.get(int(relation.from_entity_id))
        to_item = library_item_by_entity.get(int(relation.to_entity_id))
        from_name = entity_name_by_id.get(int(relation.from_entity_id), str(relation.from_entity_id))
        to_name = entity_name_by_id.get(int(relation.to_entity_id), str(relation.to_entity_id))
        db.add(
            ClaimIndex(
                claim_kind="relation",
                claim_id=relation.id,
                conversation_id=relation.conversation_id,
                space_id=from_item.space_id if from_item is not None else None,
                page_id=from_item.page_id if from_item is not None else None,
                library_item_id=from_item.id if from_item is not None else None,
                related_library_item_id=to_item.id if to_item is not None else None,
                property_key=None,
                relation_type=relation.relation_type,
                value_text=f"{from_name} {relation.relation_type} {to_name}",
                confidence=relation.confidence,
                occurred_at=relation.created_at,
                extractor_run_id=relation.extractor_run_id,
                source_message_ids_json=list(relation.source_message_ids_json or []),
            )
        )
    db.flush()


def _build_entity_summary(facts: list[Fact]) -> str | None:
    if not facts:
        return None
    fragments: list[str] = []
    for fact in facts[:2]:
        fragments.append(f"{_display_label(fact.predicate)}: {fact.object_value}")
    return " | ".join(fragments) if fragments else None


def _normalize_page_kind(kind: str | None) -> str:
    clean = str(kind or "").strip().lower()
    if clean in {"page", "table"}:
        return clean
    return "table"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _display_label(value: str) -> str:
    clean = value.replace("_", " ").strip()
    return " ".join(part.capitalize() for part in clean.split()) if clean else value


def _stat_count(stats: dict[str, object] | None, key: str) -> int:
    if not isinstance(stats, dict):
        return 0
    return int(stats.get(key, 0) or 0)
