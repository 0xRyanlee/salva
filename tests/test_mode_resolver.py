from fastapi.testclient import TestClient

from apps.api import main
from salva_core.mode_resolver import explain_experience_plan, resolve_experience_plan
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, ExperiencePlanRequest, RetrievalPolicy


def test_resolve_experience_plan_prefers_event_discovery_for_events() -> None:
    request = DiscoveryRequest(
        objective="find_events",
        intent=DiscoveryIntent(market="Berlin", industry="events", product=None, role=None),
        retrieval=RetrievalPolicy(),
    )

    plan = resolve_experience_plan(request)

    assert plan.profile == "event_discovery"
    assert plan.primary_ux == "活動發現"
    assert "recall_oriented_path" in plan.notes


def test_resolve_experience_plan_flags_custom_provider_chain() -> None:
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(
            market="Germany",
            industry="software",
            product="crm",
            role="reseller",
        ),
        retrieval=RetrievalPolicy(providers=[]),
    )

    plan = resolve_experience_plan(request)

    assert plan.profile == "lead_focus"
    assert plan.primary_ux == "線索聚焦"
    assert "precision_oriented_path" in plan.notes


def test_explain_experience_plan_includes_prompt_patch() -> None:
    request = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(market="Taipei", industry="design"),
        output_profile="company_profile",
        retrieval=RetrievalPolicy(),
    )

    explanation = explain_experience_plan(request, caller_preset="agent")

    assert explanation.plan.profile == "platform_integrator"
    assert explanation.caller_preset == "agent"
    assert explanation.prompt_patch
    assert explanation.next_steps[0].startswith("agent_hint:")
    assert "platform_integrator" in explanation.summary


def test_experience_plan_api_roundtrip() -> None:
    client = TestClient(main.app)
    response = client.post(
        "/v1/experience-plan",
        json={
            "caller_preset": "human",
            "discovery": {
                "objective": "find_events",
                "intent": {
                    "market": "Berlin",
                    "industry": "events",
                },
                "output_profile": "event",
                "retrieval": {"mode": "resilient"},
                "enrichment": {"mode": "auto"},
                "max_results": 10,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["profile"] == "event_discovery"
    assert body["caller_preset"] == "human"
    assert body["prompt_patch"]
