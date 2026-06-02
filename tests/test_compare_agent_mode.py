from __future__ import annotations

from types import SimpleNamespace

from scripts.compare_agent_mode import compare_modes


class _FakeAdvice:
    def __init__(self, objective: str, profile: str, queries: list[str], summary: str) -> None:
        self.objective = objective
        self.recommended_experience_profile = profile
        self.recommended_retrieval_mode = "wall_guarded" if profile == "company_research" else "resilient"
        self.recommended_enrichment_mode = "selected" if profile == "company_research" else "full"
        self.recommended_output_profile = "company_profile" if profile == "company_research" else "lead"
        self.next_queries = queries
        self.guidance_summary = summary


class _FakeRoute:
    def __init__(self, rotation: list[str]) -> None:
        self.strategy_rotation = rotation

    def model_dump(self, mode: str = "json"):
        return {"strategy_rotation": self.strategy_rotation}


def test_compare_modes_returns_distinct_direct_and_agent_blocks(monkeypatch, tmp_path) -> None:
    def fake_build_pilot_advice(payload, path=None):
        if payload.market == "Taiwan":
            return _FakeAdvice("find_companies", "company_research", ["site:example.com hardware"], "agent-guided")
        return _FakeAdvice("find_leads", "lead_focus", ["software reseller"], "direct")

    monkeypatch.setattr("scripts.compare_agent_mode.build_pilot_advice", fake_build_pilot_advice)
    monkeypatch.setattr("scripts.compare_agent_mode.resolve_experience_plan", lambda discovery: SimpleNamespace(objective=discovery.objective, profile="lead_focus", model_dump=lambda mode="json": {"objective": discovery.objective, "profile": "lead_focus"}))
    monkeypatch.setattr("scripts.compare_agent_mode.resolve_route_entry", lambda name: _FakeRoute([name, "anchor"]))

    report = compare_modes(
        db_path=str(tmp_path / "salva-demo.db"),
        run_id=None,
        market="Germany",
        industry="software",
        objective="find_leads",
        agent_market="Taiwan",
        agent_industry="hardware",
        agent_objective="find_companies",
        max_suggestions=2,
    )

    assert report["base_plan"]["objective"] == "find_leads"
    assert report["direct"]["experience_profile"] == "lead_focus"
    assert report["agent"]["experience_profile"] == "company_research"
    assert report["direct"]["next_queries"] == ["software reseller"]
    assert report["agent"]["next_queries"] == ["site:example.com hardware"]
