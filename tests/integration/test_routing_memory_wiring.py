"""Routing memory write/read integration tests.

Verifies:
1. record_source_attempt writes to routing_memory
2. get_routing_boost reads back the persisted boost
3. list_routing_memory → routing_boosts dict flows into plan_route notes
4. Second run can read what the first run wrote
"""
from __future__ import annotations

import pytest

from salva_core.persistence.hold import (
    get_routing_boost,
    list_routing_memory,
    record_source_attempt,
)


def test_record_success_creates_positive_boost(tmp_path):
    db = str(tmp_path / "r.db")
    record_source_attempt("https://computex.biz", True, path=db)
    record_source_attempt("https://computex.biz", True, path=db)
    boost = get_routing_boost("https://computex.biz", path=db)
    assert boost > 0.05, f"expected positive boost, got {boost}"


def test_record_failure_creates_negative_boost(tmp_path):
    db = str(tmp_path / "r.db")
    record_source_attempt("https://bad-provider.example.com", False, path=db)
    boost = get_routing_boost("https://bad-provider.example.com", path=db)
    assert boost < 0.0, f"expected negative boost, got {boost}"


def test_unknown_source_returns_zero(tmp_path):
    db = str(tmp_path / "r.db")
    assert get_routing_boost("https://never-seen.example.com", path=db) == 0.0


def test_second_run_reads_first_run_boost(tmp_path):
    """Run 2 must see the routing memory written by run 1."""
    db = str(tmp_path / "r.db")

    # Run 1: record successes
    record_source_attempt("http://localhost:8080", True, path=db)
    record_source_attempt("http://localhost:8080", True, path=db)

    # Run 2: load routing_boosts the same way execute_discovery does
    mem = list_routing_memory(top_k=10, path=db)
    boosts = {r["source_url"]: r["authority_boost"] for r in mem if r["authority_boost"] != 0.0}

    assert "http://localhost:8080" in boosts, "second run must find first run's entry"
    assert boosts["http://localhost:8080"] > 0.0, "boost must be positive after two successes"


def test_routing_boosts_appear_in_topology_notes(tmp_path):
    """routing_boosts with positive entries must annotate topology plan notes."""
    from salva_core.schemas import DiscoveryRequest
    from salva_core.topology import plan_route

    db = str(tmp_path / "r.db")
    for _ in range(3):
        record_source_attempt("https://digitimes.com", True, path=db)

    mem = list_routing_memory(top_k=50, path=db)
    boosts = {r["source_url"]: r["authority_boost"] for r in mem if r["authority_boost"] != 0.0}
    assert boosts, "must have at least one boosted source"

    req = DiscoveryRequest(
        objective="find_companies",
        intent={"industry": "semiconductor", "market": "Taiwan"},
        max_results=10,
    )
    plan = plan_route(req, routing_boosts=boosts)
    assert any("routing_memory_active" in n for n in plan.notes), (
        f"expected routing_memory_active in notes, got {plan.notes}"
    )
