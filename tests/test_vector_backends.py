import socket

import pytest

from salva_core.semantic import build_semantic_vector_catalog
from salva_core.vector_backends import (
    HybridHashVectorBackend,
    ScalarHashVectorBackend,
    SqliteVecBackend,
    resolve_semantic_vector_backend,
)


def _omlx_reachable() -> bool:
    import os
    from urllib.parse import urlparse

    parsed = urlparse(os.environ.get("OMLX_BASE_URL", "http://localhost:8140"))
    try:
        with socket.create_connection((parsed.hostname, parsed.port or 8140), timeout=1.0):
            return True
    except OSError:
        return False


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


def test_catalog_reports_sqlite_vec_available_once_package_installed() -> None:
    # sqlite-vec is now a real pip dependency (pyproject.toml [vector] extra,
    # pulled into [dev]) -- this pins down that the pre-existing catalog
    # scaffolding in salva_core/semantic.py actually flips to "available"
    # rather than staying "unavailable" forever, which the looser assertion
    # above wouldn't catch on its own.
    catalog = build_semantic_vector_catalog()
    status_by_kind = {item.kind: item.status for item in catalog.items}
    assert status_by_kind["sqlite_vec"] == "available"


class TestSqliteVecBackend:
    def test_embed_and_score_follow_the_same_contract_as_other_backends(self):
        backend = SqliteVecBackend(db_path=":memory:", dimensions=32)
        vector = backend.embed("software germany reseller")
        assert len(vector) == 32
        assert abs(backend.score(vector, vector) - 1.0) < 1e-6

    def test_backend_resolver_selects_sqlite_vec_when_requested(self, monkeypatch):
        monkeypatch.setenv("SALVA_SEMANTIC_VECTOR_BACKEND", "sqlite_vec")
        backend = resolve_semantic_vector_backend()
        assert backend.name == "sqlite_vec"

    def test_search_nearest_matches_brute_force_ranking(self):
        """Core acceptance check: index a small synthetic set, verify
        search_nearest()'s ranking via the real sqlite-vec index matches
        brute-force Python ranking computed independently with backend.score()
        on the exact same embeddings. Proves the new indexed-search
        infrastructure is wired correctly -- something no other backend in
        this module can do at all (they only support pairwise score())."""
        backend = SqliteVecBackend(db_path=":memory:", dimensions=64)
        texts = [
            "AI hardware company",
            "artificial intelligence hardware company",
            "organic vegetable farm",
            "vegetable and fruit farming business",
            "cloud infrastructure startup",
        ]
        vectors = {i: backend.embed(t) for i, t in enumerate(texts, start=1)}
        for rowid, vector in vectors.items():
            backend.index(rowid, vector)

        query_id = 1
        query_vector = vectors[query_id]

        indexed_ranking = [rowid for rowid, _ in backend.search_nearest(query_vector, k=len(texts))]

        brute_force_ranking = sorted(
            vectors.keys(),
            key=lambda rowid: -backend.score(query_vector, vectors[rowid]),
        )

        assert indexed_ranking == brute_force_ranking, (
            f"sqlite-vec index ranking {indexed_ranking} must match brute-force "
            f"ranking {brute_force_ranking} on the same embeddings"
        )
        # The query text itself should be its own nearest neighbor.
        assert indexed_ranking[0] == query_id

    @pytest.mark.skipif(
        not _omlx_reachable(),
        reason=(
            "OMLX_BASE_URL unreachable in this environment -- both SqliteVecBackend "
            "and HybridHashVectorBackend fall back to the same hash embeddings when "
            "Jina/omlx is unavailable, so there is nothing meaningfully different to "
            "compare. This test only proves something when a real omlx instance is "
            "running (real Jina embeddings vs the hash baseline)."
        ),
    )
    def test_sqlite_vec_embeddings_differ_from_hash_baseline_when_omlx_available(self):
        sqlite_vec_backend = SqliteVecBackend(db_path=":memory:", dimensions=1024)
        hash_backend = HybridHashVectorBackend(dimensions=96)

        similar_a, similar_b = "AI hardware company", "artificial intelligence hardware company"
        unrelated = "organic vegetable farm"

        sv_sim = sqlite_vec_backend.score(
            sqlite_vec_backend.embed(similar_a), sqlite_vec_backend.embed(similar_b)
        )
        sv_unrel = sqlite_vec_backend.score(
            sqlite_vec_backend.embed(similar_a), sqlite_vec_backend.embed(unrelated)
        )
        hh_sim = hash_backend.score(hash_backend.embed(similar_a), hash_backend.embed(similar_b))
        hh_unrel = hash_backend.score(hash_backend.embed(similar_a), hash_backend.embed(unrelated))

        # With real embeddings, the near-duplicate pair should be more clearly
        # separated from the unrelated pair than the hash baseline manages.
        assert (sv_sim - sv_unrel) > (hh_sim - hh_unrel)
