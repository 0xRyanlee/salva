from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api import main
from salva_core.live_probe import invalidate_probe_cache
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


def test_topology_probe_marks_retrieval_health_probe_failed_on_connection_failure(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SEARXNG_ENABLED", "true")
    invalidate_probe_cache()

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

    def failing_http_get(*args, **kwargs):
        raise ConnectionError("connection refused")

    with patch("retrieval.sources.searxng.http_get", side_effect=failing_http_get):
        response = build_topology_probe_response(TopologyProbeRequest(discovery=request))

    assert response.probe.retrieval_health == "probe_failed"
    assert response.plan.retrieval_health == "probe_failed"
    # Static classification must still be preserved, not silently degraded.
    assert response.probe.topology == "vertical"


def test_topology_probe_retrieval_health_defaults_to_ok_for_caller_preset() -> None:
    request = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(market="Taipei", industry="AI"),
    )
    response = build_topology_probe_response(
        TopologyProbeRequest(discovery=request, caller_preset="human")
    )
    # caller_preset skips the live probe entirely -- no degrade possible.
    assert response.probe.retrieval_health == "ok"
