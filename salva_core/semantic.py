from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from hashlib import sha256

from pydantic import BaseModel, Field

from .persistence.db import DEFAULT_DB_PATH
from .schemas import QueryFamilyMemoryRecord
from .vector_backends import (
    HybridHashVectorBackend,
    ScalarHashVectorBackend,
    SemanticVectorBackend,
    resolve_semantic_vector_backend,
)


class SemanticQueryFamilyHit(BaseModel):
    score: float
    vector_id: str
    query_family: QueryFamilyMemoryRecord
    matched_text: str | None = None


class SemanticQueryFamilySearchResponse(BaseModel):
    query: str
    objective: str | None = None
    strategy: str | None = None
    dimensions: int
    total: int
    items: list[SemanticQueryFamilyHit] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SemanticVectorBackendDescriptor(BaseModel):
    name: str
    kind: str
    dimensions: int
    status: str
    description: str
    notes: list[str] = Field(default_factory=list)
    source_path: str | None = None


class SemanticVectorCatalogResponse(BaseModel):
    current_backend: str
    current_dimensions: int
    items: list[SemanticVectorBackendDescriptor] = Field(default_factory=list)
    total: int = 0
    notes: list[str] = Field(default_factory=list)


class SemanticBackendBenchmarkRequest(BaseModel):
    objective: str | None = None
    strategy: str | None = None
    limit: int = Field(default=24, ge=2, le=200)
    offset: int = Field(default=0, ge=0)
    include_scalar_compatibility: bool = True


class SemanticBackendBenchmarkSeries(BaseModel):
    backend_name: str
    backend_kind: str
    dimensions: int
    status: str
    sample_count: int
    top1_objective_hit_rate: float = 0.0
    top1_strategy_hit_rate: float = 0.0
    mean_reciprocal_rank: float = 0.0
    mean_top1_similarity: float = 0.0
    notes: list[str] = Field(default_factory=list)


class SemanticBackendBenchmarkResponse(BaseModel):
    generated_at: str
    current_backend: str
    current_dimensions: int
    total_samples: int
    items: list[SemanticBackendBenchmarkSeries] = Field(default_factory=list)
    winner: str | None = None
    notes: list[str] = Field(default_factory=list)


def build_query_family_semantic_text(record: QueryFamilyMemoryRecord) -> str:
    content_weights = " ".join(f"{key}:{value}" for key, value in sorted(record.content_weights.items()))
    source_nodes = " ".join(record.source_nodes)
    source_hints = " ".join(record.source_hints)
    notes = " ".join(record.notes)
    return " ".join(
        part
        for part in [
            record.query,
            record.objective,
            record.output_profile,
            record.strategy,
            source_nodes,
            source_hints,
            notes,
            content_weights,
            str(record.raw_total),
            str(record.qualified_total),
            f"success_score:{record.success_score}",
        ]
        if part
    )


def build_semantic_vector_catalog() -> SemanticVectorCatalogResponse:
    backend = resolve_semantic_vector_backend()
    current_backend = backend.name
    current_dimensions = backend.dimensions

    items = [
        SemanticVectorBackendDescriptor(
            name="hybrid_hash",
            kind="hybrid_hash",
            dimensions=current_dimensions,
            status="current" if current_backend == "hybrid_hash" else "available",
            description="Deterministic hybrid token + n-gram hash backend.",
            notes=[
                "Dependency-free baseline for semantic memory.",
                "Default backend for Salva runtime.",
            ],
        ),
        SemanticVectorBackendDescriptor(
            name="scalar_hash",
            kind="scalar_hash",
            dimensions=current_dimensions,
            status="current" if current_backend == "scalar_hash" else "compatibility",
            description="Compatibility baseline for regression and benchmark comparison.",
            notes=[
                "Kept for fallback and historical comparisons.",
                "Single-token hashing only.",
            ],
        ),
        SemanticVectorBackendDescriptor(
            name="sqlite_vec",
            kind="sqlite_vec",
            dimensions=current_dimensions,
            status="available" if _module_available("sqlite_vec") else "unavailable",
            description="Optional SQLite-backed ANN backend for local deployments.",
            notes=["Not active by default.", "Shown for evaluation and future adapter work."],
        ),
        SemanticVectorBackendDescriptor(
            name="hnswlib",
            kind="hnswlib",
            dimensions=current_dimensions,
            status="available" if _module_available("hnswlib") else "unavailable",
            description="Optional in-process HNSW backend.",
            notes=["Only available when the package is installed."],
        ),
        SemanticVectorBackendDescriptor(
            name="faiss",
            kind="faiss",
            dimensions=current_dimensions,
            status="available" if _module_available("faiss") else "unavailable",
            description="Optional FAISS backend for larger local ANN indexes.",
            notes=["Only available when the package is installed."],
        ),
    ]

    notes = [
        f"Current backend: {current_backend}",
        "The default runtime backend is deterministic and dependency-free.",
        "Optional ANN backends are cataloged for evaluation only.",
    ]
    return SemanticVectorCatalogResponse(
        current_backend=current_backend,
        current_dimensions=current_dimensions,
        items=items,
        total=len(items),
        notes=notes,
    )


def build_semantic_backend_benchmark(
    payload: SemanticBackendBenchmarkRequest,
    path: str | None = None,
) -> SemanticBackendBenchmarkResponse:
    from salva_core.persistence import list_query_family_memory

    samples, _total = list_query_family_memory(
        objective=payload.objective,
        strategy=payload.strategy,
        limit=payload.limit,
        offset=payload.offset,
        path=path if path is not None else DEFAULT_DB_PATH,
    )
    if len(samples) < 2:
        raise ValueError("semantic backend benchmark requires at least two query-family samples")

    current_backend = resolve_semantic_vector_backend()
    candidate_backends: list[tuple[str, str, int, SemanticVectorBackend, list[str]]] = [
        (current_backend.name, current_backend.kind, current_backend.dimensions, current_backend, ["current backend"]),
    ]
    scalar_backend = ScalarHashVectorBackend(dimensions=current_backend.dimensions)
    if payload.include_scalar_compatibility and scalar_backend.name != current_backend.name:
        candidate_backends.append(
            (
                scalar_backend.name,
                scalar_backend.kind,
                scalar_backend.dimensions,
                scalar_backend,
                ["compatibility baseline"],
            )
        )

    current_texts = [build_query_family_semantic_text(sample) for sample in samples]
    series: list[SemanticBackendBenchmarkSeries] = []
    for backend_name, backend_kind, dimensions, backend, notes in candidate_backends:
        embeddings = [backend.embed(text) for text in current_texts]
        objective_hits = 0
        strategy_hits = 0
        reciprocal_ranks = 0.0
        top1_similarities: list[float] = []
        for index, sample in enumerate(samples):
            ranked: list[tuple[float, QueryFamilyMemoryRecord]] = []
            for candidate_index, candidate in enumerate(samples):
                if candidate_index == index:
                    continue
                score = backend.score(embeddings[index], embeddings[candidate_index])
                ranked.append((score, candidate))
            ranked.sort(key=lambda item: item[0], reverse=True)
            if not ranked:
                continue

            top_score, top_candidate = ranked[0]
            top1_similarities.append(top_score)
            if top_candidate.objective == sample.objective:
                objective_hits += 1
            if top_candidate.strategy == sample.strategy:
                strategy_hits += 1
            same_objective_rank = next(
                (
                    rank
                    for rank, (_, candidate) in enumerate(ranked, start=1)
                    if candidate.objective == sample.objective
                ),
                None,
            )
            if same_objective_rank is not None:
                reciprocal_ranks += 1.0 / same_objective_rank

        sample_count = len(samples)
        evaluated_count = max(sample_count, 1)
        series.append(
            SemanticBackendBenchmarkSeries(
                backend_name=backend_name,
                backend_kind=backend_kind,
                dimensions=dimensions,
                status="current" if backend_name == current_backend.name else "baseline",
                sample_count=sample_count,
                top1_objective_hit_rate=round(objective_hits / evaluated_count, 4),
                top1_strategy_hit_rate=round(strategy_hits / evaluated_count, 4),
                mean_reciprocal_rank=round(reciprocal_ranks / evaluated_count, 4),
                mean_top1_similarity=round(sum(top1_similarities) / max(len(top1_similarities), 1), 4),
                notes=list(notes),
            )
        )

    winner = _pick_semantic_backend_winner(series)
    return SemanticBackendBenchmarkResponse(
        generated_at=datetime.now(UTC).isoformat(),
        current_backend=current_backend.name,
        current_dimensions=current_backend.dimensions,
        total_samples=len(samples),
        items=series,
        winner=winner,
        notes=[
            "This benchmark compares backend behavior on sampled query-family records.",
            "It uses leave-one-out nearest-neighbor scoring on the same sample set.",
            "Optional ANN backends are reported as catalog entries even when unavailable.",
        ],
    )


def build_semantic_embedding(text: str, dimensions: int = 96) -> list[float]:
    backend = resolve_semantic_vector_backend()
    if backend.dimensions != dimensions:
        if backend.name == "hybrid_hash":
            backend = HybridHashVectorBackend(dimensions=dimensions)
        else:
            backend = ScalarHashVectorBackend(dimensions=dimensions)
    return backend.embed(text)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(l * r for l, r in zip(left, right, strict=True))


def build_semantic_vector_id(vector_kind: str, source_id: str) -> str:
    payload = f"{vector_kind}:{source_id}"
    return f"vec:{sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def vector_norm(values: list[float]) -> float:
    return cosine_similarity(values, values) ** 0.5 if values else 0.0


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _pick_semantic_backend_winner(series: list[SemanticBackendBenchmarkSeries]) -> str | None:
    if not series:
        return None
    ordered = sorted(
        series,
        key=lambda item: (
            item.top1_objective_hit_rate,
            item.mean_reciprocal_rank,
            item.mean_top1_similarity,
        ),
        reverse=True,
    )
    return ordered[0].backend_name
