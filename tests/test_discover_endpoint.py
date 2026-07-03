from fastapi.testclient import TestClient

from apps.api import main
from salva_core.schemas import CanonicalEntity, CanonicalRelation, TelemetryRecord


def test_discover_endpoint_uses_runtime(monkeypatch) -> None:
    def fake_run_discovery(_payload):
        return (
            [
                CanonicalEntity(
                    entity_id="lead:1",
                    entity_type="lead",
                    title="Example Lead",
                    source_urls=["https://example.com"],
                )
            ],
            [
                CanonicalRelation(
                    relation_id="rel:1",
                    relation_type="related_to",
                    from_entity_id="lead:1",
                    to_entity_id="source:1",
                )
            ],
            [
                TelemetryRecord(
                    query="example query",
                    round_num=1,
                    strategy="dive",
                    results_total=10,
                    results_qualified=1,
                )
            ],
            {"qualified_count": 1},
        )

    monkeypatch.setattr(main.service, "run_discovery", fake_run_discovery)

    client = TestClient(main.app)
    response = client.post(
        "/v1/discover",
        json={
            "objective": "find_leads",
            "intent": {
                "market": "Germany",
                "industry": "software",
                "product": "crm",
                "role": "reseller",
            },
            "output_profile": "lead",
            "max_results": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entities"][0]["title"] == "Example Lead"
    assert body["relations"][0]["relation_type"] == "related_to"
    assert body["telemetry"][0]["query"] == "example query"
    assert body["meta"]["qualified_count"] == 1


def test_discover_endpoint_accepts_stability_policy(monkeypatch) -> None:
    """REST /v1/discover accepts the opt-in `stability` field with zero extra
    route code -- DiscoveryRequest.stability is a real Pydantic field, so
    FastAPI's request schema already covers it."""
    captured = {}

    def fake_run_discovery(payload):
        captured["payload"] = payload
        return ([], [], [], {"qualified_count": 0})

    monkeypatch.setattr(main.service, "run_discovery", fake_run_discovery)

    client = TestClient(main.app)
    response = client.post(
        "/v1/discover",
        json={
            "objective": "find_companies",
            "intent": {"market": "US", "industry": "AI"},
            "stability": {"enabled": True, "min_history": 5, "penalty_strength": 0.2},
        },
    )

    assert response.status_code == 200
    assert captured["payload"].stability is not None
    assert captured["payload"].stability.enabled is True
    assert captured["payload"].stability.min_history == 5
    assert captured["payload"].stability.penalty_strength == 0.2


def test_discover_endpoint_stability_defaults_to_none(monkeypatch) -> None:
    captured = {}

    def fake_run_discovery(payload):
        captured["payload"] = payload
        return ([], [], [], {"qualified_count": 0})

    monkeypatch.setattr(main.service, "run_discovery", fake_run_discovery)

    client = TestClient(main.app)
    response = client.post(
        "/v1/discover",
        json={"objective": "find_companies", "intent": {"market": "US", "industry": "AI"}},
    )

    assert response.status_code == 200
    assert captured["payload"].stability is None
