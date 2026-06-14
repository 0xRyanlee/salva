from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api import main
from salva_core.mode_resolver import resolve_experience_plan
from salva_core.schemas import (
    DiscoveryIntent,
    DiscoveryRequest,
    RetrievalPolicy,
    TopologyProbeRequest,
)
from salva_core.topology import build_topology_probe_response


def test_topology_probe_classifies_semantic_union_and_plans_deep_route() -> None:
    request = DiscoveryRequest(
        objective="find_partnership_signals",
        intent=DiscoveryIntent(
            market="Taipei",
            industry="AI",
            product="assistant",
            role="partner",
        ),
        retrieval=RetrievalPolicy(),
    )

    response = build_topology_probe_response(TopologyProbeRequest(discovery=request))

    assert response.probe.topology == "semantic_union"
    assert response.plan.recommended_route == "deep_investigation"
    assert response.plan.route_entry is not None
    assert response.plan.route_entry.name == "deep_investigation"
    assert response.plan.error_surface
    assert response.plan.error_surface[0].stage == "probe"
    assert response.probe.probe_queries


def test_topology_probe_pushes_company_profile_targets_toward_platform_integrator() -> None:
    request = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(
            market="Taipei",
            industry="AI",
            constraints={"site_domains": ["example.com"]},
        ),
        output_profile="company_profile",
        retrieval=RetrievalPolicy(),
    )

    plan = resolve_experience_plan(request)

    assert plan.topology == "vertical"
    assert plan.profile == "platform_integrator"
    assert plan.topology_confidence > 0


def test_topology_probe_api_roundtrip() -> None:
    client = TestClient(main.app)
    response = client.post(
        "/v1/topology/probe",
        json={
            "caller_preset": "human",
            "probe_budget": 3,
            "discovery": {
                "objective": "find_companies",
                "intent": {
                    "market": "Taipei",
                    "industry": "AI",
                    "constraints": {"site_domains": ["example.com"]},
                },
                "output_profile": "company_profile",
                "retrieval": {"mode": "resilient"},
                "enrichment": {"mode": "auto"},
                "max_results": 20,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["probe"]["topology"] == "vertical"
    assert body["plan"]["recommended_route"] == "platform_integrator"
    assert body["plan"]["route_entry"]["name"] == "platform_integrator"
