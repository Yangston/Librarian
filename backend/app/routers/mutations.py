"""Editable/deletable record routes for workspace UIs."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.schemas.common import ApiResponse
from app.schemas.entity import EntityRead
from app.schemas.fact import FactWithSubjectRead
from app.schemas.message import MessageRead
from app.schemas.mutations import (
    ConversationDeleteResult,
    DeleteResult,
    EntityUpdateRequest,
    FactUpdateRequest,
    MessageUpdateRequest,
    RelationUpdateRequest,
    SchemaFieldMutationRead,
    SchemaFieldUpdateRequest,
    SchemaNodeMutationRead,
    SchemaNodeUpdateRequest,
    SchemaRelationMutationRead,
    SchemaRelationUpdateRequest,
)
from app.schemas.relation import RelationWithEntitiesRead
from app.services.mutations import (
    delete_conversation,
    delete_entity,
    delete_fact,
    delete_message,
    delete_relation,
    delete_schema_field,
    delete_schema_node,
    delete_schema_relation,
    update_entity,
    update_fact,
    update_message,
    update_relation,
    update_schema_field,
    update_schema_node,
    update_schema_relation,
)

router = APIRouter()


@router.patch("/messages/{message_id}", response_model=ApiResponse[MessageRead])
def patch_message(
    payload: MessageUpdateRequest,
    message_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[MessageRead]:
    """Edit one message row."""

    updated = update_message(db, message_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Message not found")
    return ApiResponse(data=MessageRead.model_validate(updated))


@router.delete("/messages/{message_id}", response_model=ApiResponse[DeleteResult])
def remove_message(
    message_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResult]:
    """Delete one message row."""

    deleted = delete_message(db, message_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    return ApiResponse(data=DeleteResult(id=message_id, deleted=True))


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ApiResponse[ConversationDeleteResult],
)
def remove_conversation(
    conversation_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
) -> ApiResponse[ConversationDeleteResult]:
    """Delete one conversation and all conversation-scoped records."""

    clean_conversation_id = conversation_id.strip()
    deleted = delete_conversation(db, clean_conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ApiResponse(
        data=ConversationDeleteResult(conversation_id=clean_conversation_id, deleted=True)
    )


@router.patch("/entities/{entity_id}", response_model=ApiResponse[EntityRead])
def patch_entity(
    payload: EntityUpdateRequest,
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[EntityRead]:
    """Edit one entity row."""

    updated = update_entity(db, entity_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ApiResponse(data=updated)


@router.delete("/entities/{entity_id}", response_model=ApiResponse[DeleteResult])
def remove_entity(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResult]:
    """Delete one entity node and related edges/facts."""

    deleted = delete_entity(db, entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ApiResponse(data=DeleteResult(id=entity_id, deleted=True))


@router.patch("/facts/{fact_id}", response_model=ApiResponse[FactWithSubjectRead])
def patch_fact(
    payload: FactUpdateRequest,
    fact_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[FactWithSubjectRead]:
    """Edit one fact row."""

    updated = update_fact(db, fact_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Fact or referenced entity not found")
    return ApiResponse(data=updated)


@router.delete("/facts/{fact_id}", response_model=ApiResponse[DeleteResult])
def remove_fact(
    fact_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResult]:
    """Delete one fact row."""

    deleted = delete_fact(db, fact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fact not found")
    return ApiResponse(data=DeleteResult(id=fact_id, deleted=True))


@router.patch("/relations/{relation_id}", response_model=ApiResponse[RelationWithEntitiesRead])
def patch_relation(
    payload: RelationUpdateRequest,
    relation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[RelationWithEntitiesRead]:
    """Edit one relation row."""

    updated = update_relation(db, relation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Relation or referenced entities not found")
    return ApiResponse(data=updated)


@router.delete("/relations/{relation_id}", response_model=ApiResponse[DeleteResult])
def remove_relation(
    relation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResult]:
    """Delete one relation row."""

    deleted = delete_relation(db, relation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relation not found")
    return ApiResponse(data=DeleteResult(id=relation_id, deleted=True))


@router.patch("/schema/nodes/{schema_node_id}", response_model=ApiResponse[SchemaNodeMutationRead])
def patch_schema_node(
    payload: SchemaNodeUpdateRequest,
    schema_node_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[SchemaNodeMutationRead]:
    """Edit one schema node row."""

    updated = update_schema_node(db, schema_node_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Schema node not found")
    return ApiResponse(data=updated)


@router.delete("/schema/nodes/{schema_node_id}", response_model=ApiResponse[DeleteResult])
def remove_schema_node(
    schema_node_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResult]:
    """Delete one schema node row."""

    deleted = delete_schema_node(db, schema_node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schema node not found")
    return ApiResponse(data=DeleteResult(id=schema_node_id, deleted=True))


@router.patch("/schema/fields/{schema_field_id}", response_model=ApiResponse[SchemaFieldMutationRead])
def patch_schema_field(
    payload: SchemaFieldUpdateRequest,
    schema_field_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[SchemaFieldMutationRead]:
    """Edit one schema field row."""

    updated = update_schema_field(db, schema_field_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Schema field or canonical target not found")
    return ApiResponse(data=updated)


@router.delete("/schema/fields/{schema_field_id}", response_model=ApiResponse[DeleteResult])
def remove_schema_field(
    schema_field_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResult]:
    """Delete one schema field row."""

    deleted = delete_schema_field(db, schema_field_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schema field not found")
    return ApiResponse(data=DeleteResult(id=schema_field_id, deleted=True))


@router.patch("/schema/relations/{schema_relation_id}", response_model=ApiResponse[SchemaRelationMutationRead])
def patch_schema_relation(
    payload: SchemaRelationUpdateRequest,
    schema_relation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[SchemaRelationMutationRead]:
    """Edit one schema relation row."""

    updated = update_schema_relation(db, schema_relation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Schema relation or canonical target not found")
    return ApiResponse(data=updated)


@router.delete("/schema/relations/{schema_relation_id}", response_model=ApiResponse[DeleteResult])
def remove_schema_relation(
    schema_relation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> ApiResponse[DeleteResult]:
    """Delete one schema relation row."""

    deleted = delete_schema_relation(db, schema_relation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schema relation not found")
    return ApiResponse(data=DeleteResult(id=schema_relation_id, deleted=True))
