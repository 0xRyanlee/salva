import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from apps.api import main
from salva_core.navigation import build_mate_report, build_pilot_advice
from salva_core.persistence import persist_discovery_run
from salva_core.schemas import (
    CanonicalEntity,
    DiscoveryIntent,
    DiscoveryRequest,
    MatePricing,
    MateReport,
    MateRequest,
    PilotRequest,
    RetrievalPolicy,
    TelemetryRecord,
)


def _make_request(objective: str = "find_leads", output_profile: str = "lead") -> DiscoveryRequest:
    return DiscoveryRequest(
        objective=objective,
        intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        output_profile=output_profile,
        retrieval=RetrievalPolicy(),
    )


def test_build_mate_report_estimates_savings(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=_make_request(),
        entities=[CanonicalEntity(entity_id="lead:1", entity_type="lead", title="Example Lead")],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=12,
                results_qualified=4,
                avg_score=0.7,
            )
        ],
        meta={
            "qualified_count": 4,
            "raw_count": 12,
            "provider_kinds": ["searxng"],
            "experience_profile": "lead_focus",
        },
        source_attempts=[],
        path=db_path,
    )

    report = build_mate_report(
        run_id,
        payload=MateRequest(pricing=MatePricing(usd_per_1k_tokens=0.02)),
        path=db_path,
    )

    assert report.estimated_candidate_units_saved == 8
    assert report.estimated_tokens_saved == 9600
    assert report.estimated_api_cost_saved == 0.192
    assert report.pricing_applied is True
    assert report.generation_latency_ms >= 0


def test_build_mate_report_uses_pricing_catalog(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    catalog_path = tmp_path / "pricing.json"
    catalog_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "source_name": "demo-catalog",
                "source_url": "https://pricing.example/api",
                "entries": [
                    {
                        "provider_name": "openai",
                        "model_name": "gpt-4.1-mini",
                        "usd_per_1k_tokens": 0.01,
                        "currency": "USD",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_id = persist_discovery_run(
        request=_make_request(),
        entities=[],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 0, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    report = build_mate_report(
        run_id,
        payload=MateRequest(
            pricing=MatePricing(
                provider_name="openai",
                model_name="gpt-4.1-mini",
                pricing_catalog_path=str(catalog_path),
            )
        ),
        path=db_path,
    )

    assert report.pricing_applied is True
    assert report.pricing_source_name == "demo-catalog"
    assert report.pricing_source_latency_ms is not None


def test_build_mate_report_skips_cost_for_local_provider(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=_make_request(),
        entities=[],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 0, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    report = build_mate_report(
        run_id,
        payload=MateRequest(
            pricing=MatePricing(
                provider_name="omlx",
                model_name="local-mini",
            )
        ),
        path=db_path,
    )

    assert report.pricing_applied is False
    assert report.estimated_api_cost_saved is None
    assert report.estimated_tokens_saved > 0


def test_build_pilot_advice_suggests_route_switch(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=_make_request("find_events", "event"),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="expo tokyo",
                round_num=1,
                strategy="radar",
                results_total=20,
                results_qualified=1,
                avg_score=0.2,
                noise_domains=["spam.example"],
            )
        ],
        meta={
            "qualified_count": 1,
            "raw_count": 20,
            "provider_kinds": ["searxng"],
            "experience_profile": "event_discovery",
            "plugin_report_count": 0,
        },
        source_attempts=[],
        path=db_path,
    )

    advice = build_pilot_advice(PilotRequest(run_id=run_id, max_suggestions=4), path=db_path)

    assert advice.recommended_retrieval_mode == "wall_guarded"
    assert advice.recommended_experience_profile == "event_discovery"
    assert advice.topology == "vertical"
    assert advice.recommended_route == "event_discovery"
    assert advice.round_budget >= 1
    assert advice.clarification_mode in {"rule", "agent"}
    assert advice.stop_conditions
    assert advice.next_queries
    assert "vertical" in advice.human_prompt
    assert "event_discovery" in advice.human_prompt
    assert advice.generation_latency_ms >= 0


def test_build_pilot_advice_applies_context_overrides(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=_make_request("find_leads", "lead"),
        entities=[],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 0, "raw_count": 0, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    advice = build_pilot_advice(
        PilotRequest(
            run_id=run_id,
            market="Taiwan",
            industry="hardware",
            objective="find_companies",
            max_suggestions=3,
        ),
        path=db_path,
    )

    assert advice.objective == "find_companies"
    assert advice.preferred_domains == []
    assert advice.topology == "concentrated"
    assert advice.recommended_route == "company_research"
    assert advice.round_budget >= 1
    assert advice.clarification_mode in {"rule", "agent"}
    assert advice.stop_conditions
    assert "Taiwan" in advice.human_prompt or "Taiwan" in advice.agent_prompt
    assert "hardware" in advice.human_prompt or "hardware" in advice.agent_prompt


def test_build_pilot_advice_requests_clarification_for_ambiguous_goals(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    run_id = persist_discovery_run(
        request=_make_request("find_market_activity", "activity_signal"),
        entities=[],
        relations=[],
        telemetry=[],
        meta={"qualified_count": 0, "raw_count": 0, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    advice = build_pilot_advice(PilotRequest(run_id=run_id, max_suggestions=5), path=db_path)

    assert advice.topology in {"distributed", "broad", "mixed"}
    assert advice.needs_clarification is True
    assert advice.clarification_mode == "agent"
    assert advice.round_budget >= 2
    assert advice.clarifying_questions
    assert advice.replan_triggers
    assert "澄清問題" in advice.human_prompt
    assert "clarification_mode" in advice.agent_prompt


def test_mate_and_pilot_api_endpoints(monkeypatch) -> None:
    def fake_mate_report(run_id: str, payload: MateRequest | None = None, path: str | None = None):
        return MateReport(
            run_id=run_id,
            objective="find_leads",
            output_profile="lead",
            experience_profile="lead_focus",
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    monkeypatch.setattr(main, "build_mate_report", fake_mate_report)

    client = TestClient(main.app)
    mate_response = client.post("/v1/mate/run:demo", json={"pricing": {"usd_per_1k_tokens": 0.02}})
    assert mate_response.status_code == 200
    assert mate_response.json()["run_id"] == "run:demo"

    response = client.post(
        "/v1/pilot",
        json={
            "discovery": {
                "objective": "find_leads",
                "intent": {
                    "market": "Germany",
                    "industry": "software",
                    "product": "crm",
                    "role": "reseller",
                },
                "output_profile": "lead",
                "retrieval": {"mode": "resilient"},
                "enrichment": {"mode": "auto"},
                "max_results": 10,
            },
            "mode": "human",
            "max_suggestions": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["objective"] == "find_leads"


def test_pricing_catalog_api_returns_resolved_quote(tmp_path) -> None:
    catalog_path = tmp_path / "pricing.json"
    catalog_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-01T00:00:00+00:00",
                "source_name": "demo-catalog",
                "source_url": "https://pricing.example/api",
                "entries": [
                    {
                        "provider_name": "openai",
                        "model_name": "gpt-4.1-mini",
                        "usd_per_1k_tokens": 0.01,
                        "currency": "USD",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    client = TestClient(main.app)
    response = client.get(
        "/v1/pricing-catalog",
        params={
            "provider_name": "openai",
            "model_name": "gpt-4.1-mini",
            "catalog_path": str(catalog_path),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resolved"] is True
    assert body["resolved_quote"]["usd_per_1k_tokens"] == 0.01
