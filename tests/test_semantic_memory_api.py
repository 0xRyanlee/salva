from fastapi.testclient import TestClient

from apps.api import main
from salva_core.persistence import persist_discovery_run, read_top_query_families_for_seeding
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, TelemetryRecord
from salva_core.semantic import SemanticBackendBenchmarkRequest, build_semantic_backend_benchmark


def test_semantic_query_families_api_roundtrip(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    main.search_query_family_memory = lambda query, objective=None, strategy=None, limit=5, offset=0: __import__(
        "salva_core.persistence",
        fromlist=["search_query_family_memory"],
    ).search_query_family_memory(
        query=query,
        objective=objective,
        strategy=strategy,
        limit=limit,
        offset=offset,
        path=db_path,
    )

    run_id = persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=3,
                avg_score=0.7,
                metadata={
                    "round_strategy": "dive",
                    "content_weights": {"title": 0.45, "platform": 0.1},
                    "source_hints": ["example.com"],
                    "notes": ["precision_first"],
                    "source_nodes": ["software", "reseller"],
                },
            )
        ],
        meta={"qualified_count": 3, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    client = TestClient(main.app)
    response = client.get("/v1/semantic/query-families", params={"query": "software reseller germany", "objective": "find_leads"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["query_family"]["query"] == "software reseller germany"
    assert body["items"][0]["score"] > 0.5


def test_retrieval_batches_api_alias(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    main.list_telemetry = lambda run_id=None, limit=100, offset=0: __import__(
        "salva_core.persistence",
        fromlist=["list_telemetry"],
    ).list_telemetry(
        run_id=run_id,
        limit=limit,
        offset=offset,
        path=db_path,
    )
    persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=3,
                avg_score=0.7,
            )
        ],
        meta={"qualified_count": 3, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    client = TestClient(main.app)
    response = client.get("/v1/retrieval-batches")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["items"][0]["query"] == "software reseller germany"


def test_semantic_index_catalog_exposes_backend_plan() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/semantic/indexes")

    assert response.status_code == 200
    body = response.json()
    assert body["current_backend"] in {"hybrid_hash", "scalar_hash", "sqlite_vec", "hnswlib", "faiss"}
    kinds = {item["kind"] for item in body["items"]}
    assert {"hybrid_hash", "scalar_hash", "sqlite_vec", "hnswlib", "faiss"}.issubset(kinds)


def test_semantic_backend_benchmark_reports_current_backend(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=5,
                avg_score=0.7,
            )
        ],
        meta={"qualified_count": 5, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )
    persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_companies",
            intent=DiscoveryIntent(market="Taipei", industry="AI"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="taipei ai companies",
                round_num=1,
                strategy="anchor",
                results_total=12,
                results_qualified=6,
                avg_score=0.6,
            )
        ],
        meta={"qualified_count": 6, "raw_count": 12, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    report = build_semantic_backend_benchmark(
        SemanticBackendBenchmarkRequest(limit=2, include_scalar_compatibility=True),
        path=db_path,
    )

    assert report.current_backend in {"hybrid_hash", "scalar_hash"}
    assert report.total_samples == 2
    assert report.items
    assert report.winner in {item.backend_name for item in report.items}
    assert report.items[0].top1_objective_hit_rate >= 0.0


def test_semantic_backend_benchmark_api_roundtrip(monkeypatch) -> None:
    def fake_benchmark(payload, path=None):
        from salva_core.semantic import SemanticBackendBenchmarkResponse, SemanticBackendBenchmarkSeries

        return SemanticBackendBenchmarkResponse(
            generated_at="2026-01-01T00:00:00+00:00",
            current_backend="hybrid_hash",
            current_dimensions=96,
            total_samples=2,
            items=[
                SemanticBackendBenchmarkSeries(
                    backend_name="hybrid_hash",
                    backend_kind="hybrid_hash",
                    dimensions=96,
                    status="current",
                    sample_count=2,
                    top1_objective_hit_rate=1.0,
                    top1_strategy_hit_rate=1.0,
                    mean_reciprocal_rank=1.0,
                    mean_top1_similarity=0.92,
                )
            ],
            winner="hybrid_hash",
        )

    monkeypatch.setattr(main, "build_semantic_backend_benchmark", fake_benchmark)

    client = TestClient(main.app)
    response = client.post("/v1/semantic/benchmark", json={"limit": 2})

    assert response.status_code == 200
    assert response.json()["winner"] == "hybrid_hash"


def test_semantic_query_families_skips_dimension_mismatches(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "salva_test.db")

    monkeypatch.setenv("SALVA_SEMANTIC_VECTOR_DIMENSIONS", "32")
    persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=3,
                avg_score=0.7,
                metadata={
                    "round_strategy": "dive",
                    "content_weights": {"title": 0.45, "platform": 0.1},
                    "source_hints": ["example.com"],
                    "notes": ["precision_first"],
                    "source_nodes": ["software", "reseller"],
                },
            )
        ],
        meta={"qualified_count": 3, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    monkeypatch.setenv("SALVA_SEMANTIC_VECTOR_DIMENSIONS", "64")
    from salva_core.persistence import search_query_family_memory as persistence_search_query_family_memory

    matches, total = persistence_search_query_family_memory(
        query="software reseller germany",
        objective="find_leads",
        path=db_path,
    )

    assert total == 0
    assert matches == []


def test_memory_seeding_respects_domain(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")

    persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=8,
                avg_score=0.8,
            )
        ],
        meta={"qualified_count": 8, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )
    persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_companies",
            intent=DiscoveryIntent(market="Taiwan", industry="hardware"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="hardware companies taiwan",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=7,
                avg_score=0.7,
            )
        ],
        meta={"qualified_count": 7, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    bd_leads = read_top_query_families_for_seeding("bd_leads", path=db_path)
    companies = read_top_query_families_for_seeding("companies", path=db_path)

    assert len(bd_leads) == 1
    assert bd_leads[0]["strategy"] == "dive"
    assert len(companies) == 1
    assert companies[0]["strategy"] == "dive"


def test_pilot_exposes_semantic_matches(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=3,
                avg_score=0.7,
                metadata={
                    "round_strategy": "dive",
                    "content_weights": {"title": 0.45, "platform": 0.1},
                    "source_hints": ["example.com"],
                    "notes": ["precision_first"],
                    "source_nodes": ["software", "reseller"],
                },
            )
        ],
        meta={"qualified_count": 3, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    advice = __import__("salva_core.navigation", fromlist=["build_pilot_advice"]).build_pilot_advice(
        __import__("salva_core.schemas", fromlist=["PilotRequest"]).PilotRequest(
            run_id=run_id,
            max_suggestions=3,
        ),
        path=db_path,
    )

    assert advice.semantic_matches
    assert advice.semantic_matches[0]["query_family"]["query"] == "software reseller germany"
