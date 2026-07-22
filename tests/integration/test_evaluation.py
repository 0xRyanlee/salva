from salva_core.evaluation import build_audit_report, compare_audits
from salva_core.persistence import persist_discovery_run
from salva_core.schemas import (
    CanonicalEntity,
    DiscoveryIntent,
    DiscoveryRequest,
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


def test_build_audit_report_summarizes_run(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=_make_request(),
        entities=[CanonicalEntity(entity_id="lead:1", entity_type="lead", title="Example Lead", source_urls=["https://example.com"])],
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

    report = build_audit_report(run_id, path=db_path)

    assert report.run_id == run_id
    assert report.metrics["qualified_rate"] == 0.3
    assert report.metrics["source_success_rate"] == 1.0
    assert report.round_profiles["precision_first"] == 1
    assert report.provider_kinds == ["searxng"]
    assert "low_qualified_rate" not in report.notes


def test_compare_audits_returns_winner(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    left_run = persist_discovery_run(
        request=_make_request(),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=1,
                avg_score=0.2,
            )
        ],
        meta={"qualified_count": 1, "raw_count": 10, "provider_kinds": ["searxng"]},
        source_attempts=[],
        path=db_path,
    )
    right_run = persist_discovery_run(
        request=_make_request(),
        entities=[CanonicalEntity(entity_id="lead:1", entity_type="lead", title="Example Lead", source_urls=["https://example.com"])],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=5,
                avg_score=0.8,
            )
        ],
        meta={"qualified_count": 5, "raw_count": 10, "provider_kinds": ["searxng"]},
        source_attempts=[],
        path=db_path,
    )

    comparison = compare_audits(left_run, right_run, path=db_path)

    assert comparison.left_run_id == left_run
    assert comparison.right_run_id == right_run
    assert comparison.deltas["qualified_rate"] > 0
    assert comparison.winner == right_run
