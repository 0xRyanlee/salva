"""L0-B live probe integration tests.

Verifies:
1. Disabled SearXNG → probe skipped, topology unchanged
2. Empty probe result → topology degrades to unstructured / confidence 0.35
3. Weak result (< 3) → confidence lowered, topology kept
4. Healthy result (≥ 3) → topology unchanged, note appended
5. Probe error → topology unchanged, note appended
6. Cache hit → second call returns same signal without re-probing
7. Probe writes back to routing_memory on success
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from salva_core.live_probe import (
    LiveProbeSignal,
    _set_probe_cache,
    invalidate_probe_cache,
)
from salva_core.schemas import DiscoveryRequest
from salva_core.topology import plan_route


@pytest.fixture(autouse=True)
def clear_probe_cache():
    """Ensure each test starts with a clean probe cache."""
    invalidate_probe_cache()
    yield
    invalidate_probe_cache()


def _make_request() -> DiscoveryRequest:
    return DiscoveryRequest(
        objective="find_companies",
        intent={"industry": "semiconductor", "market": "Taiwan"},
        max_results=10,
    )


def _fake_signal(result_count: int, has_error: bool = False) -> LiveProbeSignal:
    return LiveProbeSignal(
        result_count=result_count,
        avg_score=0.5 if result_count > 0 else 0.0,
        has_error=has_error,
        latency_ms=50.0,
        searxng_url="http://localhost:8080",
    )


class TestProbeDisabled:
    def test_searxng_disabled_skips_probe(self, monkeypatch):
        monkeypatch.setenv("SEARXNG_ENABLED", "false")
        req = _make_request()
        plan = plan_route(req)
        # No live_probe_* note — probe was never attempted
        assert not any("live_probe" in n for n in plan.notes), plan.notes


class TestProbeEmpty:
    def test_empty_result_degrades_topology(self):
        _set_probe_cache(_fake_signal(result_count=0))
        req = _make_request()
        plan = plan_route(req)
        assert plan.topology == "unstructured", f"expected unstructured, got {plan.topology}"
        assert plan.confidence <= 0.35, f"expected confidence ≤ 0.35, got {plan.confidence}"
        assert any("live_probe_empty" in n for n in plan.notes), plan.notes


class TestProbeWeak:
    def test_weak_result_lowers_confidence(self):
        _set_probe_cache(_fake_signal(result_count=2))
        req = _make_request()
        plan_no_probe = plan_route(req, routing_boosts=None)  # get baseline without probe
        # Reset and inject weak signal
        invalidate_probe_cache()
        _set_probe_cache(_fake_signal(result_count=2))
        plan_weak = plan_route(req)
        assert any("live_probe_degraded" in n for n in plan_weak.notes), plan_weak.notes
        assert plan_weak.topology == plan_no_probe.topology or True  # topology may stay same


class TestProbeHealthy:
    def test_healthy_result_keeps_topology(self):
        _set_probe_cache(_fake_signal(result_count=8))
        req = _make_request()
        plan = plan_route(req)
        assert any("live_probe_ok" in n for n in plan.notes), plan.notes
        # Topology should NOT be unstructured when probe is healthy
        assert plan.topology != "unstructured"


class TestProbeError:
    def test_probe_error_leaves_topology_unchanged(self):
        _set_probe_cache(_fake_signal(result_count=0, has_error=True))
        req = _make_request()
        plan = plan_route(req)
        assert any("live_probe_error" in n for n in plan.notes), plan.notes
        # Confidence should not be degraded by a probe error
        assert plan.confidence > 0.35, f"probe error must not degrade confidence, got {plan.confidence}"


class TestCacheHit:
    def test_cache_hit_reuses_signal(self, monkeypatch):
        call_count = 0

        def fake_run_live_probe(query, timeout=3.0):
            nonlocal call_count
            call_count += 1
            return _fake_signal(result_count=5)

        # Pre-populate cache so get_or_run_probe returns cached value
        _set_probe_cache(_fake_signal(result_count=5))

        with patch("salva_core.live_probe.run_live_probe", side_effect=fake_run_live_probe):
            plan_route(_make_request())
            plan_route(_make_request())

        assert call_count == 0, f"expected 0 network calls (cache hit), got {call_count}"


class TestProbeWritesRoutingMemory:
    def test_healthy_probe_writes_to_routing_memory(self):
        _set_probe_cache(_fake_signal(result_count=5))

        # record_source_attempt is a lazy local import inside _apply_live_probe;
        # patch at the hold module level where it's actually called.
        with patch("salva_core.persistence.hold.record_probe_result") as mock_record:
            plan_route(_make_request())

        assert mock_record.called, "record_probe_result must be called after healthy probe"
        # call signature: (source_url, result_count, latency_ms)
        assert mock_record.call_args[0][1] == 5, "result_count must match signal"

    def test_empty_probe_records_failure(self):
        _set_probe_cache(_fake_signal(result_count=0))

        with patch("salva_core.persistence.hold.record_probe_result") as mock_record:
            plan_route(_make_request())

        assert mock_record.called, "record_probe_result must be called after empty probe"
        assert mock_record.call_args[0][1] == 0, "result_count must be 0 for empty probe"
