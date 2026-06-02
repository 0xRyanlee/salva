from fastapi.testclient import TestClient

from apps.api import main


def test_output_profiles_api_exposes_catalog() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/output-profiles")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 6
    profiles = {item["profile"] for item in body["items"]}
    assert {"lead", "crm_contact", "event", "activity_signal", "company_profile", "company"}.issubset(profiles)
    assert any("Optimized for outreach" in item["notes"][0] for item in body["items"] if item["profile"] == "lead")
