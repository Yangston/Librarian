"""LLM-backed extractor for dynamic entity/fact/relation extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from pydantic import BaseModel, Field, ValidationError

from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.types import ExtractedEntity, ExtractedFact, ExtractedRelation, ExtractionResult
from app.models.message import Message

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
                        "type_label": {"type": ["string", "null"]},
                        "aliases": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number"},
                        "source_message_ids": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["name", "type_label", "aliases", "tags", "confidence", "source_message_ids"],
                },
            },
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "entity_name": {"type": "string"},
                        "field_label": {"type": "string"},
                        "value_text": {"type": "string"},
                        "confidence": {"type": "number"},
                        "source_message_ids": {"type": "array", "items": {"type": "integer"}},
                        "snippet": {"type": ["string", "null"]},
                    },
                    "required": [
                        "entity_name",
                        "field_label",
                        "value_text",
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
                        "from_entity": {"type": "string"},
                        "relation_label": {"type": "string"},
                        "to_entity": {"type": "string"},
                        "qualifiers": {
                            "anyOf": [
                                {
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
                                {
                                    "type": "object",
                                    "additionalProperties": {"type": ["string", "number", "boolean", "null"]},
                                },
                            ]
                        },
                        "confidence": {"type": "number"},
                        "source_message_ids": {"type": "array", "items": {"type": "integer"}},
                        "snippet": {"type": ["string", "null"]},
                    },
                    "required": [
                        "from_entity",
                        "relation_label",
                        "to_entity",
                        "qualifiers",
                        "confidence",
                        "source_message_ids",
                        "snippet",
                    ],
                },
            },
        },
        "required": ["entities", "facts", "relations"],
    },
}
LLM_EXTRACTION_PROMPT_VERSION = "phase2.v1"
_PROMPT_FILES: dict[str, Path] = {
    "phase2.v1": Path(__file__).resolve().parent / "prompts" / "phase2_v1.txt",
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

        system_prompt = _get_extraction_system_prompt()
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


@lru_cache(maxsize=8)
def _get_extraction_system_prompt(version: str = LLM_EXTRACTION_PROMPT_VERSION) -> str:
    prompt_file = _PROMPT_FILES.get(version)
    if prompt_file is None:
        raise LLMExtractionError(f"Extraction prompt version is not registered: {version}")
    try:
        prompt_text = prompt_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise LLMExtractionError(f"Failed to load extraction prompt file: {prompt_file}") from exc
    if not prompt_text:
        raise LLMExtractionError(f"Extraction prompt file is empty: {prompt_file}")
    return prompt_text


class _RawEntity(BaseModel):
    name: str
    type_label: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.7
    source_message_ids: list[int] = Field(default_factory=list)


class _RawFact(BaseModel):
    entity_name: str
    field_label: str
    value_text: str
    confidence: float = 0.7
    source_message_ids: list[int] = Field(default_factory=list)
    snippet: str | None = None


class _RawRelation(BaseModel):
    from_entity: str
    relation_label: str
    to_entity: str
    qualifiers: list["_RawQualifierItem"] | dict[str, Any] = Field(default_factory=list)
    confidence: float = 0.7
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
        self._last_raw_output: dict[str, Any] | None = None
        self._last_validated_output: dict[str, Any] | None = None

    def extract(self, messages: list[Message]) -> ExtractionResult:
        """Extract entities, facts, and relations using an LLM."""

        self._last_raw_output = None
        self._last_validated_output = None
        serialized_messages = [self._serialize_message(message) for message in messages if message.content.strip()]
        if not serialized_messages:
            return ExtractionResult()

        raw_payload = self._client.extract_structured(
            serialized_messages,
            conversation_hints={
                "message_count": len(serialized_messages),
            },
        )
        self._last_raw_output = raw_payload if isinstance(raw_payload, dict) else {}
        try:
            validated = _RawExtractionPayload.model_validate(raw_payload)
        except ValidationError as exc:
            raise LLMExtractionError(f"LLM extraction payload failed validation: {exc}") from exc
        self._last_validated_output = validated.model_dump(mode="json")

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
                type_label=entity.type_label,
                source_message_ids=normalized_source_ids,
                confidence=entity.confidence,
                aliases=entity.aliases,
                tags=entity.tags,
            )

        for fact in validated.facts:
            entity_name = self._clean_text(fact.entity_name)
            field_label = self._normalize_label(fact.field_label)
            value_text = self._clean_text(fact.value_text)
            source_ids = self._normalize_source_message_ids(fact.source_message_ids, valid_message_ids)
            if not (entity_name and field_label and value_text and source_ids):
                continue
            self._ensure_entity(
                entity_map,
                name=entity_name,
                type_label=None,
                source_message_ids=source_ids,
                confidence=fact.confidence,
            )
            dedupe_key = (
                entity_name.lower(),
                field_label,
                value_text.lower(),
                tuple(source_ids),
            )
            if dedupe_key in seen_facts:
                continue
            seen_facts.add(dedupe_key)
            facts.append(
                ExtractedFact(
                    entity_name=entity_name,
                    field_label=field_label,
                    value_text=value_text,
                    confidence=max(0.0, min(1.0, float(fact.confidence))),
                    source_message_ids=source_ids,
                    snippet=self._clean_snippet(fact.snippet),
                )
            )

        for relation in validated.relations:
            from_entity = self._clean_text(relation.from_entity)
            to_entity = self._clean_text(relation.to_entity)
            relation_label = self._normalize_label(relation.relation_label)
            source_ids = self._normalize_source_message_ids(relation.source_message_ids, valid_message_ids)
            if not (from_entity and to_entity and relation_label and source_ids):
                continue
            self._ensure_entity(
                entity_map,
                name=from_entity,
                type_label=None,
                source_message_ids=source_ids,
                confidence=relation.confidence,
            )
            self._ensure_entity(
                entity_map,
                name=to_entity,
                type_label=None,
                source_message_ids=source_ids,
                confidence=relation.confidence,
            )
            qualifiers = self._normalize_qualifiers(relation.qualifiers)
            snippet = self._clean_snippet(relation.snippet)
            if snippet and "snippet" not in qualifiers:
                qualifiers["snippet"] = snippet
            dedupe_qualifiers = {k: v for k, v in qualifiers.items() if k != "snippet"}
            dedupe_key = (
                from_entity.lower(),
                relation_label,
                to_entity.lower(),
                tuple(sorted((k, json.dumps(v, sort_keys=True, default=str)) for k, v in dedupe_qualifiers.items())),
                tuple(source_ids),
            )
            if dedupe_key in seen_relations:
                continue
            seen_relations.add(dedupe_key)
            relations.append(
                ExtractedRelation(
                    from_entity=from_entity,
                    relation_label=relation_label,
                    to_entity=to_entity,
                    qualifiers=qualifiers,
                    confidence=max(0.0, min(1.0, float(relation.confidence))),
                    source_message_ids=source_ids,
                    snippet=snippet,
                )
            )

        entities = sorted(entity_map.values(), key=lambda e: ((e.type_label or ""), e.name.lower()))
        facts.sort(key=lambda f: (f.entity_name.lower(), f.field_label, f.value_text.lower()))
        relations.sort(key=lambda r: (r.from_entity.lower(), r.relation_label, r.to_entity.lower()))
        return ExtractionResult(entities=entities, facts=facts, relations=relations)

    @property
    def prompt_version(self) -> str:
        return LLM_EXTRACTION_PROMPT_VERSION

    @property
    def model_name(self) -> str:
        return str(getattr(self._client, "model", self._client.__class__.__name__))

    @property
    def last_raw_output(self) -> dict[str, Any] | None:
        return self._last_raw_output

    @property
    def last_validated_output(self) -> dict[str, Any] | None:
        return self._last_validated_output

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
        type_label: str | None,
        source_message_ids: list[int],
        confidence: float = 1.0,
        aliases: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        clean_name = self._clean_text(name)
        normalized_type = self._clean_type_label(type_label)
        normalized_confidence = max(0.0, min(1.0, float(confidence)))
        if not clean_name:
            return
        name_key = clean_name.lower()
        key = (name_key, normalized_type or "")
        entity = entity_map.get(key)

        if entity is None and normalized_type is not None:
            # Prefer promoting a previously unknown type for the same entity name.
            unknown_key = (name_key, "")
            entity = entity_map.get(unknown_key)
            if entity is not None:
                entity.type_label = normalized_type
                entity_map[key] = entity
                del entity_map[unknown_key]

        if entity is None and normalized_type is None:
            # If the same name already exists with one inferred type, reuse it.
            same_name_keys = [existing_key for existing_key in entity_map if existing_key[0] == name_key]
            if len(same_name_keys) == 1:
                entity = entity_map[same_name_keys[0]]

        if entity is None:
            entity = ExtractedEntity(
                name=clean_name,
                type_label=normalized_type,
                confidence=normalized_confidence,
            )
            entity_map[key] = entity
        if entity.type_label is None and normalized_type is not None:
            entity.type_label = normalized_type
        entity.confidence = max(entity.confidence, normalized_confidence)
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
    def _clean_snippet(cls, value: str | None) -> str | None:
        cleaned = cls._clean_text(value)
        return cleaned or None

    @classmethod
    def _clean_type_label(cls, value: str | None) -> str | None:
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
