"""Deterministic string similarity helpers for entity resolution."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
_MULTISPACE_RE = re.compile(r"\s+")


def normalize_entity_text(value: str) -> str:
    """Normalize entity names/aliases for matching."""

    collapsed = _MULTISPACE_RE.sub(" ", value.strip().lower())
    cleaned = _NON_ALNUM_RE.sub("", collapsed)
    return _MULTISPACE_RE.sub(" ", cleaned).strip()


def token_set_similarity(left: str, right: str) -> float:
    """Return token overlap similarity in [0, 1]."""

    left_tokens = set(normalize_entity_text(left).split())
    right_tokens = set(normalize_entity_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def string_similarity(left: str, right: str) -> float:
    """Composite deterministic similarity score."""

    norm_left = normalize_entity_text(left)
    norm_right = normalize_entity_text(right)
    if not norm_left or not norm_right:
        return 0.0
    if norm_left == norm_right:
        return 1.0
    sequence = SequenceMatcher(a=norm_left, b=norm_right).ratio()
    token = token_set_similarity(norm_left, norm_right)
    return max(sequence, token)
