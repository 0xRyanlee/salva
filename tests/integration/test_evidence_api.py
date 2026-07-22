import asyncio

from apps.api import main
from apps.api.main import evidence, evidence_chains
from salva_core.persistence import persist_discovery_run
from salva_core.schemas import CanonicalEntity, DiscoveryIntent, DiscoveryRequest, EvidenceItem


def test_evidence_api_roundtrip(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    main.list_evidence_records = lambda run_id=None, entity_id=None, limit=200, offset=0: __import__(
        "salva_core.persistence",
        fromlist=["list_evidence_records"],
    ).list_evidence_records(run_id=run_id, entity_id=entity_id, limit=limit, offset=offset, path=db_path)
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

    response = asyncio.run(evidence(run_id=run_id, entity_id="lead:1", limit=10, offset=0))

    assert response.total == 1
    assert response.items[0].entity_id == "lead:1"


def test_evidence_chain_api_roundtrip(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    main.list_evidence_chains = lambda run_id=None, entity_id=None, limit=200, offset=0: __import__(
        "salva_core.persistence",
        fromlist=["list_evidence_chains"],
    ).list_evidence_chains(run_id=run_id, entity_id=entity_id, limit=limit, offset=offset, path=db_path)
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

    response = asyncio.run(evidence_chains(run_id=run_id, entity_id="lead:1", limit=10, offset=0))

    assert response.total == 1
    assert response.items[0].entity_id == "lead:1"
    assert response.items[0].evidence_count == 1
