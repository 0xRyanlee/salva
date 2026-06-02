from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api import main
from salva_core.persistence import persist_discovery_run
from salva_core.schemas import (
    CanonicalEntity,
    CanonicalRelation,
    DiscoveryIntent,
    DiscoveryRequest,
    EvidenceItem,
)


def test_hold_walk_builds_relation_evidence_and_source_nodes(tmp_path, monkeypatch) -> None:
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
                title="Seed Lead",
                source_urls=["https://example.com/lead"],
                evidence=[
                    EvidenceItem(
                        source_url="https://example.com/lead",
                        source_name="example",
                        title="Seed Lead",
                        snippet="Lead evidence",
                    )
                ],
            ),
            CanonicalEntity(
                entity_id="company:1",
                entity_type="company",
                title="Target Company",
            ),
        ],
        relations=[
            CanonicalRelation(
                relation_id="rel:1",
                relation_type="related_to",
                from_entity_id="lead:1",
                to_entity_id="company:1",
                confidence=0.9,
                evidence_ids=["evidence:1"],
            )
        ],
        telemetry=[],
        meta={"qualified_count": 1, "raw_count": 1, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    from salva_core.exporting import build_run_snapshot as _build_run_snapshot

    monkeypatch.setattr(main, "build_run_snapshot", lambda current_run_id: _build_run_snapshot(current_run_id, path=db_path))

    client = TestClient(main.app)
    response = client.get(
        "/v1/hold/walk",
        params={
            "run_id": run_id,
            "seed_entity_id": "lead:1",
            "depth": 2,
            "include_evidence": True,
            "include_sources": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    node_types = {item["node_type"] for item in body["nodes"]}
    edge_types = {item["edge_type"] for item in body["edges"]}
    assert {"entity", "relation", "evidence", "source"}.issubset(node_types)
    assert {"relation_out", "relation_in", "supports", "source_of"}.issubset(edge_types)
    assert body["seed_entity_ids"] == ["lead:1"]
    assert body["total_nodes"] >= 4
    assert body["total_edges"] >= 4
