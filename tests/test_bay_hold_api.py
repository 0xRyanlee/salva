from fastapi.testclient import TestClient

from apps.api import main
from salva_core.persistence import list_hyperedges, list_relations, persist_discovery_run
from salva_core.schemas import CanonicalEntity, CanonicalRelation, DiscoveryIntent, DiscoveryRequest, EvidenceItem


def test_bay_manifest_exposes_hold_and_capabilities() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/bay")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "bay"
    assert body["status"] == "draft"
    assert body["hold"]["name"] == "hold"
    assert body["hold"]["status"] == "draft"
    capability_paths = {item["path"] for item in body["capabilities"]}
    assert "/v1/bay" in capability_paths
    assert "/v1/hold/schema" in capability_paths
    assert "/v1/hold/schema/entities" in capability_paths
    assert "/v1/hold/schema/relations" in capability_paths
    assert "/v1/hold/migrations" in capability_paths
    assert "/v1/hold/storage" in capability_paths
    assert "/v1/relations" in capability_paths
    assert "/v1/evidence/chains" in capability_paths
    assert "/v1/hold/walk" in capability_paths
    assert "/v1/hyperedges" in capability_paths
    assert "/v1/providers/catalog" in capability_paths
    assert "/v1/topology/probe" in capability_paths
    assert "/v1/planner" in capability_paths
    assert "/v1/discover" in capability_paths


def test_hold_schema_exposes_core_hypergraph_contract() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/hold/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "hold"
    assert body["status"] == "draft"
    assert body["version"] == "0.1.0"
    assert body["storage_version"] == "0.1.0"
    assert body["migration_version"] == "0.1.0"
    assert body["migration_strategy"]
    assert "related_to" in body["relation_types"]
    assert "entity_to_entity" in body["relation_types"]
    assert "event_membership" in body["relation_types"]
    assert "event_hyperedge" in body["hyperedge_types"]
    assert "query_family_hyperedge" in body["hyperedge_types"]
    assert "entity_view" in body["projection_modes"]
    assert body["entity_schemas"]
    assert body["relation_schemas"]


def test_hold_schema_entity_and_relation_catalogs_are_queryable() -> None:
    client = TestClient(main.app)

    entity_response = client.get("/v1/hold/schema/entities")
    relation_response = client.get("/v1/hold/schema/relations")

    assert entity_response.status_code == 200
    assert relation_response.status_code == 200

    entity_body = entity_response.json()
    relation_body = relation_response.json()
    assert entity_body["total"] >= 7
    assert relation_body["total"] >= 8
    assert {item["entity_type"] for item in entity_body["items"]} >= {"lead", "company", "event", "person"}
    assert any(item["relation_type"] == "evidence_for" for item in relation_body["items"])


def test_hold_migrations_catalog_is_versioned_and_queryable() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/hold/migrations")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    latest = body["items"][0]
    assert latest["schema_name"] == "hold"
    assert latest["hold_version"] == "0.1.0"
    assert latest["storage_version"] == "0.1.0"
    assert latest["migration_version"] == "0.1.0"


def test_hold_storage_catalog_exposes_tables_and_indexes() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/hold/storage")

    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "sqlite"
    table_names = {item["name"] for item in body["tables"]}
    index_names = {item["name"] for item in body["indexes"]}
    assert "hyperedges" in table_names
    assert "relation_records" in table_names
    assert "evidence_chain_records" in table_names
    assert "hold_schema_registry" in table_names
    assert "idx_hyperedges_run_id" in index_names
    assert "idx_relation_records_run_id" in index_names
    assert "idx_relation_records_schema_name" in index_names
    assert "idx_relation_records_schema_version" in index_names
    assert "idx_evidence_chain_records_run_id" in index_names
    assert "idx_hold_schema_registry_versions" in index_names


def test_hold_backend_catalog_exposes_evaluation_options() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/hold/backends")

    assert response.status_code == 200
    body = response.json()
    assert body["current_backend"] == "sqlite"
    kinds = {item["kind"] for item in body["items"]}
    assert {"sqlite", "duckdb_graph", "neo4j", "kuzu"}.issubset(kinds)
    assert any(item["status"] == "available" for item in body["items"])


def test_hold_views_catalog_lists_readable_projections() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/hold/views")

    assert response.status_code == 200
    body = response.json()
    view_names = {item["name"] for item in body["items"]}
    assert {"entity_view", "query_view", "hyperedge_view", "audit_view"}.issubset(view_names)


def test_hold_entity_view_projection_roundtrip(tmp_path, monkeypatch) -> None:
    db_path = str(tmp_path / "salva_test.db")

    run_id = persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[
            CanonicalEntity(
                entity_id="lead:1",
                entity_type="lead",
                title="Example Lead",
                source_urls=["https://example.com"],
                evidence=[
                    EvidenceItem(
                        source_url="https://example.com",
                        source_name="example",
                        title="Example Lead",
                        snippet="Lead evidence",
                    )
                ],
            )
        ],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 1, "raw_count": 1, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    monkeypatch.setattr(
        main,
        "build_run_snapshot",
        lambda current_run_id: __import__(
            "salva_core.exporting",
            fromlist=["build_run_snapshot"],
        ).build_run_snapshot(current_run_id, path=db_path),
    )

    client = TestClient(main.app)
    response = client.get(f"/v1/hold/views/entity_view?run_id={run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["view_name"] == "entity_view"
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Example Lead"


def test_hyperedges_api_roundtrip(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[
            CanonicalEntity(
                entity_id="lead:1",
                entity_type="lead",
                title="Example Lead",
                source_urls=["https://example.com"],
                evidence=[
                    EvidenceItem(
                        source_url="https://example.com",
                        source_name="example",
                        title="Example Lead",
                        snippet="Lead evidence",
                    )
                ],
            )
        ],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 1, "raw_count": 1, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    rows, total = list_hyperedges(run_id=run_id, path=db_path)

    assert total == 1
    assert rows[0].hyperedge_type == "entity_bundle"
    assert rows[0].members[0].member_id == "lead:1"


def test_relations_api_roundtrip(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    relation = CanonicalRelation(
        relation_id="rel:1",
        relation_type="related_to",
        from_entity_id="lead:1",
        to_entity_id="source:1",
        confidence=0.85,
        evidence_ids=["evidence:1"],
    )
    run_id = persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[],
        relations=[relation],
        telemetry=[],
        meta={"qualified_count": 0, "raw_count": 0, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    rows, total = list_relations(run_id=run_id, path=db_path)

    assert total == 1
    assert rows[0].relation_id == "rel:1"
    assert rows[0].relation_type == "related_to"
    assert rows[0].from_entity_id == "lead:1"
    assert rows[0].to_entity_id == "source:1"
    assert rows[0].schema_name == "canonical_relation"
    assert rows[0].schema_version == "0.1.0"
