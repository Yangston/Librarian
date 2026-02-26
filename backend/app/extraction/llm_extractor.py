"""LLM-backed extractor for dynamic entity/fact/relation extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from pydantic import BaseModel, Field, ValidationError

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractedFact, ExtractedRelation, ExtractionResult
from app.models.message import Message
from app.schema.entity_types import ENTITY_TYPE_VALUES, normalize_entity_type

ALLOWED_ENTITY_TYPES = set(ENTITY_TYPE_VALUES)
_ENTITY_TYPE_VALUES = sorted(ENTITY_TYPE_VALUES)
_EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "name": "librarian_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": _ENTITY_TYPE_VALUES},
                        "aliases": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "source_message_ids": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["name", "type", "aliases", "tags", "source_message_ids"],
                },
            },
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "subject_name": {"type": "string"},
                        "subject_type": {"type": "string", "enum": _ENTITY_TYPE_VALUES},
                        "predicate": {"type": "string"},
                        "object_value": {"type": "string"},
                        "confidence": {"type": "number"},
                        "source_message_ids": {"type": "array", "items": {"type": "integer"}},
                        "snippet": {"type": ["string", "null"]},
                    },
                    "required": [
                        "subject_name",
                        "subject_type",
                        "predicate",
                        "object_value",
                        "confidence",
                        "source_message_ids",
                        "snippet",
                    ],
                },
            },
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "from_name": {"type": "string"},
                        "from_type": {"type": "string", "enum": _ENTITY_TYPE_VALUES},
                        "relation_type": {"type": "string"},
                        "to_name": {"type": "string"},
                        "to_type": {"type": "string", "enum": _ENTITY_TYPE_VALUES},
                        "qualifiers": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "key": {"type": "string"},
                                    "value": {"type": ["string", "number", "boolean", "null"]},
                                },
                                "required": ["key", "value"],
                            },
                        },
                        "source_message_ids": {"type": "array", "items": {"type": "integer"}},
                        "snippet": {"type": ["string", "null"]},
                    },
                    "required": [
                        "from_name",
                        "from_type",
                        "relation_type",
                        "to_name",
                        "to_type",
                        "qualifiers",
                        "source_message_ids",
                        "snippet",
                    ],
                },
            },
        },
        "required": ["entities", "facts", "relations"],
    },
}


class LLMExtractionError(RuntimeError):
    """Raised when AI extraction is misconfigured or the provider response is invalid."""


class LLMClient(Protocol):
    """Protocol for pluggable LLM clients used by the extractor."""

    def extract_structured(
        self,
        messages: list[dict[str, Any]],
        *,
        conversation_hints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a structured extraction payload."""


@dataclass(slots=True)
class OpenAIChatCompletionsClient:
    """Minimal OpenAI Chat Completions client using stdlib HTTP."""

    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60

    def extract_structured(
        self,
        messages: list[dict[str, Any]],
        *,
        conversation_hints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call OpenAI and return parsed JSON extraction output."""

        system_prompt = (
            "You extract structured knowledge from conversation messages. "
            "Return only structured output matching the provided JSON schema.\n"
            "Goal: produce transparent, auditable records for a relational database.\n"
            "Be conservative. Only extract supported by text.\n"
            "Each fact/relation MUST include source_message_ids using provided message IDs.\n"
            "Entity types must be one of: Company, Person, Event, Concept, Metric, Location, Other.\n"
            "Prefer short, normalized names and predicates/relation_type values.\n"
            "Keep snippets short and exact when included."
        )
        user_prompt = json.dumps(
            {
                "task": "Extract entities, facts, and relations from these messages.",
                "conversation_hints": conversation_hints or {},
                "messages": messages,
            },
            ensure_ascii=True,
        )

        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": _EXTRACTION_JSON_SCHEMA,
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        req = urllib_request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib_request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMExtractionError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        except urllib_error.URLError as exc:
            raise LLMExtractionError(f"OpenAI request failed: {exc.reason}") from exc

        try:
            decoded = json.loads(raw)
            message = decoded["choices"][0]["message"]
            refusal = message.get("refusal")
            if isinstance(refusal, str) and refusal.strip():
                raise LLMExtractionError(f"OpenAI refused extraction request: {refusal.strip()}")
            content = message["content"]
            if not isinstance(content, str):
                raise TypeError("OpenAI response content is not a string")
            return json.loads(content)
        except LLMExtractionError:
            raise
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMExtractionError("OpenAI returned an unexpected or non-JSON response") from exc


class _RawEntity(BaseModel):
    name: str
    type: str = "Other"
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_message_ids: list[int] = Field(default_factory=list)


class _RawFact(BaseModel):
    subject_name: str
    subject_type: str = "Other"
    predicate: str
    object_value: str
    confidence: float = 0.7
    source_message_ids: list[int] = Field(default_factory=list)
    snippet: str | None = None


class _RawRelation(BaseModel):
    from_name: str
    from_type: str = "Other"
    relation_type: str
    to_name: str
    to_type: str = "Other"
    qualifiers: list["_RawQualifierItem"] | dict[str, Any] = Field(default_factory=list)
    source_message_ids: list[int] = Field(default_factory=list)
    snippet: str | None = None


class _RawQualifierItem(BaseModel):
    key: str
    value: str | float | int | bool | None


class _RawExtractionPayload(BaseModel):
    entities: list[_RawEntity] = Field(default_factory=list)
    facts: list[_RawFact] = Field(default_factory=list)
    relations: list[_RawRelation] = Field(default_factory=list)


class LLMExtractor(ExtractorInterface):
    """AI-powered extractor that normalizes structured LLM output."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def extract(self, messages: list[Message]) -> ExtractionResult:
        """Extract entities, facts, and relations using an LLM."""

        serialized_messages = [self._serialize_message(message) for message in messages if message.content.strip()]
        if not serialized_messages:
            return ExtractionResult()

        raw_payload = self._client.extract_structured(
            serialized_messages,
            conversation_hints={
                "message_count": len(serialized_messages),
                "entity_type_allowlist": sorted(ALLOWED_ENTITY_TYPES),
            },
        )
        try:
            validated = _RawExtractionPayload.model_validate(raw_payload)
        except ValidationError as exc:
            raise LLMExtractionError(f"LLM extraction payload failed validation: {exc}") from exc

        valid_message_ids = {m["id"] for m in serialized_messages}
        entity_map: dict[tuple[str, str], ExtractedEntity] = {}
        facts: list[ExtractedFact] = []
        relations: list[ExtractedRelation] = []
        seen_facts: set[tuple[Any, ...]] = set()
        seen_relations: set[tuple[Any, ...]] = set()

        for entity in validated.entities:
            normalized_source_ids = self._normalize_source_message_ids(entity.source_message_ids, valid_message_ids)
            self._ensure_entity(
                entity_map,
                name=entity.name,
                entity_type=entity.type,
                source_message_ids=normalized_source_ids,
                aliases=entity.aliases,
                tags=entity.tags,
            )

        for fact in validated.facts:
            subject_name = self._clean_text(fact.subject_name)
            predicate = self._normalize_label(fact.predicate)
            object_value = self._clean_text(fact.object_value)
            source_ids = self._normalize_source_message_ids(fact.source_message_ids, valid_message_ids)
            if not (subject_name and predicate and object_value and source_ids):
                continue
            subject_type = self._normalize_entity_type(fact.subject_type)
            self._ensure_entity(entity_map, subject_name, subject_type, source_ids)
            dedupe_key = (
                subject_name.lower(),
                subject_type,
                predicate,
                object_value.lower(),
                tuple(source_ids),
            )
            if dedupe_key in seen_facts:
                continue
            seen_facts.add(dedupe_key)
            facts.append(
                ExtractedFact(
                    subject_name=subject_name,
                    subject_type=subject_type,
                    predicate=predicate,
                    object_value=object_value,
                    confidence=max(0.0, min(1.0, float(fact.confidence))),
                    source_message_ids=source_ids,
                    snippet=self._clean_snippet(fact.snippet),
                )
            )

        for relation in validated.relations:
            from_name = self._clean_text(relation.from_name)
            to_name = self._clean_text(relation.to_name)
            relation_type = self._normalize_label(relation.relation_type)
            source_ids = self._normalize_source_message_ids(relation.source_message_ids, valid_message_ids)
            if not (from_name and to_name and relation_type and source_ids):
                continue
            from_type = self._normalize_entity_type(relation.from_type)
            to_type = self._normalize_entity_type(relation.to_type)
            self._ensure_entity(entity_map, from_name, from_type, source_ids)
            self._ensure_entity(entity_map, to_name, to_type, source_ids)
            qualifiers = self._normalize_qualifiers(relation.qualifiers)
            snippet = self._clean_snippet(relation.snippet)
            if snippet and "snippet" not in qualifiers:
                qualifiers["snippet"] = snippet
            dedupe_qualifiers = {k: v for k, v in qualifiers.items() if k != "snippet"}
            dedupe_key = (
                from_name.lower(),
                from_type,
                relation_type,
                to_name.lower(),
                to_type,
                tuple(sorted((k, json.dumps(v, sort_keys=True, default=str)) for k, v in dedupe_qualifiers.items())),
                tuple(source_ids),
            )
            if dedupe_key in seen_relations:
                continue
            seen_relations.add(dedupe_key)
            relations.append(
                ExtractedRelation(
                    from_name=from_name,
                    from_type=from_type,
                    relation_type=relation_type,
                    to_name=to_name,
                    to_type=to_type,
                    qualifiers=qualifiers,
                    source_message_ids=source_ids,
                    snippet=snippet,
                )
            )

        entities = sorted(entity_map.values(), key=lambda e: (e.entity_type, e.name.lower()))
        facts.sort(key=lambda f: (f.subject_name.lower(), f.predicate, f.object_value.lower()))
        relations.sort(key=lambda r: (r.from_name.lower(), r.relation_type, r.to_name.lower()))
        return ExtractionResult(entities=entities, facts=facts, relations=relations)

    def _serialize_message(self, message: Message) -> dict[str, Any]:
        timestamp = message.timestamp
        if isinstance(timestamp, datetime):
            ts_value = timestamp.isoformat()
        else:
            ts_value = str(timestamp)
        return {
            "id": int(message.id),
            "role": str(message.role),
            "timestamp": ts_value,
            "content": message.content.strip(),
        }

    def _ensure_entity(
        self,
        entity_map: dict[tuple[str, str], ExtractedEntity],
        name: str,
        entity_type: str,
        source_message_ids: list[int],
        aliases: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        clean_name = self._clean_text(name)
        normalized_type = self._normalize_entity_type(entity_type)
        if not clean_name:
            return
        key = (clean_name.lower(), normalized_type)
        entity = entity_map.get(key)
        if entity is None:
            entity = ExtractedEntity(name=clean_name, entity_type=normalized_type)
            entity_map[key] = entity
        for message_id in source_message_ids:
            if message_id not in entity.source_message_ids:
                entity.source_message_ids.append(message_id)
        for alias in aliases or []:
            clean_alias = self._clean_text(alias)
            if clean_alias and clean_alias not in entity.aliases:
                entity.aliases.append(clean_alias)
        for tag in tags or []:
            clean_tag = self._normalize_tag(tag)
            if clean_tag and clean_tag not in entity.tags:
                entity.tags.append(clean_tag)

    @staticmethod
    def _normalize_source_message_ids(candidate_ids: list[int], valid_message_ids: set[int]) -> list[int]:
        seen: set[int] = set()
        result: list[int] = []
        for value in candidate_ids:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed not in valid_message_ids or parsed in seen:
                continue
            seen.add(parsed)
            result.append(parsed)
        return sorted(result)

    @staticmethod
    def _clean_text(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip(" \t\r\n.,:;\"'")

    @classmethod
    def _normalize_label(cls, value: str | None) -> str:
        cleaned = cls._clean_text(value)
        if not cleaned:
            return ""
        lowered = cleaned.lower()
        return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")

    @classmethod
    def _normalize_tag(cls, value: str | None) -> str:
        return cls._normalize_label(value)

    @classmethod
    def _normalize_entity_type(cls, raw_type: str | None) -> str:
        return normalize_entity_type(raw_type)

    @classmethod
    def _clean_snippet(cls, value: str | None) -> str | None:
        cleaned = cls._clean_text(value)
        return cleaned or None

    @classmethod
    def _normalize_qualifiers(
        cls,
        qualifiers: dict[str, Any] | list[_RawQualifierItem] | None,
    ) -> dict[str, Any]:
        if qualifiers is None:
            return {}
        if isinstance(qualifiers, list):
            normalized: dict[str, Any] = {}
            for item in qualifiers:
                key = cls._normalize_label(getattr(item, "key", ""))
                if not key:
                    continue
                value = getattr(item, "value", None)
                if isinstance(value, str):
                    cleaned = cls._clean_text(value)
                    if cleaned:
                        normalized[key] = cleaned
                elif isinstance(value, (int, float, bool)) or value is None:
                    normalized[key] = value
            return normalized
        if not isinstance(qualifiers, dict):
            return {}
        normalized: dict[str, Any] = {}
        for key, value in qualifiers.items():
            normalized_key = cls._normalize_label(str(key))
            if not normalized_key:
                continue
            if isinstance(value, str):
                cleaned_value = cls._clean_text(value)
                if cleaned_value:
                    normalized[normalized_key] = cleaned_value
            elif isinstance(value, (int, float, bool)) or value is None:
                normalized[normalized_key] = value
            elif isinstance(value, list):
                normalized[normalized_key] = [cls._clean_text(v) if isinstance(v, str) else v for v in value]
            elif isinstance(value, dict):
                normalized[normalized_key] = {
                    cls._normalize_label(str(sub_key)) or str(sub_key): (
                        cls._clean_text(sub_value) if isinstance(sub_value, str) else sub_value
                    )
                    for sub_key, sub_value in value.items()
                }
            else:
                normalized[normalized_key] = str(value)
        return normalized
