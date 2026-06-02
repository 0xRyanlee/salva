from salva_core.persistence import (
    get_run,
    list_evidence_records,
    list_evidence_chains,
    list_hyperedges,
    list_plugin_reports,
    list_query_family_memory,
    list_relations,
    list_runs,
    list_telemetry,
    persist_discovery_run,
)
from salva_core.schemas import (
    CanonicalEntity,
    CanonicalRelation,
    DiscoveryIntent,
    DiscoveryRequest,
    EvidenceItem,
    TelemetryRecord,
)


def test_persistence_query_helpers_roundtrip(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
    )
    entity = CanonicalEntity(
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
    relation = CanonicalRelation(
        relation_id="rel:1",
        relation_type="related_to",
        from_entity_id="lead:1",
        to_entity_id="source:1",
    )
    telemetry = TelemetryRecord(
        query="example query",
        round_num=1,
        strategy="dive",
        results_total=10,
        results_qualified=2,
    )

    run_id = persist_discovery_run(
        request=request,
        entities=[entity],
        relations=[relation],
        telemetry=[telemetry],
        meta={"qualified_count": 1},
        path=db_path,
    )

    runs, total_runs = list_runs(path=db_path)
    telemetry_rows, total_telemetry = list_telemetry(path=db_path)
    plugin_reports, total_plugin_reports = list_plugin_reports(path=db_path)
    evidence_rows, total_evidence = list_evidence_records(path=db_path)
    hyperedge_rows, total_hyperedges = list_hyperedges(path=db_path)
    query_memory_rows, total_query_memory = list_query_family_memory(path=db_path)
    relation_rows, total_relations = list_relations(path=db_path)
    detail = get_run(run_id, path=db_path)

    assert total_runs == 1
    assert runs[0].run_id == run_id
    assert runs[0].entity_count == 1
    assert total_telemetry == 1
    assert telemetry_rows[0].query == "example query"
    assert total_plugin_reports == 0
    assert total_evidence == 1
    assert evidence_rows[0].entity_id == "lead:1"
    assert total_relations == 1
    assert relation_rows[0].relation_id == "rel:1"
    assert relation_rows[0].schema_name == "canonical_relation"
    assert relation_rows[0].schema_version == "0.1.0"
    assert total_hyperedges == 2
    assert {row.hyperedge_type for row in hyperedge_rows} == {"entity_bundle", "query_family"}
    assert total_query_memory == 1
    assert query_memory_rows[0].query == "example query"
    assert detail is not None
    assert detail["run_id"] == run_id


def test_persistence_deduplicates_evidence_chain_rows_for_duplicate_entities(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software"),
    )
    entity = CanonicalEntity(
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

    run_id = persist_discovery_run(
        request=request,
        entities=[entity, entity],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 1},
        path=db_path,
    )

    chains, total_chains = list_evidence_chains(run_id=run_id, path=db_path)
    assert total_chains == 1
    assert chains[0].entity_id == "lead:1"
    assert chains[0].evidence_count >= 1
