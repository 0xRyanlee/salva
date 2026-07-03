import importlib.util
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from apps.mcp import server
from salva_core.schemas import JobRecord


def test_mcp_server_imports_without_optional_dependency() -> None:
    if importlib.util.find_spec("mcp") is None:
        assert server.mcp.available is False
    assert server.mcp.name == "salva-runtime"
    assert "salva_discover" in server.mcp.instructions
    assert callable(server.salva_discover)
    assert callable(server.salva_job_create)
    assert callable(server.salva_job_status)
    assert callable(server.salva_run_result)
    assert callable(server.salva_audit)
    assert callable(server.salva_pilot)


def test_parse_domain_hints_gracefully_handles_bad_json() -> None:
    assert server._parse_domain_hints("") is None
    assert server._parse_domain_hints("{not json}") is None


def test_salve_pilot_forwards_context_overrides(monkeypatch) -> None:
    captured = {}

    class _DummyAdvice:
        def model_dump(self, mode: str = "json", exclude_none: bool = False):
            return {"summary": "ok"}

    def fake_build_pilot_advice(payload, path=None):
        captured["payload"] = payload
        return _DummyAdvice()

    class _DummyRun:
        def get(self, key, default=None):
            if key == "request":
                return {
                    "objective": "find_leads",
                    "output_profile": "lead",
                    "intent": {
                        "market": "Germany",
                        "industry": "software",
                    },
                }
            return default

    monkeypatch.setattr(server, "get_run", lambda run_id: _DummyRun())
    monkeypatch.setattr(server, "build_pilot_advice", fake_build_pilot_advice)

    result = server.salva_pilot(
        run_id="run:demo",
        market="Taiwan",
        industry="hardware",
        objective="find_companies",
        max_suggestions=3,
    )

    assert '"ok": true' in result.lower()
    assert captured["payload"].market == "Taiwan"
    assert captured["payload"].industry == "hardware"
    assert captured["payload"].objective == "find_companies"


# ---------------------------------------------------------------------------
# Smoke coverage for the remaining tools -- apps/mcp/server.py has 14 tools
# total (verified by grep against @mcp.tool()), not the 9 README previously
# listed. The tests above only covered salva_pilot in depth plus a bare
# "callable" check for 5 others; salva_job_cancel, salva_research_report,
# salva_run_diff, salva_graph_export, salva_vocab, salva_topology,
# salva_plugins, salva_providers had zero coverage before this addition.
# No live network / SearXNG / real DB writes -- every salva_core /
# core / retrieval / enrichment call is mocked.
# ---------------------------------------------------------------------------


def _job(status: str = "completed", run_id: str | None = "run-1") -> JobRecord:
    return JobRecord(
        job_id="job-1",
        status=status,
        objective="find_companies",
        output_profile="company_profile",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        request={"objective": "find_companies"},
        run_id=run_id,
        error="boom" if status == "failed" else None,
    )


def _run() -> dict:
    return {
        "objective": "find_companies",
        "output_profile": "company_profile",
        "created_at": "2026-01-01T00:00:00",
        "entities": [
            {
                "entity_id": "e1",
                "title": "Acme Corp",
                "entity_type": "company",
                "domain": "acme.com",
                "confidence": 0.8,
                "source_urls": ["https://acme.com"],
                "description": "A company",
                "score": 0.8,
            }
        ],
        "relations": [
            {"subject_id": "e1", "object_id": "e2", "relation_type": "supplies"},
        ],
        "meta": {"qualified_count": 1, "domain": "companies", "rounds": 1},
        "request": {"objective": "find_companies", "intent": {"market": "US", "industry": "AI"}},
    }


class TestSalvaDiscover:
    def test_returns_ok_with_mocked_discovery(self):
        fake_meta = {"run_id": "run-1", "qualified_count": 0, "retrieval_health": "ok"}
        with patch.object(server, "run_discovery", return_value=([], [], [], fake_meta)):
            body = json.loads(server.salva_discover(market="US", industry="AI"))
        assert body["ok"] is True
        assert body["run_id"] == "run-1"
        assert body["retrieval_health"] == "ok"
        assert body["entities"] == []

    def test_discovery_exception_returns_graceful_error(self):
        with patch.object(server, "run_discovery", side_effect=RuntimeError("db locked")):
            body = json.loads(server.salva_discover(market="US", industry="AI"))
        assert body["ok"] is False
        assert "db locked" in body["error"]

    def test_invalid_objective_raises_before_run_discovery(self):
        """Known gap: DiscoveryRequest construction happens outside the try/except
        that wraps run_discovery(), so an invalid `objective` value raises a
        pydantic ValidationError instead of the tool's usual graceful
        {"error": ..., "ok": False} response. Documents current behavior;
        fixing this error-handling gap is out of scope for this test-coverage
        card."""
        with pytest.raises(ValidationError):
            server.salva_discover(market="US", industry="AI", objective="not_a_real_objective")

    def test_enable_stability_gating_flag_sets_policy_on_request(self):
        captured = {}

        def fake_run_discovery(request):
            captured["request"] = request
            return ([], [], [], {"run_id": "run-1"})

        with patch.object(server, "run_discovery", side_effect=fake_run_discovery):
            server.salva_discover(market="US", industry="AI", enable_stability_gating=True)

        assert captured["request"].stability is not None
        assert captured["request"].stability.enabled is True

    def test_stability_gating_defaults_to_disabled(self):
        captured = {}

        def fake_run_discovery(request):
            captured["request"] = request
            return ([], [], [], {"run_id": "run-1"})

        with patch.object(server, "run_discovery", side_effect=fake_run_discovery):
            server.salva_discover(market="US", industry="AI")

        assert captured["request"].stability is not None
        assert captured["request"].stability.enabled is False


class TestSalvaJobCreate:
    def test_returns_job_id_with_mocked_create_job(self):
        with patch.object(server, "create_job", return_value="job-42"):
            body = json.loads(server.salva_job_create(market="US", industry="AI"))
        assert body["ok"] is True
        assert body["job_id"] == "job-42"
        assert body["status"] == "queued"

    def test_create_job_exception_returns_graceful_error(self):
        with patch.object(server, "create_job", side_effect=RuntimeError("disk full")):
            body = json.loads(server.salva_job_create(market="US", industry="AI"))
        assert body["ok"] is False


class TestSalvaJobStatus:
    def test_unknown_job_returns_graceful_error(self):
        with patch.object(server, "get_job", return_value=None):
            body = json.loads(server.salva_job_status("nope"))
        assert body["ok"] is False
        assert "not found" in body["error"]

    def test_completed_job_includes_run_id_message(self):
        with patch.object(server, "get_job", return_value=_job(status="completed")):
            body = json.loads(server.salva_job_status("job-1"))
        assert body["ok"] is True
        assert body["status"] == "completed"
        assert "salva_run_result" in body["message"]


class TestSalvaJobCancel:
    def test_unknown_job_returns_graceful_error(self):
        with patch.object(server, "get_job", return_value=None):
            body = json.loads(server.salva_job_cancel("nope"))
        assert body["ok"] is False

    def test_completed_job_cannot_be_cancelled(self):
        with patch.object(server, "get_job", return_value=_job(status="completed")):
            body = json.loads(server.salva_job_cancel("job-1"))
        assert body["ok"] is False
        assert "already completed" in body["error"]

    def test_queued_job_cancels_successfully(self):
        with patch.object(server, "get_job", return_value=_job(status="queued")), \
             patch("salva_core.persistence.update_job_status") as mock_update:
            body = json.loads(server.salva_job_cancel("job-1"))
        assert body["ok"] is True
        assert body["status"] == "cancelled"
        assert mock_update.called


class TestSalvaRunResult:
    def test_unknown_run_returns_graceful_error(self):
        with patch.object(server, "get_run", return_value=None):
            body = json.loads(server.salva_run_result("nope"))
        assert body["ok"] is False

    def test_known_run_returns_compact_entities(self):
        with patch.object(server, "get_run", return_value=_run()):
            body = json.loads(server.salva_run_result("run-1"))
        assert body["ok"] is True
        assert body["entity_count"] == 1
        assert body["entities"][0]["title"] == "Acme Corp"


class TestSalvaAudit:
    def test_returns_ok_with_mocked_report(self):
        fake_report = MagicMock()
        fake_report.model_dump.return_value = {"signal_to_noise": 0.5}
        with patch.object(server, "build_audit_report", return_value=fake_report):
            body = json.loads(server.salva_audit("run-1"))
        assert body["ok"] is True
        assert body["audit"]["signal_to_noise"] == 0.5

    def test_audit_exception_returns_graceful_error(self):
        with patch.object(server, "build_audit_report", side_effect=RuntimeError("no such run")):
            body = json.loads(server.salva_audit("nope"))
        assert body["ok"] is False


class TestSalvaPilotAdditional:
    """Complements the pre-existing context-override test above with the
    unknown-run error path, which wasn't covered."""

    def test_unknown_run_returns_graceful_error(self):
        with patch.object(server, "get_run", return_value=None):
            body = json.loads(server.salva_pilot("nope"))
        assert body["ok"] is False


class TestSalvaResearchReport:
    def test_unknown_run_returns_graceful_error(self):
        with patch.object(server, "get_run", return_value=None):
            body = json.loads(server.salva_research_report("nope"))
        assert body["ok"] is False

    def test_known_run_returns_report(self):
        with patch.object(server, "get_run", return_value=_run()), \
             patch("salva_core.transforms.build_research_report", return_value={"summary": "ok"}):
            body = json.loads(server.salva_research_report("run-1"))
        assert body["ok"] is True
        assert body["report"]["summary"] == "ok"


class TestSalvaRunDiff:
    def test_unknown_run_a_returns_graceful_error(self):
        with patch.object(server, "get_run", side_effect=[None, _run()]):
            body = json.loads(server.salva_run_diff("nope", "run-2"))
        assert body["ok"] is False

    def test_diffs_two_known_runs(self):
        run_a = _run()
        run_b = _run()
        run_b["entities"] = [{**run_b["entities"][0], "title": "New Corp", "score": 0.9}]
        with patch.object(server, "get_run", side_effect=[run_a, run_b]):
            body = json.loads(server.salva_run_diff("run-1", "run-2"))
        assert body["ok"] is True
        assert body["added_count"] == 1
        assert body["removed_count"] == 1


class TestSalvaGraphExport:
    def test_unknown_run_returns_graceful_error(self):
        with patch.object(server, "get_run", return_value=None):
            body = json.loads(server.salva_graph_export("nope"))
        assert body["ok"] is False

    def test_hif_export_has_nodes_and_edges(self):
        with patch.object(server, "get_run", return_value=_run()):
            body = json.loads(server.salva_graph_export("run-1"))
        assert body["ok"] is True
        assert body["format"] == "hif"
        assert len(body["nodes"]) == 1

    def test_dot_export_produces_digraph_text(self):
        with patch.object(server, "get_run", return_value=_run()):
            body = json.loads(server.salva_graph_export("run-1", fmt="dot"))
        assert body["ok"] is True
        assert body["dot"].startswith("digraph")


class TestSalvaVocab:
    def test_no_domain_and_no_list_all_returns_graceful_error(self):
        body = json.loads(server.salva_vocab())
        assert body["ok"] is False

    def test_list_all_returns_domains(self):
        fake_vocab = MagicMock(signal_terms=["a"], source_hints=["b"], synonym_groups={})
        with patch("core.domain_vocab.list_domains", return_value=["events"]), \
             patch("core.domain_vocab.get_vocab", return_value=fake_vocab):
            body = json.loads(server.salva_vocab(list_all=True))
        assert body["ok"] is True
        assert body["domains"][0]["name"] == "events"

    def test_specific_domain_returns_vocab(self):
        fake_vocab = MagicMock(
            signal_terms=["s"], source_hints=["h"], noise_terms=["n"],
            synonym_groups={}, region_variants={},
        )
        with patch("core.domain_vocab.get_vocab", return_value=fake_vocab):
            body = json.loads(server.salva_vocab(domain="events"))
        assert body["ok"] is True
        assert body["domain"] == "events"


class TestSalvaTopology:
    def test_returns_probe_and_plan(self):
        fake_probe = MagicMock()
        fake_probe.model_dump.return_value = {"topology": "vertical"}
        fake_plan = MagicMock()
        fake_plan.model_dump.return_value = {"recommended_route": "deep_investigation"}
        fake_response = MagicMock(probe=fake_probe, plan=fake_plan)
        with patch(
            "salva_core.topology.build_topology_probe_response",
            return_value=fake_response,
        ):
            body = json.loads(server.salva_topology(market="US", industry="AI"))
        assert body["ok"] is True
        assert body["probe"]["topology"] == "vertical"
        assert body["plan"]["recommended_route"] == "deep_investigation"


class TestSalvaPlugins:
    def test_returns_plugin_list(self):
        body = json.loads(server.salva_plugins())
        assert body["ok"] is True
        assert isinstance(body["plugins"], list)


class TestSalvaProviders:
    def test_returns_provider_list(self):
        body = json.loads(server.salva_providers())
        assert body["ok"] is True
        assert isinstance(body["providers"], list)
        assert any(p["kind"] == "searxng" for p in body["providers"])
