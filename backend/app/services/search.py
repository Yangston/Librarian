"""Semantic search query services."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entity import Entity
from app.models.fact import Fact
from app.schemas.entity import EntityRead
from app.schemas.fact import FactRead, FactWithSubjectRead
from app.schemas.search import EntitySearchHit, FactSearchHit, SemanticSearchData
from app.services.embeddings import cosine_similarity, embed_texts_with_fallback, ensure_embedding


def semantic_search(
    db: Session,
    *,
    query: str,
    conversation_id: str | None = None,
    type_label: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 10,
) -> SemanticSearchData:
    """Return top semantic entity/fact matches for a query."""

    clean_query = " ".join(query.strip().split())
    if not clean_query:
        return SemanticSearchData(
            query=query,
            conversation_id=conversation_id,
            type_label=type_label,
            start_time=start_time,
            end_time=end_time,
            entities=[],
            facts=[],
        )
    query_vector = embed_texts_with_fallback([clean_query])[0]
    clean_type_label = type_label.strip() if type_label else None

    entity_hits = _search_entities(
        db,
        query_vector,
        conversation_id=conversation_id,
        type_label=clean_type_label,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    fact_hits = _search_facts(
        db,
        query_vector,
        conversation_id=conversation_id,
        type_label=clean_type_label,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return SemanticSearchData(
        query=clean_query,
        conversation_id=conversation_id,
        type_label=clean_type_label,
        start_time=start_time,
        end_time=end_time,
        entities=entity_hits,
        facts=fact_hits,
    )


def _search_entities(
    db: Session,
    query_vector: list[float],
    *,
    conversation_id: str | None,
    type_label: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
    limit: int,
) -> list[EntitySearchHit]:
    conditions = [Entity.embedding.is_not(None), Entity.merged_into_id.is_(None)]
    if conversation_id:
        conditions.append(Entity.conversation_id == conversation_id)
    if type_label:
        conditions.append(Entity.type_label == type_label)
    if start_time:
        conditions.append(Entity.updated_at >= start_time)
    if end_time:
        conditions.append(Entity.updated_at <= end_time)
    stmt = select(Entity).where(*conditions)
    try:
        if db.get_bind().dialect.name == "postgresql":
            distance_expr = Entity.embedding.cosine_distance(query_vector).label("distance")
            rows = list(
                db.execute(
                    select(Entity, distance_expr)
                    .where(*conditions)
                    .order_by(distance_expr.asc(), Entity.id.asc())
                    .limit(max(1, limit))
                )
            )
            return [
                EntitySearchHit(
                    entity=EntityRead.model_validate(entity),
                    similarity=max(0.0, min(1.0, 1.0 - float(distance))),
                )
                for entity, distance in rows
            ]
    except Exception:
        pass
    rows = list(db.scalars(stmt))

    scored: list[tuple[float, Entity]] = []
    for entity in rows:
        similarity = cosine_similarity(query_vector, ensure_embedding(entity.embedding))
        if similarity <= 0.0:
            continue
        scored.append((similarity, entity))
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return [
        EntitySearchHit(
            entity=EntityRead.model_validate(entity),
            similarity=score,
        )
        for score, entity in scored[: max(1, limit)]
    ]


def _search_facts(
    db: Session,
    query_vector: list[float],
    *,
    conversation_id: str | None,
    type_label: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
    limit: int,
) -> list[FactSearchHit]:
    stmt = (
        select(Fact, Entity.name.label("subject_entity_name"))
        .join(Entity, Entity.id == Fact.subject_entity_id)
        .where(Fact.embedding.is_not(None))
    )
    if conversation_id:
        stmt = stmt.where(Fact.conversation_id == conversation_id)
    if type_label:
        stmt = stmt.where(Entity.type_label == type_label)
    if start_time:
        stmt = stmt.where(Fact.created_at >= start_time)
    if end_time:
        stmt = stmt.where(Fact.created_at <= end_time)
    try:
        if db.get_bind().dialect.name == "postgresql":
            distance_expr = Fact.embedding.cosine_distance(query_vector).label("distance")
            query_conditions = [Fact.embedding.is_not(None)]
            if conversation_id is not None:
                query_conditions.append(Fact.conversation_id == conversation_id)
            if type_label is not None:
                query_conditions.append(Entity.type_label == type_label)
            if start_time is not None:
                query_conditions.append(Fact.created_at >= start_time)
            if end_time is not None:
                query_conditions.append(Fact.created_at <= end_time)
            rows = list(
                db.execute(
                    select(
                        Fact,
                        Entity.name.label("subject_entity_name"),
                        distance_expr,
                    )
                    .join(Entity, Entity.id == Fact.subject_entity_id)
                    .where(*query_conditions)
                    .order_by(distance_expr.asc(), Fact.id.asc())
                    .limit(max(1, limit))
                )
            )
            return [
                FactSearchHit(
                    fact=FactWithSubjectRead(
                        **FactRead.model_validate(fact).model_dump(),
                        subject_entity_name=subject_name,
                    ),
                    similarity=max(0.0, min(1.0, 1.0 - float(distance))),
                )
                for fact, subject_name, distance in rows
            ]
    except Exception:
        pass
    rows = db.execute(stmt).all()

    scored: list[tuple[float, Fact, str]] = []
    for fact, subject_entity_name in rows:
        similarity = cosine_similarity(query_vector, ensure_embedding(fact.embedding))
        if similarity <= 0.0:
            continue
        scored.append((similarity, fact, subject_entity_name))
    scored.sort(key=lambda item: (-item[0], item[1].id))

    results: list[FactSearchHit] = []
    for score, fact, subject_name in scored[: max(1, limit)]:
        results.append(
            FactSearchHit(
                fact=FactWithSubjectRead(
                    **FactRead.model_validate(fact).model_dump(),
                    subject_entity_name=subject_name,
                ),
                similarity=score,
            )
        )
    return results
