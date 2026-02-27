"""Shared embedding column type configuration."""

from __future__ import annotations

import os

from sqlalchemy import JSON

EMBEDDING_DIMENSIONS = 1536

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - optional dependency fallback
    Vector = None  # type: ignore[assignment]

_ENABLE_PGVECTOR = os.getenv("ENABLE_PGVECTOR", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if Vector is None or not _ENABLE_PGVECTOR:
    EMBEDDING_COLUMN_TYPE = JSON
else:
    EMBEDDING_COLUMN_TYPE = Vector(EMBEDDING_DIMENSIONS).with_variant(JSON, "sqlite")
