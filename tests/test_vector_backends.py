from salva_core.semantic import build_semantic_vector_catalog
from salva_core.vector_backends import HybridHashVectorBackend, ScalarHashVectorBackend, resolve_semantic_vector_backend


def test_scalar_hash_backend_produces_normalized_vectors() -> None:
    backend = ScalarHashVectorBackend(dimensions=32)
    vector = backend.embed("software germany reseller")

    assert len(vector) == 32
    assert any(value != 0.0 for value in vector)
    assert abs(backend.score(vector, vector) - 1.0) < 1e-6


def test_hybrid_hash_backend_produces_normalized_vectors() -> None:
    backend = HybridHashVectorBackend(dimensions=32)
    vector = backend.embed("software germany reseller")

    assert len(vector) == 32
    assert any(value != 0.0 for value in vector)
    assert abs(backend.score(vector, vector) - 1.0) < 1e-6


def test_backend_resolver_falls_back_to_hybrid_hash(monkeypatch) -> None:
    monkeypatch.setenv("SALVA_SEMANTIC_VECTOR_BACKEND", "faiss")
    monkeypatch.setenv("SALVA_SEMANTIC_VECTOR_DIMENSIONS", "64")

    backend = resolve_semantic_vector_backend()

    assert backend.name == "hybrid_hash"
    assert backend.dimensions == 64


def test_semantic_vector_catalog_marks_optional_backends_unavailable() -> None:
    catalog = build_semantic_vector_catalog()

    status_by_kind = {item.kind: item.status for item in catalog.items}

    assert status_by_kind["hybrid_hash"] in {"current", "available"}
    assert status_by_kind["scalar_hash"] == "compatibility"
    assert status_by_kind["sqlite_vec"] in {"available", "unavailable"}
    assert status_by_kind["hnswlib"] in {"available", "unavailable"}
    assert status_by_kind["faiss"] in {"available", "unavailable"}
