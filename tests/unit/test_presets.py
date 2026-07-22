from __future__ import annotations

from pathlib import Path

from salva_core.presets import build_preset_catalog, load_preset_profiles, resolve_preset_profile


def test_load_preset_profiles_from_custom_dir(tmp_path: Path) -> None:
    preset_dir = tmp_path / "presets"
    preset_dir.mkdir()
    (preset_dir / "custom.json").write_text(
        """
        {
          "name": "custom_preset",
          "title": "Custom Preset",
          "description": "Custom test preset.",
          "experience_profile": "quick_scan",
          "objective": "find_leads",
          "output_profile": "lead",
          "retrieval_mode": "resilient",
          "enrichment_mode": "auto",
          "prompt_patch": ["test patch"],
          "next_steps": ["test next step"],
          "preferred_domains": ["example.com"],
          "notes": ["test note"]
        }
        """,
        encoding="utf-8",
    )

    items = load_preset_profiles(preset_dir)

    assert len(items) == 1
    assert items[0].name == "custom_preset"
    assert items[0].source_path is not None
    assert items[0].source_path.endswith("custom.json")


def test_load_preset_profiles_falls_back_to_builtin_when_dir_empty(tmp_path: Path) -> None:
    preset_dir = tmp_path / "empty-presets"
    preset_dir.mkdir()

    items = load_preset_profiles(preset_dir)

    assert len(items) >= 6
    assert {item.name for item in items} >= {
        "quick_scan",
        "lead_focus",
        "event_discovery",
        "company_research",
        "deep_investigation",
        "platform_integrator",
    }


def test_build_preset_catalog_reports_source_dir(tmp_path: Path) -> None:
    preset_dir = tmp_path / "presets"
    preset_dir.mkdir()
    (preset_dir / "lead.json").write_text(
        """
        {
          "name": "lead_focus_custom",
          "title": "Lead Focus Custom",
          "description": "Lead-focused preset for tests.",
          "experience_profile": "lead_focus",
          "objective": "find_leads",
          "output_profile": "lead",
          "retrieval_mode": "resilient",
          "enrichment_mode": "auto"
        }
        """,
        encoding="utf-8",
    )

    catalog = build_preset_catalog(preset_dir)

    assert catalog.total == 1
    assert catalog.source_dir == str(preset_dir)
    assert catalog.items[0].name == "lead_focus_custom"


def test_resolve_preset_profile_matches_name_or_profile(tmp_path: Path) -> None:
    preset_dir = tmp_path / "presets"
    preset_dir.mkdir()
    (preset_dir / "platform.json").write_text(
        """
        {
          "name": "platform_integrator_custom",
          "title": "Platform Integrator Custom",
          "description": "Platform preset for tests.",
          "experience_profile": "platform_integrator",
          "objective": "find_companies",
          "output_profile": "company_profile",
          "retrieval_mode": "resilient",
          "enrichment_mode": "selected"
        }
        """,
        encoding="utf-8",
    )

    by_name = resolve_preset_profile("platform_integrator_custom", preset_dir)
    by_profile = resolve_preset_profile("platform_integrator", preset_dir)

    assert by_name is not None
    assert by_profile is not None
    assert by_name.title == "Platform Integrator Custom"
    assert by_profile.name == "platform_integrator_custom"
