"""v2 user-facing workspace routes."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.workspace_v2 import (
    LibraryItemActivityResponse,
    LibraryItemDetailResponse,
    LibraryItemsResponse,
    LibraryItemUpdateRequest,
    PropertyCatalogRead,
    PropertyCatalogResponse,
    PropertyCatalogUpdateRequest,
    SearchV2Response,
    SpaceCreateRequest,
    SpacePagesResponse,
    SpaceRead,
    SpaceUpdateRequest,
    UnifiedClaimExplainResponse,
)
from app.services.workspace_v2 import (
    create_space,
    delete_space,
    get_library_item,
    get_unified_claim_explain,
    list_library_item_activity,
    list_library_items,
    list_property_catalog,
    list_space_pages,
    list_spaces,
    patch_library_item,
    patch_property_catalog,
    search_workspace,
    update_space,
)

router = APIRouter(prefix="/v2")


@router.get("/spaces", response_model=ApiResponse[list[SpaceRead]])
def get_spaces(
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[list[SpaceRead]]:
    """List spaces."""

    return ApiResponse(data=list_spaces(db, include_technical=include_technical))


@router.post("/spaces", response_model=ApiResponse[SpaceRead], status_code=201)
def post_space(
    payload: SpaceCreateRequest,
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[SpaceRead]:
    """Create one space."""

    return ApiResponse(data=create_space(db, payload, include_technical=include_technical))


@router.patch("/spaces/{space_id}", response_model=ApiResponse[SpaceRead])
def patch_space(
    payload: SpaceUpdateRequest,
    space_id: int = Path(..., ge=1),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[SpaceRead]:
    """Update one space."""

    row = update_space(
        db,
        space_id=space_id,
        payload=payload,
        include_technical=include_technical,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return ApiResponse(data=row)


@router.delete("/spaces/{space_id}", response_model=ApiResponse[dict[str, object]])
def remove_space(
    space_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, object]]:
    """Delete one space and its assigned conversations."""

    deleted = delete_space(db, space_id=space_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Space not found")
    return ApiResponse(data={"space_id": space_id, "deleted": True})


@router.get("/spaces/{space_id}/pages", response_model=ApiResponse[SpacePagesResponse])
def get_space_pages(
    space_id: int = Path(..., ge=1),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[SpacePagesResponse]:
    """List pages/tables in one space."""

    payload = list_space_pages(db, space_id=space_id, include_technical=include_technical)
    if payload is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return ApiResponse(data=payload)


@router.get("/library/items", response_model=ApiResponse[LibraryItemsResponse])
def get_library_items(
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    type_label: str | None = Query(default=None),
    space_id: int | None = Query(default=None, ge=1),
    page_id: int | None = Query(default=None, ge=1),
    sort: Literal["last_active", "name", "mentions", "type"] = Query(default="last_active"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[LibraryItemsResponse]:
    """List library items for v2 workspace UI."""

    payload = list_library_items(
        db,
        limit=limit,
        offset=offset,
        query=q,
        type_label=type_label,
        space_id=space_id,
        page_id=page_id,
        sort=sort,
        order=order,
        include_technical=include_technical,
    )
    return ApiResponse(data=payload)


@router.get("/library/items/{item_id}", response_model=ApiResponse[LibraryItemDetailResponse])
def get_library_item_by_id(
    item_id: int = Path(..., ge=1),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[LibraryItemDetailResponse]:
    """Fetch one library item detail row."""

    payload = get_library_item(db, item_id=item_id, include_technical=include_technical)
    if payload is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    return ApiResponse(data=payload)


@router.patch("/library/items/{item_id}", response_model=ApiResponse[LibraryItemDetailResponse])
def patch_library_item_by_id(
    payload: LibraryItemUpdateRequest,
    item_id: int = Path(..., ge=1),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[LibraryItemDetailResponse]:
    """Update one library item by mutating its canonical entity."""

    updated = patch_library_item(
        db,
        item_id=item_id,
        payload=payload,
        include_technical=include_technical,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    return ApiResponse(data=updated)


@router.get(
    "/library/items/{item_id}/activity",
    response_model=ApiResponse[LibraryItemActivityResponse],
)
def get_library_item_activity_by_id(
    item_id: int = Path(..., ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[LibraryItemActivityResponse]:
    """List claim activity for one library item."""

    payload = list_library_item_activity(
        db,
        item_id=item_id,
        limit=limit,
        include_technical=include_technical,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    return ApiResponse(data=payload)


@router.get("/properties/catalog", response_model=ApiResponse[PropertyCatalogResponse])
def get_properties_catalog(
    q: str | None = Query(default=None),
    status: Literal["stable", "emerging", "deprecated"] | None = Query(default=None),
    kind: Literal["field", "relation"] | None = Query(default=None),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[PropertyCatalogResponse]:
    """List user-facing property/type catalog entries."""

    payload = list_property_catalog(
        db,
        query=q,
        status=status,
        kind=kind,
        include_technical=include_technical,
    )
    return ApiResponse(data=payload)


@router.patch("/properties/catalog/{property_id}", response_model=ApiResponse[PropertyCatalogRead])
def patch_properties_catalog_row(
    payload: PropertyCatalogUpdateRequest,
    property_id: int = Path(..., ge=1),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[PropertyCatalogRead]:
    """Update one property catalog row."""

    updated = patch_property_catalog(
        db,
        property_id=property_id,
        payload=payload,
        include_technical=include_technical,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Property not found")
    return ApiResponse(data=updated)


@router.get("/claims/{claim_id}/explain", response_model=ApiResponse[UnifiedClaimExplainResponse])
def get_claim_explain(
    claim_id: int = Path(..., ge=1),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[UnifiedClaimExplainResponse]:
    """Unified explain endpoint for fact and relation claim rows."""

    payload = get_unified_claim_explain(
        db,
        claim_index_id=claim_id,
        include_technical=include_technical,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return ApiResponse(data=payload)


@router.get("/search", response_model=ApiResponse[SearchV2Response])
def get_v2_search(
    q: str = Query(..., min_length=1),
    conversation_id: str | None = Query(default=None, min_length=1),
    type_label: str | None = Query(default=None, min_length=1),
    space_id: int | None = Query(default=None, ge=1),
    page_id: int | None = Query(default=None, ge=1),
    include_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse[SearchV2Response]:
    """Grouped search results for card-based UI surfaces."""

    payload = search_workspace(
        db,
        query=q,
        conversation_id=conversation_id,
        type_label=type_label,
        space_id=space_id,
        page_id=page_id,
        include_technical=include_technical,
    )
    return ApiResponse(data=payload)
