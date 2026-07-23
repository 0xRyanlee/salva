"""query_family_memory has no project_id column of its own (only via
discovery_runs.project_id, joined on run_id) -- previously list_query_family_memory()
and search_query_family_memory() had no way to scope by project at all, so a
non-default project's memory records were invisible to any caller (a
visibility gap, not a leak: see docs/reports/memory-isolation-audit-20260721.md)."""
from __future__ import annotations

from salva_core.persistence import (
    list_query_family_memory,
    persist_discovery_run,
    search_query_family_memory,
)
from salva_core.schemas import (
    DiscoveryIntent,
    DiscoveryRequest,
    ExecutionContext,
    TelemetryRecord,
)


def _persist_run(db_path: str, project_id: str, query: str) -> str:
    return persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
            execution=ExecutionContext(project_id=project_id),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query=query,
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=3,
                avg_score=0.7,
                metadata={
                    "round_strategy": "dive",
                    "content_weights": {"title": 0.4},
                    "source_hints": [],
                    "notes": [],
                    "source_nodes": ["software"],
                },
            )
        ],
        meta={"qualified_count": 3, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )


def test_list_query_family_memory_project_id_filters_to_that_project(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    _persist_run(db_path, "project-a", "software reseller germany a")
    _persist_run(db_path, "project-b", "software reseller germany b")

    all_items, all_total = list_query_family_memory(path=db_path)
    assert all_total == 2

    project_a_items, project_a_total = list_query_family_memory(project_id="project-a", path=db_path)
    assert project_a_total == 1
    assert project_a_items[0].query == "software reseller germany a"

    project_c_items, project_c_total = list_query_family_memory(project_id="project-c", path=db_path)
    assert project_c_total == 0
    assert project_c_items == []


def test_search_query_family_memory_project_id_filters_to_that_project(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    _persist_run(db_path, "project-a", "software reseller germany a")
    _persist_run(db_path, "project-b", "software reseller germany b")

    all_matches, all_total = search_query_family_memory("software reseller germany", path=db_path)
    assert all_total == 2

    project_a_matches, project_a_total = search_query_family_memory(
        "software reseller germany", project_id="project-a", path=db_path
    )
    assert project_a_total == 1
    assert project_a_matches[0][0].query == "software reseller germany a"
