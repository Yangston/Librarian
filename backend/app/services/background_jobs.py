"""Background jobs for post-extraction processing."""

from __future__ import annotations

import logging
from time import perf_counter

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.conversation_entity_link import ConversationEntityLink
from app.models.entity import Entity
from app.models.fact import Fact
from app.services.embeddings import embed_texts_with_fallback
from app.services.extraction import _build_entity_embedding_text, _build_fact_embedding_text  # noqa: PLC2701
from app.services.schema_stabilization import run_schema_stabilization

logger = logging.getLogger(__name__)


def run_embedding_backfill_for_conversation(conversation_id: str) -> None:
    """Populate missing embeddings for entities/facts linked to a conversation."""

    total_started = perf_counter()
    db = SessionLocal()
    try:
        started = perf_counter()
        entity_count = _populate_entity_embeddings(db, conversation_id)
        entity_embedding_ms = (perf_counter() - started) * 1000.0

        started = perf_counter()
        fact_count = _populate_fact_embeddings(db, conversation_id)
        fact_embedding_ms = (perf_counter() - started) * 1000.0

        db.commit()
        logger.info(
            (
                "phase2.embedding_backfill_timing conversation_id=%s "
                "entity_rows=%d fact_rows=%d entity_embedding_ms=%.2f fact_embedding_ms=%.2f total_ms=%.2f"
            ),
            conversation_id,
            entity_count,
            fact_count,
            entity_embedding_ms,
            fact_embedding_ms,
            (perf_counter() - total_started) * 1000.0,
        )
    except Exception:
        logger.exception(
            "phase2.embedding_backfill_failed conversation_id=%s elapsed_ms=%.2f",
            conversation_id,
            (perf_counter() - total_started) * 1000.0,
        )
        raise
    finally:
        db.close()


def run_schema_stabilization_job(conversation_id: str) -> None:
    """Run schema stabilization in a background-friendly DB session."""

    total_started = perf_counter()
    db = SessionLocal()
    try:
        run_schema_stabilization(db, conversation_id=conversation_id)
        db.commit()
        logger.info(
            "phase2.schema_stabilization_timing conversation_id=%s total_ms=%.2f",
            conversation_id,
            (perf_counter() - total_started) * 1000.0,
        )
    except Exception:
        logger.exception(
            "phase2.schema_stabilization_failed conversation_id=%s elapsed_ms=%.2f",
            conversation_id,
            (perf_counter() - total_started) * 1000.0,
        )
        raise
    finally:
        db.close()


def run_phase2_post_processing_jobs(conversation_id: str) -> None:
    """Run both embedding and stabilization jobs for a conversation."""

    total_started = perf_counter()
    run_embedding_backfill_for_conversation(conversation_id)
    run_schema_stabilization_job(conversation_id)
    logger.info(
        "phase2.post_processing_timing conversation_id=%s total_ms=%.2f",
        conversation_id,
        (perf_counter() - total_started) * 1000.0,
    )


def _populate_entity_embeddings(db, conversation_id: str) -> int:
    linked_entity_ids = list(
        db.scalars(
            select(ConversationEntityLink.entity_id).where(
                ConversationEntityLink.conversation_id == conversation_id
            )
        )
    )
    if not linked_entity_ids:
        return 0
    entities = list(
        db.scalars(
            select(Entity)
            .where(Entity.id.in_(linked_entity_ids), Entity.embedding.is_(None))
            .order_by(Entity.id.asc())
        )
    )
    if not entities:
        return 0
    texts = [
        _build_entity_embedding_text(
            canonical_name=entity.canonical_name,
            type_label=entity.type_label or entity.type,
            aliases=entity.known_aliases_json,
        )
        for entity in entities
    ]
    vectors = embed_texts_with_fallback(texts)
    for idx, entity in enumerate(entities):
        entity.embedding = vectors[idx]
    return len(entities)


def _populate_fact_embeddings(db, conversation_id: str) -> int:
    rows = list(
        db.execute(
            select(Fact, Entity)
            .join(Entity, Entity.id == Fact.subject_entity_id)
            .where(Fact.conversation_id == conversation_id, Fact.embedding.is_(None))
            .order_by(Fact.id.asc())
        ).all()
    )
    if not rows:
        return 0
    texts = [
        _build_fact_embedding_text(
            canonical_name=entity.canonical_name,
            predicate=fact.predicate,
            object_value=fact.object_value,
        )
        for fact, entity in rows
    ]
    vectors = embed_texts_with_fallback(texts)
    for idx, (fact, _) in enumerate(rows):
        fact.embedding = vectors[idx]
    return len(rows)
