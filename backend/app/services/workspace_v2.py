"""v2 user-facing workspace query and mutation services."""

from __future__ import annotations

from collections import defaultdict
import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.claim_index import ClaimIndex
from app.models.item_link import ItemLink
from app.models.item_property import ItemProperty
from app.models.library_item import LibraryItem
from app.models.pod import Pod
from app.models.property_catalog import PropertyCatalog
from app.models.space import Space
from app.models.space_page import SpacePage
from app.schemas.mutations import EntityUpdateRequest
from app.schemas.workspace_v2 import (
    LibraryItemActivityRead,
    LibraryItemActivityResponse,
    LibraryItemDetailResponse,
    LibraryItemLinkRead,
    LibraryItemListRow,
    LibraryItemPropertyRead,
    LibraryItemsResponse,
    LibraryItemUpdateRequest,
    PropertyCatalogRead,
    PropertyCatalogResponse,
    PropertyCatalogUpdateRequest,
    SearchResultCard,
    SearchResultGroup,
    SearchV2Response,
    SpaceCreateRequest,
    SpacePageRead,
    SpacePagesResponse,
    SpaceRead,
    SpaceUpdateRequest,
    UnifiedClaimExplainResponse,
)
from app.services.experience_projection import rebuild_experience_projection
from app.services.explain import get_fact_explain_by_id, get_relation_explain_by_id
from app.services.mutations import update_entity
from app.services.organization import delete_pod_with_conversations
from app.services.search import semantic_search


def list_spaces(db: Session, *, include_technical: bool) -> list[SpaceRead]:
    """List user-facing spaces with item/page counts."""

    page_counts = (
        select(SpacePage.space_id.label("space_id"), func.count(SpacePage.id).label("page_count"))
        .group_by(SpacePage.space_id)
        .subquery()
    )
    item_counts = (
        select(LibraryItem.space_id.label("space_id"), func.count(LibraryItem.id).label("item_count"))
        .group_by(LibraryItem.space_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Space,
            func.coalesce(page_counts.c.page_count, 0).label("page_count"),
            func.coalesce(item_counts.c.item_count, 0).label("item_count"),
        )
        .outerjoin(page_counts, page_counts.c.space_id == Space.id)
        .outerjoin(item_counts, item_counts.c.space_id == Space.id)
        .order_by(Space.name.asc(), Space.id.asc())
    ).all()
    return [
        SpaceRead(
            id=space.id,
            slug=space.slug,
            name=space.name,
            description=space.description,
            page_count=int(page_count or 0),
            item_count=int(item_count or 0),
            created_at=space.created_at,
            updated_at=space.updated_at,
            technical_details={"pod_id": int(space.pod_id)} if include_technical else None,
        )
        for space, page_count, item_count in rows
    ]


def create_space(db: Session, payload: SpaceCreateRequest, *, include_technical: bool) -> SpaceRead:
    """Create one space by creating a backing pod then rebuilding projection."""

    clean_name = payload.name.strip()
    pod = Pod(
        slug=_unique_pod_slug(db, clean_name),
        name=clean_name,
        description=(payload.description or "").strip() or None,
        is_default=False,
    )
    db.add(pod)
    db.flush()
    rebuild_experience_projection(db, space_id=None, conversation_id=None)
    db.commit()
    space = db.scalar(select(Space).where(Space.pod_id == pod.id))
    if space is None:
        raise RuntimeError("Space projection rebuild did not create a matching space row.")
    return SpaceRead(
        id=space.id,
        slug=space.slug,
        name=space.name,
        description=space.description,
        page_count=int(db.scalar(select(func.count(SpacePage.id)).where(SpacePage.space_id == space.id)) or 0),
        item_count=int(db.scalar(select(func.count(LibraryItem.id)).where(LibraryItem.space_id == space.id)) or 0),
        created_at=space.created_at,
        updated_at=space.updated_at,
        technical_details={"pod_id": int(space.pod_id)} if include_technical else None,
    )


def update_space(
    db: Session,
    *,
    space_id: int,
    payload: SpaceUpdateRequest,
    include_technical: bool,
) -> SpaceRead | None:
    """Update one space by mutating the backing pod then rebuilding projection."""

    space = db.scalar(select(Space).where(Space.id == space_id))
    if space is None:
        return None
    pod = db.scalar(select(Pod).where(Pod.id == space.pod_id))
    if pod is None:
        return None

    if payload.name is not None:
        clean_name = payload.name.strip()
        pod.name = clean_name
        pod.slug = _unique_pod_slug(db, clean_name, exclude_pod_id=pod.id)
    if payload.description is not None:
        pod.description = (payload.description or "").strip() or None
    db.add(pod)
    rebuild_experience_projection(db, space_id=space_id, conversation_id=None)
    db.commit()

    refreshed = db.scalar(select(Space).where(Space.pod_id == pod.id))
    if refreshed is None:
        return None
    return SpaceRead(
        id=refreshed.id,
        slug=refreshed.slug,
        name=refreshed.name,
        description=refreshed.description,
        page_count=int(
            db.scalar(select(func.count(SpacePage.id)).where(SpacePage.space_id == refreshed.id)) or 0
        ),
        item_count=int(
            db.scalar(select(func.count(LibraryItem.id)).where(LibraryItem.space_id == refreshed.id)) or 0
        ),
        created_at=refreshed.created_at,
        updated_at=refreshed.updated_at,
        technical_details={"pod_id": int(refreshed.pod_id)} if include_technical else None,
    )


def delete_space(db: Session, *, space_id: int) -> bool:
    """Delete one space by deleting its backing pod and related records."""

    space = db.scalar(select(Space).where(Space.id == space_id))
    if space is None:
        return False
    deleted = delete_pod_with_conversations(db, pod_id=int(space.pod_id))
    return deleted is not None


def list_space_pages(
    db: Session,
    *,
    space_id: int,
    include_technical: bool,
) -> SpacePagesResponse | None:
    """List pages/tables within one space."""

    exists = db.scalar(select(Space.id).where(Space.id == space_id))
    if exists is None:
        return None
    item_counts = (
        select(LibraryItem.page_id.label("page_id"), func.count(LibraryItem.id).label("item_count"))
        .group_by(LibraryItem.page_id)
        .subquery()
    )
    rows = db.execute(
        select(
            SpacePage,
            func.coalesce(item_counts.c.item_count, 0).label("item_count"),
        )
        .outerjoin(item_counts, item_counts.c.page_id == SpacePage.id)
        .where(SpacePage.space_id == space_id)
        .order_by(SpacePage.sort_order.asc(), SpacePage.name.asc(), SpacePage.id.asc())
    ).all()
    return SpacePagesResponse(
        space_id=space_id,
        items=[
            SpacePageRead(
                id=page.id,
                space_id=page.space_id,
                parent_id=page.parent_id,
                kind="page" if page.kind.lower() == "page" else "table",
                slug=page.slug,
                name=page.name,
                description=page.description,
                sort_order=page.sort_order,
                item_count=int(item_count or 0),
                updated_at=page.updated_at,
                technical_details={"collection_id": int(page.collection_id)} if include_technical else None,
            )
            for page, item_count in rows
        ],
    )


def list_library_items(
    db: Session,
    *,
    limit: int,
    offset: int,
    query: str | None,
    type_label: str | None,
    space_id: int | None,
    page_id: int | None,
    sort: str,
    order: str,
    include_technical: bool,
) -> LibraryItemsResponse:
    """List library items from the projection read model."""

    filters = []
    clean_query = (query or "").strip()
    if clean_query:
        like = f"%{clean_query}%"
        filters.append(
            or_(
                LibraryItem.name.ilike(like),
                LibraryItem.type_label.ilike(like),
                LibraryItem.summary.ilike(like),
            )
        )
    clean_type_label = (type_label or "").strip()
    if clean_type_label:
        filters.append(LibraryItem.type_label == clean_type_label)
    if space_id is not None:
        filters.append(LibraryItem.space_id == space_id)
    if page_id is not None:
        filters.append(LibraryItem.page_id == page_id)

    total = int(
        db.scalar(select(func.count()).select_from(select(LibraryItem.id).where(*filters).subquery())) or 0
    )

    sort_map = {
        "name": LibraryItem.name,
        "mentions": LibraryItem.mention_count,
        "last_active": LibraryItem.last_seen_at,
        "type": LibraryItem.type_label,
    }
    sort_expr = sort_map.get(sort, LibraryItem.last_seen_at)
    sort_expr = sort_expr.asc() if order == "asc" else sort_expr.desc()

    rows = db.execute(
        select(
            LibraryItem,
            Space.name.label("space_name"),
            SpacePage.name.label("page_name"),
        )
        .outerjoin(Space, Space.id == LibraryItem.space_id)
        .outerjoin(SpacePage, SpacePage.id == LibraryItem.page_id)
        .where(*filters)
        .order_by(sort_expr, LibraryItem.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    item_ids = [row_item.id for row_item, _, _ in rows]
    key_properties = _list_item_properties(
        db,
        item_ids=item_ids,
        max_per_item=3,
        include_technical=include_technical,
    )

    return LibraryItemsResponse(
        items=[
            LibraryItemListRow(
                id=item.id,
                entity_id=int(item.entity_id),
                name=item.name,
                type_label=item.type_label,
                summary=item.summary,
                mention_count=int(item.mention_count),
                last_seen_at=item.last_seen_at,
                space_id=item.space_id,
                space_name=space_name,
                page_id=item.page_id,
                page_name=page_name,
                key_properties=key_properties.get(item.id, []),
                technical_details={"entity_id": int(item.entity_id)} if include_technical else None,
            )
            for item, space_name, page_name in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_library_item(
    db: Session,
    *,
    item_id: int,
    include_technical: bool,
) -> LibraryItemDetailResponse | None:
    """Return one library item detail payload."""

    row = db.execute(
        select(
            LibraryItem,
            Space.name.label("space_name"),
            SpacePage.name.label("page_name"),
        )
        .outerjoin(Space, Space.id == LibraryItem.space_id)
        .outerjoin(SpacePage, SpacePage.id == LibraryItem.page_id)
        .where(LibraryItem.id == item_id)
    ).one_or_none()
    if row is None:
        return None
    item, space_name, page_name = row
    properties = _list_item_properties(
        db,
        item_ids=[item.id],
        max_per_item=250,
        include_technical=include_technical,
    ).get(item.id, [])
    links = _list_item_links(db, item_id=item.id)
    activity = list_library_item_activity(
        db,
        item_id=item.id,
        limit=20,
        include_technical=include_technical,
    )
    if activity is None:
        return None
    return LibraryItemDetailResponse(
        id=item.id,
        entity_id=int(item.entity_id),
        name=item.name,
        type_label=item.type_label,
        summary=item.summary,
        mention_count=int(item.mention_count),
        last_seen_at=item.last_seen_at,
        space_id=item.space_id,
        space_name=space_name,
        page_id=item.page_id,
        page_name=page_name,
        properties=properties,
        links=links,
        activity_preview=activity.items,
        technical_details={"entity_id": int(item.entity_id)} if include_technical else None,
    )


def patch_library_item(
    db: Session,
    *,
    item_id: int,
    payload: LibraryItemUpdateRequest,
    include_technical: bool,
) -> LibraryItemDetailResponse | None:
    """Patch one library item by editing the backing canonical entity."""

    item = db.scalar(select(LibraryItem).where(LibraryItem.id == item_id))
    if item is None:
        return None
    update_payload = EntityUpdateRequest(
        canonical_name=payload.canonical_name,
        display_name=payload.display_name,
        type_label=payload.type_label,
        type=payload.type,
        known_aliases_json=payload.known_aliases_json,
        aliases_json=payload.aliases_json,
        tags_json=payload.tags_json,
    )
    updated = update_entity(db, int(item.entity_id), update_payload)
    if updated is None:
        return None
    return get_library_item(db, item_id=item_id, include_technical=include_technical)


def list_library_item_activity(
    db: Session,
    *,
    item_id: int,
    limit: int,
    include_technical: bool,
) -> LibraryItemActivityResponse | None:
    """List claim activity for one library item from claim_index."""

    exists = db.scalar(select(LibraryItem.id).where(LibraryItem.id == item_id))
    if exists is None:
        return None
    rows = list(
        db.scalars(
            select(ClaimIndex)
            .where(
                or_(
                    ClaimIndex.library_item_id == item_id,
                    ClaimIndex.related_library_item_id == item_id,
                )
            )
            .order_by(ClaimIndex.occurred_at.desc(), ClaimIndex.id.desc())
            .limit(limit)
        ).all()
    )
    related_ids: set[int] = set()
    for row in rows:
        if row.library_item_id is not None:
            related_ids.add(int(row.library_item_id))
        if row.related_library_item_id is not None:
            related_ids.add(int(row.related_library_item_id))
    names_by_id = {
        int(library_item_id): str(name)
        for library_item_id, name in db.execute(
            select(LibraryItem.id, LibraryItem.name).where(LibraryItem.id.in_(sorted(related_ids) or [-1]))
        ).all()
    }

    items: list[LibraryItemActivityRead] = []
    for row in rows:
        label = row.property_key or row.relation_type or row.claim_kind
        related_id: int | None = None
        if row.library_item_id == item_id:
            related_id = int(row.related_library_item_id) if row.related_library_item_id is not None else None
        elif row.related_library_item_id == item_id:
            related_id = int(row.library_item_id) if row.library_item_id is not None else None
        items.append(
            LibraryItemActivityRead(
                claim_index_id=int(row.id),
                claim_kind="fact" if row.claim_kind == "fact" else "relation",
                claim_id=int(row.claim_id),
                label=label,
                value_text=row.value_text,
                confidence=row.confidence,
                occurred_at=row.occurred_at,
                related_item_id=related_id,
                related_item_name=names_by_id.get(related_id) if related_id is not None else None,
                technical_details=(
                    {
                        "conversation_id": row.conversation_id,
                        "extractor_run_id": row.extractor_run_id,
                        "source_message_ids_json": list(row.source_message_ids_json or []),
                    }
                    if include_technical
                    else None
                ),
            )
        )
    return LibraryItemActivityResponse(item_id=item_id, items=items)


def list_property_catalog(
    db: Session,
    *,
    query: str | None,
    status: str | None,
    kind: str | None,
    include_technical: bool,
) -> PropertyCatalogResponse:
    """List user-facing property/type catalog entries."""

    filters = []
    clean_query = (query or "").strip()
    if clean_query:
        filters.append(PropertyCatalog.display_label.ilike(f"%{clean_query}%"))
    clean_status = (status or "").strip()
    if clean_status:
        filters.append(PropertyCatalog.status == clean_status)
    clean_kind = (kind or "").strip()
    if clean_kind:
        filters.append(PropertyCatalog.kind == clean_kind)

    total = int(
        db.scalar(select(func.count()).select_from(select(PropertyCatalog.id).where(*filters).subquery())) or 0
    )
    rows = list(
        db.scalars(
            select(PropertyCatalog)
            .where(*filters)
            .order_by(PropertyCatalog.mention_count.desc(), PropertyCatalog.display_label.asc())
        ).all()
    )
    return PropertyCatalogResponse(
        items=[
            PropertyCatalogRead(
                id=row.id,
                display_label=row.display_label,
                kind="field" if row.kind == "field" else "relation",
                status="stable"
                if row.status == "stable"
                else ("deprecated" if row.status == "deprecated" else "emerging"),
                mention_count=int(row.mention_count),
                last_seen_at=row.last_seen_at,
                technical_details={"property_key": row.property_key} if include_technical else None,
            )
            for row in rows
        ],
        total=total,
    )


def patch_property_catalog(
    db: Session,
    *,
    property_id: int,
    payload: PropertyCatalogUpdateRequest,
    include_technical: bool,
) -> PropertyCatalogRead | None:
    """Patch one catalog entry (display label and/or stability status)."""

    row = db.scalar(select(PropertyCatalog).where(PropertyCatalog.id == property_id))
    if row is None:
        return None
    if payload.display_label is not None:
        row.display_label = payload.display_label.strip()
    if payload.status is not None:
        row.status = payload.status
    db.add(row)
    db.commit()
    db.refresh(row)
    return PropertyCatalogRead(
        id=row.id,
        display_label=row.display_label,
        kind="field" if row.kind == "field" else "relation",
        status="stable" if row.status == "stable" else ("deprecated" if row.status == "deprecated" else "emerging"),
        mention_count=int(row.mention_count),
        last_seen_at=row.last_seen_at,
        technical_details={"property_key": row.property_key} if include_technical else None,
    )


def get_unified_claim_explain(
    db: Session,
    *,
    claim_index_id: int,
    include_technical: bool,
) -> UnifiedClaimExplainResponse | None:
    """Return unified explain payload for one claim_index row."""

    claim_row = db.scalar(select(ClaimIndex).where(ClaimIndex.id == claim_index_id))
    if claim_row is None:
        return None
    if claim_row.claim_kind == "fact":
        explain = get_fact_explain_by_id(db, int(claim_row.claim_id))
        if explain is None:
            return None
        title = f"{explain.fact.subject_entity_name} {explain.fact.predicate} {explain.fact.object_value}"
        why_this_exists = (
            "This claim was extracted from source messages and retained as a stable fact in the workspace."
        )
        technical_details = (
            {
                "extractor_run_id": explain.extractor_run_id,
                "extraction_metadata": explain.extraction_metadata.model_dump()
                if explain.extraction_metadata is not None
                else None,
                "resolution_events": [event.model_dump() for event in explain.resolution_events],
                "claim_index": {
                    "id": int(claim_row.id),
                    "conversation_id": claim_row.conversation_id,
                    "source_message_ids_json": list(claim_row.source_message_ids_json or []),
                },
            }
            if include_technical
            else None
        )
        return UnifiedClaimExplainResponse(
            claim_index_id=int(claim_row.id),
            claim_kind="fact",
            claim_id=int(claim_row.claim_id),
            title=title,
            why_this_exists=why_this_exists,
            evidence_snippets=list(dict.fromkeys(explain.snippets)),
            source_messages=explain.source_messages,
            canonicalization=explain.schema_canonicalization,
            technical_details=technical_details,
        )

    explain = get_relation_explain_by_id(db, int(claim_row.claim_id))
    if explain is None:
        return None
    title = (
        f"{explain.relation.from_entity_name} {explain.relation.relation_type} "
        f"{explain.relation.to_entity_name}"
    )
    why_this_exists = (
        "This relationship was extracted from source messages and linked across items in the workspace."
    )
    technical_details = (
        {
            "extractor_run_id": explain.extractor_run_id,
            "extraction_metadata": explain.extraction_metadata.model_dump()
            if explain.extraction_metadata is not None
            else None,
            "resolution_events": [event.model_dump() for event in explain.resolution_events],
            "qualifiers_json": explain.relation.qualifiers_json,
            "claim_index": {
                "id": int(claim_row.id),
                "conversation_id": claim_row.conversation_id,
                "source_message_ids_json": list(claim_row.source_message_ids_json or []),
            },
        }
        if include_technical
        else None
    )
    return UnifiedClaimExplainResponse(
        claim_index_id=int(claim_row.id),
        claim_kind="relation",
        claim_id=int(claim_row.claim_id),
        title=title,
        why_this_exists=why_this_exists,
        evidence_snippets=list(dict.fromkeys(explain.snippets)),
        source_messages=explain.source_messages,
        canonicalization=explain.schema_canonicalization,
        technical_details=technical_details,
    )


def search_workspace(
    db: Session,
    *,
    query: str,
    conversation_id: str | None,
    type_label: str | None,
    space_id: int | None,
    page_id: int | None,
    include_technical: bool,
) -> SearchV2Response:
    """Return grouped, card-friendly search results for v2 UI surfaces."""

    legacy = semantic_search(
        db,
        query=query,
        conversation_id=conversation_id,
        type_label=type_label,
        pod_id=space_id,
        collection_id=page_id,
        start_time=None,
        end_time=None,
        limit=20,
    )
    fact_ids = [int(hit.fact.id) for hit in legacy.facts]
    claim_index_by_fact_id = {
        int(claim_id): int(claim_index_id)
        for claim_index_id, claim_id in db.execute(
            select(ClaimIndex.id, ClaimIndex.claim_id).where(
                ClaimIndex.claim_kind == "fact",
                ClaimIndex.claim_id.in_(fact_ids or [-1]),
            )
        ).all()
    }
    item_cards = [
        SearchResultCard(
            id=f"item-{hit.entity.id}",
            kind="item",
            title=hit.entity.canonical_name,
            subtitle=hit.entity.type_label,
            score=float(hit.similarity),
            href=f"/app/entities/{hit.entity.id}",
            technical_details=(
                {
                    "entity_id": int(hit.entity.id),
                    "conversation_id": hit.entity.conversation_id,
                }
                if include_technical
                else None
            ),
        )
        for hit in legacy.entities
    ]
    claim_cards = [
        SearchResultCard(
            id=f"claim-{claim_index_by_fact_id.get(int(hit.fact.id), hit.fact.id)}",
            kind="claim",
            title=f"{hit.fact.subject_entity_name} {hit.fact.predicate}",
            subtitle=hit.fact.object_value,
            score=float(hit.similarity),
            href=f"/app/explain/facts/{hit.fact.id}",
            technical_details=(
                {
                    "fact_id": int(hit.fact.id),
                    "claim_index_id": claim_index_by_fact_id.get(int(hit.fact.id)),
                    "conversation_id": hit.fact.conversation_id,
                }
                if include_technical
                else None
            ),
        )
        for hit in legacy.facts
    ]
    return SearchV2Response(
        query=legacy.query,
        groups=[
            SearchResultGroup(
                key="items",
                label="Library Items",
                count=len(item_cards),
                items=item_cards,
            ),
            SearchResultGroup(
                key="claims",
                label="Claims",
                count=len(claim_cards),
                items=claim_cards,
            ),
        ],
    )


def _list_item_properties(
    db: Session,
    *,
    item_ids: list[int],
    max_per_item: int,
    include_technical: bool,
) -> dict[int, list[LibraryItemPropertyRead]]:
    by_item: dict[int, list[ItemProperty]] = defaultdict(list)
    if not item_ids:
        return {}
    rows = list(
        db.scalars(
            select(ItemProperty)
            .where(ItemProperty.library_item_id.in_(item_ids))
            .order_by(
                ItemProperty.library_item_id.asc(),
                ItemProperty.last_observed_at.desc(),
                ItemProperty.id.desc(),
            )
        ).all()
    )
    for row in rows:
        bucket = by_item[int(row.library_item_id)]
        if len(bucket) >= max_per_item:
            continue
        bucket.append(row)

    fact_claim_ids = [int(row.claim_id) for row in rows if row.claim_kind == "fact"]
    relation_claim_ids = [int(row.claim_id) for row in rows if row.claim_kind == "relation"]
    claim_index_map: dict[tuple[str, int], int] = {}
    if fact_claim_ids:
        for claim_index_id, claim_id in db.execute(
            select(ClaimIndex.id, ClaimIndex.claim_id).where(
                ClaimIndex.claim_kind == "fact",
                ClaimIndex.claim_id.in_(fact_claim_ids),
            )
        ).all():
            claim_index_map[("fact", int(claim_id))] = int(claim_index_id)
    if relation_claim_ids:
        for claim_index_id, claim_id in db.execute(
            select(ClaimIndex.id, ClaimIndex.claim_id).where(
                ClaimIndex.claim_kind == "relation",
                ClaimIndex.claim_id.in_(relation_claim_ids),
            )
        ).all():
            claim_index_map[("relation", int(claim_id))] = int(claim_index_id)

    payload: dict[int, list[LibraryItemPropertyRead]] = defaultdict(list)
    for item_id, item_rows in by_item.items():
        payload[item_id] = [
            LibraryItemPropertyRead(
                property_key=row.property_key,
                label=row.property_label,
                value=row.property_value,
                claim_index_id=claim_index_map.get((row.claim_kind, int(row.claim_id))),
                claim_kind=row.claim_kind if include_technical else None,
                claim_id=int(row.claim_id) if include_technical else None,
                last_observed_at=row.last_observed_at if include_technical else None,
            )
            for row in item_rows
        ]
    return payload


def _list_item_links(db: Session, *, item_id: int) -> list[LibraryItemLinkRead]:
    left_item = aliased(LibraryItem)
    right_item = aliased(LibraryItem)

    outgoing_rows = db.execute(
        select(
            ItemLink.relation_type,
            ItemLink.relation_count,
            ItemLink.last_seen_at,
            right_item.id.label("other_item_id"),
            right_item.name.label("other_item_name"),
        )
        .join(right_item, right_item.id == ItemLink.to_library_item_id)
        .where(ItemLink.from_library_item_id == item_id)
        .order_by(ItemLink.relation_count.desc(), ItemLink.last_seen_at.desc())
        .limit(60)
    ).all()
    incoming_rows = db.execute(
        select(
            ItemLink.relation_type,
            ItemLink.relation_count,
            ItemLink.last_seen_at,
            left_item.id.label("other_item_id"),
            left_item.name.label("other_item_name"),
        )
        .join(left_item, left_item.id == ItemLink.from_library_item_id)
        .where(ItemLink.to_library_item_id == item_id)
        .order_by(ItemLink.relation_count.desc(), ItemLink.last_seen_at.desc())
        .limit(60)
    ).all()
    links: list[LibraryItemLinkRead] = [
        LibraryItemLinkRead(
            relation_type=str(relation_type),
            relation_count=int(relation_count),
            direction="outgoing",
            other_item_id=int(other_item_id),
            other_item_name=str(other_item_name),
            last_seen_at=last_seen_at,
        )
        for relation_type, relation_count, last_seen_at, other_item_id, other_item_name in outgoing_rows
    ]
    links.extend(
        LibraryItemLinkRead(
            relation_type=str(relation_type),
            relation_count=int(relation_count),
            direction="incoming",
            other_item_id=int(other_item_id),
            other_item_name=str(other_item_name),
            last_seen_at=last_seen_at,
        )
        for relation_type, relation_count, last_seen_at, other_item_id, other_item_name in incoming_rows
    )
    return links[:100]


def _unique_pod_slug(db: Session, value: str, *, exclude_pod_id: int | None = None) -> str:
    base_slug = _slugify(value) or "space"
    slug = base_slug
    suffix = 2
    while True:
        stmt = select(Pod.id).where(Pod.slug == slug)
        if exclude_pod_id is not None:
            stmt = stmt.where(Pod.id != exclude_pod_id)
        if db.scalar(stmt) is None:
            return slug
        slug = f"{base_slug}-{suffix}"
        suffix += 1


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
