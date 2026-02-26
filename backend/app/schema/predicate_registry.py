"""Predicate registry for schema governance and vocabulary stabilization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.entity_resolution.similarity import string_similarity
from app.models.predicate_registry_entry import PredicateRegistryEntry

PredicateKind = Literal["fact_predicate", "relation_type"]
_SIMILARITY_THRESHOLD = 0.96


@dataclass(slots=True)
class PredicateRegistryDecision:
    """Outcome of registry normalization/registration."""

    canonical_predicate: str
    kind: PredicateKind
    reason: str
    created_new: bool
    matched_existing: bool
    registry_entry_id: int | None = None


class PredicateRegistry:
    """DB-backed predicate registry with deterministic dedupe logic."""

    def register(self, db: Session, *, value: str, kind: PredicateKind) -> PredicateRegistryDecision:
        """Normalize and register a predicate/relation type."""

        normalized = normalize_predicate_label(value)
        if not normalized:
            normalized = "unknown_predicate" if kind == "fact_predicate" else "unknown_relation"

        existing_entries = list(
            db.scalars(
                select(PredicateRegistryEntry)
                .where(PredicateRegistryEntry.kind == kind)
                .order_by(PredicateRegistryEntry.frequency.desc(), PredicateRegistryEntry.predicate.asc())
            ).all()
        )

        exact = next((entry for entry in existing_entries if entry.predicate == normalized), None)
        if exact is not None:
            _touch_entry(exact)
            db.flush()
            return PredicateRegistryDecision(
                canonical_predicate=exact.predicate,
                kind=kind,
                reason="exact_predicate_match",
                created_new=False,
                matched_existing=True,
                registry_entry_id=exact.id,
            )

        alias_entry = next(
            (
                entry
                for entry in existing_entries
                if normalized in {normalize_predicate_label(alias) for alias in entry.aliases_json}
            ),
            None,
        )
        if alias_entry is not None:
            _touch_entry(alias_entry)
            _append_alias(alias_entry, normalized)
            db.flush()
            return PredicateRegistryDecision(
                canonical_predicate=alias_entry.predicate,
                kind=kind,
                reason="alias_match",
                created_new=False,
                matched_existing=True,
                registry_entry_id=alias_entry.id,
            )

        best_similarity: tuple[PredicateRegistryEntry, float] | None = None
        for entry in existing_entries:
            score = max(
                [string_similarity(normalized, entry.predicate)]
                + [string_similarity(normalized, alias) for alias in entry.aliases_json]
            )
            if score >= _SIMILARITY_THRESHOLD and (
                best_similarity is None or score > best_similarity[1]
            ):
                best_similarity = (entry, score)

        if best_similarity is not None:
            matched_entry, _score = best_similarity
            _touch_entry(matched_entry)
            _append_alias(matched_entry, normalized)
            db.flush()
            return PredicateRegistryDecision(
                canonical_predicate=matched_entry.predicate,
                kind=kind,
                reason="similarity_threshold_match",
                created_new=False,
                matched_existing=True,
                registry_entry_id=matched_entry.id,
            )

        now = datetime.now(timezone.utc)
        new_entry = PredicateRegistryEntry(
            kind=kind,
            predicate=normalized,
            aliases_json=[],
            frequency=1,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(new_entry)
        db.flush()
        return PredicateRegistryDecision(
            canonical_predicate=new_entry.predicate,
            kind=kind,
            reason="new_registry_entry",
            created_new=True,
            matched_existing=False,
            registry_entry_id=new_entry.id,
        )


def normalize_predicate_label(value: str | None) -> str:
    """Normalize predicate/relation labels to snake_case."""

    if not value:
        return ""
    cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n.,:;\"'")
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return _singularize_last_token(normalized)


def _singularize_last_token(value: str) -> str:
    if "_" in value:
        head, tail = value.rsplit("_", 1)
        singular_tail = _singularize_token(tail)
        return f"{head}_{singular_tail}"
    return _singularize_token(value)


def _singularize_token(token: str) -> str:
    if len(token) <= 4:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith(("ss", "us", "is")):
        return token
    if token.endswith("s"):
        return token[:-1]
    return token


def _touch_entry(entry: PredicateRegistryEntry) -> None:
    entry.frequency += 1
    entry.last_seen_at = datetime.now(timezone.utc)


def _append_alias(entry: PredicateRegistryEntry, alias: str) -> None:
    if alias == entry.predicate:
        return
    aliases = [normalize_predicate_label(candidate) for candidate in entry.aliases_json]
    aliases = [candidate for candidate in aliases if candidate]
    if alias not in aliases:
        aliases.append(alias)
    entry.aliases_json = sorted(set(aliases))
