"""Deterministic entity resolution and merge planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from app.entity_resolution.similarity import normalize_entity_text, string_similarity
from app.extraction.types import ExtractedEntity


RESOLVER_VERSION = "phase2-v1"
_SIMILARITY_THRESHOLD = 0.94


@dataclass(slots=True)
class EntityResolutionAssignment:
    """Resolution metadata for one extracted entity (aligned by index)."""

    extracted_index: int
    canonical_cluster_index: int
    canonical_name: str
    entity_type: str
    merged: bool
    reason_for_merge: str | None
    confidence: float
    known_aliases: list[str]


@dataclass(slots=True)
class EntityResolutionPlan:
    """Resolution output used by persistence and reference mapping."""

    assignments: list[EntityResolutionAssignment]
    canonical_cluster_indexes: list[int]

    def resolve_reference(self, name: str, entity_type: str) -> int | None:
        """Resolve an extracted fact/relation reference to a canonical cluster index."""

        candidate_normalized = normalize_entity_text(name)
        if not candidate_normalized:
            return None

        type_key = entity_type.strip()
        best_exact: int | None = None
        best_alias: int | None = None
        best_similarity: tuple[int, float] | None = None

        for assignment in self.assignments:
            if assignment.entity_type != type_key:
                continue
            aliases = {normalize_entity_text(alias) for alias in assignment.known_aliases}
            aliases.discard("")
            if not aliases:
                continue
            if candidate_normalized == normalize_entity_text(assignment.canonical_name):
                best_exact = assignment.canonical_cluster_index
                break
            if candidate_normalized in aliases:
                best_alias = assignment.canonical_cluster_index
                continue
            score = max(string_similarity(candidate_normalized, alias) for alias in aliases)
            if score >= _SIMILARITY_THRESHOLD and (
                best_similarity is None or score > best_similarity[1]
            ):
                best_similarity = (assignment.canonical_cluster_index, score)

        if best_exact is not None:
            return best_exact
        if best_alias is not None:
            return best_alias
        if best_similarity is not None:
            return best_similarity[0]
        return None


@dataclass(slots=True)
class _ClusterMember:
    extracted_index: int
    entity: ExtractedEntity
    merge_reason: str | None
    merge_confidence: float


@dataclass(slots=True)
class _EntityCluster:
    entity_type: str
    members: list[_ClusterMember] = field(default_factory=list)
    aliases: set[str] = field(default_factory=set)
    normalized_aliases: set[str] = field(default_factory=set)
    canonical_name: str = ""
    canonical_member_index: int | None = None

    def add_member(
        self,
        *,
        extracted_index: int,
        entity: ExtractedEntity,
        merge_reason: str | None,
        merge_confidence: float,
    ) -> None:
        self.members.append(
            _ClusterMember(
                extracted_index=extracted_index,
                entity=entity,
                merge_reason=merge_reason,
                merge_confidence=merge_confidence,
            )
        )
        for alias in _iter_entity_aliases(entity):
            self.aliases.add(alias)
            normalized = normalize_entity_text(alias)
            if normalized:
                self.normalized_aliases.add(normalized)
        self._recompute_canonical()

    def match(self, entity: ExtractedEntity) -> tuple[str, float] | None:
        """Return (reason, confidence) when the entity matches this cluster."""

        candidate_names = list(_iter_entity_aliases(entity))
        candidate_normalized = {
            normalize_entity_text(candidate)
            for candidate in candidate_names
            if normalize_entity_text(candidate)
        }
        if not candidate_normalized:
            return None

        if candidate_normalized & self.normalized_aliases:
            overlap = 1.0
            return ("exact_name_match" if normalize_entity_text(entity.name) in self.normalized_aliases else "alias_match", overlap)

        best_similarity = 0.0
        for candidate in candidate_names:
            for existing in self.aliases:
                best_similarity = max(best_similarity, string_similarity(candidate, existing))
        if best_similarity >= _SIMILARITY_THRESHOLD:
            return ("embedding_similarity_threshold", best_similarity)
        return None

    def build_assignment(self, cluster_index: int, member: _ClusterMember) -> EntityResolutionAssignment:
        is_canonical = (
            self.canonical_member_index is not None and member.extracted_index == self.canonical_member_index
        )
        confidence = 1.0 if is_canonical else member.merge_confidence
        return EntityResolutionAssignment(
            extracted_index=member.extracted_index,
            canonical_cluster_index=cluster_index,
            canonical_name=self.canonical_name,
            entity_type=self.entity_type,
            merged=not is_canonical,
            reason_for_merge=(
                None
                if is_canonical
                else (member.merge_reason or "cluster_canonicalization")
            ),
            confidence=confidence,
            known_aliases=sorted(self.aliases),
        )

    def _recompute_canonical(self) -> None:
        """Choose the best canonical label deterministically."""

        best: tuple[tuple[int, int, int, int], int, str] | None = None
        for member in self.members:
            name = member.entity.name.strip()
            if not name:
                continue
            score = _canonical_name_score(name)
            candidate = (score, member.extracted_index, name)
            if best is None or candidate[0] > best[0] or (
                candidate[0] == best[0] and candidate[1] < best[1]
            ):
                best = candidate
        if best is None:
            return
        _, canonical_index, canonical_name = best
        self.canonical_member_index = canonical_index
        self.canonical_name = canonical_name


class EntityResolver:
    """Deterministic entity resolver with transparent merge decisions."""

    def resolve(
        self,
        entities: list[ExtractedEntity],
        *,
        observed_message_timestamps: dict[int, datetime] | None = None,
    ) -> EntityResolutionPlan:
        """Build a resolution plan for extracted entities.

        The optional timestamps argument is accepted for future scoring hooks and traceability.
        """

        _ = observed_message_timestamps
        clusters: list[_EntityCluster] = []

        for extracted_index, entity in enumerate(entities):
            matched_cluster_index: int | None = None
            matched_reason: str | None = None
            matched_confidence = 0.0

            for cluster_index, cluster in enumerate(clusters):
                if cluster.entity_type != entity.entity_type:
                    continue
                match = cluster.match(entity)
                if match is None:
                    continue
                reason, confidence = match
                if confidence > matched_confidence:
                    matched_cluster_index = cluster_index
                    matched_reason = reason
                    matched_confidence = confidence

            if matched_cluster_index is None:
                cluster = _EntityCluster(entity_type=entity.entity_type)
                cluster.add_member(
                    extracted_index=extracted_index,
                    entity=entity,
                    merge_reason=None,
                    merge_confidence=1.0,
                )
                clusters.append(cluster)
                continue

            clusters[matched_cluster_index].add_member(
                extracted_index=extracted_index,
                entity=entity,
                merge_reason=matched_reason,
                merge_confidence=matched_confidence,
            )

        assignments: list[EntityResolutionAssignment] = []
        canonical_cluster_indexes: list[int] = []
        for cluster_index, cluster in enumerate(clusters):
            for member in cluster.members:
                assignment = cluster.build_assignment(cluster_index, member)
                assignments.append(assignment)
            canonical_cluster_indexes.append(cluster_index)

        assignments.sort(key=lambda assignment: assignment.extracted_index)
        return EntityResolutionPlan(
            assignments=assignments,
            canonical_cluster_indexes=canonical_cluster_indexes,
        )


def _iter_entity_aliases(entity: ExtractedEntity) -> Iterable[str]:
    yield entity.name
    for alias in entity.aliases:
        yield alias


def _canonical_name_score(name: str) -> tuple[int, int, int, int]:
    """Higher tuple is preferred as canonical name."""

    stripped = name.strip()
    token_count = len([token for token in stripped.split() if token])
    is_ticker_like = stripped.isupper() and stripped.isascii() and token_count == 1 and len(stripped) <= 6
    has_legal_suffix = any(
        suffix in stripped.lower()
        for suffix in (" inc", " corp", " corporation", " ltd", " llc", " plc", " co.")
    )
    return (
        1 if has_legal_suffix else 0,
        0 if is_ticker_like else 1,
        token_count,
        len(stripped),
    )
