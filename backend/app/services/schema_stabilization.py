"""Schema stabilization job for soft canonicalization proposals."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.entity_resolution.similarity import string_similarity
from app.models.schema_field import SchemaField
from app.models.schema_node import SchemaNode
from app.models.schema_proposal import SchemaProposal
from app.models.schema_relation import SchemaRelation
from app.services.embeddings import cosine_similarity, ensure_embedding

PROPOSAL_THRESHOLD = 0.85
AUTO_ACCEPT_THRESHOLD = 0.95


@dataclass(slots=True)
class SchemaStabilizationResult:
    """Summary of stabilization job actions."""

    proposals_created: int = 0
    auto_accepted: int = 0


def run_schema_stabilization(db: Session, *, conversation_id: str | None = None) -> SchemaStabilizationResult:
    """Generate schema merge proposals and auto-accept very high-confidence cases."""

    result = SchemaStabilizationResult()
    for model_cls, proposal_type in (
        (SchemaField, "merge_fields"),
        (SchemaRelation, "merge_relations"),
        (SchemaNode, "merge_nodes"),
    ):
        created, accepted = _stabilize_model(
            db,
            model_cls=model_cls,
            proposal_type=proposal_type,
            conversation_id=conversation_id,
        )
        result.proposals_created += created
        result.auto_accepted += accepted
    return result


def _stabilize_model(
    db: Session,
    *,
    model_cls: type[SchemaField] | type[SchemaRelation] | type[SchemaNode],
    proposal_type: str,
    conversation_id: str | None,
) -> tuple[int, int]:
    rows = list(
        db.scalars(
            select(model_cls)
            .where(model_cls.canonical_of_id.is_(None) if hasattr(model_cls, "canonical_of_id") else True)
            .order_by(model_cls.id.asc())
        )
    )
    existing_pairs = _existing_pair_keys(db, proposal_type)
    proposals_created = 0
    auto_accepted = 0

    for idx, left in enumerate(rows):
        for right in rows[idx + 1 :]:
            if left.id == right.id:
                continue
            if _is_canonicalized(left) or _is_canonicalized(right):
                continue
            pair_key = _pair_key(left.id, right.id)
            if pair_key in existing_pairs:
                continue

            similarity, similarity_method = _schema_similarity(left, right)
            if similarity < PROPOSAL_THRESHOLD:
                continue

            canonical, merged = _choose_canonical(left, right)
            status = "auto_accepted" if similarity >= AUTO_ACCEPT_THRESHOLD else "proposed"
            proposal = SchemaProposal(
                proposal_type=proposal_type,
                payload_json={
                    "canonical_id": canonical.id,
                    "canonical_label": canonical.label,
                    "merged_id": merged.id,
                    "merged_label": merged.label,
                    "table_name": canonical.__tablename__,
                },
                confidence=similarity,
                evidence_json={
                    "method": similarity_method,
                    "similarity_score": similarity,
                    "conversation_id": conversation_id,
                },
                status=status,
            )
            db.add(proposal)
            proposals_created += 1
            existing_pairs.add(pair_key)

            if status == "auto_accepted":
                merged.canonical_of_id = canonical.id
                db.add(merged)
                auto_accepted += 1

    db.flush()
    return proposals_created, auto_accepted


def _choose_canonical(
    left: SchemaField | SchemaRelation | SchemaNode,
    right: SchemaField | SchemaRelation | SchemaNode,
) -> tuple[SchemaField | SchemaRelation | SchemaNode, SchemaField | SchemaRelation | SchemaNode]:
    left_obs = int((left.stats_json or {}).get("observations", 0))
    right_obs = int((right.stats_json or {}).get("observations", 0))
    if left_obs != right_obs:
        return (left, right) if left_obs > right_obs else (right, left)
    left_rank = (_label_specificity(left.label), left.label.lower(), left.id)
    right_rank = (_label_specificity(right.label), right.label.lower(), right.id)
    return (left, right) if left_rank <= right_rank else (right, left)


def _label_specificity(label: str) -> tuple[int, int]:
    token_count = len([token for token in label.split("_") if token])
    return (-token_count, -len(label))


def _existing_pair_keys(db: Session, proposal_type: str) -> set[tuple[int, int]]:
    proposals = list(db.scalars(select(SchemaProposal).where(SchemaProposal.proposal_type == proposal_type)))
    keys: set[tuple[int, int]] = set()
    for proposal in proposals:
        payload = proposal.payload_json or {}
        canonical_id = payload.get("canonical_id")
        merged_id = payload.get("merged_id")
        if isinstance(canonical_id, int) and isinstance(merged_id, int):
            keys.add(_pair_key(canonical_id, merged_id))
    return keys


def _pair_key(left_id: int, right_id: int) -> tuple[int, int]:
    return (left_id, right_id) if left_id < right_id else (right_id, left_id)


def _is_canonicalized(row: SchemaField | SchemaRelation | SchemaNode) -> bool:
    canonical_of_id = getattr(row, "canonical_of_id", None)
    return canonical_of_id is not None


def _schema_similarity(
    left: SchemaField | SchemaRelation | SchemaNode,
    right: SchemaField | SchemaRelation | SchemaNode,
) -> tuple[float, str]:
    string_score = string_similarity(left.label, right.label)
    left_embedding = ensure_embedding(getattr(left, "embedding", None))
    right_embedding = ensure_embedding(getattr(right, "embedding", None))
    embedding_score = cosine_similarity(left_embedding, right_embedding)
    if embedding_score > string_score:
        return embedding_score, "embedding_cosine_v1"
    return string_score, "string_similarity_v1"
