"""Schemas for editable/deletable record endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeleteResult(BaseModel):
    """Generic delete response payload."""

    id: int
    deleted: bool


class MessageUpdateRequest(BaseModel):
    """Allowed mutable fields for a message row."""

    role: Literal["user", "assistant"] | None = None
    content: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "MessageUpdateRequest":
        if self.role is None and self.content is None:
            raise ValueError("At least one field must be provided.")
        return self


class EntityUpdateRequest(BaseModel):
    """Allowed mutable fields for an entity row."""

    canonical_name: str | None = Field(default=None, min_length=1)
    display_name: str | None = Field(default=None, min_length=1)
    type_label: str | None = Field(default=None, min_length=1)
    type: str | None = Field(default=None, min_length=1)
    known_aliases_json: list[str] | None = None
    aliases_json: list[str] | None = None
    tags_json: list[str] | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "EntityUpdateRequest":
        if not any(
            value is not None
            for value in (
                self.canonical_name,
                self.display_name,
                self.type_label,
                self.type,
                self.known_aliases_json,
                self.aliases_json,
                self.tags_json,
            )
        ):
            raise ValueError("At least one field must be provided.")
        return self


class FactUpdateRequest(BaseModel):
    """Allowed mutable fields for a fact row."""

    subject_entity_id: int | None = Field(default=None, ge=1)
    predicate: str | None = Field(default=None, min_length=1)
    object_value: str | None = Field(default=None, min_length=1)
    scope: str | None = Field(default=None, min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "FactUpdateRequest":
        if not any(
            value is not None
            for value in (
                self.subject_entity_id,
                self.predicate,
                self.object_value,
                self.scope,
                self.confidence,
            )
        ):
            raise ValueError("At least one field must be provided.")
        return self


class RelationUpdateRequest(BaseModel):
    """Allowed mutable fields for a relation row."""

    from_entity_id: int | None = Field(default=None, ge=1)
    to_entity_id: int | None = Field(default=None, ge=1)
    relation_type: str | None = Field(default=None, min_length=1)
    scope: str | None = Field(default=None, min_length=1)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    qualifiers_json: dict[str, object] | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "RelationUpdateRequest":
        if not any(
            value is not None
            for value in (
                self.from_entity_id,
                self.to_entity_id,
                self.relation_type,
                self.scope,
                self.confidence,
                self.qualifiers_json,
            )
        ):
            raise ValueError("At least one field must be provided.")
        return self


class SchemaNodeUpdateRequest(BaseModel):
    """Allowed mutable fields for schema node rows."""

    label: str | None = Field(default=None, min_length=1)
    description: str | None = None
    examples_json: list[str] | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "SchemaNodeUpdateRequest":
        if self.label is None and self.description is None and self.examples_json is None:
            raise ValueError("At least one field must be provided.")
        return self


class SchemaFieldUpdateRequest(BaseModel):
    """Allowed mutable fields for schema field rows."""

    label: str | None = Field(default=None, min_length=1)
    description: str | None = None
    examples_json: list[str] | None = None
    canonical_of_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "SchemaFieldUpdateRequest":
        if (
            self.label is None
            and self.description is None
            and self.examples_json is None
            and self.canonical_of_id is None
        ):
            raise ValueError("At least one field must be provided.")
        return self


class SchemaRelationUpdateRequest(BaseModel):
    """Allowed mutable fields for schema relation rows."""

    label: str | None = Field(default=None, min_length=1)
    description: str | None = None
    examples_json: list[str] | None = None
    canonical_of_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> "SchemaRelationUpdateRequest":
        if (
            self.label is None
            and self.description is None
            and self.examples_json is None
            and self.canonical_of_id is None
        ):
            raise ValueError("At least one field must be provided.")
        return self


class SchemaNodeMutationRead(BaseModel):
    """Serialized schema node mutation response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    description: str | None
    examples_json: list[str]


class SchemaFieldMutationRead(BaseModel):
    """Serialized schema field mutation response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    canonical_of_id: int | None
    description: str | None
    examples_json: list[str]


class SchemaRelationMutationRead(BaseModel):
    """Serialized schema relation mutation response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    canonical_of_id: int | None
    description: str | None
    examples_json: list[str]
