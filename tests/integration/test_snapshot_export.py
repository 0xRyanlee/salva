from salva_core.exporting import build_run_snapshot, write_run_snapshot
from salva_core.persistence import persist_discovery_run
from salva_core.schemas import (
    CanonicalEntity,
    DiscoveryIntent,
    DiscoveryRequest,
    EvidenceItem,
    RetrievalPolicy,
    SourceAttemptRecord,
    TelemetryRecord,
)


def _make_request() -> DiscoveryRequest:
    return DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        retrieval=RetrievalPolicy(),
    )


def test_build_run_snapshot_includes_audit_and_records(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=_make_request(),
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
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=3,
                avg_score=0.7,
                metadata={"notes": ["precision_first"]},
            )
        ],
        meta={"qualified_count": 3, "raw_count": 10, "provider_kinds": ["searxng"]},
        source_attempts=[
            SourceAttemptRecord(
                run_id="pending",
                strategy="dive",
                base_url="https://example.com",
                mode="resilient",
                source_class="search",
                trust_level="medium",
                risk_level="low",
                recommended_crawl_mode="normal",
                result_count=10,
                succeeded=True,
            )
        ],
        path=db_path,
    )

    snapshot = build_run_snapshot(run_id, path=db_path)

    assert snapshot.run_id == run_id
    assert snapshot.entity_count == 1
    assert snapshot.evidence_count == 1
    assert snapshot.evidence_records[0].entity_id == "lead:1"
    assert snapshot.evidence_chain_count == 1
    assert snapshot.evidence_chains[0].entity_id == "lead:1"
    assert snapshot.hyperedge_count == 2
    assert {hyperedge.hyperedge_type for hyperedge in snapshot.hyperedges} == {
        "entity_bundle",
        "query_family",
    }
    assert snapshot.query_family_count == 1
    assert snapshot.telemetry_count == 1
    assert snapshot.source_attempt_count == 1
    assert snapshot.plugin_report_count == 0
    assert snapshot.audit.run_id == run_id
    assert snapshot.audit.metrics["qualified_rate"] == 0.3


def test_write_run_snapshot_exports_json(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=_make_request(),
        entities=[],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 0, "raw_count": 0, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    export_path = tmp_path / "exports" / "snapshot.json"
    result = write_run_snapshot(run_id, output_path=str(export_path), path=db_path)

    assert result.export_path == str(export_path)
    assert export_path.exists()
    assert result.bytes_written > 0
    assert len(result.sha256) == 64
