"""Stable workspace-first v3 routes."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.models.collection import Collection
from app.models.collection_item import CollectionItem
from app.models.conversation import Conversation
from app.models.pod import Pod
from app.schemas.common import ApiResponse
from app.schemas.workspace_v3 import (
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
    WorkspaceRowCreateRequest,
    WorkspaceRowDetailRead,
    WorkspaceRowUpdateRequest,
    WorkspaceRowsResponse,
    WorkspaceSuggestionReviewResult,
    WorkspaceSpaceCreateRequest,
    WorkspaceSpaceRead,
    WorkspaceSpaceUpdateRequest,
    WorkspaceSyncRunRead,
)
from app.services.background_jobs import run_workspace_enrichment_job
from app.services.workspace_sync import (
    create_workspace_enrichment_run,
    get_latest_workspace_enrichment_run,
    get_workspace_enrichment_run,
    rebuild_workspace_for_pod,
    run_workspace_sync_for_conversation,
)
from app.services.workspace_v3 import (
    accept_collection_suggestions,
    accept_graph_scope_suggestions,
    create_workspace_space,
    create_workspace_collection,
    create_workspace_column,
    create_workspace_row,
    delete_workspace_collection,
    delete_workspace_column,
    delete_workspace_row,
    delete_workspace_space,
    get_workspace_overview,
    get_workspace_row_detail,
    list_pending_enrichment_runs,
    list_workspace_library,
    list_workspace_property_catalog,
    list_workspace_rows,
    list_workspace_spaces,
    reject_collection_suggestions,
    reject_graph_scope_suggestions,
    update_workspace_space,
    update_workspace_cell,
    update_workspace_collection,
    update_workspace_column,
    update_workspace_row,
)

router = APIRouter(prefix="/v3")


@router.get("/spaces", response_model=ApiResponse[list[WorkspaceSpaceRead]])
def get_spaces(db: Session = Depends(get_db)) -> ApiResponse[list[WorkspaceSpaceRead]]:
    return ApiResponse(data=list_workspace_spaces(db))


@router.post("/spaces", response_model=ApiResponse[WorkspaceSpaceRead], status_code=201)
def post_space(
    payload: WorkspaceSpaceCreateRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceSpaceRead]:
    return ApiResponse(data=create_workspace_space(db, payload=payload))


@router.patch("/spaces/{space_id}", response_model=ApiResponse[WorkspaceSpaceRead])
def patch_space(
    payload: WorkspaceSpaceUpdateRequest,
    space_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceSpaceRead]:
    updated = update_workspace_space(db, space_id=space_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return ApiResponse(data=updated)


@router.delete("/spaces/{space_id}", response_model=ApiResponse[dict[str, object]])
def remove_space(
    space_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, object]]:
    deleted = delete_workspace_space(db, space_id=space_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Space not found")
    return ApiResponse(data={"space_id": space_id, "deleted": True})


@router.get("/spaces/{space_id}/workspace", response_model=ApiResponse[WorkspaceOverviewResponse])
def get_space_workspace(
    space_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceOverviewResponse]:
    payload = get_workspace_overview(db, space_id=space_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return ApiResponse(data=payload)


@router.post("/spaces/{space_id}/collections", response_model=ApiResponse[WorkspaceCollectionRead], status_code=201)
def post_collection(
    payload: WorkspaceCollectionCreateRequest,
    space_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceCollectionRead]:
    created = create_workspace_collection(db, space_id=space_id, payload=payload)
    if created is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return ApiResponse(data=created)


@router.patch("/collections/{collection_id}", response_model=ApiResponse[WorkspaceCollectionRead])
def patch_collection(
    payload: WorkspaceCollectionUpdateRequest,
    collection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceCollectionRead]:
    updated = update_workspace_collection(db, collection_id=collection_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ApiResponse(data=updated)


@router.delete("/collections/{collection_id}", response_model=ApiResponse[dict[str, object]])
def remove_collection(
    collection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, object]]:
    deleted = delete_workspace_collection(db, collection_id=collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ApiResponse(data={"collection_id": collection_id, "deleted": True})


@router.post("/collections/{collection_id}/columns", response_model=ApiResponse[WorkspaceColumnRead], status_code=201)
def post_collection_column(
    payload: WorkspaceColumnCreateRequest,
    collection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceColumnRead]:
    created = create_workspace_column(db, collection_id=collection_id, payload=payload)
    if created is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ApiResponse(data=created)


@router.patch("/columns/{column_id}", response_model=ApiResponse[WorkspaceColumnRead])
def patch_collection_column(
    payload: WorkspaceColumnUpdateRequest,
    column_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceColumnRead]:
    updated = update_workspace_column(db, column_id=column_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Column not found")
    return ApiResponse(data=updated)


@router.delete("/columns/{column_id}", response_model=ApiResponse[dict[str, object]])
def remove_column(
    column_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, object]]:
    deleted = delete_workspace_column(db, column_id=column_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Column not found")
    return ApiResponse(data={"column_id": column_id, "deleted": True})


@router.get("/collections/{collection_id}/rows", response_model=ApiResponse[WorkspaceRowsResponse])
def get_collection_rows(
    collection_id: int = Path(..., ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceRowsResponse]:
    payload = list_workspace_rows(db, collection_id=collection_id, limit=limit, offset=offset, query=q)
    if payload is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ApiResponse(data=payload)


@router.post("/collections/{collection_id}/rows", response_model=ApiResponse[WorkspaceRowDetailRead], status_code=201)
def post_collection_row(
    payload: WorkspaceRowCreateRequest,
    collection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceRowDetailRead]:
    created = create_workspace_row(db, collection_id=collection_id, payload=payload)
    if created is None:
        raise HTTPException(status_code=404, detail="Collection or entity not found")
    return ApiResponse(data=created)


@router.patch("/collection-rows/{row_id}", response_model=ApiResponse[WorkspaceRowDetailRead])
def patch_collection_row(
    payload: WorkspaceRowUpdateRequest,
    row_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceRowDetailRead]:
    updated = update_workspace_row(db, row_id=row_id, payload=payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return ApiResponse(data=updated)


@router.delete("/collection-rows/{row_id}", response_model=ApiResponse[dict[str, object]])
def remove_collection_row(
    row_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, object]]:
    deleted = delete_workspace_row(db, row_id=row_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Row not found")
    return ApiResponse(data={"row_id": row_id, "deleted": True})


@router.patch("/collection-rows/{row_id}/values/{column_id}", response_model=ApiResponse[WorkspaceRowDetailRead])
def patch_collection_row_value(
    row_id: int = Path(..., ge=1),
    column_id: int = Path(..., ge=1),
    payload: dict[str, object] | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceRowDetailRead]:
    payload = payload or {}
    updated = update_workspace_cell(
        db,
        row_id=row_id,
        column_id=column_id,
        display_value=str(payload.get("display_value")) if payload.get("display_value") is not None else None,
        value_json=payload.get("value_json"),
        status=str(payload.get("status")) if payload.get("status") is not None else None,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Row or column not found")
    return ApiResponse(data=updated)


@router.get("/collection-rows/{row_id}", response_model=ApiResponse[WorkspaceRowDetailRead])
def get_collection_row(
    row_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceRowDetailRead]:
    payload = get_workspace_row_detail(db, row_id=row_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Row not found")
    return ApiResponse(data=payload)


@router.get("/library", response_model=ApiResponse[WorkspaceLibraryResponse])
def get_workspace_library(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    space_id: int | None = Query(default=None, ge=1),
    collection_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceLibraryResponse]:
    return ApiResponse(
        data=list_workspace_library(
            db,
            limit=limit,
            offset=offset,
            query=q,
            space_id=space_id,
            collection_id=collection_id,
        )
    )


@router.get("/properties", response_model=ApiResponse[WorkspacePropertyCatalogResponse])
def get_workspace_properties(
    space_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspacePropertyCatalogResponse]:
    return ApiResponse(data=list_workspace_property_catalog(db, space_id=space_id))


@router.post("/conversations/{conversation_id}/workspace-sync", response_model=ApiResponse[WorkspaceSyncRunRead])
def post_workspace_sync(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceSyncRunRead]:
    try:
        payload = run_workspace_sync_for_conversation(db, conversation_id=conversation_id, allow_enrichment=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return ApiResponse(data=payload)


@router.post("/spaces/{space_id}/enrich", response_model=ApiResponse[WorkspaceEnrichmentRunRead], status_code=202)
def post_space_enrich(
    background_tasks: BackgroundTasks,
    space_id: int = Path(..., ge=1),
    include_sources: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceEnrichmentRunRead]:
    if db.scalar(select(Pod.id).where(Pod.id == space_id).limit(1)) is None:
        raise HTTPException(status_code=404, detail="Space not found")
    payload = create_workspace_enrichment_run(
        db,
        pod_id=space_id,
        requested_by="user",
        run_kind="manual_space",
        summary_json={"include_sources": include_sources},
    )
    db.commit()
    background_tasks.add_task(run_workspace_enrichment_job, payload.id)
    return ApiResponse(data=payload)


@router.get("/spaces/{space_id}/enrichment/latest", response_model=ApiResponse[WorkspaceEnrichmentRunRead | None])
def get_latest_space_enrichment_run(
    space_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceEnrichmentRunRead | None]:
    if db.scalar(select(Pod.id).where(Pod.id == space_id).limit(1)) is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return ApiResponse(data=get_latest_workspace_enrichment_run(db, pod_id=space_id))


@router.get("/enrichment-runs/{run_id}", response_model=ApiResponse[WorkspaceEnrichmentRunRead])
def get_enrichment_run(
    run_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceEnrichmentRunRead]:
    payload = get_workspace_enrichment_run(db, run_id=run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Enrichment run not found")
    return ApiResponse(data=payload)


@router.post("/collections/{collection_id}/enrich", response_model=ApiResponse[WorkspaceEnrichmentRunRead], status_code=202)
def post_collection_enrich(
    background_tasks: BackgroundTasks,
    collection_id: int = Path(..., ge=1),
    include_sources: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceEnrichmentRunRead]:
    row = db.scalar(select(Collection).where(Collection.id == collection_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    payload = create_workspace_enrichment_run(
        db,
        pod_id=int(row.pod_id),
        collection_id=int(row.id),
        requested_by="user",
        run_kind="manual_collection",
        summary_json={"include_sources": include_sources},
    )
    db.commit()
    background_tasks.add_task(run_workspace_enrichment_job, payload.id)
    return ApiResponse(data=payload)


@router.post("/collection-rows/{row_id}/enrich", response_model=ApiResponse[WorkspaceEnrichmentRunRead], status_code=202)
def post_row_enrich(
    background_tasks: BackgroundTasks,
    row_id: int = Path(..., ge=1),
    include_sources: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceEnrichmentRunRead]:
    row = db.scalar(select(CollectionItem).where(CollectionItem.id == row_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    collection = db.scalar(select(Collection).where(Collection.id == row.collection_id))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    payload = create_workspace_enrichment_run(
        db,
        pod_id=int(collection.pod_id),
        collection_id=int(collection.id),
        collection_item_id=int(row.id),
        requested_by="user",
        run_kind="manual_row",
        summary_json={"include_sources": include_sources},
    )
    db.commit()
    background_tasks.add_task(run_workspace_enrichment_job, payload.id)
    return ApiResponse(data=payload)


@router.post("/collections/{collection_id}/suggestions/accept", response_model=ApiResponse[WorkspaceSuggestionReviewResult])
def post_accept_collection_suggestions(
    collection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceSuggestionReviewResult]:
    if db.scalar(select(Collection.id).where(Collection.id == collection_id)) is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ApiResponse(data=accept_collection_suggestions(db, collection_id=collection_id))


@router.post("/collections/{collection_id}/suggestions/reject", response_model=ApiResponse[WorkspaceSuggestionReviewResult])
def post_reject_collection_suggestions(
    collection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceSuggestionReviewResult]:
    if db.scalar(select(Collection.id).where(Collection.id == collection_id)) is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ApiResponse(data=reject_collection_suggestions(db, collection_id=collection_id))


@router.post("/graph/scopes/{scope_key}/suggestions/accept", response_model=ApiResponse[WorkspaceSuggestionReviewResult])
def post_accept_graph_suggestions(
    scope_key: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceSuggestionReviewResult]:
    return ApiResponse(data=accept_graph_scope_suggestions(db, scope_key=scope_key))


@router.post("/graph/scopes/{scope_key}/suggestions/reject", response_model=ApiResponse[WorkspaceSuggestionReviewResult])
def post_reject_graph_suggestions(
    scope_key: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[WorkspaceSuggestionReviewResult]:
    return ApiResponse(data=reject_graph_scope_suggestions(db, scope_key=scope_key))
