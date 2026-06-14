from salva_core.benchmark import (
    build_benchmark_bundle,
    build_benchmark_report,
    render_benchmark_markdown,
    write_benchmark_report,
)
from salva_core.persistence import persist_discovery_run
from salva_core.schemas import (
    BenchmarkRequest,
    CanonicalEntity,
    DiscoveryIntent,
    DiscoveryRequest,
    RetrievalPolicy,
    SourceAttemptRecord,
    TelemetryRecord,
)


def _make_request(objective: str = "find_leads", output_profile: str = "lead") -> DiscoveryRequest:
    return DiscoveryRequest(
        objective=objective,
        intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        output_profile=output_profile,
        retrieval=RetrievalPolicy(),
    )


def test_build_benchmark_report_aggregates_profiles(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_a = persist_discovery_run(
        request=_make_request("find_leads", "lead"),
        entities=[CanonicalEntity(entity_id="lead:1", entity_type="lead", title="Example Lead")],
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
        meta={
            "qualified_count": 3,
            "raw_count": 10,
            "provider_kinds": ["searxng"],
            "experience_profile": "lead_focus",
        },
        source_attempts=[
            SourceAttemptRecord(
                run_id="pending",
                strategy="dive",
                base_url="https://example.com",
                mode="resilient",
                result_count=10,
                succeeded=True,
            )
        ],
        path=db_path,
    )
    run_b = persist_discovery_run(
        request=_make_request("find_events", "event"),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="expo tokyo",
                round_num=1,
                strategy="radar",
                results_total=20,
                results_qualified=6,
                avg_score=0.5,
            )
        ],
        meta={
            "qualified_count": 6,
            "raw_count": 20,
            "provider_kinds": ["whoogle"],
            "experience_profile": "event_discovery",
        },
        source_attempts=[],
        path=db_path,
    )

    report = build_benchmark_report(BenchmarkRequest(run_ids=[run_a, run_b], label="demo"), path=db_path)

    assert report.total_runs == 2
    assert len(report.runs) == 2
    assert len(report.by_experience_profile) == 2
    assert len(report.by_objective) == 2
    assert report.chart_data["runs"][0]["run_id"] in {run_a, run_b}


def test_write_benchmark_report_exports_json(tmp_path) -> None:
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

    export_path = tmp_path / "exports" / "benchmark.json"
    result = write_benchmark_report(
        BenchmarkRequest(run_ids=[run_id], label="chart"),
        output_path=str(export_path),
        path=db_path,
    )

    assert result.export_path == str(export_path)
    assert export_path.exists()
    assert result.bytes_written > 0
    assert len(result.sha256) == 64


def test_build_benchmark_bundle_writes_markdown_and_json(tmp_path) -> None:
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

    report, json_path, md_path = build_benchmark_bundle(BenchmarkRequest(run_ids=[run_id], label="bundle"), output_dir=str(tmp_path / "bundle"), path=db_path)

    assert report.total_runs == 1
    assert json_path.exists()
    assert md_path.exists()
    assert "# Salva Benchmark Report" in md_path.read_text(encoding="utf-8")


def test_render_benchmark_markdown_includes_summary(tmp_path) -> None:
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

    report = build_benchmark_report(BenchmarkRequest(run_ids=[run_id], label="summary"), path=db_path)
    markdown = render_benchmark_markdown(report)

    assert "Salva Benchmark Report" in markdown
    assert "Profile Summary" in markdown
