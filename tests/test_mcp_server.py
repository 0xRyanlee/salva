import importlib.util

from apps.mcp import server


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
