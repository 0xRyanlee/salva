#!/usr/bin/env python3
"""Run deterministic memory-isolation and trust-boundary adversarial checks."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from core.keyword_graph import KeywordGraph
from salva_core import service
from salva_core.persistence import persist_discovery_run
from salva_core.schemas import (
    DiscoveryIntent,
    DiscoveryRequest,
    DomainHints,
    ExecutionContext,
    MemoryPolicy,
    TelemetryRecord,
)


def _request(
    campaign_id: str,
    *,
    read_scope: str = "none",
    write_mode: str = "quarantine",
) -> DiscoveryRequest:
    return DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(market="Germany", industry="outdoor"),
        execution=ExecutionContext(
            campaign_id=campaign_id,
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
            query=term,
            round_num=1,
            strategy="dive",
            results_total=10,
            results_qualified=9,
            avg_score=0.9,
            metadata={
                "round_strategy": "dive",
                "content_terms": [term],
                "source_nodes": [term],
            },
        )
    ]


def _seeded_nodes(request: DiscoveryRequest, db_path: str) -> set[str]:
    graph = KeywordGraph(service.discovery_request_to_legacy_intent(request))
    service._seed_graph_from_memory(
        graph,
        "companies",
        request,
        path=db_path,
    )
    return {
        phrase
        for phrase, node in graph.nodes.items()
        if node.node_type == "memory"
    }


def run_experiment() -> dict:
    with tempfile.TemporaryDirectory(prefix="salva-isolation-") as temp_dir:
        db_path = str(Path(temp_dir) / "isolation.db")
        persist_discovery_run(
            _request("campaign-poison", write_mode="promote"),
            [],
            [],
            _telemetry("POISONED_VENDOR_TERM"),
            {"domain": "companies"},
            path=db_path,
        )
        persist_discovery_run(
            _request("campaign-clean", write_mode="promote"),
            [],
            [],
            _telemetry("CLEAN_VENDOR_TERM"),
            {"domain": "companies"},
            path=db_path,
        )
        persist_discovery_run(
            _request("campaign-clean", write_mode="quarantine"),
            [],
            [],
            _telemetry("UNREVIEWED_TERM"),
            {"domain": "companies"},
            path=db_path,
        )

        clean_promoted = _seeded_nodes(
            _request("campaign-clean", read_scope="campaign_promoted"),
            db_path,
        )
        clean_all = _seeded_nodes(
            _request("campaign-clean", read_scope="campaign_all"),
            db_path,
        )
        memory_off = _seeded_nodes(
            _request("campaign-clean", read_scope="none"),
            db_path,
        )

    hint_request = DiscoveryRequest(
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
    scorer = service._build_scorer(hint_request, "companies")
    trusted_sources = set(scorer.config.trusted_sources if scorer.config else [])

    checks = {
        "cross_campaign_blocked": "POISONED_VENDOR_TERM" not in clean_promoted,
        "promoted_memory_available": "CLEAN_VENDOR_TERM" in clean_promoted,
        "quarantine_blocked": "UNREVIEWED_TERM" not in clean_promoted,
        "campaign_all_explicitly_reads_quarantine": "UNREVIEWED_TERM" in clean_all,
        "memory_off_reads_nothing": not memory_off,
        "source_hint_cannot_self_declare_trust": "attacker.invalid" not in trusted_sources,
    }
    return {
        "experiment_id": "execution-isolation-adversarial",
        "checks": checks,
        "passed": all(checks.values()),
        "observed": {
            "campaign_promoted_nodes": sorted(clean_promoted),
            "campaign_all_nodes": sorted(clean_all),
            "memory_off_nodes": sorted(memory_off),
            "trusted_sources": sorted(trusted_sources),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_experiment()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
