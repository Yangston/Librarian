"""Embedding helpers for semantic search and similarity."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.config import get_settings
from app.models.embedding_type import EMBEDDING_DIMENSIONS

DEFAULT_HASH_DIMENSIONS = EMBEDDING_DIMENSIONS
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class EmbeddingError(RuntimeError):
    """Raised when embedding generation fails."""


class EmbeddingClient(Protocol):
    """Protocol for pluggable embedding clients."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return vectors for each input text."""


@dataclass(slots=True)
class OpenAIEmbeddingsClient:
    """Minimal OpenAI embeddings client using stdlib HTTP."""

    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": self.model,
            "input": texts,
        }
        url = f"{self.base_url.rstrip('/')}/embeddings"
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
            raise EmbeddingError(f"OpenAI embeddings HTTP {exc.code}: {detail}") from exc
        except urllib_error.URLError as exc:
            raise EmbeddingError(f"OpenAI embeddings request failed: {exc.reason}") from exc

        try:
            decoded = json.loads(raw)
            rows = sorted(decoded["data"], key=lambda row: int(row.get("index", 0)))
            return [list(map(float, row["embedding"])) for row in rows]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise EmbeddingError("OpenAI embeddings response was invalid") from exc


@dataclass(slots=True)
class HashEmbeddingsClient:
    """Deterministic local fallback embeddings used in tests/offline mode."""

    dimensions: int = DEFAULT_HASH_DIMENSIONS

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [hash_embed_text(text, dimensions=self.dimensions) for text in texts]


def get_default_embedding_client() -> EmbeddingClient:
    """Return configured embedding client with deterministic fallback."""

    settings = get_settings()
    if settings.openai_api_key:
        return OpenAIEmbeddingsClient(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    return HashEmbeddingsClient()


def embed_texts_with_fallback(
    texts: list[str],
    *,
    client: EmbeddingClient | None = None,
) -> list[list[float]]:
    """Embed text list and fall back to deterministic vectors if provider fails."""

    if not texts:
        return []
    active_client = client or get_default_embedding_client()
    try:
        vectors = active_client.embed_texts(texts)
        if len(vectors) != len(texts):
            raise EmbeddingError("Embedding client returned wrong vector count")
        return [_normalize_embedding(vector) for vector in vectors]
    except EmbeddingError:
        fallback = HashEmbeddingsClient()
        return fallback.embed_texts(texts)


def hash_embed_text(text: str, *, dimensions: int = DEFAULT_HASH_DIMENSIONS) -> list[float]:
    """Generate a deterministic normalized embedding from text tokens."""

    clean_text = " ".join((text or "").strip().lower().split())
    tokens = _TOKEN_RE.findall(clean_text)
    vector = [0.0 for _ in range(max(1, int(dimensions)))]
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for offset in range(8):
            index = digest[offset] % len(vector)
            sign = -1.0 if (digest[offset + 8] % 2) else 1.0
            magnitude = (digest[offset + 16] / 255.0) + 0.5
            vector[index] += sign * magnitude

    return _normalize_embedding(vector)


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    """Return cosine similarity for two vectors in [0, 1] when possible."""

    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = _vector_norm(left)
    right_norm = _vector_norm(right)
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    dot = sum(l * r for l, r in zip(left, right, strict=False))
    cosine = dot / (left_norm * right_norm)
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


def ensure_embedding(value: Any) -> list[float] | None:
    """Best-effort conversion from JSON-like payload to float vector."""

    if not isinstance(value, list):
        return None
    parsed: list[float] = []
    for item in value:
        try:
            parsed.append(float(item))
        except (TypeError, ValueError):
            return None
    return parsed


def _normalize_embedding(vector: list[float]) -> list[float]:
    norm = _vector_norm(vector)
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _vector_norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))
