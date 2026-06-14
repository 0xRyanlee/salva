"""Semantic vector backend selection and deterministic hash baselines."""
from __future__ import annotations

import math
import os
import re
import threading
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Protocol

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class SemanticVectorBackend(Protocol):
    name: str
    kind: str
    dimensions: int

    def embed(self, text: str) -> list[float]: ...

    def score(self, left: list[float], right: list[float]) -> float: ...


def _read_dimensions() -> int:
    raw = os.environ.get("SALVA_SEMANTIC_VECTOR_DIMENSIONS", "96").strip()
    try:
        return max(int(raw), 16)
    except ValueError:
        return 96


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token]


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _character_ngrams(text: str, size: int) -> list[str]:
    compact = text.replace(" ", "")
    if len(compact) < size:
        return [compact] if compact else []
    return [compact[idx : idx + size] for idx in range(len(compact) - size + 1)]


def _vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


@dataclass(slots=True)
class ScalarHashVectorBackend:
    dimensions: int = 96
    name: str = "scalar_hash"
    kind: str = "scalar_hash"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = _tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + min(len(token), 12) / 12.0
            vector[bucket] += sign * weight

        norm = _vector_norm(vector)
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def score(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(l * r for l, r in zip(left, right, strict=True))


@dataclass(slots=True)
class HybridHashVectorBackend:
    dimensions: int = 96
    name: str = "hybrid_hash"
    kind: str = "hybrid_hash"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        if not text.strip():
            return vector

        token_dims = max(self.dimensions // 2, 1)
        ngram_dims = max(self.dimensions - token_dims, 1)
        tokens = _tokenize(text)
        normalized = _normalize_text(text)

        for token in tokens:
            digest = sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % token_dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + min(len(token), 12) / 12.0
            vector[bucket] += sign * weight

        for gram in _character_ngrams(normalized, 3):
            digest = sha256(gram.encode("utf-8")).digest()
            bucket = token_dims + (int.from_bytes(digest[:4], "big") % ngram_dims)
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 0.45 + min(len(gram), 5) / 10.0
            vector[bucket] += sign * weight

        norm = _vector_norm(vector)
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def score(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        return sum(l * r for l, r in zip(left, right, strict=True))


@dataclass(slots=True)
class JinaOmlxVectorBackend:
    """Multilingual embedding via Jina v5 served by local omlx."""

    base_url: str = field(default_factory=lambda: os.environ.get("OMLX_BASE_URL", "http://localhost:8140"))
    model: str = "jina-embeddings-v5-text-small-retrieval-mlx"
    dimensions: int = 1024
    name: str = "jina_omlx"
    kind: str = "jina_omlx"
    _timeout: float = field(default=10.0, repr=False)
    _fallback: HybridHashVectorBackend = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_fallback", HybridHashVectorBackend(dimensions=96))

    def _call(self, texts: list[str]) -> list[list[float]] | None:
        try:
            import httpx
            url = f"{self.base_url.rstrip('/')}/v1/embeddings"
            r = httpx.post(
                url,
                json={"model": self.model, "input": texts},
                timeout=self._timeout,
            )
            r.raise_for_status()
            data: list[dict[str, Any]] = r.json()["data"]
            data.sort(key=lambda x: x["index"])
            return [item["embedding"] for item in data]
        except Exception:
            return None

    def embed(self, text: str) -> list[float]:
        result = self._call([text])
        if result:
            return result[0]
        return self._fallback.embed(text)

    def score(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(l * r for l, r in zip(left, right, strict=True))
        nl = math.sqrt(sum(x * x for x in left))
        nr = math.sqrt(sum(x * x for x in right))
        return dot / (nl * nr) if nl > 0 and nr > 0 else 0.0


_scalar_hash_instances: dict[int, ScalarHashVectorBackend] = {}
_hybrid_hash_instances: dict[int, HybridHashVectorBackend] = {}
_jina_omlx_instance: JinaOmlxVectorBackend | None = None
_instance_lock = threading.Lock()


def resolve_semantic_vector_backend() -> SemanticVectorBackend:
    backend = os.environ.get("SALVA_SEMANTIC_VECTOR_BACKEND", "hybrid_hash").strip() or "hybrid_hash"
    dimensions = _read_dimensions()

    global _scalar_hash_instances, _hybrid_hash_instances, _jina_omlx_instance

    if backend == "jina_omlx":
        if _jina_omlx_instance is None:
            with _instance_lock:
                if _jina_omlx_instance is None:
                    _jina_omlx_instance = JinaOmlxVectorBackend()
        return _jina_omlx_instance

    if backend == "scalar_hash":
        if dimensions not in _scalar_hash_instances:
            with _instance_lock:
                if dimensions not in _scalar_hash_instances:
                    _scalar_hash_instances[dimensions] = ScalarHashVectorBackend(dimensions=dimensions)
        return _scalar_hash_instances[dimensions]

    if dimensions not in _hybrid_hash_instances:
        with _instance_lock:
            if dimensions not in _hybrid_hash_instances:
                _hybrid_hash_instances[dimensions] = HybridHashVectorBackend(dimensions=dimensions)
    return _hybrid_hash_instances[dimensions]
