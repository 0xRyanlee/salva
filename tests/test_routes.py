from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apps.api import main
from salva_core.routes import build_route_catalog, resolve_route_entry


def test_build_route_catalog_contains_canonical_profiles() -> None:
    catalog = build_route_catalog()

    assert catalog.total >= 6
    names = {item.name for item in catalog.items}
    assert {"quick_scan", "lead_focus", "event_discovery", "company_research", "deep_investigation", "platform_integrator"}.issubset(names)
    deep = next(item for item in catalog.items if item.name == "deep_investigation")
    assert "pirate" in deep.strategy_rotation
    assert "POST /v1/jobs" in deep.recommended_call_surfaces


def test_resolve_route_entry_matches_name_or_profile(tmp_path: Path) -> None:
    preset_dir = tmp_path / "presets"
    preset_dir.mkdir()
    (preset_dir / "custom.json").write_text(
        """
        {
          "name": "route_custom",
          "title": "Route Custom",
          "description": "Custom route for testing.",
          "experience_profile": "platform_integrator",
          "objective": "find_companies",
          "output_profile": "company_profile",
          "retrieval_mode": "resilient",
          "enrichment_mode": "selected"
        }
        """,
        encoding="utf-8",
    )

    by_name = resolve_route_entry("route_custom", preset_dir)
    by_profile = resolve_route_entry("platform_integrator", preset_dir)

    assert by_name is not None
    assert by_profile is not None
    assert by_name.title == "Route Custom"
    assert by_profile.name == "route_custom"


def test_routes_api_roundtrip() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/routes")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 6
    assert any(item["name"] == "quick_scan" for item in body["items"])
