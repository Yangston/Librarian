"""Organization routes for pods, collections, and scoped graph views."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.organization import (
    PodCreateRequest,
    PodDeleteResponse,
    CollectionItemMutationRequest,
    CollectionItemMutationResponse,
    CollectionItemsResponse,
    CollectionRead,
    PodRead,
    PodTreeData,
    ScopedGraphData,
    ScopeMode,
)
from app.services.organization import (
    create_pod,
    delete_pod_with_conversations,
    get_collection,
    get_pod,
    get_pod_tree,
    get_scoped_graph,
    list_collection_items,
    list_pods,
    remove_collection_item,
    upsert_collection_item,
)

router = APIRouter()


@router.get("/pods", response_model=ApiResponse[list[PodRead]])
def get_pods(db: Session = Depends(get_db)) -> ApiResponse[list[PodRead]]:
    """List pods."""

    return ApiResponse(data=list_pods(db))


@router.post("/pods", response_model=ApiResponse[PodRead], status_code=201)
def create_pod_record(
    payload: PodCreateRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[PodRead]:
    """Create one pod."""

    return ApiResponse(
        data=create_pod(db, name=payload.name, description=payload.description)
    )


@router.get("/pods/{pod_id}", response_model=ApiResponse[PodRead])
def get_pod_by_id(
    pod_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[PodRead]:
    """Fetch a pod."""

    payload = get_pod(db, pod_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Pod not found")
    return ApiResponse(data=payload)


@router.delete("/pods/{pod_id}", response_model=ApiResponse[PodDeleteResponse])
def delete_pod_by_id(
    pod_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[PodDeleteResponse]:
    """Delete one pod and all pod conversations + derived data."""

    try:
        payload = delete_pod_with_conversations(db, pod_id=pod_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="Pod not found")
    return ApiResponse(data=payload)


@router.get("/pods/{pod_id}/tree", response_model=ApiResponse[PodTreeData])
def get_pod_tree_by_id(
    pod_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[PodTreeData]:
    """Fetch pod and nested collection tree."""

    payload = get_pod_tree(db, pod_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Pod not found")
    return ApiResponse(data=payload)


@router.get("/collections/{collection_id}", response_model=ApiResponse[CollectionRead])
def get_collection_by_id(
    collection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[CollectionRead]:
    """Fetch a collection record."""

    payload = get_collection(db, collection_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ApiResponse(data=payload)


@router.get("/collections/{collection_id}/items", response_model=ApiResponse[CollectionItemsResponse])
def get_collection_items(
    collection_id: int = Path(..., ge=1),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: Literal["canonical_name", "type_label", "last_seen", "conversation_count", "alias_count"] = Query(
        default="last_seen"
    ),
    order: Literal["asc", "desc"] = Query(default="desc"),
    q: str | None = Query(default=None),
    fields: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApiResponse[CollectionItemsResponse]:
    """List collection entity rows."""

    selected_fields = [segment.strip() for segment in (fields or "").split(",") if segment.strip()]
    payload = list_collection_items(
        db,
        collection_id=collection_id,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
        query=q,
        selected_fields=selected_fields,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return ApiResponse(data=payload)


@router.post("/collections/{collection_id}/items", response_model=ApiResponse[CollectionItemMutationResponse])
def add_collection_item(
    payload: CollectionItemMutationRequest,
    collection_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[CollectionItemMutationResponse]:
    """Add entity membership to collection."""

    result = upsert_collection_item(
        db,
        collection_id=collection_id,
        entity_id=payload.entity_id,
        sort_key=payload.sort_key,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Collection or entity not found")
    db.commit()
    return ApiResponse(data=result)


@router.delete(
    "/collections/{collection_id}/items/{entity_id}",
    response_model=ApiResponse[CollectionItemMutationResponse],
)
def delete_collection_item(
    collection_id: int = Path(..., ge=1),
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[CollectionItemMutationResponse]:
    """Remove entity membership from collection."""

    removed = remove_collection_item(db, collection_id=collection_id, entity_id=entity_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Collection membership not found")
    db.commit()
    return ApiResponse(
        data=CollectionItemMutationResponse(collection_id=collection_id, entity_id=entity_id, added=False)
    )


@router.get("/graph/scoped", response_model=ApiResponse[ScopedGraphData])
def get_graph_scoped(
    scope_mode: ScopeMode = Query(default="global"),
    pod_id: int | None = Query(default=None, ge=1),
    collection_id: int | None = Query(default=None, ge=1),
    one_hop: bool = Query(default=False),
    include_external: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[ScopedGraphData]:
    """Return graph scoped to global/pod/collection context."""

    if scope_mode == "pod" and pod_id is None:
        raise HTTPException(status_code=400, detail="pod_id is required for pod scope")
    if scope_mode == "collection" and collection_id is None:
        raise HTTPException(status_code=400, detail="collection_id is required for collection scope")
    payload = get_scoped_graph(
        db,
        scope_mode=scope_mode,
        pod_id=pod_id,
        collection_id=collection_id,
        one_hop=one_hop,
        include_external=include_external,
    )
    return ApiResponse(data=payload)
