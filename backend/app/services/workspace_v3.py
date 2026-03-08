"""Stable workspace-first v3 query and mutation services."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.collection import Collection
from app.models.collection_column import CollectionColumn
from app.models.collection_item import CollectionItem
from app.models.collection_item_relation import CollectionItemRelation
from app.models.collection_item_relation_suggestion import CollectionItemRelationSuggestion
from app.models.collection_item_value import CollectionItemValue
from app.models.collection_item_value_suggestion import CollectionItemValueSuggestion
from app.models.evidence import Evidence
from app.models.entity import Entity
from app.models.pod import Pod
from app.models.source import Source
from app.models.workspace_enrichment_run import WorkspaceEnrichmentRun
from app.services.organization import delete_pod_with_conversations
from app.schemas.workspace_v3 import (
    WorkspaceCatalogRow,
    WorkspaceCellRead,
    WorkspaceCellSuggestionRead,
    WorkspaceSpaceCreateRequest,
    WorkspaceCollectionCreateRequest,
    WorkspaceCollectionRead,
    WorkspaceCollectionUpdateRequest,
    WorkspaceColumnCreateRequest,
    WorkspaceColumnRead,
    WorkspaceColumnUpdateRequest,
    WorkspaceLibraryResponse,
    WorkspaceOverviewResponse,
    WorkspaceEnrichmentRunRead,
    WorkspacePropertyCatalogResponse,
    WorkspacePropertyCatalogRow,
    WorkspaceRowCreateRequest,
    WorkspaceRowDetailRead,
    WorkspaceRowRead,
    WorkspaceRowRelationRead,
    WorkspaceRowUpdateRequest,
    WorkspaceRowsResponse,
    WorkspaceSuggestionReviewResult,
    WorkspaceSourceRead,
    WorkspaceSpaceRead,
    WorkspaceSpaceUpdateRequest,
)


def list_workspace_spaces(db: Session) -> list[WorkspaceSpaceRead]:
    collection_counts = (
        select(Collection.pod_id.label("pod_id"), func.count(Collection.id).label("collection_count"))
        .group_by(Collection.pod_id)
        .subquery()
    )
    row_counts = (
        select(Collection.pod_id.label("pod_id"), func.count(CollectionItem.id).label("row_count"))
        .join(CollectionItem, CollectionItem.collection_id == Collection.id)
        .group_by(Collection.pod_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Pod,
            func.coalesce(collection_counts.c.collection_count, 0).label("collection_count"),
            func.coalesce(row_counts.c.row_count, 0).label("row_count"),
        )
        .outerjoin(collection_counts, collection_counts.c.pod_id == Pod.id)
        .outerjoin(row_counts, row_counts.c.pod_id == Pod.id)
        .where(~Pod.slug.like("compat-pod-%"), Pod.slug != "imported")
        .order_by(Pod.is_default.desc(), Pod.name.asc(), Pod.id.asc())
    ).all()
    return [
        WorkspaceSpaceRead(
            id=pod.id,
            slug=pod.slug,
            name=pod.name,
            description=pod.description,
            collection_count=int(collection_count or 0),
            row_count=int(row_count or 0),
            created_at=pod.created_at,
            updated_at=pod.updated_at,
        )
        for pod, collection_count, row_count in rows
    ]


def create_workspace_space(
    db: Session,
    *,
    payload: WorkspaceSpaceCreateRequest,
) -> WorkspaceSpaceRead:
    base_slug = _slugify(payload.name)
    slug = base_slug
    suffix = 2
    while db.scalar(select(Pod.id).where(Pod.slug == slug)) is not None:
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    pod = Pod(
        slug=slug,
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        is_default=False,
    )
    db.add(pod)
    db.commit()
    db.refresh(pod)
    return WorkspaceSpaceRead(
        id=pod.id,
        slug=pod.slug,
        name=pod.name,
        description=pod.description,
        collection_count=0,
        row_count=0,
        created_at=pod.created_at,
        updated_at=pod.updated_at,
    )


def update_workspace_space(
    db: Session,
    *,
    space_id: int,
    payload: WorkspaceSpaceUpdateRequest,
) -> WorkspaceSpaceRead | None:
    pod = db.scalar(select(Pod).where(Pod.id == space_id, ~Pod.slug.like("compat-pod-%"), Pod.slug != "imported"))
    if pod is None:
        return None
    if payload.name is not None:
        pod.name = payload.name.strip()
    if payload.description is not None:
        pod.description = (payload.description or "").strip() or None
    db.add(pod)
    db.commit()
    return get_workspace_overview(db, space_id=space_id).space if get_workspace_overview(db, space_id=space_id) else None


def delete_workspace_space(db: Session, *, space_id: int) -> bool:
    deleted = delete_pod_with_conversations(db, pod_id=space_id)
    return deleted is not None


def get_workspace_overview(db: Session, *, space_id: int) -> WorkspaceOverviewResponse | None:
    pod = db.scalar(select(Pod).where(Pod.id == space_id))
    if pod is None:
        return None
    collections = _list_collections_for_space(db, space_id=space_id)
    row_count = sum(collection.row_count for collection in collections)
    return WorkspaceOverviewResponse(
        space=WorkspaceSpaceRead(
            id=pod.id,
            slug=pod.slug,
            name=pod.name,
            description=pod.description,
            collection_count=len(collections),
            row_count=row_count,
            created_at=pod.created_at,
            updated_at=pod.updated_at,
        ),
        collections=collections,
    )


def create_workspace_collection(
    db: Session,
    *,
    space_id: int,
    payload: WorkspaceCollectionCreateRequest,
) -> WorkspaceCollectionRead | None:
    pod = db.scalar(select(Pod).where(Pod.id == space_id))
    if pod is None:
        return None
    base_slug = _slugify(payload.name)
    slug = base_slug
    suffix = 2
    existing_slugs = set(db.scalars(select(Collection.slug).where(Collection.pod_id == space_id)).all())
    while slug in existing_slugs:
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    row = Collection(
        pod_id=space_id,
        parent_id=None,
        kind="TABLE",
        slug=slug,
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        schema_json={"columns": [{"name": "title", "label": "Name", "type": "title"}], "source": "manual"},
        view_config_json={},
        sort_order=int(db.scalar(select(func.coalesce(func.max(Collection.sort_order), 0)).where(Collection.pod_id == space_id)) or 0) + 10,
        is_auto_generated=False,
    )
    db.add(row)
    db.flush()
    title_column = CollectionColumn(
        collection_id=row.id,
        key="title",
        label="Name",
        data_type="title",
        kind="title",
        sort_order=0,
        required=True,
        is_relation=False,
        origin="manual",
        planner_locked=True,
        user_locked=True,
        enrichment_policy_json={"enabled": False},
    )
    db.add(title_column)
    db.commit()
    return _collection_read(db, row.id)


def update_workspace_collection(
    db: Session,
    *,
    collection_id: int,
    payload: WorkspaceCollectionUpdateRequest,
) -> WorkspaceCollectionRead | None:
    row = db.scalar(select(Collection).where(Collection.id == collection_id))
    if row is None:
        return None
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.description is not None:
        row.description = (payload.description or "").strip() or None
    db.add(row)
    db.commit()
    return _collection_read(db, row.id)


def delete_workspace_collection(db: Session, *, collection_id: int) -> bool:
    row = db.scalar(select(Collection).where(Collection.id == collection_id))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def create_workspace_column(
    db: Session,
    *,
    collection_id: int,
    payload: WorkspaceColumnCreateRequest,
) -> WorkspaceColumnRead | None:
    collection = db.scalar(select(Collection).where(Collection.id == collection_id))
    if collection is None:
        return None
    key = _slugify(payload.label).replace("-", "_")
    suffix = 2
    existing_keys = set(
        db.scalars(select(CollectionColumn.key).where(CollectionColumn.collection_id == collection_id)).all()
    )
    while key in existing_keys:
        key = f"{_slugify(payload.label).replace('-', '_')}_{suffix}"
        suffix += 1
    row = CollectionColumn(
        collection_id=collection_id,
        key=key,
        label=payload.label.strip(),
        data_type=payload.data_type.strip().lower(),
        kind="property",
        sort_order=int(db.scalar(select(func.coalesce(func.max(CollectionColumn.sort_order), 0)).where(CollectionColumn.collection_id == collection_id)) or 0) + 1,
        required=False,
        is_relation=False,
        origin="manual",
        planner_locked=False,
        user_locked=True,
        enrichment_policy_json={"enabled": True},
    )
    db.add(row)
    db.commit()
    return _column_read(db, row.id)


def update_workspace_column(
    db: Session,
    *,
    column_id: int,
    payload: WorkspaceColumnUpdateRequest,
) -> WorkspaceColumnRead | None:
    row = db.scalar(select(CollectionColumn).where(CollectionColumn.id == column_id))
    if row is None:
        return None
    if payload.label is not None:
        row.label = payload.label.strip()
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    if payload.required is not None:
        row.required = payload.required
    if payload.user_locked is not None:
        row.user_locked = payload.user_locked
    db.add(row)
    db.commit()
    return _column_read(db, row.id)


def delete_workspace_column(db: Session, *, column_id: int) -> bool:
    row = db.scalar(select(CollectionColumn).where(CollectionColumn.id == column_id))
    if row is None or row.key == "title":
        return False
    db.delete(row)
    db.commit()
    return True


def list_workspace_rows(
    db: Session,
    *,
    collection_id: int,
    limit: int,
    offset: int,
    query: str | None,
) -> WorkspaceRowsResponse | None:
    collection = _collection_read(db, collection_id)
    if collection is None:
        return None
    columns = _columns_for_collection(db, collection_id=collection_id)
    filters = [CollectionItem.collection_id == collection_id]
    if query:
        filters.append(or_(CollectionItem.title.ilike(f"%{query.strip()}%"), CollectionItem.summary.ilike(f"%{query.strip()}%")))
    total = int(db.scalar(select(func.count(CollectionItem.id)).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(CollectionItem)
            .where(*filters)
            .order_by(CollectionItem.sort_order.asc(), CollectionItem.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    row_ids = [row.id for row in rows]
    cells_by_row = _cells_for_rows(db, row_ids=row_ids, columns=columns)
    pending_count = int(
        db.scalar(
            select(func.count(CollectionItemValueSuggestion.id))
            .join(CollectionItem, CollectionItem.id == CollectionItemValueSuggestion.collection_item_id)
            .where(
                CollectionItem.collection_id == collection_id,
                CollectionItemValueSuggestion.status == "pending",
            )
        )
        or 0
    )
    return WorkspaceRowsResponse(
        collection=collection,
        columns=columns,
        rows=[
            WorkspaceRowRead(
                id=row.id,
                collection_id=row.collection_id,
                entity_id=row.entity_id,
                primary_entity_id=row.primary_entity_id,
                title=row.title or f"Row {row.id}",
                summary=row.summary,
                detail_blurb=row.detail_blurb,
                sort_order=row.sort_order,
                updated_at=row.updated_at,
                cells=cells_by_row.get(row.id, _empty_cells(columns)),
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
        pending_suggestion_count=pending_count,
    )


def create_workspace_row(
    db: Session,
    *,
    collection_id: int,
    payload: WorkspaceRowCreateRequest,
) -> WorkspaceRowRead | None:
    collection = db.scalar(select(Collection).where(Collection.id == collection_id))
    entity = db.scalar(select(Entity).where(Entity.id == payload.entity_id, Entity.merged_into_id.is_(None)))
    if collection is None or entity is None:
        return None
    row = db.scalar(
        select(CollectionItem).where(
            CollectionItem.collection_id == collection_id,
            CollectionItem.entity_id == payload.entity_id,
        )
    )
    if row is None:
        row = CollectionItem(
            collection_id=collection_id,
            entity_id=payload.entity_id,
            primary_entity_id=payload.entity_id,
            title=entity.display_name or entity.canonical_name,
            summary=None,
            detail_blurb=f"{entity.canonical_name} is tracked in this workspace.",
            notes_markdown=None,
            sort_key=None,
            sort_order=int(db.scalar(select(func.coalesce(func.max(CollectionItem.sort_order), 0)).where(CollectionItem.collection_id == collection_id)) or 0) + 1,
        )
        db.add(row)
        db.commit()
    return get_workspace_row_detail(db, row_id=row.id)


def update_workspace_row(
    db: Session,
    *,
    row_id: int,
    payload: WorkspaceRowUpdateRequest,
) -> WorkspaceRowDetailRead | None:
    row = db.scalar(select(CollectionItem).where(CollectionItem.id == row_id))
    if row is None:
        return None
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.summary is not None:
        row.summary = payload.summary
    if payload.detail_blurb is not None:
        row.detail_blurb = payload.detail_blurb
    if payload.notes_markdown is not None:
        row.notes_markdown = payload.notes_markdown
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    db.add(row)
    db.commit()
    return get_workspace_row_detail(db, row_id=row.id)


def delete_workspace_row(db: Session, *, row_id: int) -> bool:
    row = db.scalar(select(CollectionItem).where(CollectionItem.id == row_id))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def update_workspace_cell(
    db: Session,
    *,
    row_id: int,
    column_id: int,
    display_value: str | None,
    value_json: object | None,
    status: str | None,
) -> WorkspaceRowDetailRead | None:
    row = db.scalar(select(CollectionItem).where(CollectionItem.id == row_id))
    column = db.scalar(select(CollectionColumn).where(CollectionColumn.id == column_id))
    if row is None or column is None or row.collection_id != column.collection_id:
        return None
    value = db.scalar(
        select(CollectionItemValue).where(
            CollectionItemValue.collection_item_id == row_id,
            CollectionItemValue.collection_column_id == column_id,
        )
    )
    if value is None:
        value = CollectionItemValue(
            collection_item_id=row_id,
            collection_column_id=column_id,
        )
    if display_value is not None:
        value.display_value = display_value
    if value_json is not None or display_value is None:
        value.value_json = value_json if value_json is not None else display_value
    value.value_type = column.data_type
    value.source_kind = "manual"
    value.status = status or "manual"
    value.edited_by_user = True
    value.last_verified_at = None
    db.add(value)
    db.flush()
    db.execute(delete(Evidence).where(Evidence.collection_item_value_id == value.id))
    db.commit()
    return get_workspace_row_detail(db, row_id=row_id)


def get_workspace_row_detail(db: Session, *, row_id: int) -> WorkspaceRowDetailRead | None:
    row = db.scalar(select(CollectionItem).where(CollectionItem.id == row_id))
    if row is None:
        return None
    collection = _collection_read(db, row.collection_id)
    if collection is None:
        return None
    columns = _columns_for_collection(db, collection_id=row.collection_id)
    cells = _cells_for_rows(db, row_ids=[row.id], columns=columns).get(row.id, _empty_cells(columns))
    relations = _relations_for_row(db, row_id=row.id)
    pending_relation_count = int(
        db.scalar(
            select(func.count(CollectionItemRelationSuggestion.id)).where(
                CollectionItemRelationSuggestion.status == "pending",
                or_(
                    CollectionItemRelationSuggestion.from_collection_item_id == row.id,
                    CollectionItemRelationSuggestion.to_collection_item_id == row.id,
                ),
            )
        )
        or 0
    )
    return WorkspaceRowDetailRead(
        id=row.id,
        collection_id=row.collection_id,
        collection_name=collection.name,
        collection_slug=collection.slug,
        entity_id=row.entity_id,
        primary_entity_id=row.primary_entity_id,
        title=row.title or f"Row {row.id}",
        summary=row.summary,
        detail_blurb=row.detail_blurb,
        notes_markdown=row.notes_markdown,
        sort_order=row.sort_order,
        updated_at=row.updated_at,
        cells=cells,
        relations=relations,
        pending_relation_suggestion_count=pending_relation_count,
    )


def list_workspace_library(
    db: Session,
    *,
    limit: int,
    offset: int,
    query: str | None,
    space_id: int | None,
    collection_id: int | None,
) -> WorkspaceLibraryResponse:
    pod_alias = aliased(Pod)
    collection_alias = aliased(Collection)
    filters = []
    if space_id is not None:
        filters.append(collection_alias.pod_id == space_id)
    if collection_id is not None:
        filters.append(collection_alias.id == collection_id)
    if query:
        filters.append(or_(CollectionItem.title.ilike(f"%{query.strip()}%"), CollectionItem.summary.ilike(f"%{query.strip()}%")))
    total = int(
        db.scalar(
            select(func.count(CollectionItem.id))
            .join(collection_alias, collection_alias.id == CollectionItem.collection_id)
            .where(*filters)
        )
        or 0
    )
    rows = db.execute(
        select(CollectionItem, collection_alias, pod_alias)
        .join(collection_alias, collection_alias.id == CollectionItem.collection_id)
        .join(pod_alias, pod_alias.id == collection_alias.pod_id)
        .where(*filters)
        .order_by(CollectionItem.updated_at.desc(), CollectionItem.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    collection_columns: dict[int, list[WorkspaceColumnRead]] = {}
    cells_by_row: dict[int, list[WorkspaceCellRead]] = {}
    for row, collection, _ in rows:
        if collection.id not in collection_columns:
            collection_columns[collection.id] = _columns_for_collection(db, collection_id=collection.id)
        if row.id not in cells_by_row:
            cells_by_row.update(_cells_for_rows(db, row_ids=[row.id], columns=collection_columns[collection.id]))
    items = [
        WorkspaceCatalogRow(
            collection_id=collection.id,
            collection_name=collection.name,
            collection_slug=collection.slug,
            space_id=pod.id,
            space_name=pod.name,
            space_slug=pod.slug,
            row=WorkspaceRowRead(
                id=row.id,
                collection_id=row.collection_id,
                entity_id=row.entity_id,
                primary_entity_id=row.primary_entity_id,
                title=row.title or f"Row {row.id}",
                summary=row.summary,
                detail_blurb=row.detail_blurb,
                sort_order=row.sort_order,
                updated_at=row.updated_at,
                cells=cells_by_row.get(row.id, _empty_cells(collection_columns[collection.id])),
            ),
        )
        for row, collection, pod in rows
    ]
    return WorkspaceLibraryResponse(items=items, total=total, limit=limit, offset=offset)


def list_workspace_property_catalog(
    db: Session,
    *,
    space_id: int | None,
) -> WorkspacePropertyCatalogResponse:
    rows = []
    for column, collection, pod in db.execute(
        select(CollectionColumn, Collection, Pod)
        .join(Collection, Collection.id == CollectionColumn.collection_id)
        .join(Pod, Pod.id == Collection.pod_id)
        .where(*( [Collection.pod_id == space_id] if space_id is not None else []))
        .order_by(Pod.name.asc(), Collection.name.asc(), CollectionColumn.sort_order.asc())
    ).all():
        row_count = int(
            db.scalar(select(func.count(CollectionItem.id)).where(CollectionItem.collection_id == collection.id)) or 0
        )
        coverage_count = int(
            db.scalar(
                select(func.count(CollectionItemValue.id)).where(
                    CollectionItemValue.collection_column_id == column.id,
                    CollectionItemValue.display_value.is_not(None),
                )
            )
            or 0
        )
        coverage_ratio = float(coverage_count / row_count) if row_count else 0.0
        rows.append(
            WorkspacePropertyCatalogRow(
                id=column.id,
                collection_id=collection.id,
                collection_name=collection.name,
                collection_slug=collection.slug,
                space_id=pod.id,
                space_name=pod.name,
                key=column.key,
                label=column.label,
                data_type=column.data_type,
                kind=column.kind,
                origin=column.origin,
                planner_locked=column.planner_locked,
                user_locked=column.user_locked,
                coverage_count=coverage_count,
                row_count=row_count,
                coverage_ratio=coverage_ratio,
                updated_at=column.updated_at,
            )
        )
    return WorkspacePropertyCatalogResponse(items=rows, total=len(rows))


def _collection_read(db: Session, collection_id: int) -> WorkspaceCollectionRead | None:
    row = db.scalar(select(Collection).where(Collection.id == collection_id))
    if row is None:
        return None
    row_count = int(db.scalar(select(func.count(CollectionItem.id)).where(CollectionItem.collection_id == row.id)) or 0)
    column_count = int(db.scalar(select(func.count(CollectionColumn.id)).where(CollectionColumn.collection_id == row.id)) or 0)
    pending_value_count = int(
        db.scalar(
            select(func.count(CollectionItemValueSuggestion.id))
            .join(CollectionItem, CollectionItem.id == CollectionItemValueSuggestion.collection_item_id)
            .where(
                CollectionItem.collection_id == row.id,
                CollectionItemValueSuggestion.status == "pending",
            )
        )
        or 0
    )
    pending_relation_count = int(
        db.scalar(
            select(func.count(CollectionItemRelationSuggestion.id))
            .join(CollectionItem, CollectionItem.id == CollectionItemRelationSuggestion.from_collection_item_id)
            .where(
                CollectionItem.collection_id == row.id,
                CollectionItemRelationSuggestion.status == "pending",
            )
        )
        or 0
    )
    pending_total = pending_value_count + pending_relation_count
    return WorkspaceCollectionRead(
        id=row.id,
        pod_id=row.pod_id,
        parent_id=row.parent_id,
        kind=row.kind,
        slug=row.slug,
        name=row.name,
        description=row.description,
        is_auto_generated=row.is_auto_generated,
        sort_order=row.sort_order,
        column_count=column_count,
        row_count=row_count,
        pending_suggestion_count=pending_total,
        has_pending_suggestions=pending_total > 0,
        updated_at=row.updated_at,
    )


def _list_collections_for_space(db: Session, *, space_id: int) -> list[WorkspaceCollectionRead]:
    return [
        item
        for item in (
            _collection_read(db, collection.id)
            for collection in db.scalars(
                select(Collection).where(Collection.pod_id == space_id).order_by(Collection.sort_order.asc(), Collection.id.asc())
            ).all()
        )
        if item is not None
    ]


def _column_read(db: Session, column_id: int) -> WorkspaceColumnRead | None:
    row = db.scalar(select(CollectionColumn).where(CollectionColumn.id == column_id))
    if row is None:
        return None
    row_count = int(db.scalar(select(func.count(CollectionItem.id)).where(CollectionItem.collection_id == row.collection_id)) or 0)
    coverage_count = int(
        db.scalar(
            select(func.count(CollectionItemValue.id)).where(
                CollectionItemValue.collection_column_id == row.id,
                CollectionItemValue.display_value.is_not(None),
            )
        )
        or 0
    )
    return WorkspaceColumnRead(
        id=row.id,
        collection_id=row.collection_id,
        key=row.key,
        label=row.label,
        data_type=row.data_type,
        kind=row.kind,
        sort_order=row.sort_order,
        required=row.required,
        is_relation=row.is_relation,
        relation_target_collection_id=row.relation_target_collection_id,
        origin=row.origin,
        planner_locked=row.planner_locked,
        user_locked=row.user_locked,
        enrichment_policy_json=dict(row.enrichment_policy_json or {}),
        coverage_count=coverage_count,
        coverage_ratio=float(coverage_count / row_count) if row_count else 0.0,
    )


def _columns_for_collection(db: Session, *, collection_id: int) -> list[WorkspaceColumnRead]:
    return [
        item
        for item in (
            _column_read(db, column.id)
            for column in db.scalars(
                select(CollectionColumn)
                .where(CollectionColumn.collection_id == collection_id)
                .order_by(CollectionColumn.sort_order.asc(), CollectionColumn.id.asc())
            ).all()
        )
        if item is not None
    ]


def _cells_for_rows(
    db: Session,
    *,
    row_ids: list[int],
    columns: list[WorkspaceColumnRead],
) -> dict[int, list[WorkspaceCellRead]]:
    by_row: dict[int, list[WorkspaceCellRead]] = {row_id: _empty_cells(columns) for row_id in row_ids}
    if not row_ids:
        return by_row
    values = list(
        db.scalars(
            select(CollectionItemValue).where(CollectionItemValue.collection_item_id.in_(row_ids))
        ).all()
    )
    sources_by_value = _sources_for_values(db, value_ids=[value.id for value in values])
    suggestions_by_target = _pending_value_suggestions_for_rows(db, row_ids=row_ids)
    column_by_id = {column.id: column for column in columns}
    cell_index: dict[tuple[int, int], int] = {}
    for row_id, cells in by_row.items():
        for idx, cell in enumerate(cells):
            cell_index[(row_id, cell.column_id)] = idx
    for value in values:
        column = column_by_id.get(int(value.collection_column_id))
        if column is None:
            continue
        idx = cell_index.get((int(value.collection_item_id), int(value.collection_column_id)))
        if idx is None:
            continue
        by_row[int(value.collection_item_id)][idx] = WorkspaceCellRead(
            id=value.id,
            column_id=column.id,
            column_key=column.key,
            label=column.label,
            data_type=column.data_type,
            value_json=value.value_json,
            display_value=value.display_value,
            source_kind=value.source_kind,
            confidence=value.confidence,
            status=value.status,
            edited_by_user=value.edited_by_user,
            last_verified_at=value.last_verified_at,
            sources=sources_by_value.get(value.id, []),
            pending_suggestion_count=len(
                suggestions_by_target.get((int(value.collection_item_id), int(value.collection_column_id)), [])
            ),
            pending_suggestions=suggestions_by_target.get(
                (int(value.collection_item_id), int(value.collection_column_id)),
                [],
            ),
        )
    for row_id, cells in by_row.items():
        for idx, cell in enumerate(cells):
            pending = suggestions_by_target.get((row_id, cell.column_id), [])
            if not pending:
                continue
            by_row[row_id][idx] = cell.model_copy(
                update={
                    "pending_suggestion_count": len(pending),
                    "pending_suggestions": pending,
                }
            )
    return by_row


def _empty_cells(columns: list[WorkspaceColumnRead]) -> list[WorkspaceCellRead]:
    return [
        WorkspaceCellRead(
            id=None,
            column_id=column.id,
            column_key=column.key,
            label=column.label,
            data_type=column.data_type,
            value_json=None,
            display_value=None,
            source_kind=None,
            confidence=None,
            status=None,
            edited_by_user=False,
            last_verified_at=None,
            sources=[],
            pending_suggestion_count=0,
            pending_suggestions=[],
        )
        for column in columns
        if column.key != "title"
    ]


def _sources_for_values(db: Session, *, value_ids: list[int]) -> dict[int, list[WorkspaceSourceRead]]:
    by_value: dict[int, list[WorkspaceSourceRead]] = defaultdict(list)
    if not value_ids:
        return by_value
    for evidence, source in db.execute(
        select(Evidence, Source)
        .join(Source, Source.id == Evidence.source_id)
        .where(Evidence.collection_item_value_id.in_(value_ids))
        .order_by(Evidence.id.asc())
    ).all():
        if evidence.collection_item_value_id is None:
            continue
        by_value[int(evidence.collection_item_value_id)].append(
            WorkspaceSourceRead(
                id=source.id,
                source_kind=source.source_kind,
                title=source.title,
                uri=source.uri,
                snippet=evidence.snippet,
                confidence=evidence.confidence,
                created_at=source.created_at,
            )
        )
    return by_value


def _relations_for_row(db: Session, *, row_id: int) -> list[WorkspaceRowRelationRead]:
    other_row = aliased(CollectionItem)
    outgoing = list(
        db.execute(
            select(CollectionItemRelation, other_row)
            .join(other_row, other_row.id == CollectionItemRelation.to_collection_item_id)
            .where(CollectionItemRelation.from_collection_item_id == row_id)
        ).all()
    )
    incoming = list(
        db.execute(
            select(CollectionItemRelation, other_row)
            .join(other_row, other_row.id == CollectionItemRelation.from_collection_item_id)
            .where(CollectionItemRelation.to_collection_item_id == row_id)
        ).all()
    )
    evidence_by_relation: dict[int, list[WorkspaceSourceRead]] = defaultdict(list)
    relation_ids = [relation.id for relation, _ in [*outgoing, *incoming]]
    if relation_ids:
        for evidence, source in db.execute(
            select(Evidence, Source)
            .join(Source, Source.id == Evidence.source_id)
            .where(Evidence.collection_item_relation_id.in_(relation_ids))
            .order_by(Evidence.id.asc())
        ).all():
            if evidence.collection_item_relation_id is None:
                continue
            evidence_by_relation[int(evidence.collection_item_relation_id)].append(
                WorkspaceSourceRead(
                    id=source.id,
                    source_kind=source.source_kind,
                    title=source.title,
                    uri=source.uri,
                    snippet=evidence.snippet,
                    confidence=evidence.confidence,
                    created_at=source.created_at,
                )
            )
    rows: list[WorkspaceRowRelationRead] = []
    for relation, other in outgoing:
        rows.append(
            WorkspaceRowRelationRead(
                id=relation.id,
                relation_label=relation.relation_label,
                direction="outgoing",
                other_row_id=other.id,
                other_row_title=other.title or f"Row {other.id}",
                source_kind=relation.source_kind,
                confidence=relation.confidence,
                status=relation.status,
                sources=evidence_by_relation.get(relation.id, []),
                suggested=False,
            )
        )
    for relation, other in incoming:
        rows.append(
            WorkspaceRowRelationRead(
                id=relation.id,
                relation_label=relation.relation_label,
                direction="incoming",
                other_row_id=other.id,
                other_row_title=other.title or f"Row {other.id}",
                source_kind=relation.source_kind,
                confidence=relation.confidence,
                status=relation.status,
                sources=evidence_by_relation.get(relation.id, []),
                suggested=False,
            )
        )
    rows.extend(_pending_relation_suggestions_for_row(db, row_id=row_id))
    return rows


def _pending_value_suggestions_for_rows(
    db: Session,
    *,
    row_ids: list[int],
) -> dict[tuple[int, int], list[WorkspaceCellSuggestionRead]]:
    by_target: dict[tuple[int, int], list[WorkspaceCellSuggestionRead]] = defaultdict(list)
    if not row_ids:
        return by_target
    source_cache = _source_reads_by_ids(
        db,
        source_ids=[
            source_id
            for source_ids_json in db.scalars(
                select(CollectionItemValueSuggestion.source_ids_json).where(
                    CollectionItemValueSuggestion.collection_item_id.in_(row_ids),
                    CollectionItemValueSuggestion.status == "pending",
                )
            ).all()
            for source_id in list(source_ids_json or [])
        ],
    )
    for suggestion in db.scalars(
        select(CollectionItemValueSuggestion).where(
            CollectionItemValueSuggestion.collection_item_id.in_(row_ids),
            CollectionItemValueSuggestion.status == "pending",
        )
    ).all():
        by_target[(int(suggestion.collection_item_id), int(suggestion.collection_column_id))].append(
            WorkspaceCellSuggestionRead(
                id=suggestion.id,
                suggested_display_value=suggestion.suggested_display_value,
                source_kind=suggestion.source_kind,
                confidence=suggestion.confidence,
                status=suggestion.status,
                sources=[source_cache[source_id] for source_id in suggestion.source_ids_json if source_id in source_cache],
            )
        )
    return by_target


def _pending_relation_suggestions_for_row(
    db: Session,
    *,
    row_id: int,
) -> list[WorkspaceRowRelationRead]:
    rows: list[WorkspaceRowRelationRead] = []
    other_row = aliased(CollectionItem)
    suggestion_rows = list(
        db.execute(
            select(CollectionItemRelationSuggestion, other_row)
            .join(
                other_row,
                other_row.id == CollectionItemRelationSuggestion.to_collection_item_id,
            )
            .where(
                CollectionItemRelationSuggestion.from_collection_item_id == row_id,
                CollectionItemRelationSuggestion.status == "pending",
            )
        ).all()
    )
    suggestion_rows.extend(
        db.execute(
            select(CollectionItemRelationSuggestion, other_row)
            .join(
                other_row,
                other_row.id == CollectionItemRelationSuggestion.from_collection_item_id,
            )
            .where(
                CollectionItemRelationSuggestion.to_collection_item_id == row_id,
                CollectionItemRelationSuggestion.status == "pending",
            )
        ).all()
    )
    source_cache = _source_reads_by_ids(
        db,
        source_ids=[
            source_id
            for source_ids_json in db.scalars(
                select(CollectionItemRelationSuggestion.source_ids_json).where(
                    CollectionItemRelationSuggestion.status == "pending",
                    or_(
                        CollectionItemRelationSuggestion.from_collection_item_id == row_id,
                        CollectionItemRelationSuggestion.to_collection_item_id == row_id,
                    ),
                )
            ).all()
            for source_id in list(source_ids_json or [])
        ],
    )
    for suggestion, other in suggestion_rows:
        rows.append(
            WorkspaceRowRelationRead(
                id=suggestion.id,
                relation_label=suggestion.relation_label,
                direction="outgoing"
                if int(suggestion.from_collection_item_id) == row_id
                else "incoming",
                other_row_id=other.id,
                other_row_title=other.title or f"Row {other.id}",
                source_kind=suggestion.source_kind,
                confidence=suggestion.confidence,
                status=suggestion.status,
                sources=[source_cache[source_id] for source_id in suggestion.source_ids_json if source_id in source_cache],
                suggested=True,
            )
        )
    return rows


def _source_reads_by_ids(db: Session, *, source_ids: list[int]) -> dict[int, WorkspaceSourceRead]:
    result: dict[int, WorkspaceSourceRead] = {}
    if not source_ids:
        return result
    for source in db.scalars(select(Source).where(Source.id.in_(sorted(set(source_ids))))).all():
        result[int(source.id)] = WorkspaceSourceRead(
            id=source.id,
            source_kind=source.source_kind,
            title=source.title,
            uri=source.uri,
            snippet=str(source.payload_json.get("snippet")) if isinstance(source.payload_json, dict) and source.payload_json.get("snippet") is not None else None,
            confidence=None,
            created_at=source.created_at,
        )
    return result


def accept_collection_suggestions(db: Session, *, collection_id: int) -> WorkspaceSuggestionReviewResult:
    row_ids = list(db.scalars(select(CollectionItem.id).where(CollectionItem.collection_id == collection_id)).all())
    applied = _apply_value_suggestions(db, row_ids=row_ids) + _apply_relation_suggestions_for_collection(db, collection_id=collection_id)
    db.commit()
    return WorkspaceSuggestionReviewResult(applied=applied, rejected=0)


def reject_collection_suggestions(db: Session, *, collection_id: int) -> WorkspaceSuggestionReviewResult:
    row_ids = list(db.scalars(select(CollectionItem.id).where(CollectionItem.collection_id == collection_id)).all())
    rejected = _reject_value_suggestions(db, row_ids=row_ids) + _reject_relation_suggestions_for_rows(db, row_ids=row_ids)
    db.commit()
    return WorkspaceSuggestionReviewResult(applied=0, rejected=rejected)


def accept_graph_scope_suggestions(db: Session, *, scope_key: str) -> WorkspaceSuggestionReviewResult:
    applied = _apply_relation_suggestions_for_scope(db, scope_key=scope_key)
    db.commit()
    return WorkspaceSuggestionReviewResult(applied=applied, rejected=0)


def reject_graph_scope_suggestions(db: Session, *, scope_key: str) -> WorkspaceSuggestionReviewResult:
    rejected = _reject_relation_suggestions_for_scope(db, scope_key=scope_key)
    db.commit()
    return WorkspaceSuggestionReviewResult(applied=0, rejected=rejected)


def _apply_value_suggestions(db: Session, *, row_ids: list[int]) -> int:
    applied = 0
    for suggestion in db.scalars(
        select(CollectionItemValueSuggestion).where(
            CollectionItemValueSuggestion.collection_item_id.in_(row_ids if row_ids else [-1]),
            CollectionItemValueSuggestion.status == "pending",
        )
    ).all():
        live = db.scalar(
            select(CollectionItemValue).where(
                CollectionItemValue.collection_item_id == suggestion.collection_item_id,
                CollectionItemValue.collection_column_id == suggestion.collection_column_id,
            )
        )
        if live is not None and live.edited_by_user:
            suggestion.status = "rejected"
            db.add(suggestion)
            continue
        if live is None:
            live = CollectionItemValue(
                collection_item_id=suggestion.collection_item_id,
                collection_column_id=suggestion.collection_column_id,
            )
        live.value_json = suggestion.suggested_value_json
        live.display_value = suggestion.suggested_display_value
        live.value_type = suggestion.value_type
        live.source_kind = suggestion.source_kind
        live.confidence = suggestion.confidence
        live.status = "accepted"
        live.edited_by_user = False
        db.add(live)
        db.flush()
        db.execute(delete(Evidence).where(Evidence.collection_item_value_id == live.id))
        for source_id in suggestion.source_ids_json:
            db.add(
                Evidence(
                    source_id=source_id,
                    fact_id=None,
                    relation_id=None,
                    collection_item_value_id=live.id,
                    collection_item_relation_id=None,
                    message_id=None,
                    snippet=None,
                    confidence=suggestion.confidence,
                    meta_json={"origin": "accepted_workspace_value_suggestion"},
                )
            )
        suggestion.status = "accepted"
        db.add(suggestion)
        applied += 1
    return applied


def _apply_relation_suggestions_for_collection(db: Session, *, collection_id: int) -> int:
    row_ids = list(db.scalars(select(CollectionItem.id).where(CollectionItem.collection_id == collection_id)).all())
    return _apply_relation_suggestions_for_rows(db, row_ids=row_ids)


def _apply_relation_suggestions_for_scope(db: Session, *, scope_key: str) -> int:
    row_ids = _row_ids_for_scope(db, scope_key=scope_key)
    return _apply_relation_suggestions_for_rows(db, row_ids=row_ids)


def _apply_relation_suggestions_for_rows(db: Session, *, row_ids: list[int]) -> int:
    applied = 0
    for suggestion in db.scalars(
        select(CollectionItemRelationSuggestion).where(
            CollectionItemRelationSuggestion.status == "pending",
            CollectionItemRelationSuggestion.from_collection_item_id.in_(row_ids if row_ids else [-1]),
            CollectionItemRelationSuggestion.to_collection_item_id.in_(row_ids if row_ids else [-1]),
        )
    ).all():
        live = db.scalar(
            select(CollectionItemRelation).where(
                CollectionItemRelation.from_collection_item_id == suggestion.from_collection_item_id,
                CollectionItemRelation.to_collection_item_id == suggestion.to_collection_item_id,
                CollectionItemRelation.relation_label == suggestion.relation_label,
            )
        )
        if live is None:
            live = CollectionItemRelation(
                from_collection_item_id=suggestion.from_collection_item_id,
                to_collection_item_id=suggestion.to_collection_item_id,
                relation_label=suggestion.relation_label,
                source_kind=suggestion.source_kind,
                confidence=suggestion.confidence,
                status="accepted",
            )
        else:
            live.source_kind = suggestion.source_kind
            live.confidence = suggestion.confidence
            live.status = "accepted"
        db.add(live)
        db.flush()
        db.execute(delete(Evidence).where(Evidence.collection_item_relation_id == live.id))
        for source_id in suggestion.source_ids_json:
            db.add(
                Evidence(
                    source_id=source_id,
                    fact_id=None,
                    relation_id=None,
                    collection_item_value_id=None,
                    collection_item_relation_id=live.id,
                    message_id=None,
                    snippet=None,
                    confidence=suggestion.confidence,
                    meta_json={"origin": "accepted_workspace_relation_suggestion"},
                )
            )
        suggestion.status = "accepted"
        db.add(suggestion)
        applied += 1
    return applied


def _reject_value_suggestions(db: Session, *, row_ids: list[int]) -> int:
    rows = list(
        db.scalars(
            select(CollectionItemValueSuggestion).where(
                CollectionItemValueSuggestion.collection_item_id.in_(row_ids if row_ids else [-1]),
                CollectionItemValueSuggestion.status == "pending",
            )
        ).all()
    )
    for row in rows:
        row.status = "rejected"
        db.add(row)
    return len(rows)


def _reject_relation_suggestions_for_rows(db: Session, *, row_ids: list[int]) -> int:
    rows = list(
        db.scalars(
            select(CollectionItemRelationSuggestion).where(
                CollectionItemRelationSuggestion.status == "pending",
                CollectionItemRelationSuggestion.from_collection_item_id.in_(row_ids if row_ids else [-1]),
                CollectionItemRelationSuggestion.to_collection_item_id.in_(row_ids if row_ids else [-1]),
            )
        ).all()
    )
    for row in rows:
        row.status = "rejected"
        db.add(row)
    return len(rows)


def _reject_relation_suggestions_for_scope(db: Session, *, scope_key: str) -> int:
    return _reject_relation_suggestions_for_rows(db, row_ids=_row_ids_for_scope(db, scope_key=scope_key))


def _row_ids_for_scope(db: Session, *, scope_key: str) -> list[int]:
    clean = scope_key.strip().lower()
    if clean == "global":
        return list(db.scalars(select(CollectionItem.id)).all())
    if clean.startswith("pod-"):
        pod_id = int(clean.split("-", 1)[1])
        return list(
            db.scalars(
                select(CollectionItem.id)
                .join(Collection, Collection.id == CollectionItem.collection_id)
                .where(Collection.pod_id == pod_id)
            ).all()
        )
    if clean.startswith("collection-"):
        collection_id = int(clean.split("-", 1)[1])
        return list(db.scalars(select(CollectionItem.id).where(CollectionItem.collection_id == collection_id)).all())
    return []


def list_pending_enrichment_runs(db: Session, *, run_id: int) -> WorkspaceEnrichmentRunRead | None:
    row = db.scalar(select(WorkspaceEnrichmentRun).where(WorkspaceEnrichmentRun.id == run_id))
    if row is None:
        return None
    return WorkspaceEnrichmentRunRead(
        id=row.id,
        pod_id=row.pod_id,
        conversation_id=row.conversation_id,
        collection_id=row.collection_id,
        collection_item_id=row.collection_item_id,
        requested_by=row.requested_by,
        run_kind=row.run_kind,
        status=row.status,
        stage=row.stage,
        error_message=row.error_message,
        summary_json=dict(row.summary_json or {}),
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


def _slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-") or "item"
