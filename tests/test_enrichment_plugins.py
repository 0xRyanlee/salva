from types import SimpleNamespace

import enrichment.plugins as plugin_module
import enrichment.omlx as omlx_module
from enrichment.plugins import AmassPlugin, PluginRegistry, SiteHTMLPlugin, SpiderFootPlugin, TheHarvesterPlugin, enrich_entities
from salva_core.schemas import CanonicalEntity, DiscoveryIntent, DiscoveryRequest


def test_plugin_registry_auto_mode_resolves_default_plugins() -> None:
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software"),
    )
    plugins = PluginRegistry().resolve(request)
    names = [plugin.name for plugin in plugins]
    assert "omlx" in names
    assert "site_html" in names


def test_enrich_entities_returns_plugin_reports() -> None:
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software"),
    )
    entity = CanonicalEntity(
        entity_id="lead:1",
        entity_type="lead",
        title="Example Lead",
        summary="",
        source_urls=["https://example.com/contact"],
        attributes={"description": "Reseller profile"},
    )
    entities, reports = enrich_entities([entity], request)
    assert len(entities) == 1
    assert len(reports) >= 1
    assert any(report.plugin == "site_html" for report in reports)


def test_plugin_registry_selected_mode() -> None:
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software"),
        enrichment={"mode": "selected", "enabled_plugins": ["amass"]},
    )
    plugins = PluginRegistry().resolve(request)
    assert [plugin.name for plugin in plugins] == ["amass"]


def test_command_plugins_only_run_on_high_value_targets(monkeypatch) -> None:
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software"),
        enrichment={"mode": "selected", "enabled_plugins": ["amass"], "max_targets": 4},
    )
    entities = [
        CanonicalEntity(entity_id="lead:1", entity_type="lead", title="Low", score=0.1, confidence=0.1, source_urls=["https://a.example"]),
        CanonicalEntity(entity_id="lead:2", entity_type="lead", title="High A", score=0.9, confidence=0.9, source_urls=["https://b.example"]),
        CanonicalEntity(entity_id="lead:3", entity_type="lead", title="High B", score=0.8, confidence=0.8, source_urls=["https://c.example"]),
        CanonicalEntity(entity_id="lead:4", entity_type="lead", title="High C", score=0.7, confidence=0.7, source_urls=["https://d.example"]),
    ]
    calls: list[str] = []

    monkeypatch.setattr(AmassPlugin, "is_available", lambda self: True)
    monkeypatch.setattr(AmassPlugin, "applies_to", lambda self, entity, request: True)

    def fake_enrich(self, entity, request):
        calls.append(entity.entity_id)
        return plugin_module.PluginOutcome(
            plugin=self.name,
            target_entity_id=entity.entity_id,
            status="completed",
            applied=True,
        )

    monkeypatch.setattr(AmassPlugin, "enrich", fake_enrich)

    enriched_entities, reports = enrich_entities(entities, request)

    assert [entity.entity_id for entity in enriched_entities[:4]] == ["lead:1", "lead:2", "lead:3", "lead:4"]
    assert calls[0] == "lead:2"
    assert set(calls) == {"lead:2", "lead:3", "lead:4"}
    assert sum(1 for report in reports if report.plugin == "amass" and report.applied) == 3


def test_command_plugins_require_domain_target() -> None:
    entity = CanonicalEntity(
        entity_id="lead:1",
        entity_type="lead",
        title="Example Lead",
        source_urls=["https://example.com/contact"],
        attributes={},
    )
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software"),
    )
    assert TheHarvesterPlugin().applies_to(entity, request) is True
    assert AmassPlugin().applies_to(entity, request) is True
    site_outcome = SiteHTMLPlugin().enrich(entity, request)
    assert site_outcome.applied is True


def test_spiderfoot_plugin_parses_json_output(monkeypatch) -> None:
    entity = CanonicalEntity(
        entity_id="lead:2",
        entity_type="lead",
        title="Example Lead",
        source_urls=["https://example.com/contact"],
        attributes={},
    )
    request = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software"),
    )

    monkeypatch.setattr(SpiderFootPlugin, "command_path", lambda self: "sf.py")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout='[{"Source":"example.com","Type":"DOMAIN_NAME","Data":"example.com"}]',
            stderr="",
        )

    monkeypatch.setattr(plugin_module.subprocess, "run", fake_run)

    outcome = SpiderFootPlugin().enrich(entity, request)
    assert outcome.applied is True
    assert outcome.status == "completed"
    assert outcome.attributes["spiderfoot"]["event_count"] == 1


def test_spiderfoot_plugin_respects_env_command_path(monkeypatch, tmp_path) -> None:
    sf_script = tmp_path / "sf.py"
    sf_script.write_text("#!/usr/bin/env python3\nprint('[]')\n", encoding="utf-8")
    monkeypatch.setenv("SPIDERFOOT_SF_PY", str(sf_script))
    plugin = SpiderFootPlugin()
    assert plugin.command_path() == str(sf_script)


def test_command_plugins_respect_env_command_paths(monkeypatch, tmp_path) -> None:
    theharvester_script = tmp_path / "theharvester"
    theharvester_script.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    amass_script = tmp_path / "amass"
    amass_script.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")

    monkeypatch.setenv("THEHARVESTER_COMMAND", str(theharvester_script))
    monkeypatch.setenv("AMASS_COMMAND", str(amass_script))

    assert TheHarvesterPlugin().command_path() == str(theharvester_script)
    assert AmassPlugin().command_path() == str(amass_script)


def test_omlx_prompt_selection_changes_by_objective(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_bounded_prompt(task, system_prompt, user_prompt, model_name=None, max_tokens=500, temperature=0.3):
        captured["task"] = task
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        captured["model_name"] = model_name
        return SimpleNamespace(
            task=task,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    monkeypatch.setattr(omlx_module, "build_bounded_prompt", fake_build_bounded_prompt)
    monkeypatch.setattr(
        omlx_module,
        "complete_with_omlx",
        lambda bundle, **kwargs: SimpleNamespace(available=True, content='{"summary":"ok","tags":["alpha"]}', message=None),
    )

    request = DiscoveryRequest(
        objective="find_partnership_signals",
        intent=DiscoveryIntent(market="Germany", industry="software"),
    )
    entity = CanonicalEntity(
        entity_id="lead:3",
        entity_type="lead",
        title="Example Lead",
        source_urls=["https://example.com"],
        attributes={"description": "Partner profile"},
    )

    outcome = omlx_module.enrich("bd_leads", {"title": entity.title, "description": "x", "source_url": "https://example.com"}, request=request)

    assert outcome is not None
    assert captured["task"] == "output_shaping"
    assert "partnership" in str(captured["system_prompt"])
    assert "Return company-level descriptors" not in str(captured["system_prompt"])
