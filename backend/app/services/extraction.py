"""Extraction orchestration and persistence services."""

from datetime import datetime, timezone
import logging
from time import perf_counter
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.entity_resolution import RESOLVER_VERSION, EntityResolutionPlan, EntityResolver
from app.entity_resolution.similarity import normalize_entity_text, string_similarity
from app.extraction.extractor_interface import ExtractorInterface
from app.extraction.llm_extractor import LLMExtractionError, LLMExtractor, OpenAIChatCompletionsClient
from app.extraction.types import ExtractionResult
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.entity_merge_audit import EntityMergeAudit
from app.models.extractor_run import ExtractorRun
from app.models.fact import Fact
from app.models.message import Message
from app.models.resolution_event import ResolutionEvent
from app.models.relation import Relation
from app.models.schema_field import SchemaField
from app.models.schema_node import SchemaNode
from app.models.schema_relation import SchemaRelation
from app.schema.predicate_registry import PredicateRegistry
from app.schemas.extraction import ExtractionRunResult
from app.services.embeddings import (
    cosine_similarity,
    embed_texts_with_fallback,
    ensure_embedding,
    hash_embed_text,
)
from app.services.schema_stabilization import run_schema_stabilization

logger = logging.getLogger(__name__)


def get_default_extractor() -> ExtractorInterface:
    """Return the LLM extractor implementation."""

    settings = get_settings()
    if not settings.openai_api_key:
        raise LLMExtractionError(
            "OPENAI_API_KEY is not configured. Set it in backend/.env before running extraction."
        )
    return LLMExtractor(
        OpenAIChatCompletionsClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    )


def run_extraction_for_conversation(
    db: Session,
    conversation_id: str,
    extractor: ExtractorInterface | None = None,
    *,
    post_processing_mode: Literal["inline", "none"] = "inline",
) -> ExtractionRunResult:
    """Run extraction for a conversation and replace previous extracted data."""

    total_started = perf_counter()
    try:
        started = perf_counter()
        messages = _get_conversation_messages(db, conversation_id)
        message_load_ms = (perf_counter() - started) * 1000.0

        active_extractor = extractor or get_default_extractor()

        started = perf_counter()
        extraction_result = active_extractor.extract(messages)
        llm_extract_ms = (perf_counter() - started) * 1000.0

        started = perf_counter()
        extractor_run = _log_extractor_run(
            db,
            conversation_id=conversation_id,
            extractor=active_extractor,
            extraction_result=extraction_result,
            messages=messages,
        )
        extractor_run_log_ms = (perf_counter() - started) * 1000.0

        started = perf_counter()
        persisted_counts = _replace_extracted_records(
            db,
            conversation_id,
            extraction_result,
            messages,
            extractor_run_id=extractor_run.id,
            post_processing_mode=post_processing_mode,
        )
        persist_ms = (perf_counter() - started) * 1000.0

        result = ExtractionRunResult(
            extractor_run_id=extractor_run.id,
            conversation_id=conversation_id,
            messages_processed=len(messages),
            entities_created=persisted_counts["entities"],
            facts_created=persisted_counts["facts"],
            relations_created=persisted_counts["relations"],
        )
        logger.info(
            (
                "phase2.extraction_timing conversation_id=%s extractor_run_id=%s "
                "messages=%d message_load_ms=%.2f llm_extract_ms=%.2f "
                "extractor_run_log_ms=%.2f persist_ms=%.2f total_ms=%.2f "
                "post_processing_mode=%s entities=%d facts=%d relations=%d"
            ),
            conversation_id,
            result.extractor_run_id,
            result.messages_processed,
            message_load_ms,
            llm_extract_ms,
            extractor_run_log_ms,
            persist_ms,
            (perf_counter() - total_started) * 1000.0,
            post_processing_mode,
            result.entities_created,
            result.facts_created,
            result.relations_created,
        )
        return result
    except Exception:
        logger.exception(
            "phase2.extraction_failed conversation_id=%s elapsed_ms=%.2f post_processing_mode=%s",
            conversation_id,
            (perf_counter() - total_started) * 1000.0,
            post_processing_mode,
        )
        raise


def _get_conversation_messages(db: Session, conversation_id: str) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc(), Message.id.asc())
    )
    return list(db.scalars(stmt).all())


def _replace_extracted_records(
    db: Session,
    conversation_id: str,
    result: ExtractionResult,
    messages: list[Message],
    *,
    extractor_run_id: int | None,
    post_processing_mode: Literal["inline", "none"],
) -> dict[str, int]:
    """Delete prior records for the conversation and persist the new extraction result."""

    _normalize_extraction_payload(result)
    type_observations: dict[str, set[str]] = {}
    field_observations: dict[str, set[str]] = {}
    relation_observations: dict[str, set[str]] = {}

    db.execute(delete(Relation).where(Relation.conversation_id == conversation_id))
    db.execute(delete(Fact).where(Fact.conversation_id == conversation_id))
    db.execute(delete(ConversationEntityLink).where(ConversationEntityLink.conversation_id == conversation_id))
    db.execute(delete(ResolutionEvent).where(ResolutionEvent.conversation_id == conversation_id))
    db.execute(delete(EntityMergeAudit).where(EntityMergeAudit.conversation_id == conversation_id))
    db.flush()

    message_timestamps = {message.id: message.timestamp for message in messages}
    resolution_plan = EntityResolver().resolve(
        result.entities,
        observed_message_timestamps=message_timestamps,
    )
    assignments_by_index = {
        assignment.extracted_index: assignment for assignment in resolution_plan.assignments
    }

    entities_by_index: dict[int, Entity] = {}
    entity_embedding_rows: list[tuple[Entity, str]] = []
    for extracted_index, extracted_entity in enumerate(result.entities):
        assignment = assignments_by_index[extracted_index]
        first_seen_timestamp = _first_seen_timestamp(extracted_entity.source_message_ids, message_timestamps)
        entity = Entity(
            conversation_id=conversation_id,
            name=extracted_entity.name,
            display_name=extracted_entity.name,
            canonical_name=assignment.canonical_name,
            type=extracted_entity.type_label or "Unspecified",
            type_label=extracted_entity.type_label or "Unspecified",
            aliases_json=sorted(set(extracted_entity.aliases)),
            known_aliases_json=assignment.known_aliases,
            tags_json=sorted(set(extracted_entity.tags)),
            first_seen_timestamp=first_seen_timestamp or datetime.now(timezone.utc),
            resolution_confidence=assignment.confidence,
            resolution_reason=assignment.reason_for_merge,
            resolver_version=RESOLVER_VERSION,
        )
        db.add(entity)
        entities_by_index[extracted_index] = entity
        entity_embedding_rows.append(
            (
                entity,
                _build_entity_embedding_text(
                    canonical_name=assignment.canonical_name,
                    type_label=extracted_entity.type_label,
                    aliases=assignment.known_aliases,
                ),
            )
        )
        if extracted_entity.type_label:
            _record_schema_observation(
                type_observations,
                label=extracted_entity.type_label,
                example=assignment.canonical_name,
            )
    db.flush()

    canonical_entity_by_cluster: dict[int, Entity] = {}
    for assignment in resolution_plan.assignments:
        if assignment.merged:
            continue
        canonical_entity_by_cluster[assignment.canonical_cluster_index] = entities_by_index[
            assignment.extracted_index
        ]
    local_entity_ids = {entity.id for entity in entities_by_index.values()}
    global_merge_audits = _apply_global_entity_matching(
        db,
        conversation_id=conversation_id,
        canonical_entity_by_cluster=canonical_entity_by_cluster,
        local_entity_ids=local_entity_ids,
    )
    if global_merge_audits:
        db.add_all(global_merge_audits)

    for assignment in resolution_plan.assignments:
        if not assignment.merged:
            continue
        merged_entity = entities_by_index[assignment.extracted_index]
        canonical_entity = canonical_entity_by_cluster.get(assignment.canonical_cluster_index)
        if canonical_entity is None:
            continue
        merged_entity.merged_into_id = canonical_entity.id
        db.add(
            EntityMergeAudit(
                conversation_id=conversation_id,
                survivor_entity_id=canonical_entity.id,
                merged_entity_ids_json=[merged_entity.id],
                reason_for_merge=assignment.reason_for_merge or "unknown",
                confidence=assignment.confidence,
                resolver_version=RESOLVER_VERSION,
                details_json={
                    "type_label": assignment.type_label,
                    "survivor_canonical_name": assignment.canonical_name,
                    "merged_name": merged_entity.name,
                    "merge_scope": "conversation",
                },
            )
        )
    db.flush()
    db.add_all(
        _build_resolution_events(
            conversation_id=conversation_id,
            result=result,
            resolution_plan=resolution_plan,
            entities_by_index=entities_by_index,
            canonical_entity_by_cluster=canonical_entity_by_cluster,
        )
    )
    db.flush()

    predicate_registry = PredicateRegistry()
    fact_embedding_rows: list[tuple[Fact, str]] = []

    facts_created = 0
    for extracted_fact in result.facts:
        cluster_index = resolution_plan.resolve_reference(
            extracted_fact.entity_name,
        )
        subject_entity = canonical_entity_by_cluster.get(cluster_index) if cluster_index is not None else None
        if subject_entity is None:
            continue
        predicate_decision = predicate_registry.register(
            db,
            value=extracted_fact.field_label,
            kind="fact_predicate",
        )
        fact_row = Fact(
            conversation_id=conversation_id,
            subject_entity_id=subject_entity.id,
            predicate=predicate_decision.canonical_predicate,
            object_value=extracted_fact.value_text,
            scope="conversation",
            confidence=extracted_fact.confidence,
            source_message_ids_json=extracted_fact.source_message_ids,
            extractor_run_id=extractor_run_id,
        )
        db.add(fact_row)
        fact_embedding_rows.append(
            (
                fact_row,
                _build_fact_embedding_text(
                    canonical_name=subject_entity.canonical_name,
                    predicate=predicate_decision.canonical_predicate,
                    object_value=extracted_fact.value_text,
                ),
            )
        )
        _record_schema_observation(
            field_observations,
            label=predicate_decision.canonical_predicate,
            example=f"{subject_entity.canonical_name}: {extracted_fact.value_text}",
        )
        facts_created += 1

    relations_created = 0
    for extracted_relation in result.relations:
        from_cluster_index = resolution_plan.resolve_reference(
            extracted_relation.from_entity,
        )
        to_cluster_index = resolution_plan.resolve_reference(
            extracted_relation.to_entity,
        )
        from_entity = (
            canonical_entity_by_cluster.get(from_cluster_index)
            if from_cluster_index is not None
            else None
        )
        to_entity = canonical_entity_by_cluster.get(to_cluster_index) if to_cluster_index is not None else None
        if from_entity is None or to_entity is None:
            continue
        relation_type_decision = predicate_registry.register(
            db,
            value=extracted_relation.relation_label,
            kind="relation_type",
        )
        qualifiers = dict(extracted_relation.qualifiers)
        qualifiers.setdefault("extraction_confidence", extracted_relation.confidence)
        db.add(
            Relation(
                conversation_id=conversation_id,
                from_entity_id=from_entity.id,
                relation_type=relation_type_decision.canonical_predicate,
                to_entity_id=to_entity.id,
                scope="conversation",
                confidence=extracted_relation.confidence,
                qualifiers_json=qualifiers,
                source_message_ids_json=extracted_relation.source_message_ids,
                extractor_run_id=extractor_run_id,
            )
        )
        _record_schema_observation(
            relation_observations,
            label=relation_type_decision.canonical_predicate,
            example=f"{from_entity.canonical_name} {relation_type_decision.canonical_predicate} {to_entity.canonical_name}",
        )
        relations_created += 1

    _upsert_conversation_entity_links(
        db,
        conversation_id=conversation_id,
        result=result,
        resolution_plan=resolution_plan,
        canonical_entity_by_cluster=canonical_entity_by_cluster,
    )
    if post_processing_mode == "inline":
        _apply_embeddings_on_write(
            entity_embeddings=entity_embedding_rows,
            fact_embeddings=fact_embedding_rows,
        )
    _apply_schema_on_write(
        db,
        conversation_id=conversation_id,
        type_observations=type_observations,
        field_observations=field_observations,
        relation_observations=relation_observations,
    )
    if post_processing_mode == "inline":
        run_schema_stabilization(db, conversation_id=conversation_id)

    db.commit()
    return {"entities": len(result.entities), "facts": facts_created, "relations": relations_created}


def _first_seen_timestamp(
    source_message_ids: list[int],
    message_timestamps: dict[int, datetime],
) -> datetime | None:
    timestamps = [
        message_timestamps[message_id]
        for message_id in source_message_ids
        if message_id in message_timestamps
    ]
    if not timestamps:
        return None
    return min(timestamps)


def _normalize_extraction_payload(result: ExtractionResult) -> None:
    """Apply lightweight cleanup without enforcing fixed ontology enums."""

    for entity in result.entities:
        entity.type_label = _clean_optional_text(entity.type_label)
        entity.confidence = _clamp_confidence(entity.confidence)
    for fact in result.facts:
        fact.confidence = _clamp_confidence(fact.confidence)
    for relation in result.relations:
        relation.confidence = _clamp_confidence(relation.confidence)


def _build_resolution_events(
    *,
    conversation_id: str,
    result: ExtractionResult,
    resolution_plan: EntityResolutionPlan,
    entities_by_index: dict[int, Entity],
    canonical_entity_by_cluster: dict[int, Entity],
) -> list[ResolutionEvent]:
    events: list[ResolutionEvent] = []
    for assignment in resolution_plan.assignments:
        extracted_entity = result.entities[assignment.extracted_index]
        resolved_entity = entities_by_index[assignment.extracted_index]
        canonical_entity = canonical_entity_by_cluster.get(assignment.canonical_cluster_index, resolved_entity)
        source_ids = sorted(set(extracted_entity.source_message_ids))

        if assignment.merged:
            entity_ids = [canonical_entity.id, resolved_entity.id]
            events.append(
                ResolutionEvent(
                    conversation_id=conversation_id,
                    event_type="match",
                    entity_ids_json=entity_ids,
                    similarity_score=assignment.confidence,
                    rationale=assignment.reason_for_merge or "resolved_to_existing_canonical",
                    source_message_ids_json=source_ids,
                )
            )
            events.append(
                ResolutionEvent(
                    conversation_id=conversation_id,
                    event_type="merge",
                    entity_ids_json=entity_ids,
                    similarity_score=assignment.confidence,
                    rationale=assignment.reason_for_merge or "merged_into_canonical",
                    source_message_ids_json=source_ids,
                )
            )
            alias_candidates = [resolved_entity.name, *extracted_entity.aliases]
        else:
            event_entity_ids = [resolved_entity.id]
            rationale = "canonical_entity_created"
            similarity = 1.0
            if canonical_entity.id != resolved_entity.id:
                event_entity_ids = [canonical_entity.id, resolved_entity.id]
                rationale = "resolved_to_existing_global_canonical"
                similarity = max(0.0, min(1.0, float(resolved_entity.resolution_confidence)))
            events.append(
                ResolutionEvent(
                    conversation_id=conversation_id,
                    event_type="match",
                    entity_ids_json=event_entity_ids,
                    similarity_score=similarity,
                    rationale=rationale,
                    source_message_ids_json=source_ids,
                )
            )
            alias_candidates = list(extracted_entity.aliases)

        for alias in _extract_alias_additions(alias_candidates, canonical_entity.canonical_name):
            events.append(
                ResolutionEvent(
                    conversation_id=conversation_id,
                    event_type="alias_add",
                    entity_ids_json=[canonical_entity.id, resolved_entity.id]
                    if assignment.merged
                    else [resolved_entity.id],
                    similarity_score=assignment.confidence if assignment.merged else 1.0,
                    rationale=f"alias_observed:{alias}",
                    source_message_ids_json=source_ids,
                )
            )
    return events


def _apply_schema_on_write(
    db: Session,
    *,
    conversation_id: str,
    type_observations: dict[str, set[str]],
    field_observations: dict[str, set[str]],
    relation_observations: dict[str, set[str]],
) -> None:
    _upsert_schema_registry(db, SchemaNode, type_observations, conversation_id)
    _upsert_schema_registry(db, SchemaField, field_observations, conversation_id)
    _upsert_schema_registry(db, SchemaRelation, relation_observations, conversation_id)
    db.flush()


def _upsert_schema_registry(
    db: Session,
    model_cls: type[SchemaNode] | type[SchemaField] | type[SchemaRelation],
    observations: dict[str, set[str]],
    conversation_id: str,
) -> None:
    labels = list(observations)
    vectors = embed_texts_with_fallback(labels)
    embedding_by_label = {label: vectors[idx] for idx, label in enumerate(labels)}
    for label, examples in observations.items():
        existing = db.scalar(select(model_cls).where(model_cls.label == label))
        normalized_examples = _merge_examples(existing.examples_json if existing is not None else [], examples)
        if existing is None:
            db.add(
                model_cls(
                    label=label,
                    examples_json=normalized_examples,
                    embedding=embedding_by_label.get(label),
                    stats_json={
                        "observations": 1,
                        "last_seen_conversation_id": conversation_id,
                    },
                )
            )
            continue

        stats = dict(existing.stats_json or {})
        stats["observations"] = int(stats.get("observations", 0)) + 1
        stats["last_seen_conversation_id"] = conversation_id
        existing.examples_json = normalized_examples
        existing.embedding = embedding_by_label.get(label)
        existing.stats_json = stats
        db.add(existing)


def _upsert_conversation_entity_links(
    db: Session,
    *,
    conversation_id: str,
    result: ExtractionResult,
    resolution_plan: EntityResolutionPlan,
    canonical_entity_by_cluster: dict[int, Entity],
) -> None:
    source_ids_by_cluster: dict[int, set[int]] = {}
    for assignment in resolution_plan.assignments:
        cluster_ids = source_ids_by_cluster.setdefault(assignment.canonical_cluster_index, set())
        cluster_ids.update(result.entities[assignment.extracted_index].source_message_ids)

    for cluster_index, canonical_entity in canonical_entity_by_cluster.items():
        sorted_message_ids = sorted(source_ids_by_cluster.get(cluster_index, set()))
        db.add(
            ConversationEntityLink(
                conversation_id=conversation_id,
                entity_id=canonical_entity.id,
                first_seen_message_id=sorted_message_ids[0] if sorted_message_ids else None,
                last_seen_message_id=sorted_message_ids[-1] if sorted_message_ids else None,
            )
        )


def _apply_embeddings_on_write(
    *,
    entity_embeddings: list[tuple[Entity, str]],
    fact_embeddings: list[tuple[Fact, str]],
) -> None:
    rows = [*entity_embeddings, *fact_embeddings]
    if not rows:
        return
    vectors = embed_texts_with_fallback([text for _, text in rows])
    for idx, (row, _) in enumerate(rows):
        row.embedding = vectors[idx]


def _apply_global_entity_matching(
    db: Session,
    *,
    conversation_id: str,
    canonical_entity_by_cluster: dict[int, Entity],
    local_entity_ids: set[int],
) -> list[EntityMergeAudit]:
    settings = get_settings()
    max_candidates = max(50, int(settings.global_resolution_max_candidates))
    global_candidates = list(
        db.scalars(
            select(Entity)
            .where(
                Entity.merged_into_id.is_(None),
                Entity.conversation_id != conversation_id,
                ~Entity.id.in_(sorted(local_entity_ids)),
            )
            .order_by(Entity.id.desc())
            .limit(max_candidates)
        )
    )
    audits: list[EntityMergeAudit] = []
    for cluster_index, local_canonical in list(canonical_entity_by_cluster.items()):
        match = _find_best_global_entity_match(local_canonical, global_candidates)
        if match is None:
            continue
        survivor, reason, confidence = match
        if survivor.id == local_canonical.id:
            continue
        local_canonical.merged_into_id = survivor.id
        local_canonical.resolution_reason = reason
        local_canonical.resolution_confidence = confidence
        survivor.known_aliases_json = _merge_aliases(
            survivor.known_aliases_json,
            [survivor.name, local_canonical.name, *local_canonical.known_aliases_json],
        )
        canonical_entity_by_cluster[cluster_index] = survivor
        global_candidates.append(local_canonical)
        audits.append(
            EntityMergeAudit(
                conversation_id=conversation_id,
                survivor_entity_id=survivor.id,
                merged_entity_ids_json=[local_canonical.id],
                reason_for_merge=reason,
                confidence=confidence,
                resolver_version=RESOLVER_VERSION,
                details_json={
                    "merge_scope": "global",
                    "survivor_canonical_name": survivor.canonical_name,
                    "merged_name": local_canonical.name,
                },
            )
        )
    return audits


def _find_best_global_entity_match(local_entity: Entity, candidates: list[Entity]) -> tuple[Entity, str, float] | None:
    local_type = (local_entity.type_label or local_entity.type).strip().lower()
    local_aliases = _entity_aliases(local_entity)
    local_alias_keys = {_alias_key(alias) for alias in local_aliases}
    local_alias_keys.discard("")
    local_embedding = _entity_embedding_vector(local_entity)

    best_match: tuple[Entity, str, float] | None = None
    borderline_candidate: tuple[Entity, float] | None = None
    for candidate in candidates:
        candidate_type = (candidate.type_label or candidate.type).strip().lower()
        if local_type and candidate_type and local_type != candidate_type:
            continue

        if _alias_key(local_entity.canonical_name) == _alias_key(candidate.canonical_name):
            return candidate, "global_exact_canonical_match", 1.0

        candidate_alias_keys = {_alias_key(alias) for alias in _entity_aliases(candidate)}
        candidate_alias_keys.discard("")
        if local_alias_keys & candidate_alias_keys:
            return candidate, "global_alias_match", 0.99
        if not _coarse_name_gate(local_entity.canonical_name, candidate.canonical_name):
            continue

        similarity = _best_alias_similarity(local_aliases, _entity_aliases(candidate))
        if similarity >= 0.96:
            return candidate, "global_string_similarity", similarity

        candidate_embedding = _entity_embedding_vector(candidate)
        embedding_similarity = cosine_similarity(local_embedding, candidate_embedding)
        if embedding_similarity >= 0.92:
            if best_match is None or embedding_similarity > best_match[2]:
                best_match = (candidate, "global_embedding_similarity", embedding_similarity)
            continue
        if 0.84 <= embedding_similarity < 0.92:
            if borderline_candidate is None or embedding_similarity > borderline_candidate[1]:
                borderline_candidate = (candidate, embedding_similarity)

    if best_match is not None:
        return best_match
    if borderline_candidate is not None:
        candidate, similarity = borderline_candidate
        if _llm_disambiguation_accepts(local_entity, candidate):
            return candidate, "global_llm_disambiguation", max(similarity, 0.85)
    return None


def _llm_disambiguation_accepts(left: Entity, right: Entity) -> bool:
    try:
        from app.entity_resolution.resolver import llm_entity_disambiguation
    except Exception:
        return False
    return llm_entity_disambiguation(
        left_name=left.canonical_name,
        left_aliases=_entity_aliases(left),
        right_name=right.canonical_name,
        right_aliases=_entity_aliases(right),
    )


def _entity_embedding_vector(entity: Entity) -> list[float]:
    existing = ensure_embedding(entity.embedding)
    if existing is not None:
        return existing
    # Keep global matching deterministic and fast; avoid remote embedding calls here.
    return hash_embed_text(
        _build_entity_embedding_text(
            canonical_name=entity.canonical_name,
            type_label=entity.type_label or entity.type,
            aliases=entity.known_aliases_json,
        )
    )


def _entity_aliases(entity: Entity) -> list[str]:
    return _merge_aliases(entity.known_aliases_json, [entity.name, entity.canonical_name, *entity.aliases_json])


def _merge_aliases(existing: list[str], incoming: list[str]) -> list[str]:
    seen = set()
    merged: list[str] = []
    for value in [*existing, *incoming]:
        clean = " ".join(value.strip().split())
        key = _alias_key(clean)
        if not clean or not key or key in seen:
            continue
        seen.add(key)
        merged.append(clean)
    return merged


def _best_alias_similarity(left_aliases: list[str], right_aliases: list[str]) -> float:
    best = 0.0
    for left_alias in left_aliases:
        left_norm = normalize_entity_text(left_alias)
        if not left_norm:
            continue
        for right_alias in right_aliases:
            right_norm = normalize_entity_text(right_alias)
            if not right_norm:
                continue
            best = max(best, string_similarity(left_norm, right_norm))
    return best


def _coarse_name_gate(left_name: str, right_name: str) -> bool:
    left_tokens = set(normalize_entity_text(left_name).split())
    right_tokens = set(normalize_entity_text(right_name).split())
    if not left_tokens or not right_tokens:
        return False
    if left_tokens & right_tokens:
        return True
    left_primary = sorted(left_tokens)[0]
    right_primary = sorted(right_tokens)[0]
    return bool(left_primary and right_primary and left_primary[:1] == right_primary[:1])


def _log_extractor_run(
    db: Session,
    *,
    conversation_id: str,
    extractor: ExtractorInterface,
    extraction_result: ExtractionResult,
    messages: list[Message],
) -> ExtractorRun:
    validated_output = _extract_validated_output(extractor, extraction_result)
    extractor_run = ExtractorRun(
        conversation_id=conversation_id,
        model_name=_extract_model_name(extractor),
        prompt_version=_extract_prompt_version(extractor),
        input_message_ids_json=[message.id for message in messages],
        raw_output_json=_extract_raw_output(extractor, fallback=validated_output),
        validated_output_json=validated_output,
    )
    db.add(extractor_run)
    db.flush()
    return extractor_run


def _extract_model_name(extractor: ExtractorInterface) -> str:
    model_name = getattr(extractor, "model_name", None)
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    return extractor.__class__.__name__


def _extract_prompt_version(extractor: ExtractorInterface) -> str:
    prompt_version = getattr(extractor, "prompt_version", None)
    if isinstance(prompt_version, str) and prompt_version.strip():
        return prompt_version.strip()
    return "unknown"


def _extract_raw_output(extractor: ExtractorInterface, *, fallback: dict[str, Any]) -> dict[str, Any]:
    raw_output = getattr(extractor, "last_raw_output", None)
    if isinstance(raw_output, dict):
        return raw_output
    return fallback


def _extract_validated_output(
    extractor: ExtractorInterface,
    extraction_result: ExtractionResult,
) -> dict[str, Any]:
    validated_output = getattr(extractor, "last_validated_output", None)
    if isinstance(validated_output, dict):
        return validated_output
    return _serialize_extraction_result(extraction_result)


def _serialize_extraction_result(result: ExtractionResult) -> dict[str, Any]:
    return {
        "entities": [
            {
                "name": entity.name,
                "type_label": entity.type_label,
                "aliases": entity.aliases,
                "confidence": entity.confidence,
                "tags": entity.tags,
                "source_message_ids": entity.source_message_ids,
            }
            for entity in result.entities
        ],
        "facts": [
            {
                "entity_name": fact.entity_name,
                "field_label": fact.field_label,
                "value_text": fact.value_text,
                "confidence": fact.confidence,
                "source_message_ids": fact.source_message_ids,
                "snippet": fact.snippet,
            }
            for fact in result.facts
        ],
        "relations": [
            {
                "from_entity": relation.from_entity,
                "relation_label": relation.relation_label,
                "to_entity": relation.to_entity,
                "qualifiers": relation.qualifiers,
                "confidence": relation.confidence,
                "source_message_ids": relation.source_message_ids,
                "snippet": relation.snippet,
            }
            for relation in result.relations
        ],
    }


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _extract_alias_additions(candidates: list[str], canonical_name: str) -> list[str]:
    canonical_key = _alias_key(canonical_name)
    seen_keys: set[str] = set()
    aliases: list[str] = []
    for candidate in candidates:
        cleaned = candidate.strip()
        key = _alias_key(cleaned)
        if not cleaned or not key or key == canonical_key or key in seen_keys:
            continue
        seen_keys.add(key)
        aliases.append(cleaned)
    return aliases


def _alias_key(value: str) -> str:
    return " ".join(value.lower().split())


def _record_schema_observation(
    bucket: dict[str, set[str]],
    *,
    label: str,
    example: str | None = None,
) -> None:
    clean_label = _normalize_schema_label(label)
    if not clean_label:
        return
    examples = bucket.setdefault(clean_label, set())
    if example:
        clean_example = _normalize_schema_example(example)
        if clean_example:
            examples.add(clean_example)


def _normalize_schema_label(value: str) -> str:
    return " ".join(value.strip().split())


def _normalize_schema_example(value: str) -> str:
    return " ".join(value.strip().split())


def _build_entity_embedding_text(
    *,
    canonical_name: str,
    type_label: str | None,
    aliases: list[str],
) -> str:
    alias_text = ", ".join(sorted(set(alias.strip() for alias in aliases if alias.strip())))
    base = canonical_name.strip()
    if type_label:
        base = f"{base} :: {type_label.strip()}"
    if alias_text:
        base = f"{base} :: aliases: {alias_text}"
    return base


def _build_fact_embedding_text(
    *,
    canonical_name: str,
    predicate: str,
    object_value: str,
) -> str:
    return f"{canonical_name.strip()} {predicate.strip()} {object_value.strip()}".strip()


def _merge_examples(existing: list[str], incoming: set[str], *, limit: int = 8) -> list[str]:
    merged = list(existing or [])
    for example in sorted(incoming):
        if example not in merged:
            merged.append(example)
    return merged[:limit]
