from fastapi.testclient import TestClient

from apps.api import main
from salva_core.schemas import CanonicalEntity, DiscoveryRequest, TelemetryRecord


def test_discover_endpoint_reports_experience_meta(monkeypatch) -> None:
    def fake_run_discovery(_payload: DiscoveryRequest):
        return (
            [
                CanonicalEntity(
                    entity_id="lead:1",
                    entity_type="lead",
                    title="Example Lead",
                    source_urls=["https://example.com"],
                )
            ],
            [],
            [
                TelemetryRecord(
                    query="example query",
                    round_num=1,
                    strategy="dive",
                    results_total=10,
                    results_qualified=1,
                )
            ],
            {
                "qualified_count": 1,
                "experience_profile": "lead_focus",
                "experience_ux": "線索聚焦",
            },
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
            "retrieval": {
                "mode": "resilient"
            },
            "enrichment": {
                "mode": "auto"
            },
            "max_results": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["experience_profile"] == "lead_focus"
