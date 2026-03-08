"""Workspace-first planning, enrichment, and materialization services."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.entity_resolution.similarity import token_set_similarity
from app.models.collection import Collection
from app.models.collection_column import CollectionColumn
from app.models.collection_item import CollectionItem
from app.models.collection_item_relation import CollectionItemRelation
from app.models.collection_item_relation_suggestion import CollectionItemRelationSuggestion
from app.models.collection_item_value import CollectionItemValue
from app.models.collection_item_value_suggestion import CollectionItemValueSuggestion
from app.models.conversation import Conversation
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.extractor_run import ExtractorRun
from app.models.fact import Fact
from app.models.message import Message
from app.models.pod import Pod
from app.models.property_catalog import PropertyCatalog
from app.models.relation import Relation
from app.models.source import Source
from app.models.workspace_enrichment_run import WorkspaceEnrichmentRun
from app.schemas.workspace_v3 import WorkspaceEnrichmentRunRead, WorkspaceSyncRunRead

_MANAGED_COLLECTION_ORIGIN = "workspace_v3"
_DEFAULT_COLUMN_DEFS: dict[str, list[tuple[str, str, str]]] = {
    "accommodations": [
        ("title", "Name", "title"),
        ("location", "Location", "text"),
        ("price", "Price", "text"),
        ("rating", "Rating", "text"),
        ("website", "Website", "url"),
    ],
    "food": [
        ("title", "Name", "title"),
        ("cuisine", "Cuisine", "text"),
        ("location", "Location", "text"),
        ("price", "Price", "text"),
        ("website", "Website", "url"),
    ],
    "transportation": [
        ("title", "Name", "title"),
        ("provider", "Provider", "text"),
        ("departure", "Departure", "text"),
        ("arrival", "Arrival", "text"),
        ("price", "Price", "text"),
        ("booking_url", "Booking URL", "url"),
    ],
    "activities": [
        ("title", "Name", "title"),
        ("location", "Location", "text"),
        ("category", "Category", "text"),
        ("price", "Price", "text"),
        ("website", "Website", "url"),
    ],
    "general": [
        ("title", "Name", "title"),
        ("category", "Category", "text"),
        ("location", "Location", "text"),
        ("price", "Price", "text"),
        ("notes", "Notes", "text"),
    ],
}
_CATEGORY_KEYWORDS: list[tuple[str, set[str]]] = [
    ("accommodations", {"hotel", "hostel", "resort", "villa", "apartment", "lodging", "accommodation"}),
    ("food", {"restaurant", "cafe", "bar", "food", "eatery", "dining", "cuisine"}),
    ("transportation", {"flight", "airline", "train", "bus", "ferry", "airport", "transport"}),
    ("activities", {"museum", "tour", "activity", "excursion", "beach", "attraction", "temple"}),
]
_GENERIC_PREDICATES = {"name", "title", "type", "summary", "notes"}
_INFERRED_RELATION_COLUMNS = {"location", "category", "provider"}
_RESEARCH_PROMPT_VERSION = "workspace_research_v1"
_WORKSPACE_PLAN_PROMPT_VERSION = "workspace_plan_v2"
_MAX_RELATION_SUGGESTION_PAIRS = 24
_MAX_BATCH_ROWS = 30
_MAX_BATCH_MISSING_CELLS = 120
_MAX_BATCH_RELATION_CANDIDATES = 80


class WorkspaceResearchError(RuntimeError):
    """Raised when enrichment research fails."""


class WorkspaceResearchClient(Protocol):
    def lookup(
        self,
        *,
        entity_name: str,
        collection_name: str,
        column_label: str,
        include_sources: bool = True,
    ) -> dict[str, Any] | None:
        """Return researched value with citations for one cell."""

    def lookup_row(
        self,
        *,
        entity_name: str,
        collection_name: str,
        column_labels: list[str],
        include_sources: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """Return researched values keyed by column label for one row."""

    def lookup_relations(
        self,
        *,
        collection_name: str,
        entity_names: list[str],
        include_sources: bool = True,
    ) -> list[dict[str, Any]]:
        """Return researched relations among the provided entity names."""

    def lookup_value_batch(
        self,
        *,
        scope_label: str,
        rows: list[dict[str, Any]],
        include_sources: bool = True,
    ) -> list[dict[str, Any]]:
        """Return researched value suggestions for rows in scope."""

    def lookup_relation_batch(
        self,
        *,
        scope_label: str,
        rows: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        include_sources: bool = True,
    ) -> list[dict[str, Any]]:
        """Return researched relation suggestions for candidate pairs."""


def _is_self_evident_column(key: str, *, origin: str | None = None) -> bool:
    normalized = _column_key(key)
    if normalized == "title":
        return True
    if origin == "manual":
        return False
    return normalized in _GENERIC_PREDICATES


def _normalized_enrichment_policy(
    *,
    key: str,
    origin: str | None,
    current: dict[str, Any] | None = None,
) -> dict[str, object]:
    policy = dict(current or {})
    if _is_self_evident_column(key, origin=origin):
        policy["enabled"] = False
    elif "enabled" not in policy:
        policy["enabled"] = True
    return policy


def _column_enrichment_enabled(column: CollectionColumn) -> bool:
    return bool(
        _normalized_enrichment_policy(
            key=column.key,
            origin=column.origin,
            current=dict(column.enrichment_policy_json or {}),
        ).get("enabled", True)
    )


def _derived_workspace_value(
    *,
    entity: Entity,
    row: CollectionItem,
    key: str,
) -> tuple[str, Any] | None:
    normalized = _column_key(key)
    if normalized in {"name", "title"}:
        raw_value = row.title or entity.display_name or entity.canonical_name or entity.name
    elif normalized == "type":
        raw_value = entity.type_label or entity.type
    elif normalized == "summary":
        raw_value = row.summary
    elif normalized == "notes":
        raw_value = row.notes_markdown
    else:
        return None

    display_value = str(raw_value or "").strip()
    if not display_value:
        return None
    return display_value, display_value


def _normalized_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [source for source in value if isinstance(source, dict) and source.get("uri")]


@dataclass(slots=True)
class OpenAIWorkspaceResearchClient:
    """Minimal OpenAI Responses API client using built-in web search."""

    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60

    def _post_responses(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        req = urllib_request.Request(
            url=f"{self.base_url.rstrip('/')}/responses",
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
            raise WorkspaceResearchError(exc.read().decode("utf-8", errors="replace")) from exc
        except urllib_error.URLError as exc:
            raise WorkspaceResearchError(str(exc.reason)) from exc
        try:
            decoded = json.loads(raw)
            output_text = _extract_responses_output_text(decoded)
            if not isinstance(output_text, str) or not output_text.strip():
                return None
            parsed = json.loads(output_text)
            return parsed if isinstance(parsed, dict) else None
        except (TypeError, json.JSONDecodeError):
            return None

    def lookup(
        self,
        *,
        entity_name: str,
        collection_name: str,
        column_label: str,
        include_sources: bool = True,
    ) -> dict[str, Any] | None:
        prompt = (
            "Find the best current value for the requested property using the open web. "
            f"Return strict JSON with keys: value, confidence{', sources' if include_sources else ''}. "
            + (
                "sources should be an array of {title, uri, snippet} when available. "
                if include_sources
                else "Sources are optional. Omit them if collecting citations would slow the answer down. "
            )
            + "If no reliable value is found, return value as null."
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": prompt}]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "entity_name": entity_name,
                                    "collection_name": collection_name,
                                    "column_label": column_label,
                                },
                                ensure_ascii=True,
                            ),
                        }
                    ],
                },
            ],
            "tools": [{"type": "web_search_preview"}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "workspace_research_result",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "value": {"type": ["string", "null"]},
                            "confidence": {"type": ["number", "null"]},
                            "sources": {
                                "type": ["array", "null"],
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "title": {"type": ["string", "null"]},
                                        "uri": {"type": "string"},
                                        "snippet": {"type": ["string", "null"]},
                                    },
                                    "required": ["title", "uri", "snippet"],
                                },
                            },
                        },
                        "required": ["value", "confidence", "sources"],
                    },
                }
            },
        }
        parsed = self._post_responses(payload)
        if not isinstance(parsed, dict):
            return None
        return {
            "value": parsed.get("value"),
            "confidence": parsed.get("confidence"),
            "sources": _normalized_sources(parsed.get("sources")),
        }

    def lookup_row(
        self,
        *,
        entity_name: str,
        collection_name: str,
        column_labels: list[str],
        include_sources: bool = True,
    ) -> dict[str, dict[str, Any]]:
        if not column_labels:
            return {}
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Find the best current values for the requested properties using the open web. "
                                "Return strict JSON with key results. Each result must contain: "
                                f"column_label, value, confidence{', sources' if include_sources else ''}. "
                                + (
                                    "Include sources when available. "
                                    if include_sources
                                    else "Sources are optional. "
                                )
                                + "Do not fabricate missing values."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "entity_name": entity_name,
                                    "collection_name": collection_name,
                                    "column_labels": column_labels,
                                },
                                ensure_ascii=True,
                            ),
                        }
                    ],
                },
            ],
            "tools": [{"type": "web_search_preview"}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "workspace_row_research_result",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "results": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "column_label": {"type": "string"},
                                        "value": {"type": ["string", "null"]},
                                        "confidence": {"type": ["number", "null"]},
                                        "sources": {
                                            "type": ["array", "null"],
                                            "items": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "title": {"type": ["string", "null"]},
                                                    "uri": {"type": "string"},
                                                    "snippet": {"type": ["string", "null"]},
                                                },
                                                "required": ["title", "uri", "snippet"],
                                            },
                                        },
                                    },
                                    "required": ["column_label", "value", "confidence", "sources"],
                                },
                            }
                        },
                        "required": ["results"],
                    },
                }
            },
        }
        parsed = self._post_responses(payload)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
            return {}
        output: dict[str, dict[str, Any]] = {}
        for row in parsed["results"]:
            if not isinstance(row, dict):
                continue
            label = str(row.get("column_label") or "").strip()
            if not label:
                continue
            output[label] = {
                "value": row.get("value"),
                "confidence": row.get("confidence"),
                "sources": _normalized_sources(row.get("sources")),
            }
        return output

    def lookup_relations(
        self,
        *,
        collection_name: str,
        entity_names: list[str],
        include_sources: bool = True,
    ) -> list[dict[str, Any]]:
        if len(entity_names) < 2:
            return []
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Use the open web to find concise factual relationships among the provided entities. "
                                f"Return strict JSON with relations. Each relation must include from_name, to_name, relation_label, confidence{', sources' if include_sources else ''}. "
                                "Only include well-supported relationships."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "collection_name": collection_name,
                                    "entity_names": entity_names,
                                },
                                ensure_ascii=True,
                            ),
                        }
                    ],
                },
            ],
            "tools": [{"type": "web_search_preview"}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "workspace_relation_batch_result",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "relations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "from_name": {"type": "string"},
                                        "to_name": {"type": "string"},
                                        "relation_label": {"type": ["string", "null"]},
                                        "confidence": {"type": ["number", "null"]},
                                        "sources": {
                                            "type": ["array", "null"],
                                            "items": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "title": {"type": ["string", "null"]},
                                                    "uri": {"type": "string"},
                                                    "snippet": {"type": ["string", "null"]},
                                                },
                                                "required": ["title", "uri", "snippet"],
                                            },
                                        },
                                    },
                                    "required": ["from_name", "to_name", "relation_label", "confidence", "sources"],
                                },
                            }
                        },
                        "required": ["relations"],
                    },
                }
            },
        }
        parsed = self._post_responses(payload)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("relations"), list):
            return []
        return [row for row in parsed["relations"] if isinstance(row, dict)]

    def lookup_value_batch(
        self,
        *,
        scope_label: str,
        rows: list[dict[str, Any]],
        include_sources: bool = True,
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Use the open web to fill only missing table cells. "
                                f"Return strict JSON. Each suggestion must include row_id, column_key, value, confidence{', and sources' if include_sources else ''}. "
                                "Only return suggestions for the provided missing cells. "
                                "Do not return values for cells that already have data. "
                                + (
                                    "Use concise factual values and include citations when available."
                                    if include_sources
                                    else "Use concise factual values. Sources are optional."
                                )
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "scope_label": scope_label,
                                    "rows": rows,
                                },
                                ensure_ascii=True,
                            ),
                        }
                    ],
                },
            ],
            "tools": [{"type": "web_search_preview"}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "workspace_value_batch_result",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "suggestions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "row_id": {"type": "integer"},
                                        "column_key": {"type": "string"},
                                        "value": {"type": ["string", "null"]},
                                        "confidence": {"type": ["number", "null"]},
                                        "sources": {
                                            "type": ["array", "null"],
                                            "items": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "title": {"type": ["string", "null"]},
                                                    "uri": {"type": "string"},
                                                    "snippet": {"type": ["string", "null"]},
                                                },
                                                "required": ["title", "uri", "snippet"],
                                            },
                                        },
                                    },
                                    "required": ["row_id", "column_key", "value", "confidence", "sources"],
                                },
                            }
                        },
                        "required": ["suggestions"],
                    },
                }
            },
        }
        parsed = self._post_responses(payload)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("suggestions"), list):
            return []
        return [row for row in parsed["suggestions"] if isinstance(row, dict)]

    def lookup_relation_batch(
        self,
        *,
        scope_label: str,
        rows: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        include_sources: bool = True,
    ) -> list[dict[str, Any]]:
        if not rows or not candidates:
            return []
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Use the open web to confirm missing factual relationships between provided rows. "
                                f"Return strict JSON. Each result must include candidate_id, relation_label, confidence{', and sources' if include_sources else ''}. "
                                "Only return confirmed relationships for provided candidates. "
                                + (
                                    "Use short snake_case style relation labels and include citations when available."
                                    if include_sources
                                    else "Use short snake_case style relation labels. Sources are optional."
                                )
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "scope_label": scope_label,
                                    "rows": rows,
                                    "candidates": candidates,
                                },
                                ensure_ascii=True,
                            ),
                        }
                    ],
                },
            ],
            "tools": [{"type": "web_search_preview"}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "workspace_relation_batch_review_result",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "relations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "candidate_id": {"type": "string"},
                                        "relation_label": {"type": ["string", "null"]},
                                        "confidence": {"type": ["number", "null"]},
                                        "sources": {
                                            "type": ["array", "null"],
                                            "items": {
                                                "type": "object",
                                                "additionalProperties": False,
                                                "properties": {
                                                    "title": {"type": ["string", "null"]},
                                                    "uri": {"type": "string"},
                                                    "snippet": {"type": ["string", "null"]},
                                                },
                                                "required": ["title", "uri", "snippet"],
                                            },
                                        },
                                    },
                                    "required": ["candidate_id", "relation_label", "confidence", "sources"],
                                },
                            }
                        },
                        "required": ["relations"],
                    },
                }
            },
        }
        parsed = self._post_responses(payload)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("relations"), list):
            return []
        return [row for row in parsed["relations"] if isinstance(row, dict)]


@dataclass(slots=True)
class PlannedCollection:
    slug: str
    name: str
    category: str
    description: str
    entity_ids: list[int]
    columns: list[tuple[str, str, str]]


def get_default_research_client() -> WorkspaceResearchClient | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return OpenAIWorkspaceResearchClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def run_workspace_sync_for_conversation(
    db: Session,
    *,
    conversation_id: str,
    allow_enrichment: bool = True,
) -> WorkspaceSyncRunRead:
    conversation = db.scalar(select(Conversation).where(Conversation.conversation_id == conversation_id))
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id!r} not found.")
    return rebuild_workspace_for_pod(
        db,
        pod_id=int(conversation.pod_id),
        conversation_id=conversation_id,
        allow_enrichment=allow_enrichment,
    )


def rebuild_workspace_for_pod(
    db: Session,
    *,
    pod_id: int,
    conversation_id: str | None = None,
    allow_enrichment: bool = False,
) -> WorkspaceSyncRunRead:
    pod = db.scalar(select(Pod).where(Pod.id == pod_id))
    if pod is None:
        raise ValueError(f"Pod {pod_id} not found.")

    entity_rows = list(
        db.scalars(
            select(Entity)
            .where(Entity.pod_id == pod_id, Entity.merged_into_id.is_(None))
            .order_by(Entity.updated_at.desc(), Entity.id.asc())
        ).all()
    )
    fact_rows = list(
        db.scalars(
            select(Fact).where(Fact.pod_id == pod_id).order_by(Fact.created_at.desc(), Fact.id.desc())
        ).all()
    )
    relation_rows = list(
        db.scalars(
            select(Relation).where(Relation.pod_id == pod_id).order_by(Relation.created_at.desc(), Relation.id.desc())
        ).all()
    )

    planner_run = _log_workspace_run(
        db,
        conversation_id=conversation_id,
        pod_id=pod_id,
        run_kind="workspace_plan",
        model_name="heuristic_workspace_planner",
        prompt_version="workspace_plan_v1",
        payload_json={
            "entity_count": len(entity_rows),
            "fact_count": len(fact_rows),
            "relation_count": len(relation_rows),
        },
    )
    planned_collections = _plan_collections(db, pod_id=pod_id, entities=entity_rows, facts=fact_rows)
    collections_by_slug = _upsert_planned_collections(db, pod_id=pod_id, planned=planned_collections)
    columns_by_collection = _upsert_collection_columns(
        db,
        planned=planned_collections,
        collections_by_slug=collections_by_slug,
    )
    row_map = _upsert_collection_rows(
        db,
        planned=planned_collections,
        collections_by_slug=collections_by_slug,
        entities=entity_rows,
        facts=fact_rows,
    )
    values_upserted = _upsert_collection_values(
        db,
        planned=planned_collections,
        collections_by_slug=collections_by_slug,
        columns_by_collection=columns_by_collection,
        row_map=row_map,
        facts=fact_rows,
    )
    relations_upserted = _upsert_collection_relations(db, row_map=row_map, relations=relation_rows)
    _sync_collection_schema_json(collections_by_slug=collections_by_slug, columns_by_collection=columns_by_collection)
    _rebuild_property_catalog_from_columns(db)

    db.flush()
    return WorkspaceSyncRunRead(
        conversation_id=conversation_id or f"pod:{pod_id}",
        pod_id=pod_id,
        planner_run_id=planner_run.id if planner_run is not None else None,
        enrichment_run_id=None,
        collections_upserted=len(collections_by_slug),
        rows_upserted=len(row_map),
        values_upserted=values_upserted,
        relations_upserted=relations_upserted,
    )


def create_workspace_enrichment_run(
    db: Session,
    *,
    pod_id: int,
    conversation_id: str | None = None,
    collection_id: int | None = None,
    collection_item_id: int | None = None,
    requested_by: str = "user",
    run_kind: str | None = None,
    summary_json: dict[str, object] | None = None,
) -> WorkspaceEnrichmentRunRead:
    resolved_run_kind = run_kind or (
        "manual_row"
        if collection_item_id is not None
        else "manual_collection"
        if collection_id is not None
        else "manual_space"
    )
    row = WorkspaceEnrichmentRun(
        pod_id=pod_id,
        conversation_id=conversation_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
        requested_by=requested_by,
        run_kind=resolved_run_kind,
        status="queued",
        stage="queued",
        error_message=None,
        summary_json=dict(summary_json or {}),
        started_at=None,
        completed_at=None,
    )
    db.add(row)
    db.flush()
    return _workspace_enrichment_run_read(row)


def get_workspace_enrichment_run(
    db: Session,
    *,
    run_id: int,
) -> WorkspaceEnrichmentRunRead | None:
    row = db.scalar(select(WorkspaceEnrichmentRun).where(WorkspaceEnrichmentRun.id == run_id))
    if row is None:
        return None
    return _workspace_enrichment_run_read(row)


def get_latest_workspace_enrichment_run(
    db: Session,
    *,
    pod_id: int,
) -> WorkspaceEnrichmentRunRead | None:
    row = db.scalar(
        select(WorkspaceEnrichmentRun)
        .where(WorkspaceEnrichmentRun.pod_id == pod_id)
        .order_by(WorkspaceEnrichmentRun.created_at.desc(), WorkspaceEnrichmentRun.id.desc())
        .limit(1)
    )
    if row is None:
        return None
    return _workspace_enrichment_run_read(row)


def _merge_workspace_run_summary(
    db: Session,
    *,
    run: WorkspaceEnrichmentRun,
    summary: dict[str, object],
) -> None:
    next_summary = dict(run.summary_json or {})
    next_summary.update(summary)
    run.summary_json = next_summary
    db.add(run)
    db.commit()
    db.refresh(run)


def _set_workspace_run_state(
    db: Session,
    *,
    run: WorkspaceEnrichmentRun,
    status: str,
    stage: str,
    started: bool = False,
    completed: bool = False,
    clear_error: bool = False,
    error_message: str | None = None,
) -> None:
    run.status = status
    run.stage = stage
    if started and run.started_at is None:
        run.started_at = datetime.now(timezone.utc)
    if completed:
        run.completed_at = datetime.now(timezone.utc)
    if clear_error:
        run.error_message = None
    if error_message is not None:
        run.error_message = error_message
    db.add(run)
    db.commit()
    db.refresh(run)


def run_workspace_enrichment_run(
    db: Session,
    *,
    run_id: int,
) -> WorkspaceEnrichmentRunRead | None:
    run = db.scalar(select(WorkspaceEnrichmentRun).where(WorkspaceEnrichmentRun.id == run_id))
    if run is None:
        return None
    _set_workspace_run_state(
        db,
        run=run,
        status="running",
        stage="workspace_sync" if run.run_kind == "system_chat" else "value_enrichment",
        started=True,
        clear_error=True,
    )

    try:
        include_sources = bool(run.summary_json.get("include_sources", True))
        if run.run_kind == "system_chat":
            if not run.conversation_id:
                raise WorkspaceResearchError("System workspace runs require a conversation_id.")
            sync_result = run_workspace_sync_for_conversation(
                db,
                conversation_id=run.conversation_id,
                allow_enrichment=False,
            )
            _merge_workspace_run_summary(
                db,
                run=run,
                summary={
                    "conversation_id": run.conversation_id,
                    "workspace_sync": sync_result.model_dump(mode="json"),
                },
            )
            _set_workspace_run_state(db, run=run, status="running", stage="value_enrichment")
        settings = get_settings()
        if not settings.openai_api_key:
            raise WorkspaceResearchError("OPENAI_API_KEY is not configured in backend/.env.")

        _clear_pending_suggestions(
            db,
            pod_id=int(run.pod_id),
            collection_id=int(run.collection_id) if run.collection_id is not None else None,
            collection_item_id=int(run.collection_item_id) if run.collection_item_id is not None else None,
        )
        value_summary = generate_value_enrichment_suggestions(
            db,
            pod_id=int(run.pod_id),
            collection_id=int(run.collection_id) if run.collection_id is not None else None,
            collection_item_id=int(run.collection_item_id) if run.collection_item_id is not None else None,
            run_id=int(run.id),
            include_sources=include_sources,
        )
        _merge_workspace_run_summary(db, run=run, summary=value_summary)
        _set_workspace_run_state(db, run=run, status="running", stage="relation_enrichment")
        relation_summary = generate_relation_enrichment_suggestions(
            db,
            pod_id=int(run.pod_id),
            collection_id=int(run.collection_id) if run.collection_id is not None else None,
            collection_item_id=int(run.collection_item_id) if run.collection_item_id is not None else None,
            run_id=int(run.id),
            include_sources=include_sources,
        )
        _merge_workspace_run_summary(db, run=run, summary=relation_summary)
        _set_workspace_run_state(
            db,
            run=run,
            status="completed",
            stage="completed",
            completed=True,
            clear_error=True,
        )
    except Exception as exc:
        db.rollback()
        failed = db.scalar(select(WorkspaceEnrichmentRun).where(WorkspaceEnrichmentRun.id == run_id))
        if failed is None:
            return None
        _merge_workspace_run_summary(db, run=failed, summary={"error": str(exc)})
        _set_workspace_run_state(
            db,
            run=failed,
            status="failed",
            stage="failed",
            completed=True,
            error_message=str(exc),
        )
        run = failed

    return _workspace_enrichment_run_read(run)


def generate_enrichment_suggestions(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None = None,
    collection_item_id: int | None = None,
    run_id: int | None = None,
    include_sources: bool = True,
) -> dict[str, object]:
    _clear_pending_suggestions(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
    )
    value_summary = generate_value_enrichment_suggestions(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
        run_id=run_id,
        include_sources=include_sources,
    )
    relation_summary = generate_relation_enrichment_suggestions(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
        run_id=run_id,
        include_sources=include_sources,
    )
    return {**value_summary, **relation_summary}


def generate_value_enrichment_suggestions(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None = None,
    collection_item_id: int | None = None,
    run_id: int | None = None,
    include_sources: bool = True,
) -> dict[str, object]:
    return _generate_value_suggestions(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
        run_id=run_id,
        include_sources=include_sources,
    )


def generate_relation_enrichment_suggestions(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None = None,
    collection_item_id: int | None = None,
    run_id: int | None = None,
    include_sources: bool = True,
) -> dict[str, object]:
    return _generate_relation_suggestions(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
        run_id=run_id,
        include_sources=include_sources,
    )


def _plan_collections(
    db: Session,
    *,
    pod_id: int,
    entities: list[Entity],
    facts: list[Fact],
) -> list[PlannedCollection]:
    llm_plan = _plan_collections_with_llm(entities=entities, facts=facts)
    if llm_plan:
        return llm_plan
    assigned_to_user_collection = {
        int(entity_id)
        for entity_id in db.scalars(
            select(CollectionItem.entity_id)
            .join(Collection, Collection.id == CollectionItem.collection_id)
            .where(Collection.pod_id == pod_id, Collection.is_auto_generated.is_(False))
        ).all()
    }
    facts_by_entity: dict[int, list[Fact]] = defaultdict(list)
    for fact in facts:
        facts_by_entity[int(fact.subject_entity_id)].append(fact)

    grouped: dict[str, list[Entity]] = defaultdict(list)
    for entity in entities:
        if entity.id in assigned_to_user_collection:
            continue
        category = _infer_entity_category(entity, facts_by_entity.get(int(entity.id), []))
        grouped[category].append(entity)

    planned: list[PlannedCollection] = []
    for category, rows in sorted(grouped.items(), key=lambda item: item[0]):
        if not rows:
            continue
        name = _display_collection_name(category, rows)
        slug = _slugify(name)
        default_columns = list(_DEFAULT_COLUMN_DEFS.get(category, _DEFAULT_COLUMN_DEFS["general"]))
        top_predicates = _top_predicates_for_entities(facts_by_entity, [entity.id for entity in rows], limit=6)
        extra_columns = [
            (_column_key(predicate), _display_label(predicate), "text")
            for predicate in top_predicates
            if _column_key(predicate) not in {column_key for column_key, _, _ in default_columns}
        ]
        planned.append(
            PlannedCollection(
                slug=slug,
                name=name,
                category=category,
                description=f"Auto-generated workspace table for {name.lower()} in this space.",
                entity_ids=sorted(int(entity.id) for entity in rows),
                columns=[*default_columns, *extra_columns],
            )
        )
    return planned


def _plan_collections_with_llm(
    *,
    entities: list[Entity],
    facts: list[Fact],
) -> list[PlannedCollection] | None:
    settings = get_settings()
    if not settings.openai_api_key or not entities:
        return None
    entity_by_name: dict[str, Entity] = {}
    for entity in entities:
        normalized = _normalize_token(entity.canonical_name)
        if normalized and normalized not in entity_by_name:
            entity_by_name[normalized] = entity

    facts_by_entity: dict[int, list[Fact]] = defaultdict(list)
    for fact in facts:
        facts_by_entity[int(fact.subject_entity_id)].append(fact)

    payload = {
        "entities": [
            {
                "name": entity.canonical_name,
                "type_label": entity.type_label,
                "facts": [
                    {"predicate": fact.predicate, "value": fact.object_value}
                    for fact in facts_by_entity.get(int(entity.id), [])[:8]
                ],
            }
            for entity in entities[:120]
        ]
    }
    request_payload = {
        "model": settings.openai_model,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "workspace_plan",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "collections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "description": {"type": ["string", "null"]},
                                    "entity_names": {"type": "array", "items": {"type": "string"}},
                                    "columns": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "label": {"type": "string"},
                                                "data_type": {"type": "string"},
                                            },
                                            "required": ["label", "data_type"],
                                        },
                                    },
                                },
                                "required": ["name", "description", "entity_names", "columns"],
                            },
                        }
                    },
                    "required": ["collections"],
                },
            },
        },
        "messages": [
            {
                "role": "system",
                "content": (
                    "Plan a Notion-like workspace from conversation-derived entities only. "
                    "Create semantically coherent tables, standardize columns per table, "
                    "and never introduce entities not already provided."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ],
    }
    req = urllib_request.Request(
        url=f"{settings.openai_base_url.rstrip('/')}/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=settings.openai_timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
        decoded = json.loads(raw)
        content = decoded["choices"][0]["message"]["content"]
        parsed = json.loads(content) if isinstance(content, str) else {}
    except (urllib_error.URLError, urllib_error.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None

    raw_collections = parsed.get("collections")
    if not isinstance(raw_collections, list):
        return None
    planned: list[PlannedCollection] = []
    seen_slugs: set[str] = set()
    for raw_collection in raw_collections:
        if not isinstance(raw_collection, dict):
            continue
        raw_name = str(raw_collection.get("name") or "").strip()
        if not raw_name:
            continue
        matched_entities: list[Entity] = []
        entity_ids: list[int] = []
        for entity_name in raw_collection.get("entity_names") or []:
            normalized = _normalize_token(str(entity_name or ""))
            entity = entity_by_name.get(normalized)
            if entity is not None:
                entity_ids.append(int(entity.id))
                matched_entities.append(entity)
        if not entity_ids:
            continue
        category = _normalize_llm_collection_category(raw_name, matched_entities)
        name = _display_collection_name(category, matched_entities)
        slug = _slugify(name)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        raw_columns = raw_collection.get("columns")
        columns: list[tuple[str, str, str]] = [("title", "Name", "title")]
        if isinstance(raw_columns, list):
            for raw_column in raw_columns:
                if not isinstance(raw_column, dict):
                    continue
                label = str(raw_column.get("label") or "").strip()
                if not label:
                    continue
                key = _column_key(label)
                if key == "title" or key in _GENERIC_PREDICATES or any(existing[0] == key for existing in columns):
                    continue
                data_type = str(raw_column.get("data_type") or "text").strip().lower()
                if data_type not in {"text", "url", "number", "boolean", "date"}:
                    data_type = "text"
                columns.append((key, label, data_type))
        planned.append(
            PlannedCollection(
                slug=slug,
                name=name,
                category=category,
                description=str(raw_collection.get("description") or "").strip()
                or f"Auto-generated workspace table for {name.lower()} in this space.",
                entity_ids=sorted(set(entity_ids)),
                columns=columns,
            )
        )
    return planned or None


def _normalize_llm_collection_category(name: str, entities: list[Entity]) -> str:
    normalized_name = _normalize_token(name)
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in normalized_name for keyword in keywords):
            return category
    if entities:
        return _infer_entity_category(entities[0], [])
    return _column_key(name) or "general"


def _infer_entity_category(entity: Entity, facts: list[Fact]) -> str:
    haystacks = [
        str(entity.type_label or ""),
        str(entity.type or ""),
        str(entity.canonical_name or ""),
        " ".join(str(fact.predicate) for fact in facts[:8]),
    ]
    normalized = " ".join(_normalize_token(haystack) for haystack in haystacks if haystack).lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return category
    type_label = _normalize_token(entity.type_label or entity.type or "")
    if type_label:
        return _pluralize_key(type_label)
    return "general"


def _display_collection_name(category: str, entities: list[Entity]) -> str:
    if category in {"accommodations", "food", "transportation", "activities", "general"}:
        return _display_label(category)
    labels = {str(entity.type_label or entity.type or "").strip() for entity in entities if (entity.type_label or entity.type)}
    if len(labels) == 1:
        return _display_label(_pluralize_key(next(iter(labels))))
    return _display_label(category)


def _upsert_planned_collections(
    db: Session,
    *,
    pod_id: int,
    planned: list[PlannedCollection],
) -> dict[str, Collection]:
    existing = {
        str(collection.slug): collection
        for collection in db.scalars(select(Collection).where(Collection.pod_id == pod_id)).all()
    }
    result: dict[str, Collection] = {}
    for index, spec in enumerate(planned, start=1):
        collection = existing.get(spec.slug)
        schema_stub = {
            "columns": [{"name": key, "label": label, "type": data_type} for key, label, data_type in spec.columns],
            "source": _MANAGED_COLLECTION_ORIGIN,
            "category": spec.category,
        }
        if collection is None:
            collection = Collection(
                pod_id=pod_id,
                parent_id=None,
                kind="TABLE",
                slug=spec.slug,
                name=spec.name,
                description=spec.description,
                schema_json=schema_stub,
                view_config_json={},
                sort_order=index * 10,
                is_auto_generated=True,
            )
            db.add(collection)
            db.flush()
        else:
            if collection.is_auto_generated:
                collection.name = spec.name
                collection.description = spec.description
                collection.sort_order = index * 10
                collection.schema_json = schema_stub
                db.add(collection)
        result[spec.slug] = collection
    return result


def _upsert_collection_columns(
    db: Session,
    *,
    planned: list[PlannedCollection],
    collections_by_slug: dict[str, Collection],
) -> dict[int, list[CollectionColumn]]:
    by_collection: dict[int, list[CollectionColumn]] = defaultdict(list)
    for spec in planned:
        collection = collections_by_slug[spec.slug]
        existing_rows = list(
            db.scalars(
                select(CollectionColumn)
                .where(CollectionColumn.collection_id == collection.id)
                .order_by(CollectionColumn.sort_order.asc(), CollectionColumn.id.asc())
            ).all()
        )
        existing_by_key = {row.key: row for row in existing_rows}
        for order_index, (key, label, data_type) in enumerate(spec.columns):
            row = existing_by_key.get(key)
            if row is None:
                row = CollectionColumn(
                    collection_id=collection.id,
                    key=key,
                    label=label,
                    data_type=data_type,
                    kind="title" if key == "title" else "property",
                    sort_order=order_index,
                    required=key == "title",
                    is_relation=False,
                    origin="planner",
                    planner_locked=key == "title",
                    user_locked=False,
                    enrichment_policy_json=_normalized_enrichment_policy(key=key, origin="planner"),
                )
                db.add(row)
                db.flush()
                existing_by_key[key] = row
            else:
                if not row.user_locked:
                    row.label = label
                    row.data_type = data_type
                    row.sort_order = order_index
                    row.required = key == "title"
                    row.kind = "title" if key == "title" else "property"
                    row.origin = row.origin or "planner"
                    row.planner_locked = key == "title"
                    db.add(row)
                normalized_policy = _normalized_enrichment_policy(
                    key=key,
                    origin=row.origin or "planner",
                    current=dict(row.enrichment_policy_json or {}),
                )
                if dict(row.enrichment_policy_json or {}) != normalized_policy:
                    row.enrichment_policy_json = normalized_policy
                    db.add(row)
            by_collection[int(collection.id)].append(row)

        for legacy_column in _coerce_dict_list(collection.schema_json.get("columns") if isinstance(collection.schema_json, dict) else None):
            key = _column_key(str(legacy_column.get("name") or legacy_column.get("label") or ""))
            if not key or key in existing_by_key:
                continue
            row = CollectionColumn(
                collection_id=collection.id,
                key=key,
                label=str(legacy_column.get("label") or legacy_column.get("name") or key),
                data_type=str(legacy_column.get("type") or "text"),
                kind="property",
                sort_order=len(by_collection[int(collection.id)]),
                required=False,
                is_relation=False,
                origin="legacy",
                planner_locked=False,
                user_locked=False,
                enrichment_policy_json=_normalized_enrichment_policy(key=key, origin="legacy"),
            )
            db.add(row)
            db.flush()
            existing_by_key[key] = row
            by_collection[int(collection.id)].append(row)
    return by_collection


def _upsert_collection_rows(
    db: Session,
    *,
    planned: list[PlannedCollection],
    collections_by_slug: dict[str, Collection],
    entities: list[Entity],
    facts: list[Fact],
) -> dict[tuple[int, int], CollectionItem]:
    entity_by_id = {int(entity.id): entity for entity in entities}
    facts_by_entity: dict[int, list[Fact]] = defaultdict(list)
    for fact in facts:
        facts_by_entity[int(fact.subject_entity_id)].append(fact)

    row_map: dict[tuple[int, int], CollectionItem] = {}
    for spec in planned:
        collection = collections_by_slug[spec.slug]
        existing_rows = {
            (int(row.collection_id), int(row.entity_id)): row
            for row in db.scalars(select(CollectionItem).where(CollectionItem.collection_id == collection.id)).all()
        }
        planned_keys = {(int(collection.id), entity_id) for entity_id in spec.entity_ids}
        for entity_id in spec.entity_ids:
            entity = entity_by_id.get(entity_id)
            if entity is None:
                continue
            row = existing_rows.get((int(collection.id), entity_id))
            summary = _build_row_summary(facts_by_entity.get(entity_id, []))
            detail_blurb = _build_detail_blurb(entity, facts_by_entity.get(entity_id, []))
            if row is None:
                row = CollectionItem(
                    collection_id=collection.id,
                    entity_id=entity_id,
                    primary_entity_id=entity_id,
                    title=entity.display_name or entity.canonical_name,
                    summary=summary,
                    detail_blurb=detail_blurb,
                    notes_markdown=None,
                    sort_key=None,
                    sort_order=len(row_map),
                )
                db.add(row)
                db.flush()
            else:
                row.primary_entity_id = row.primary_entity_id or entity_id
                row.title = row.title or entity.display_name or entity.canonical_name
                row.summary = row.summary or summary
                row.detail_blurb = row.detail_blurb or detail_blurb
                db.add(row)
            row_map[(int(collection.id), entity_id)] = row

        for stale_key, stale_row in existing_rows.items():
            if stale_key in planned_keys:
                continue
            has_manual_values = bool(
                db.scalar(
                    select(CollectionItemValue.id).where(
                        CollectionItemValue.collection_item_id == stale_row.id,
                        CollectionItemValue.edited_by_user.is_(True),
                    )
                )
            )
            if stale_row.notes_markdown or has_manual_values:
                row_map[stale_key] = stale_row
                continue
            db.delete(stale_row)
    return row_map


def _upsert_collection_values(
    db: Session,
    *,
    planned: list[PlannedCollection],
    collections_by_slug: dict[str, Collection],
    columns_by_collection: dict[int, list[CollectionColumn]],
    row_map: dict[tuple[int, int], CollectionItem],
    facts: list[Fact],
) -> int:
    entity_ids = sorted({entity_id for spec in planned for entity_id in spec.entity_ids})
    entity_by_id = {
        int(entity.id): entity
        for entity in db.scalars(select(Entity).where(Entity.id.in_(entity_ids if entity_ids else [-1]))).all()
    }
    latest_fact_by_entity_predicate: dict[tuple[int, str], Fact] = {}
    for fact in facts:
        key = (int(fact.subject_entity_id), _column_key(fact.predicate))
        if key not in latest_fact_by_entity_predicate:
            latest_fact_by_entity_predicate[key] = fact

    upserted = 0
    for spec in planned:
        collection = collections_by_slug[spec.slug]
        columns = columns_by_collection.get(int(collection.id), [])
        column_by_key = {column.key: column for column in columns}
        for entity_id in spec.entity_ids:
            row = row_map.get((int(collection.id), entity_id))
            entity = entity_by_id.get(entity_id)
            if row is None or entity is None:
                continue
            for key, _, _ in spec.columns:
                column = column_by_key.get(key)
                if column is None or key == "title":
                    continue
                current = db.scalar(
                    select(CollectionItemValue).where(
                        CollectionItemValue.collection_item_id == row.id,
                        CollectionItemValue.collection_column_id == column.id,
                    )
                )
                if current is not None and current.edited_by_user:
                    continue

                derived = _derived_workspace_value(entity=entity, row=row, key=key)
                if derived is not None:
                    display_value, value_json = derived
                    value_row = _upsert_collection_item_value(
                        db,
                        row=row,
                        column=column,
                        display_value=display_value,
                        value_json=value_json,
                        source_kind="workspace",
                        status="derived",
                        confidence=1.0,
                        edited_by_user=False,
                    )
                    db.execute(delete(Evidence).where(Evidence.collection_item_value_id == value_row.id))
                    upserted += 1
                    continue

                fact = latest_fact_by_entity_predicate.get((entity_id, key))
                if fact is not None:
                    value_row = _upsert_collection_item_value(
                        db,
                        row=row,
                        column=column,
                        display_value=fact.object_value,
                        value_json=fact.object_value,
                        source_kind="conversation",
                        status="confirmed",
                        confidence=fact.confidence,
                        edited_by_user=False,
                    )
                    _replace_cell_evidence_from_fact(db, value_row=value_row, fact=fact)
                    upserted += 1
                    continue

    return upserted


def _upsert_collection_relations(
    db: Session,
    *,
    row_map: dict[tuple[int, int], CollectionItem],
    relations: list[Relation],
) -> int:
    row_ids_by_entity: dict[int, list[CollectionItem]] = defaultdict(list)
    for (_, entity_id), row in row_map.items():
        row_ids_by_entity[entity_id].append(row)

    upserted = 0
    for relation in relations:
        from_rows = row_ids_by_entity.get(int(relation.from_entity_id), [])
        to_rows = row_ids_by_entity.get(int(relation.to_entity_id), [])
        for from_row in from_rows:
            for to_row in to_rows:
                if from_row.collection_id != to_row.collection_id:
                    continue
                row = db.scalar(
                    select(CollectionItemRelation).where(
                        CollectionItemRelation.from_collection_item_id == from_row.id,
                        CollectionItemRelation.to_collection_item_id == to_row.id,
                        CollectionItemRelation.relation_label == relation.relation_type,
                    )
                )
                if row is None:
                    row = CollectionItemRelation(
                        from_collection_item_id=from_row.id,
                        to_collection_item_id=to_row.id,
                        relation_label=relation.relation_type,
                        source_kind="conversation",
                        confidence=relation.confidence,
                        status="confirmed",
                    )
                    db.add(row)
                    db.flush()
                else:
                    row.source_kind = "conversation"
                    row.confidence = relation.confidence
                    row.status = "confirmed"
                    db.add(row)
                _replace_relation_evidence_from_relation(db, relation_row=row, relation=relation)
                upserted += 1
    return upserted


def _generate_value_suggestions(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
    run_id: int | None,
    include_sources: bool,
) -> dict[str, object]:
    research_client = get_default_research_client()
    if research_client is None:
        raise WorkspaceResearchError("OPENAI_API_KEY is not configured in backend/.env.")
    if not hasattr(research_client, "lookup_value_batch"):
        return _generate_value_suggestions_legacy(
            db,
            pod_id=pod_id,
            collection_id=collection_id,
            collection_item_id=collection_item_id,
            run_id=run_id,
            include_sources=include_sources,
        )

    rows = _target_collection_rows(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
    )
    row_ids = [int(row.id) for row in rows]
    if not row_ids:
        return {
            "value_batch_count": 0,
            "rows_considered": 0,
            "missing_cells_considered": 0,
            "value_suggestions_created": 0,
        }
    columns_by_collection: dict[int, list[CollectionColumn]] = defaultdict(list)
    for column in db.scalars(
        select(CollectionColumn)
        .join(Collection, Collection.id == CollectionColumn.collection_id)
        .where(Collection.pod_id == pod_id)
        .order_by(CollectionColumn.sort_order.asc(), CollectionColumn.id.asc())
    ).all():
        normalized_policy = _normalized_enrichment_policy(
            key=column.key,
            origin=column.origin,
            current=dict(column.enrichment_policy_json or {}),
        )
        if dict(column.enrichment_policy_json or {}) != normalized_policy:
            column.enrichment_policy_json = normalized_policy
            db.add(column)
        columns_by_collection[int(column.collection_id)].append(column)
    _hydrate_derived_workspace_values(
        db,
        rows=rows,
        columns_by_collection=columns_by_collection,
    )
    collections_by_id = {
        int(collection.id): collection
        for collection in db.scalars(select(Collection).where(Collection.pod_id == pod_id)).all()
    }
    existing_values = {
        (int(value.collection_item_id), int(value.collection_column_id)): value
        for value in db.scalars(
            select(CollectionItemValue).where(CollectionItemValue.collection_item_id.in_(row_ids))
        ).all()
    }
    target_columns_by_row: dict[int, list[CollectionColumn]] = {}
    row_payloads: list[dict[str, Any]] = []
    rows_considered = 0
    missing_cells_considered = 0

    for row in rows:
        collection = collections_by_id.get(int(row.collection_id))
        if collection is None:
            continue
        target_columns = [
            column
            for column in columns_by_collection.get(int(collection.id), [])
            if column.key != "title"
            and _column_enrichment_enabled(column)
            and not (
                existing_values.get((int(row.id), int(column.id))) is not None
                and str(existing_values[(int(row.id), int(column.id))].display_value or "").strip()
            )
        ]
        if not target_columns:
            continue
        target_columns_by_row[int(row.id)] = target_columns
        rows_considered += 1
        missing_cells_considered += len(target_columns)
        row_payloads.append(
            {
                "row_id": int(row.id),
                "title": row.title or f"Entity {row.entity_id}",
                "collection_id": int(collection.id),
                "collection_name": collection.name,
                "summary_info": _workspace_row_summary_info(
                    row=row,
                    existing_values=existing_values,
                    columns=columns_by_collection.get(int(collection.id), []),
                ),
                "current_values": _workspace_row_current_values(
                    row=row,
                    existing_values=existing_values,
                    columns=columns_by_collection.get(int(collection.id), []),
                ),
                "missing_columns": [
                    {
                        "column_id": int(column.id),
                        "column_key": column.key,
                        "label": column.label,
                        "data_type": column.data_type,
                    }
                    for column in target_columns
                ],
            }
        )
    if not row_payloads:
        return {
            "value_batch_count": 0,
            "rows_considered": 0,
            "missing_cells_considered": 0,
            "value_suggestions_created": 0,
        }

    valid_targets = {
        (row_id, column.key): column
        for row_id, columns in target_columns_by_row.items()
        for column in columns
    }
    created = 0
    value_batch_count = 0
    for batch in _chunk_value_enrichment_rows(row_payloads):
        value_batch_count += 1
        suggestions = research_client.lookup_value_batch(
            scope_label=_workspace_scope_label(
                pod_id=pod_id,
                collection_id=collection_id,
                collection_item_id=collection_item_id,
                collections_by_id=collections_by_id,
            ),
            rows=batch,
            include_sources=include_sources,
        )
        for researched in suggestions:
            row_id = int(researched.get("row_id") or 0)
            column_key = _column_key(str(researched.get("column_key") or ""))
            column = valid_targets.get((row_id, column_key))
            sources = _normalized_sources(researched.get("sources"))
            suggested_value = str(researched.get("value") or "").strip()
            if column is None or not suggested_value:
                continue
            source_ids = _create_external_sources(db, sources=sources)
            suggestion = _upsert_value_suggestion(
                db,
                run_id=run_id,
                row_id=row_id,
                column_id=int(column.id),
                suggested_display_value=suggested_value,
                suggested_value_json=suggested_value,
                value_type=column.data_type,
                source_kind="external",
                confidence=_safe_float(researched.get("confidence")),
                source_ids=source_ids,
                meta_json={
                    "column_label": column.label,
                    "collection_name": collections_by_id.get(int(column.collection_id)).name if collections_by_id.get(int(column.collection_id)) is not None else None,
                    "batch_enriched": True,
                },
            )
            if suggestion is not None:
                created += 1
    db.flush()
    return {
        "value_batch_count": value_batch_count,
        "rows_considered": rows_considered,
        "missing_cells_considered": missing_cells_considered,
        "value_suggestions_created": created,
    }


def _generate_value_suggestions_legacy(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
    run_id: int | None,
    include_sources: bool,
) -> dict[str, object]:
    research_client = get_default_research_client()
    if research_client is None:
        raise WorkspaceResearchError("OPENAI_API_KEY is not configured in backend/.env.")
    rows = _target_collection_rows(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
    )
    row_ids = [int(row.id) for row in rows]
    if not row_ids:
        return {
            "value_batch_count": 0,
            "rows_considered": 0,
            "missing_cells_considered": 0,
            "value_suggestions_created": 0,
        }
    columns_by_collection: dict[int, list[CollectionColumn]] = defaultdict(list)
    for column in db.scalars(
        select(CollectionColumn)
        .join(Collection, Collection.id == CollectionColumn.collection_id)
        .where(Collection.pod_id == pod_id)
        .order_by(CollectionColumn.sort_order.asc(), CollectionColumn.id.asc())
    ).all():
        normalized_policy = _normalized_enrichment_policy(
            key=column.key,
            origin=column.origin,
            current=dict(column.enrichment_policy_json or {}),
        )
        if dict(column.enrichment_policy_json or {}) != normalized_policy:
            column.enrichment_policy_json = normalized_policy
            db.add(column)
        columns_by_collection[int(column.collection_id)].append(column)
    _hydrate_derived_workspace_values(db, rows=rows, columns_by_collection=columns_by_collection)
    existing_values = {
        (int(value.collection_item_id), int(value.collection_column_id)): value
        for value in db.scalars(
            select(CollectionItemValue).where(CollectionItemValue.collection_item_id.in_(row_ids))
        ).all()
    }
    collections_by_id = {
        int(collection.id): collection
        for collection in db.scalars(select(Collection).where(Collection.pod_id == pod_id)).all()
    }
    created = 0
    rows_considered = 0
    missing_cells_considered = 0
    for row in rows:
        collection = collections_by_id.get(int(row.collection_id))
        if collection is None:
            continue
        target_columns = [
            column
            for column in columns_by_collection.get(int(collection.id), [])
            if column.key != "title"
            and _column_enrichment_enabled(column)
            and not (
                existing_values.get((int(row.id), int(column.id))) is not None
                and str(existing_values[(int(row.id), int(column.id))].display_value or "").strip()
            )
        ]
        if not target_columns:
            continue
        rows_considered += 1
        missing_cells_considered += len(target_columns)
        row_results: dict[str, dict[str, Any]] = {}
        if hasattr(research_client, "lookup_row"):
            try:
                row_results = research_client.lookup_row(
                    entity_name=row.title or f"Entity {row.entity_id}",
                    collection_name=collection.name,
                    column_labels=[column.label for column in target_columns],
                    include_sources=include_sources,
                )
            except WorkspaceResearchError:
                row_results = {}
        for column in target_columns:
            researched = row_results.get(column.label)
            if researched is None and hasattr(research_client, "lookup"):
                try:
                    researched = research_client.lookup(
                        entity_name=row.title or f"Entity {row.entity_id}",
                        collection_name=collection.name,
                        column_label=column.label,
                        include_sources=include_sources,
                    )
                except WorkspaceResearchError:
                    researched = None
            if not researched:
                continue
            suggested_value = str(researched.get("value") or "").strip()
            researched_sources = _normalized_sources(researched.get("sources"))
            if not suggested_value:
                continue
            source_ids = _create_external_sources(db, sources=researched_sources)
            suggestion = _upsert_value_suggestion(
                db,
                run_id=run_id,
                row_id=int(row.id),
                column_id=int(column.id),
                suggested_display_value=suggested_value,
                suggested_value_json=suggested_value,
                value_type=column.data_type,
                source_kind="external",
                confidence=_safe_float(researched.get("confidence")),
                source_ids=source_ids,
                meta_json={"column_label": column.label, "collection_name": collection.name},
            )
            if suggestion is not None:
                created += 1
    db.flush()
    return {
        "value_batch_count": rows_considered,
        "rows_considered": rows_considered,
        "missing_cells_considered": missing_cells_considered,
        "value_suggestions_created": created,
    }


def _hydrate_derived_workspace_values(
    db: Session,
    *,
    rows: list[CollectionItem],
    columns_by_collection: dict[int, list[CollectionColumn]],
) -> None:
    if not rows:
        return
    entity_ids = sorted({int(row.entity_id) for row in rows})
    entities_by_id = {
        int(entity.id): entity
        for entity in db.scalars(select(Entity).where(Entity.id.in_(entity_ids))).all()
    }
    for row in rows:
        entity = entities_by_id.get(int(row.entity_id))
        if entity is None:
            continue
        for column in columns_by_collection.get(int(row.collection_id), []):
            if not _is_self_evident_column(column.key, origin=column.origin) or column.key == "title":
                continue
            current = db.scalar(
                select(CollectionItemValue).where(
                    CollectionItemValue.collection_item_id == row.id,
                    CollectionItemValue.collection_column_id == column.id,
                )
            )
            if current is not None and current.edited_by_user:
                continue
            derived = _derived_workspace_value(entity=entity, row=row, key=column.key)
            if derived is None:
                continue
            display_value, value_json = derived
            value_row = _upsert_collection_item_value(
                db,
                row=row,
                column=column,
                display_value=display_value,
                value_json=value_json,
                source_kind="workspace",
                status="derived",
                confidence=1.0,
                edited_by_user=False,
            )
            db.execute(delete(Evidence).where(Evidence.collection_item_value_id == value_row.id))


def _workspace_row_current_values(
    *,
    row: CollectionItem,
    existing_values: dict[tuple[int, int], CollectionItemValue],
    columns: list[CollectionColumn],
) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    for column in columns:
        value = existing_values.get((int(row.id), int(column.id)))
        display_value = str(value.display_value or "").strip() if value is not None else ""
        if not display_value:
            continue
        values.append({"column_key": column.key, "label": column.label, "value": display_value})
    return values


def _workspace_row_summary_info(
    *,
    row: CollectionItem,
    existing_values: dict[tuple[int, int], CollectionItemValue],
    columns: list[CollectionColumn],
) -> str:
    parts: list[str] = []
    if row.summary:
        parts.append(f"summary: {row.summary}")
    if row.detail_blurb:
        parts.append(f"detail: {row.detail_blurb}")
    for item in _workspace_row_current_values(row=row, existing_values=existing_values, columns=columns)[:8]:
        parts.append(f"{item['label']}: {item['value']}")
    return " | ".join(parts[:10])


def _chunk_value_enrichment_rows(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_missing_cells = 0
    for row in rows:
        row_missing_cells = len(list(row.get("missing_columns") or []))
        if current and (
            len(current) >= _MAX_BATCH_ROWS or current_missing_cells + row_missing_cells > _MAX_BATCH_MISSING_CELLS
        ):
            batches.append(current)
            current = []
            current_missing_cells = 0
        current.append(row)
        current_missing_cells += row_missing_cells
    if current:
        batches.append(current)
    return batches


def _workspace_scope_label(
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
    collections_by_id: dict[int, Collection],
) -> str:
    if collection_item_id is not None:
        return f"pod-{pod_id}:row-{collection_item_id}"
    if collection_id is not None:
        collection = collections_by_id.get(collection_id)
        return f"pod-{pod_id}:collection-{collection.name if collection is not None else collection_id}"
    return f"pod-{pod_id}:space"


def _relation_row_payload(row: CollectionItem) -> dict[str, Any]:
    return {
        "row_id": int(row.id),
        "entity_id": int(row.entity_id),
        "title": row.title or f"Entity {row.entity_id}",
        "collection_id": int(row.collection_id),
        "summary": row.summary,
        "detail_blurb": row.detail_blurb,
    }


def _chunk_relation_candidates(candidates: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for candidate in candidates:
        if current and len(current) >= _MAX_BATCH_RELATION_CANDIDATES:
            batches.append(current)
            current = []
        current.append(candidate)
    if current:
        batches.append(current)
    return batches


def _relation_enrichment_candidates(
    db: Session,
    *,
    rows: list[CollectionItem],
    pod_id: int,
) -> list[dict[str, Any]]:
    row_by_id = {int(row.id): row for row in rows}
    rows_by_entity_id: dict[int, list[CollectionItem]] = defaultdict(list)
    for row in rows:
        rows_by_entity_id[int(row.entity_id)].append(row)

    existing_relation_pairs = {
        (
            int(relation.from_collection_item_id),
            int(relation.to_collection_item_id),
            str(relation.relation_label).strip().lower(),
        )
        for relation in db.scalars(select(CollectionItemRelation)).all()
    }
    candidates_by_key: dict[tuple[int, int, str], dict[str, Any]] = {}

    def add_candidate(
        *,
        from_row: CollectionItem,
        to_row: CollectionItem,
        hint_label: str | None,
        reason: str,
        extra: dict[str, object] | None = None,
    ) -> None:
        if int(from_row.id) == int(to_row.id):
            return
        normalized_hint = _column_key(hint_label or "") or "candidate"
        key = (int(from_row.id), int(to_row.id), normalized_hint)
        if key in existing_relation_pairs:
            return
        candidate = candidates_by_key.get(key)
        if candidate is None:
            candidate = {
                "candidate_id": f"{from_row.id}:{to_row.id}:{normalized_hint}",
                "from_row_id": int(from_row.id),
                "to_row_id": int(to_row.id),
                "from_title": from_row.title or f"Entity {from_row.entity_id}",
                "to_title": to_row.title or f"Entity {to_row.entity_id}",
                "from_collection_id": int(from_row.collection_id),
                "to_collection_id": int(to_row.collection_id),
                "hint_relation_label": normalized_hint,
                "reasons": [],
                "meta": {},
            }
            candidates_by_key[key] = candidate
        if reason not in candidate["reasons"]:
            candidate["reasons"].append(reason)
        if extra:
            candidate["meta"].update(extra)

    pod_relations = list(
        db.scalars(
            select(Relation).where(Relation.pod_id == pod_id).order_by(Relation.created_at.desc(), Relation.id.desc())
        ).all()
    )
    for relation in pod_relations:
        for from_row in rows_by_entity_id.get(int(relation.from_entity_id), []):
            for to_row in rows_by_entity_id.get(int(relation.to_entity_id), []):
                add_candidate(
                    from_row=from_row,
                    to_row=to_row,
                    hint_label=relation.relation_type,
                    reason="accepted_extracted_relation",
                    extra={"extracted_relation_id": int(relation.id)},
                )

    inferred_columns = {
        int(column.id): column
        for column in db.scalars(
            select(CollectionColumn)
            .join(Collection, Collection.id == CollectionColumn.collection_id)
            .where(Collection.pod_id == pod_id, CollectionColumn.key.in_(sorted(_INFERRED_RELATION_COLUMNS)))
        ).all()
    }
    grouped_values: dict[tuple[str, str], list[tuple[CollectionItemValue, CollectionItem]]] = defaultdict(list)
    for value in db.scalars(
        select(CollectionItemValue).where(CollectionItemValue.collection_item_id.in_(sorted(row_by_id.keys())))
    ).all():
        column = inferred_columns.get(int(value.collection_column_id))
        row = row_by_id.get(int(value.collection_item_id))
        normalized = _normalize_token(str(value.display_value or ""))
        if column is None or row is None or not normalized:
            continue
        grouped_values[(column.key, normalized)].append((value, row))
    for (column_key, normalized_value), matches in grouped_values.items():
        if len(matches) < 2:
            continue
        for idx, (_, left_row) in enumerate(matches):
            for _, right_row in matches[idx + 1 :]:
                add_candidate(
                    from_row=left_row,
                    to_row=right_row,
                    hint_label=f"same_{column_key}",
                    reason="shared_value_overlap",
                    extra={"shared_value": normalized_value, "column_key": column_key},
                )

    ordered_rows = sorted(rows, key=lambda item: (item.collection_id, item.sort_order, item.id))
    for idx, left_row in enumerate(ordered_rows):
        for right_row in ordered_rows[idx + 1 :]:
            if token_set_similarity(left_row.title or "", right_row.title or "") < 0.55:
                continue
            add_candidate(
                from_row=left_row,
                to_row=right_row,
                hint_label="related_to",
                reason="title_token_overlap",
            )

    return list(candidates_by_key.values())


def _generate_relation_suggestions(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
    run_id: int | None,
    include_sources: bool,
) -> dict[str, object]:
    research_client = get_default_research_client()
    if research_client is None:
        raise WorkspaceResearchError("OPENAI_API_KEY is not configured in backend/.env.")
    if not hasattr(research_client, "lookup_relation_batch"):
        return _generate_relation_suggestions_legacy(
            db,
            pod_id=pod_id,
            collection_id=collection_id,
            collection_item_id=collection_item_id,
            run_id=run_id,
            include_sources=include_sources,
        )
    rows = _target_collection_rows(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
    )
    if len(rows) < 2:
        return {
            "relation_batch_count": 0,
            "candidate_relations_considered": 0,
            "relation_suggestions_created": 0,
        }
    row_by_id = {int(row.id): row for row in rows}
    candidate_pairs = _relation_enrichment_candidates(
        db,
        rows=rows,
        pod_id=pod_id,
    )
    if collection_item_id is not None:
        candidate_pairs = [
            candidate
            for candidate in candidate_pairs
            if int(candidate["from_row_id"]) == collection_item_id or int(candidate["to_row_id"]) == collection_item_id
        ]
    if collection_id is not None:
        candidate_pairs = [
            candidate
            for candidate in candidate_pairs
            if int(candidate["from_collection_id"]) == collection_id or int(candidate["to_collection_id"]) == collection_id
        ]
    if not candidate_pairs:
        return {
            "relation_batch_count": 0,
            "candidate_relations_considered": 0,
            "relation_suggestions_created": 0,
        }
    created = 0
    relation_batch_count = 0
    for batch in _chunk_relation_candidates(candidate_pairs):
        relation_batch_count += 1
        relation_rows = [_relation_row_payload(row) for row in rows]
        results = research_client.lookup_relation_batch(
            scope_label=_workspace_scope_label(
                pod_id=pod_id,
                collection_id=collection_id,
                collection_item_id=collection_item_id,
                collections_by_id={
                    int(collection.id): collection
                    for collection in db.scalars(select(Collection).where(Collection.pod_id == pod_id)).all()
                },
            ),
            rows=relation_rows,
            candidates=batch,
            include_sources=include_sources,
        )
        batch_candidate_by_id = {str(candidate["candidate_id"]): candidate for candidate in batch}
        for researched in results:
            candidate = batch_candidate_by_id.get(str(researched.get("candidate_id") or ""))
            relation_label = _column_key(str(researched.get("relation_label") or ""))
            sources = _normalized_sources(researched.get("sources"))
            if candidate is None or not relation_label:
                continue
            from_row = row_by_id.get(int(candidate["from_row_id"]))
            to_row = row_by_id.get(int(candidate["to_row_id"]))
            if from_row is None or to_row is None:
                continue
            source_ids = _create_external_sources(db, sources=sources)
            suggestion = _upsert_relation_suggestion(
                db,
                run_id=run_id,
                from_row_id=int(from_row.id),
                to_row_id=int(to_row.id),
                relation_label=relation_label,
                source_kind="external",
                confidence=_safe_float(researched.get("confidence")),
                source_ids=source_ids,
                meta_json={
                    "candidate_id": candidate["candidate_id"],
                    "reasons": candidate.get("reasons", []),
                    "batch_enriched": True,
                },
            )
            if suggestion is not None:
                created += 1
    db.flush()
    return {
        "relation_batch_count": relation_batch_count,
        "candidate_relations_considered": len(candidate_pairs),
        "relation_suggestions_created": created,
    }


def _generate_relation_suggestions_legacy(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
    run_id: int | None,
    include_sources: bool,
) -> dict[str, object]:
    created = 0
    created += _generate_relation_suggestions_from_values(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
        run_id=run_id,
    )
    created += _generate_relation_suggestions_with_research(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
        run_id=run_id,
    )
    db.flush()
    return {
        "relation_batch_count": 1 if created else 0,
        "candidate_relations_considered": 0,
        "relation_suggestions_created": created,
    }


def _generate_relation_suggestions_from_values(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
    run_id: int | None,
) -> int:
    rows = _target_collection_rows(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
    )
    row_ids = [row.id for row in rows]
    if len(row_ids) < 2:
        return 0
    row_by_id = {int(row.id): row for row in rows}
    columns = {
        int(column.id): column
        for column in db.scalars(
            select(CollectionColumn).where(CollectionColumn.key.in_(sorted(_INFERRED_RELATION_COLUMNS)))
        ).all()
    }
    values = list(
        db.scalars(
            select(CollectionItemValue).where(
                CollectionItemValue.collection_item_id.in_(row_ids),
                CollectionItemValue.display_value.is_not(None),
            )
        ).all()
    )
    grouped: dict[tuple[int, str, str], list[CollectionItemValue]] = defaultdict(list)
    for value in values:
        row = row_by_id.get(int(value.collection_item_id))
        column = columns.get(int(value.collection_column_id))
        if row is None or column is None or not value.display_value:
            continue
        normalized = _normalize_token(value.display_value)
        if not normalized:
            continue
        grouped[(int(row.collection_id), column.key, normalized)].append(value)

    created = 0
    for (target_collection_id, key, normalized), matches in grouped.items():
        if collection_id is not None and target_collection_id != collection_id:
            continue
        if len(matches) < 2:
            continue
        for idx, left_value in enumerate(matches):
            left_row = row_by_id.get(int(left_value.collection_item_id))
            if left_row is None:
                continue
            for right_value in matches[idx + 1 :]:
                right_row = row_by_id.get(int(right_value.collection_item_id))
                if right_row is None:
                    continue
                suggestion = _upsert_relation_suggestion(
                    db,
                    run_id=run_id,
                    from_row_id=int(left_row.id),
                    to_row_id=int(right_row.id),
                    relation_label=f"same_{key}",
                    source_kind="inferred",
                    confidence=_min_confidence([left_value.confidence, right_value.confidence]),
                    source_ids=_source_ids_for_value_records(db, [int(left_value.id), int(right_value.id)]),
                    meta_json={"shared_value": normalized, "column_key": key},
                )
                if suggestion is not None:
                    created += 1
    return created


def _generate_relation_suggestions_with_research(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
    run_id: int | None,
) -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        raise WorkspaceResearchError("OPENAI_API_KEY is not configured in backend/.env.")
    rows = _target_collection_rows(
        db,
        pod_id=pod_id,
        collection_id=collection_id,
        collection_item_id=collection_item_id,
    )
    if len(rows) < 2:
        return 0
    research_client = get_default_research_client()
    if research_client is None:
        raise WorkspaceResearchError("OPENAI_API_KEY is not configured in backend/.env.")
    existing_relation_pairs = {
        (
            int(relation.from_collection_item_id),
            int(relation.to_collection_item_id),
            str(relation.relation_label).strip().lower(),
        )
        for relation in db.scalars(select(CollectionItemRelation)).all()
    }
    pairs_to_check: list[tuple[CollectionItem, CollectionItem]] = []
    for idx, left in enumerate(rows):
        for right in rows[idx + 1 :]:
            if left.collection_id != right.collection_id:
                continue
            if any(pair[0] == left.id and pair[1] == right.id for pair in pairs_to_check):
                continue
            pairs_to_check.append((left, right))
    pairs_to_check = pairs_to_check[:_MAX_RELATION_SUGGESTION_PAIRS]

    batched_relations: list[dict[str, Any]] = []
    entity_name_by_normalized: dict[str, CollectionItem] = {}
    for row in rows:
        entity_name_by_normalized[_normalize_token(row.title or f"Entity {row.entity_id}")] = row
    if hasattr(research_client, "lookup_relations"):
        try:
            batched_relations = research_client.lookup_relations(
                collection_name=db.scalar(select(Collection.name).where(Collection.id == rows[0].collection_id)) or "Collection",
                entity_names=[row.title or f"Entity {row.entity_id}" for row in rows[: min(len(rows), 20)]],
            )
        except WorkspaceResearchError:
            batched_relations = []

    created = 0
    consumed_pairs: set[tuple[int, int, str]] = set()
    for researched in batched_relations:
        left = entity_name_by_normalized.get(_normalize_token(str(researched.get("from_name") or "")))
        right = entity_name_by_normalized.get(_normalize_token(str(researched.get("to_name") or "")))
        relation_label = str(researched.get("relation_label") or "").strip()
        sources = researched.get("sources")
        if left is None or right is None or not relation_label or not isinstance(sources, list) or not sources:
            continue
        relation_key = (int(left.id), int(right.id), relation_label.lower())
        consumed_pairs.add(relation_key)
        if relation_key in existing_relation_pairs:
            continue
        source_ids = _create_external_sources(db, sources=sources)
        suggestion = _upsert_relation_suggestion(
            db,
            run_id=run_id,
            from_row_id=int(left.id),
            to_row_id=int(right.id),
            relation_label=relation_label,
            source_kind="external",
            confidence=_safe_float(researched.get("confidence")),
            source_ids=source_ids,
            meta_json={"left_name": left.title, "right_name": right.title},
        )
        if suggestion is not None:
            created += 1

    for left, right in pairs_to_check:
        pair_prefix = (int(left.id), int(right.id))
        if any(key[0] == pair_prefix[0] and key[1] == pair_prefix[1] for key in consumed_pairs):
            continue
        researched = _research_relation_between_entities(
            left_name=left.title or f"Entity {left.entity_id}",
            right_name=right.title or f"Entity {right.entity_id}",
        )
        if not researched:
            continue
        relation_label = str(researched.get("relation_label") or "").strip()
        sources = researched.get("sources")
        if not relation_label or not isinstance(sources, list) or not sources:
            continue
        if (
            int(left.id),
            int(right.id),
            relation_label.lower(),
        ) in existing_relation_pairs:
            continue
        source_ids = _create_external_sources(db, sources=sources)
        suggestion = _upsert_relation_suggestion(
            db,
            run_id=run_id,
            from_row_id=int(left.id),
            to_row_id=int(right.id),
            relation_label=relation_label,
            source_kind="external",
            confidence=_safe_float(researched.get("confidence")),
            source_ids=source_ids,
            meta_json={"left_name": left.title, "right_name": right.title},
        )
        if suggestion is not None:
            created += 1
    return created


def _upsert_inferred_relations_from_values(db: Session) -> int:
    columns = {
        int(column.id): column
        for column in db.scalars(select(CollectionColumn).where(CollectionColumn.key.in_(sorted(_INFERRED_RELATION_COLUMNS)))).all()
    }
    if not columns:
        return 0
    values_by_collection_and_key: dict[tuple[int, str], list[tuple[CollectionItemValue, CollectionItem, str]]] = defaultdict(list)
    rows_by_id = {
        int(row.id): row
        for row in db.scalars(select(CollectionItem)).all()
    }
    for value in db.scalars(
        select(CollectionItemValue).where(CollectionItemValue.display_value.is_not(None))
    ).all():
        column = columns.get(int(value.collection_column_id))
        row = rows_by_id.get(int(value.collection_item_id))
        if column is None or row is None or not value.display_value:
            continue
        normalized = _normalize_token(value.display_value)
        if not normalized:
            continue
        values_by_collection_and_key[(int(row.collection_id), column.key)].append((value, row, normalized))

    created = 0
    for (collection_id, key), entries in values_by_collection_and_key.items():
        if len(entries) < 2:
            continue
        grouped: dict[str, list[tuple[CollectionItemValue, CollectionItem]]] = defaultdict(list)
        for value, row, normalized in entries:
            grouped[normalized].append((value, row))
        for normalized, matches in grouped.items():
            if len(matches) < 2:
                continue
            relation_label = f"same_{key}"
            for idx, (left_value, left_row) in enumerate(matches):
                for right_value, right_row in matches[idx + 1 :]:
                    relation = db.scalar(
                        select(CollectionItemRelation).where(
                            CollectionItemRelation.from_collection_item_id == left_row.id,
                            CollectionItemRelation.to_collection_item_id == right_row.id,
                            CollectionItemRelation.relation_label == relation_label,
                        )
                    )
                    if relation is None:
                        relation = CollectionItemRelation(
                            from_collection_item_id=left_row.id,
                            to_collection_item_id=right_row.id,
                            relation_label=relation_label,
                            source_kind="external" if any(
                                value.source_kind == "external" for value in (left_value, right_value)
                            ) else "inferred",
                            confidence=min(
                                score for score in [left_value.confidence, right_value.confidence] if score is not None
                            )
                            if any(score is not None for score in [left_value.confidence, right_value.confidence])
                            else None,
                            status="inferred",
                        )
                        db.add(relation)
                        db.flush()
                        created += 1
                    _replace_relation_evidence_from_value_sources(
                        db,
                        relation_row=relation,
                        value_ids=[left_value.id, right_value.id],
                        normalized_value=normalized,
                    )
    return created


def _sync_collection_schema_json(
    *,
    collections_by_slug: dict[str, Collection],
    columns_by_collection: dict[int, list[CollectionColumn]],
) -> None:
    for collection in collections_by_slug.values():
        columns = columns_by_collection.get(int(collection.id), [])
        collection.schema_json = {
            "columns": [
                {
                    "name": column.key,
                    "label": column.label,
                    "type": column.data_type,
                    "origin": column.origin,
                }
                for column in sorted(columns, key=lambda item: (item.sort_order, item.id))
            ],
            "source": _MANAGED_COLLECTION_ORIGIN,
        }


def _rebuild_property_catalog_from_columns(db: Session) -> None:
    db.execute(delete(PropertyCatalog))
    coverage_counts = {
        int(column_id): int(count)
        for column_id, count in db.execute(
            select(CollectionItemValue.collection_column_id, func.count(CollectionItemValue.id))
            .group_by(CollectionItemValue.collection_column_id)
        ).all()
    }
    for column in db.scalars(select(CollectionColumn).order_by(CollectionColumn.updated_at.desc())).all():
        mention_count = coverage_counts.get(int(column.id), 0)
        status = "stable" if mention_count >= 3 or column.user_locked else "emerging"
        db.add(
            PropertyCatalog(
                property_key=f"collection_column:{column.id}",
                display_label=column.label,
                kind="relation" if column.is_relation else "field",
                status=status,
                mention_count=mention_count,
                last_seen_at=column.updated_at,
            )
        )
    db.flush()


def _upsert_collection_item_value(
    db: Session,
    *,
    row: CollectionItem,
    column: CollectionColumn,
    display_value: str,
    value_json: Any,
    source_kind: str,
    status: str,
    confidence: float | None,
    edited_by_user: bool,
    last_verified_at: datetime | None = None,
) -> CollectionItemValue:
    value_row = db.scalar(
        select(CollectionItemValue).where(
            CollectionItemValue.collection_item_id == row.id,
            CollectionItemValue.collection_column_id == column.id,
        )
    )
    if value_row is None:
        value_row = CollectionItemValue(
            collection_item_id=row.id,
            collection_column_id=column.id,
        )
    value_row.display_value = display_value
    value_row.value_json = value_json
    value_row.value_type = column.data_type
    value_row.source_kind = source_kind
    value_row.status = status
    value_row.confidence = confidence
    value_row.edited_by_user = edited_by_user
    value_row.last_verified_at = last_verified_at
    db.add(value_row)
    db.flush()
    return value_row


def _replace_cell_evidence_from_fact(
    db: Session,
    *,
    value_row: CollectionItemValue,
    fact: Fact,
) -> None:
    db.execute(delete(Evidence).where(Evidence.collection_item_value_id == value_row.id))
    for message_id in fact.source_message_ids_json or []:
        source = _ensure_message_source(db, message_id=message_id)
        if source is None:
            continue
        db.add(
            Evidence(
                source_id=source.id,
                fact_id=None,
                relation_id=None,
                collection_item_value_id=value_row.id,
                collection_item_relation_id=None,
                message_id=message_id,
                snippet=_message_snippet(db, message_id=message_id),
                confidence=fact.confidence,
                meta_json={"origin": "workspace_conversation_value", "predicate": fact.predicate},
            )
        )
    db.flush()


def _replace_cell_evidence_from_sources(
    db: Session,
    *,
    value_row: CollectionItemValue,
    sources: list[dict[str, Any]],
) -> None:
    db.execute(delete(Evidence).where(Evidence.collection_item_value_id == value_row.id))
    for raw_source in sources:
        uri = str(raw_source.get("uri") or "").strip()
        if not uri:
            continue
        source = Source(
            conversation_id=None,
            source_kind="external_web",
            message_id=None,
            title=str(raw_source.get("title") or "").strip() or None,
            uri=uri,
            payload_json={"snippet": raw_source.get("snippet")},
        )
        db.add(source)
        db.flush()
        db.add(
            Evidence(
                source_id=source.id,
                fact_id=None,
                relation_id=None,
                collection_item_value_id=value_row.id,
                collection_item_relation_id=None,
                message_id=None,
                snippet=_truncate_snippet(str(raw_source.get("snippet") or "").strip() or None),
                confidence=value_row.confidence,
                meta_json={"origin": "workspace_external_value"},
            )
        )
    db.flush()


def _replace_relation_evidence_from_relation(
    db: Session,
    *,
    relation_row: CollectionItemRelation,
    relation: Relation,
) -> None:
    db.execute(delete(Evidence).where(Evidence.collection_item_relation_id == relation_row.id))
    for message_id in relation.source_message_ids_json or []:
        source = _ensure_message_source(db, message_id=message_id)
        if source is None:
            continue
        db.add(
            Evidence(
                source_id=source.id,
                fact_id=None,
                relation_id=None,
                collection_item_value_id=None,
                collection_item_relation_id=relation_row.id,
                message_id=message_id,
                snippet=_message_snippet(db, message_id=message_id),
                confidence=relation.confidence,
                meta_json={"origin": "workspace_conversation_relation", "relation_type": relation.relation_type},
            )
        )
    db.flush()


def _replace_relation_evidence_from_value_sources(
    db: Session,
    *,
    relation_row: CollectionItemRelation,
    value_ids: list[int],
    normalized_value: str,
) -> None:
    db.execute(delete(Evidence).where(Evidence.collection_item_relation_id == relation_row.id))
    if not value_ids:
        db.flush()
        return
    for evidence, source in db.execute(
        select(Evidence, Source)
        .join(Source, Source.id == Evidence.source_id)
        .where(Evidence.collection_item_value_id.in_(value_ids))
        .order_by(Evidence.id.asc())
    ).all():
        db.add(
            Evidence(
                source_id=source.id,
                fact_id=None,
                relation_id=None,
                collection_item_value_id=None,
                collection_item_relation_id=relation_row.id,
                message_id=evidence.message_id,
                snippet=evidence.snippet,
                confidence=evidence.confidence,
                meta_json={"origin": "workspace_inferred_relation", "shared_value": normalized_value},
            )
        )
    db.flush()


def _target_collection_rows(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
) -> list[CollectionItem]:
    stmt = select(CollectionItem).join(Collection, Collection.id == CollectionItem.collection_id).where(Collection.pod_id == pod_id)
    if collection_id is not None:
        stmt = stmt.where(CollectionItem.collection_id == collection_id)
    if collection_item_id is not None:
        stmt = stmt.where(CollectionItem.id == collection_item_id)
    return list(db.scalars(stmt.order_by(CollectionItem.sort_order.asc(), CollectionItem.id.asc())).all())


def _clear_pending_suggestions(
    db: Session,
    *,
    pod_id: int,
    collection_id: int | None,
    collection_item_id: int | None,
) -> None:
    row_ids = [row.id for row in _target_collection_rows(db, pod_id=pod_id, collection_id=collection_id, collection_item_id=collection_item_id)]
    if row_ids:
        db.execute(
            delete(CollectionItemValueSuggestion).where(
                CollectionItemValueSuggestion.collection_item_id.in_(row_ids),
                CollectionItemValueSuggestion.status == "pending",
            )
        )
        db.execute(
            delete(CollectionItemRelationSuggestion).where(
                CollectionItemRelationSuggestion.status == "pending",
                or_(
                    CollectionItemRelationSuggestion.from_collection_item_id.in_(row_ids),
                    CollectionItemRelationSuggestion.to_collection_item_id.in_(row_ids),
                ),
            )
        )
    db.flush()


def _create_external_sources(db: Session, *, sources: list[dict[str, Any]]) -> list[int]:
    created_ids: list[int] = []
    for raw_source in sources:
        uri = str(raw_source.get("uri") or "").strip()
        if not uri:
            continue
        row = Source(
            conversation_id=None,
            source_kind="external_web",
            message_id=None,
            title=str(raw_source.get("title") or "").strip() or None,
            uri=uri,
            payload_json={"snippet": raw_source.get("snippet")},
        )
        db.add(row)
        db.flush()
        created_ids.append(int(row.id))
    return created_ids


def _upsert_value_suggestion(
    db: Session,
    *,
    run_id: int | None,
    row_id: int,
    column_id: int,
    suggested_display_value: str,
    suggested_value_json: Any,
    value_type: str,
    source_kind: str,
    confidence: float | None,
    source_ids: list[int],
    meta_json: dict[str, object],
) -> CollectionItemValueSuggestion | None:
    dedupe_key = _dedupe_key(f"{row_id}:{column_id}:{suggested_display_value}")
    existing = db.scalar(
        select(CollectionItemValueSuggestion).where(
            CollectionItemValueSuggestion.collection_item_id == row_id,
            CollectionItemValueSuggestion.collection_column_id == column_id,
            CollectionItemValueSuggestion.dedupe_key == dedupe_key,
        )
    )
    if existing is not None and existing.status == "rejected":
        return None
    if existing is None:
        existing = CollectionItemValueSuggestion(
            enrichment_run_id=run_id,
            collection_item_id=row_id,
            collection_column_id=column_id,
            dedupe_key=dedupe_key,
        )
    existing.enrichment_run_id = run_id
    existing.suggested_display_value = suggested_display_value
    existing.suggested_value_json = suggested_value_json
    existing.value_type = value_type
    existing.source_kind = source_kind
    existing.confidence = confidence
    existing.status = "pending"
    existing.source_ids_json = source_ids
    existing.meta_json = meta_json
    db.add(existing)
    db.flush()
    return existing


def _upsert_relation_suggestion(
    db: Session,
    *,
    run_id: int | None,
    from_row_id: int,
    to_row_id: int,
    relation_label: str,
    source_kind: str,
    confidence: float | None,
    source_ids: list[int],
    meta_json: dict[str, object],
) -> CollectionItemRelationSuggestion | None:
    dedupe_key = _dedupe_key(f"{from_row_id}:{to_row_id}:{relation_label}:{json.dumps(meta_json, sort_keys=True, default=str)}")
    existing = db.scalar(
        select(CollectionItemRelationSuggestion).where(
            CollectionItemRelationSuggestion.from_collection_item_id == from_row_id,
            CollectionItemRelationSuggestion.to_collection_item_id == to_row_id,
            CollectionItemRelationSuggestion.relation_label == relation_label,
            CollectionItemRelationSuggestion.dedupe_key == dedupe_key,
        )
    )
    if existing is not None and existing.status == "rejected":
        return None
    if existing is None:
        existing = CollectionItemRelationSuggestion(
            enrichment_run_id=run_id,
            from_collection_item_id=from_row_id,
            to_collection_item_id=to_row_id,
            relation_label=relation_label,
            dedupe_key=dedupe_key,
        )
    existing.enrichment_run_id = run_id
    existing.source_kind = source_kind
    existing.confidence = confidence
    existing.status = "pending"
    existing.source_ids_json = source_ids
    existing.meta_json = meta_json
    db.add(existing)
    db.flush()
    return existing


def _source_ids_for_value_records(db: Session, value_ids: list[int]) -> list[int]:
    if not value_ids:
        return []
    ids = [
        int(source_id)
        for source_id in db.scalars(
            select(Evidence.source_id).where(Evidence.collection_item_value_id.in_(value_ids))
        ).all()
        if source_id is not None
    ]
    seen: set[int] = set()
    ordered: list[int] = []
    for value in ids:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _research_relation_between_entities(*, left_name: str, right_name: str) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise WorkspaceResearchError("OPENAI_API_KEY is not configured in backend/.env.")
    payload = {
        "model": settings.openai_model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Use the web to determine whether a concise factual relationship exists between the two named entities. "
                            "Return strict JSON with keys relation_label, confidence, sources. "
                            "If no reliable relation exists, return relation_label as null and sources as []."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps({"left_name": left_name, "right_name": right_name}, ensure_ascii=True),
                    }
                ],
            },
        ],
        "tools": [{"type": "web_search_preview"}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "workspace_relation_research_result",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "relation_label": {"type": ["string", "null"]},
                        "confidence": {"type": ["number", "null"]},
                        "sources": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "title": {"type": ["string", "null"]},
                                    "uri": {"type": "string"},
                                    "snippet": {"type": ["string", "null"]},
                                },
                                "required": ["title", "uri", "snippet"],
                            },
                        },
                    },
                    "required": ["relation_label", "confidence", "sources"],
                },
            }
        },
    }
    req = urllib_request.Request(
        url=f"{settings.openai_base_url.rstrip('/')}/responses",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=settings.openai_timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
        decoded = json.loads(raw)
        output_text = _extract_responses_output_text(decoded)
        if not isinstance(output_text, str) or not output_text.strip():
            return None
        parsed = json.loads(output_text)
    except (urllib_error.URLError, urllib_error.HTTPError, TypeError, KeyError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _workspace_enrichment_run_read(row: WorkspaceEnrichmentRun) -> WorkspaceEnrichmentRunRead:
    return WorkspaceEnrichmentRunRead(
        id=row.id,
        pod_id=int(row.pod_id),
        conversation_id=row.conversation_id,
        collection_id=int(row.collection_id) if row.collection_id is not None else None,
        collection_item_id=int(row.collection_item_id) if row.collection_item_id is not None else None,
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


def _ensure_message_source(db: Session, *, message_id: int) -> Source | None:
    message = db.scalar(select(Message).where(Message.id == message_id))
    if message is None:
        return None
    source = db.scalar(select(Source).where(Source.message_id == message_id))
    if source is not None:
        return source
    source = Source(
        conversation_id=message.conversation_id,
        source_kind="message",
        message_id=message_id,
        title=f"{message.role} message #{message.id}",
        uri=None,
        payload_json={
            "role": message.role,
            "timestamp": message.timestamp.isoformat() if message.timestamp is not None else None,
        },
    )
    db.add(source)
    db.flush()
    return source


def _message_snippet(db: Session, *, message_id: int) -> str | None:
    message = db.scalar(select(Message).where(Message.id == message_id))
    return _truncate_snippet(message.content if message is not None else None)


def _log_workspace_run(
    db: Session,
    *,
    conversation_id: str | None,
    pod_id: int,
    run_kind: str,
    model_name: str,
    prompt_version: str,
    payload_json: dict[str, Any],
) -> ExtractorRun | None:
    row = ExtractorRun(
        conversation_id=conversation_id or f"pod:{pod_id}",
        pod_id=pod_id,
        run_kind=run_kind,
        model_name=model_name,
        prompt_version=prompt_version,
        input_message_ids_json=[],
        raw_output_json=payload_json,
        validated_output_json=payload_json,
    )
    db.add(row)
    db.flush()
    return row


def _top_predicates_for_entities(
    facts_by_entity: dict[int, list[Fact]],
    entity_ids: list[int],
    *,
    limit: int,
) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for entity_id in entity_ids:
        for fact in facts_by_entity.get(entity_id, []):
            key = _column_key(fact.predicate)
            if not key or key in _GENERIC_PREDICATES:
                continue
            counts[key] += 1
    return [key for key, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _build_row_summary(facts: list[Fact]) -> str | None:
    fragments = [
        f"{_display_label(fact.predicate)}: {fact.object_value}"
        for fact in facts[:3]
        if str(fact.object_value or "").strip()
    ]
    return " | ".join(fragments) if fragments else None


def _build_detail_blurb(entity: Entity, facts: list[Fact]) -> str | None:
    if not facts:
        return f"{entity.canonical_name} is tracked in this workspace."
    first = facts[0]
    return f"{entity.canonical_name} has {_display_label(first.predicate).lower()} {first.object_value}."


def _column_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized[:120]


def _display_label(value: str) -> str:
    clean = re.sub(r"[_\-]+", " ", value).strip()
    return " ".join(token.capitalize() for token in clean.split()) if clean else value


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _pluralize_key(value: str) -> str:
    normalized = _column_key(value)
    if normalized.endswith("y") and len(normalized) > 1:
        return f"{normalized[:-1]}ies"
    if normalized.endswith("s"):
        return normalized
    return f"{normalized}s"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "collection"


def _coerce_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _truncate_snippet(content: str | None, *, max_len: int = 280) -> str | None:
    if not content:
        return None
    normalized = " ".join(content.strip().split())
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 3]}..."


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_responses_output_text(decoded: dict[str, Any]) -> str | None:
    direct = decoded.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    output = decoded.get("output")
    if not isinstance(output, list):
        return None
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                return text
    return None


def _min_confidence(values: list[float | None]) -> float | None:
    normalized = [value for value in values if value is not None]
    if not normalized:
        return None
    return min(normalized)


def _dedupe_key(value: str) -> str:
    normalized = _normalize_token(value)
    return normalized[:255] or "suggestion"
