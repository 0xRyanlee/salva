from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from core.keyword_graph import KeywordGraph
from salva_core import service
from salva_core.persistence import (
    get_db_path_for_project,
    list_query_family_memory,
    list_runs,
    persist_discovery_run,
    promote_query_family_memory,
)
from salva_core.schemas import (
    CachePolicy,
    DiscoveryIntent,
    DiscoveryRequest,
    DomainHints,
    ExecutionContext,
    MemoryPolicy,
    TelemetryRecord,
)


def _request(
    *,
    campaign_id: str | None = None,
    read_scope: str = "none",
    write_mode: str = "quarantine",
    persistence: str = "audit",
) -> DiscoveryRequest:
    return DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(market="Germany", industry="outdoor"),
        execution=ExecutionContext(
            campaign_id=campaign_id,
            persistence=persistence,
            memory=MemoryPolicy(
                read_scope=read_scope,
                write_mode=write_mode,
                min_success_score=0.2,
            ),
        ),
    )


def _telemetry(term: str) -> list[TelemetryRecord]:
    return [
        TelemetryRecord(
            query=f"{term} Germany",
            round_num=1,
            strategy="dive",
            results_total=10,
            results_qualified=8,
            avg_score=0.8,
            metadata={
                "round_strategy": "dive",
                "source_nodes": [term],
                "content_terms": [f"{term}_content"],
            },
        )
    ]


def test_campaign_memory_scope_requires_campaign_id() -> None:
    with pytest.raises(ValidationError):
        _request(read_scope="campaign_promoted")


def test_unimplemented_cache_mode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CachePolicy(mode="content_addressed")


def test_promoted_write_requires_campaign_id() -> None:
    with pytest.raises(ValidationError):
        _request(write_mode="promote")


def test_default_memory_is_quarantined_and_not_seeded(tmp_path) -> None:
    db_path = str(tmp_path / "memory.db")
    request = _request(campaign_id="campaign-a")
    persist_discovery_run(
        request,
        [],
        [],
        _telemetry("quarantine_term"),
        {"domain": "companies"},
        path=db_path,
    )

    rows, total = list_query_family_memory(path=db_path)
    graph = KeywordGraph(service.discovery_request_to_legacy_intent(request))

    assert total == 1
    assert rows[0].memory_status == "quarantine"
    assert service._seed_graph_from_memory(graph, "companies", request, path=db_path) == 0
    assert "quarantine_term" not in graph.nodes


def test_promoted_memory_is_isolated_by_campaign(tmp_path) -> None:
    db_path = str(tmp_path / "memory.db")
    for campaign_id, term in (
        ("campaign-a", "alpha_promoted"),
        ("campaign-b", "beta_promoted"),
    ):
        persist_discovery_run(
            _request(campaign_id=campaign_id, write_mode="promote"),
            [],
            [],
            _telemetry(term),
            {"domain": "companies"},
            path=db_path,
        )

    request = _request(campaign_id="campaign-a", read_scope="campaign_promoted")
    graph = KeywordGraph(service.discovery_request_to_legacy_intent(request))
    seeded = service._seed_graph_from_memory(graph, "companies", request, path=db_path)

    assert seeded >= 1
    assert "alpha_promoted_content" in graph.nodes
    assert "beta_promoted_content" not in graph.nodes


def test_campaign_all_can_read_quarantine_within_same_campaign(tmp_path) -> None:
    db_path = str(tmp_path / "memory.db")
    persist_discovery_run(
        _request(campaign_id="campaign-a"),
        [],
        [],
        _telemetry("campaign_draft"),
        {"domain": "companies"},
        path=db_path,
    )

    request = _request(campaign_id="campaign-a", read_scope="campaign_all")
    graph = KeywordGraph(service.discovery_request_to_legacy_intent(request))

    assert service._seed_graph_from_memory(graph, "companies", request, path=db_path) >= 1
    assert "campaign_draft_content" in graph.nodes


def test_memory_can_be_promoted_after_review(tmp_path) -> None:
    db_path = str(tmp_path / "memory.db")
    persist_discovery_run(
        _request(campaign_id="campaign-a"),
        [],
        [],
        _telemetry("reviewed_term"),
        {"domain": "companies"},
        path=db_path,
    )
    rows, _ = list_query_family_memory(campaign_id="campaign-a", path=db_path)

    promoted = promote_query_family_memory(
        rows[0].memory_id,
        campaign_id="campaign-a",
        path=db_path,
    )

    assert promoted.memory_status == "promoted"
    assert promoted.promoted_at is not None

    with pytest.raises(KeyError):
        promote_query_family_memory(
            rows[0].memory_id,
            campaign_id="campaign-b",
            path=db_path,
        )


def test_run_and_memory_filters_enforce_campaign_scope(tmp_path) -> None:
    db_path = str(tmp_path / "memory.db")
    for campaign_id in ("campaign-a", "campaign-b"):
        persist_discovery_run(
            _request(campaign_id=campaign_id),
            [],
            [],
            _telemetry(campaign_id),
            {"domain": "companies"},
            path=db_path,
        )

    runs, run_total = list_runs(campaign_id="campaign-a", path=db_path)
    rows, memory_total = list_query_family_memory(
        campaign_id="campaign-a",
        path=db_path,
    )

    assert run_total == 1
    assert runs[0].campaign_id == "campaign-a"
    assert memory_total == 1
    assert rows[0].campaign_id == "campaign-a"


def test_persistence_none_skips_all_database_writes(monkeypatch) -> None:
    request = _request(persistence="none")
    observed: dict[str, DiscoveryRequest] = {}

    def fake_execute(payload: DiscoveryRequest):
        observed["request"] = payload
        return [], [], [], {"execution": {}}, []

    monkeypatch.setattr(
        service,
        "execute_discovery",
        fake_execute,
    )
    monkeypatch.setattr(
        service,
        "persist_discovery_run",
        lambda *args, **kwargs: pytest.fail("persistence should be disabled"),
    )

    _, _, _, meta = service.run_discovery(request)

    assert meta["run_id"] is None
    assert meta["feedback"] == {}
    assert observed["request"].execution.campaign_id.startswith("campaign:auto:")
    assert observed["request"].execution.continuation_id.startswith("research:")


def test_source_hints_do_not_become_trusted_sources() -> None:
    request = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(
            market="Germany",
            industry="outdoor",
            domain_hints=DomainHints(
                signal_terms=["distributor"],
                source_hints=["attacker.invalid"],
            ),
        ),
    )

    scorer = service._build_scorer(request, "companies")

    assert scorer.config is not None
    assert "attacker.invalid" not in scorer.config.trusted_sources


def test_legacy_database_rows_are_marked_legacy(tmp_path) -> None:
    db_path = str(tmp_path / "legacy.db")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE discovery_runs (
                run_id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                output_profile TEXT NOT NULL,
                request_json TEXT NOT NULL,
                entities_json TEXT NOT NULL,
                relations_json TEXT NOT NULL,
                meta_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE query_family_memory (
                memory_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT 'general',
                objective TEXT NOT NULL,
                output_profile TEXT NOT NULL,
                round_num INTEGER NOT NULL,
                strategy TEXT NOT NULL,
                query TEXT NOT NULL,
                query_signature TEXT NOT NULL,
                source_nodes_json TEXT NOT NULL,
                content_weights_json TEXT NOT NULL,
                source_hints_json TEXT NOT NULL,
                notes_json TEXT NOT NULL,
                raw_total INTEGER NOT NULL,
                qualified_total INTEGER NOT NULL,
                avg_score REAL NOT NULL,
                success_score REAL NOT NULL,
                created_at TEXT NOT NULL,
                content_nodes_json TEXT NOT NULL DEFAULT '[]'
            );
            """
        )

    from salva_core.persistence import ensure_db

    ensure_db(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(query_family_memory)")
        }

    assert {"campaign_id", "continuation_id", "memory_status", "promoted_at"} <= columns


def test_project_db_path_is_isolated_per_project() -> None:
    path_a = get_db_path_for_project("project-alpha")
    path_b = get_db_path_for_project("project-beta")
    path_none = get_db_path_for_project(None)

    assert path_a != path_b
    assert "project-alpha" in path_a
    assert "project-beta" in path_b
    assert path_none.endswith("salva_runtime.db")


def test_project_db_path_rejects_traversal() -> None:
    path = get_db_path_for_project("../../etc/passwd")
    assert ".." not in path
    assert "/" not in path.split("projects/")[-1].split("/salva.db")[0]


def test_runs_written_to_project_db_are_isolated(tmp_path, monkeypatch) -> None:
    from salva_core.persistence import DEFAULT_DB_PATH
    from salva_core.persistence.db import get_db_path_for_project as _get

    base = str(tmp_path / "salva_runtime.db")
    monkeypatch.setattr(
        "salva_core.persistence.db.DEFAULT_DB_PATH",
        base,
    )
    monkeypatch.setattr(
        "salva_core.persistence.DEFAULT_DB_PATH",
        base,
    )

    def _patched(project_id):
        if not project_id:
            return base
        import os
        from pathlib import Path
        data_dir = Path(base).parent
        safe = "".join(c for c in project_id if c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        return str(data_dir / "projects" / safe / "salva.db")

    monkeypatch.setattr(
        "salva_core.persistence.get_db_path_for_project",
        _patched,
    )
    monkeypatch.setattr(
        "salva_core.service.get_db_path_for_project",
        _patched,
    )

    req_a = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(market="Germany", industry="outdoor"),
        execution=ExecutionContext(project_id="proj-a"),
    )
    req_b = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(market="Germany", industry="outdoor"),
        execution=ExecutionContext(project_id="proj-b"),
    )

    db_a = _patched("proj-a")
    db_b = _patched("proj-b")

    persist_discovery_run(req_a, [], [], [], {"domain": "companies"}, path=db_a)
    persist_discovery_run(req_b, [], [], [], {"domain": "companies"}, path=db_b)

    runs_a, total_a = list_runs(path=db_a)
    runs_b, total_b = list_runs(path=db_b)

    assert total_a == 1
    assert total_b == 1
    assert runs_a[0].project_id == "proj-a"
    assert runs_b[0].project_id == "proj-b"
    # No cross-contamination
    runs_a_from_b, _ = list_runs(project_id="proj-a", path=db_b)
    assert len(runs_a_from_b) == 0
