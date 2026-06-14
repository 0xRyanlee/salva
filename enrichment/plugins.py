from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast
from urllib.parse import urlparse

from enrichment.omlx import enrich as omlx_enrich
from salva_core.schemas import (
    CanonicalEntity,
    DiscoveryRequest,
    EnrichmentPluginName,
    PluginDescriptor,
    PluginReportRecord,
)

DEFAULT_COMMAND_TIMEOUT = int(os.getenv("SALVA_PLUGIN_COMMAND_TIMEOUT", "20"))
DEEP_ENRICH_TARGET_LIMIT = int(os.getenv("SALVA_DEEP_ENRICH_TARGET_LIMIT", "3"))


@dataclass
class PluginOutcome:
    plugin: EnrichmentPluginName
    target_entity_id: str
    status: str
    applied: bool = False
    message: str | None = None
    summary: str | None = None
    tags: list[str] = field(default_factory=list)
    attributes: dict[str, object] = field(default_factory=dict)


class EnrichmentPlugin(Protocol):
    name: EnrichmentPluginName
    default_auto_enabled: bool
    supported_entity_types: set[str]
    execution_mode: str

    def is_available(self) -> bool: ...
    def applies_to(self, entity: CanonicalEntity, request: DiscoveryRequest) -> bool: ...
    def enrich(self, entity: CanonicalEntity, request: DiscoveryRequest) -> PluginOutcome: ...
    def describe(self) -> PluginDescriptor: ...


class OMLXPlugin:
    name: Literal["omlx"] = "omlx"
    default_auto_enabled = True
    supported_entity_types = {"lead", "company", "event", "activity_signal"}
    execution_mode = "local_llm"

    def is_available(self) -> bool:
        return True

    def applies_to(self, entity: CanonicalEntity, request: DiscoveryRequest) -> bool:
        return entity.entity_type in self.supported_entity_types

    def enrich(self, entity: CanonicalEntity, request: DiscoveryRequest) -> PluginOutcome:
        domain = "events" if entity.entity_type == "event" else "bd_leads"
        fields = {
            "title": entity.title,
            "description": entity.attributes.get("description") or entity.summary or "",
            "location": entity.attributes.get("location_name") or entity.attributes.get("city") or "",
            "starts_at": entity.attributes.get("starts_at") or "",
            "price": entity.attributes.get("price_amount") or "",
            "source_url": entity.source_urls[0] if entity.source_urls else "",
        }
        result = omlx_enrich(domain, fields)
        if not result:
            return PluginOutcome(
                plugin=self.name,
                target_entity_id=entity.entity_id,
                status="no_result",
                message="OMLX 未返回可解析結果。",
            )
        summary = result.get("summary")
        raw_tags = result.get("tags")
        tags = raw_tags if isinstance(raw_tags, list) else []
        return PluginOutcome(
            plugin=self.name,
            target_entity_id=entity.entity_id,
            status="completed",
            applied=True,
            summary=summary if isinstance(summary, str) else None,
            tags=[str(tag) for tag in tags],
            attributes={"omlx": result},
        )

    def describe(self) -> PluginDescriptor:
        return PluginDescriptor(
            name=self.name,
            available=self.is_available(),
            default_auto_enabled=self.default_auto_enabled,
            execution_mode=self.execution_mode,
            supported_entity_types=sorted(self.supported_entity_types),
            notes="本地 OMLx LLM enrich。",
        )


class SiteHTMLPlugin:
    name: Literal["site_html"] = "site_html"
    default_auto_enabled = True
    supported_entity_types = {"lead", "company", "event", "activity_signal"}
    execution_mode = "derived_metadata"

    def is_available(self) -> bool:
        return True

    def applies_to(self, entity: CanonicalEntity, request: DiscoveryRequest) -> bool:
        return bool(entity.source_urls)

    def enrich(self, entity: CanonicalEntity, request: DiscoveryRequest) -> PluginOutcome:
        if not entity.source_urls:
            return PluginOutcome(plugin=self.name, target_entity_id=entity.entity_id, status="skipped", message="無來源網址。")
        parsed = urlparse(entity.source_urls[0])
        path_segments = [segment for segment in parsed.path.split("/") if segment]
        return PluginOutcome(
            plugin=self.name,
            target_entity_id=entity.entity_id,
            status="completed",
            applied=True,
            attributes={
                "site_html": {
                    "domain": parsed.netloc,
                    "path_depth": len(path_segments),
                    "path_segments": path_segments[:6],
                    "scheme": parsed.scheme,
                }
            },
            tags=[parsed.netloc] if parsed.netloc else [],
        )

    def describe(self) -> PluginDescriptor:
        return PluginDescriptor(
            name=self.name,
            available=self.is_available(),
            default_auto_enabled=self.default_auto_enabled,
            execution_mode=self.execution_mode,
            supported_entity_types=sorted(self.supported_entity_types),
            notes="從 source URL 推導輕量 metadata。",
        )


class CommandPlugin:
    default_auto_enabled = False
    execution_mode = "local_command"

    def __init__(
        self,
        name: EnrichmentPluginName,
        commands: list[str],
        supported_entity_types: set[str],
        notes: str,
    ) -> None:
        self.name = name
        self.commands = commands
        self.supported_entity_types = supported_entity_types
        self.notes = notes

    def command_path(self) -> str | None:
        for command in self.commands:
            path = shutil.which(command)
            if path:
                return path
        return None

    def is_available(self) -> bool:
        return self.command_path() is not None

    def applies_to(self, entity: CanonicalEntity, request: DiscoveryRequest) -> bool:
        return entity.entity_type in self.supported_entity_types and bool(_candidate_domains(entity))

    def describe(self) -> PluginDescriptor:
        return PluginDescriptor(
            name=self.name,
            available=self.is_available(),
            default_auto_enabled=self.default_auto_enabled,
            execution_mode=self.execution_mode,
            supported_entity_types=sorted(self.supported_entity_types),
            notes=self.notes,
        )


class TheHarvesterPlugin(CommandPlugin):
    name: Literal["theharvester"] = "theharvester"
    def __init__(self) -> None:
        super().__init__(
            name="theharvester",
            commands=["theHarvester"],
            supported_entity_types={"lead", "company"},
            notes="針對 domain 執行 email / host 被動枚舉。",
        )

    def command_path(self) -> str | None:
        configured = os.getenv("THEHARVESTER_COMMAND")
        if configured:
            configured = configured.strip()
            if configured:
                if os.path.isabs(configured) and os.path.exists(configured):
                    return configured
                env_path = shutil.which(configured)
                if env_path:
                    return env_path
                if os.path.exists(configured):
                    return configured
        return super().command_path()

    def enrich(self, entity: CanonicalEntity, request: DiscoveryRequest) -> PluginOutcome:
        domain = _first_domain(entity)
        command_path = self.command_path()
        if not domain or command_path is None:
            return PluginOutcome(
                plugin=self.name,
                target_entity_id=entity.entity_id,
                status="unavailable",
                message="缺少 domain 或 theHarvester 未安裝。",
            )
        try:
            completed = subprocess.run(
                [command_path, "-d", domain, "-b", "all", "-l", "50"],
                capture_output=True,
                text=True,
                timeout=DEFAULT_COMMAND_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return PluginOutcome(self.name, entity.entity_id, "timeout", message="theHarvester 執行逾時。")

        output = _coalesce_output(completed.stdout, completed.stderr)
        emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@" + re.escape(domain), output, flags=re.IGNORECASE)))
        hosts = sorted(set(re.findall(r"(?:[A-Za-z0-9-]+\.)+" + re.escape(domain), output, flags=re.IGNORECASE)))
        applied = bool(emails or hosts)
        return PluginOutcome(
            plugin=self.name,
            target_entity_id=entity.entity_id,
            status="completed" if completed.returncode == 0 else "partial",
            applied=applied,
            summary=f"theHarvester 發現 {len(emails)} 個 email、{len(hosts)} 個 host。" if applied else None,
            tags=[domain],
            message=None if applied else "theHarvester 已執行，但未解析到結構化結果。",
            attributes={
                "theharvester": {
                    "domain": domain,
                    "returncode": completed.returncode,
                    "emails": emails[:20],
                    "hosts": hosts[:20],
                    "stdout_excerpt": output[:1200],
                }
            },
        )


class AmassPlugin(CommandPlugin):
    name: Literal["amass"] = "amass"
    def __init__(self) -> None:
        super().__init__(
            name="amass",
            commands=["amass"],
            supported_entity_types={"lead", "company"},
            notes="針對 domain 執行被動子網域枚舉。",
        )

    def command_path(self) -> str | None:
        configured = os.getenv("AMASS_COMMAND")
        if configured:
            configured = configured.strip()
            if configured:
                if os.path.isabs(configured) and os.path.exists(configured):
                    return configured
                env_path = shutil.which(configured)
                if env_path:
                    return env_path
                if os.path.exists(configured):
                    return configured
        return super().command_path()

    def enrich(self, entity: CanonicalEntity, request: DiscoveryRequest) -> PluginOutcome:
        domain = _first_domain(entity)
        command_path = self.command_path()
        if not domain or command_path is None:
            return PluginOutcome(
                plugin=self.name,
                target_entity_id=entity.entity_id,
                status="unavailable",
                message="缺少 domain 或 amass 未安裝。",
            )
        try:
            completed = subprocess.run(
                [command_path, "enum", "-passive", "-norecursive", "-noalts", "-d", domain],
                capture_output=True,
                text=True,
                timeout=DEFAULT_COMMAND_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return PluginOutcome(self.name, entity.entity_id, "timeout", message="amass 執行逾時。")

        output = _coalesce_output(completed.stdout, completed.stderr)
        subdomains = sorted(
            {
                line.strip()
                for line in output.splitlines()
                if line.strip().endswith(domain) and " " not in line.strip()
            }
        )
        applied = bool(subdomains)
        return PluginOutcome(
            plugin=self.name,
            target_entity_id=entity.entity_id,
            status="completed" if completed.returncode == 0 else "partial",
            applied=applied,
            summary=f"amass 發現 {len(subdomains)} 個子網域。" if applied else None,
            tags=[domain],
            message=None if applied else "amass 已執行，但未解析到結構化結果。",
            attributes={
                "amass": {
                    "domain": domain,
                    "returncode": completed.returncode,
                    "subdomains": subdomains[:50],
                    "stdout_excerpt": output[:1200],
                }
            },
        )


class SpiderFootPlugin(CommandPlugin):
    name: Literal["spiderfoot"] = "spiderfoot"
    def __init__(self) -> None:
        super().__init__(
            name="spiderfoot",
            commands=["sf.py", "spiderfoot"],
            supported_entity_types={"lead", "company", "activity_signal", "event"},
            notes="若本機安裝 SpiderFoot CLI，會以 JSON 模式執行有限度掃描並回收事件。",
        )

    def command_path(self) -> str | None:
        configured = os.getenv("SPIDERFOOT_COMMAND") or os.getenv("SPIDERFOOT_SF_PY")
        if configured:
            configured = configured.strip()
            if configured:
                if os.path.isabs(configured) and os.path.exists(configured):
                    return configured
                env_path = shutil.which(configured)
                if env_path:
                    return env_path
                if configured.endswith(".py") and os.path.exists(configured):
                    return configured
        return super().command_path()

    def enrich(self, entity: CanonicalEntity, request: DiscoveryRequest) -> PluginOutcome:
        command_path = self.command_path()
        target = _spiderfoot_target(entity)
        if command_path is None or not target:
            return PluginOutcome(
                self.name,
                entity.entity_id,
                "unavailable",
                message="spiderfoot 未安裝或無法推導掃描目標。",
            )

        args = [command_path, "-s", target, "-o", "json"]
        requested_types = _spiderfoot_requested_types(entity, request)
        if requested_types:
            args.extend(["-t", ",".join(requested_types)])

        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=DEFAULT_COMMAND_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return PluginOutcome(self.name, entity.entity_id, "timeout", message="SpiderFoot 執行逾時。")

        output = _coalesce_output(completed.stdout, completed.stderr)
        events = _parse_spiderfoot_events(output)
        event_types = sorted({str(event.get("type") or event.get("Type") or "").strip() for event in events if event.get("type") or event.get("Type")})
        sources = sorted({str(event.get("Source") or event.get("source") or "").strip() for event in events if event.get("Source") or event.get("source")})
        applied = bool(events)
        summary = f"SpiderFoot 回收 {len(events)} 筆事件。" if applied else None
        return PluginOutcome(
            plugin=self.name,
            target_entity_id=entity.entity_id,
            status="completed" if completed.returncode == 0 else "partial",
            applied=applied,
            summary=summary,
            tags=[source for source in sources if source][:10],
            message=None if applied else "SpiderFoot 已執行，但未解析到結構化結果。",
            attributes={
                "spiderfoot": {
                    "command_path": command_path,
                    "target": target,
                    "requested_types": requested_types,
                    "returncode": completed.returncode,
                    "event_count": len(events),
                    "event_types": event_types[:40],
                    "events": events[:40],
                    "stdout_excerpt": output[:2000],
                }
            },
        )

    def describe(self) -> PluginDescriptor:
        return PluginDescriptor(
            name=self.name,
            available=self.is_available(),
            default_auto_enabled=self.default_auto_enabled,
            execution_mode="local_command_json",
            supported_entity_types=sorted(self.supported_entity_types),
            notes="SpiderFoot CLI JSON 掃描，適合 domain / hostname / email 類目標。",
        )


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[EnrichmentPluginName, EnrichmentPlugin] = {
            "omlx": cast(EnrichmentPlugin, OMLXPlugin()),
            "site_html": cast(EnrichmentPlugin, SiteHTMLPlugin()),
            "theharvester": cast(EnrichmentPlugin, TheHarvesterPlugin()),
            "amass": cast(EnrichmentPlugin, AmassPlugin()),
            "spiderfoot": cast(EnrichmentPlugin, SpiderFootPlugin()),
        }

    def resolve(self, request: DiscoveryRequest) -> list[EnrichmentPlugin]:
        mode = request.enrichment.mode
        if mode == "disabled":
            return []

        if mode == "selected":
            names: list[EnrichmentPluginName] = list(request.enrichment.enabled_plugins)
        elif mode == "all":
            names = list(self._plugins.keys())
        else:
            names = [name for name, plugin in self._plugins.items() if plugin.default_auto_enabled]
            for name in request.enrichment.enabled_plugins:
                if name not in names:
                    names.append(name)

        resolved: list[EnrichmentPlugin] = []
        for name in names:
            plugin = self._plugins.get(name)
            if plugin is not None:
                resolved.append(plugin)
        return resolved

    def describe(self) -> list[PluginDescriptor]:
        return [plugin.describe() for plugin in self._plugins.values()]


def enrich_entities(
    entities: list[CanonicalEntity],
    request: DiscoveryRequest,
) -> tuple[list[CanonicalEntity], list[PluginReportRecord]]:
    registry = PluginRegistry()
    plugins = registry.resolve(request)
    if not plugins or not entities:
        return entities, []

    target_entities = _rank_enrichment_targets(entities)[: request.enrichment.max_targets]
    deep_targets = target_entities[: min(len(target_entities), max(1, DEEP_ENRICH_TARGET_LIMIT))]
    reports: list[PluginReportRecord] = []
    entity_map = {entity.entity_id: entity for entity in entities}

    with ThreadPoolExecutor(max_workers=max(1, request.enrichment.parallelism)) as executor:
        futures = []
        for entity in target_entities:
            for plugin in plugins:
                if not plugin.applies_to(entity, request):
                    reports.append(
                        PluginReportRecord(
                            plugin=plugin.name,
                            target_entity_id=entity.entity_id,
                            status="skipped",
                            applied=False,
                            message="plugin 不適用於此 entity 類型或缺少可用 target。",
                        )
                    )
                    continue
                if plugin.execution_mode == "local_command" and entity not in deep_targets:
                    reports.append(
                        PluginReportRecord(
                            plugin=plugin.name,
                            target_entity_id=entity.entity_id,
                            status="skipped",
                            applied=False,
                            message="深度富化僅適用於高價值目標。",
                        )
                    )
                    continue
                if not plugin.is_available():
                    reports.append(
                        PluginReportRecord(
                            plugin=plugin.name,
                            target_entity_id=entity.entity_id,
                            status="unavailable",
                            applied=False,
                            message="plugin 所需依賴不存在。",
                        )
                    )
                    continue
                futures.append(executor.submit(plugin.enrich, entity, request))

        for future in as_completed(futures):
            outcome = future.result()
            reports.append(
                PluginReportRecord(
                    plugin=outcome.plugin,
                    target_entity_id=outcome.target_entity_id,
                    status=outcome.status,
                    applied=outcome.applied,
                    message=outcome.message,
                    data=outcome.attributes,
                )
            )
            if not outcome.applied or not request.enrichment.auto_merge:
                continue
            target_entity = entity_map.get(outcome.target_entity_id)
            if target_entity is None:
                continue
            if outcome.summary and not target_entity.summary:
                target_entity.summary = outcome.summary
            for tag in outcome.tags:
                if tag not in target_entity.tags:
                    target_entity.tags.append(tag)
            target_entity.attributes.setdefault("enrichment", {})
            enrichment_bucket = target_entity.attributes["enrichment"]
            if isinstance(enrichment_bucket, dict):
                enrichment_bucket[outcome.plugin] = outcome.attributes.get(outcome.plugin, outcome.attributes)

    return entities, reports


def list_plugin_descriptors() -> list[PluginDescriptor]:
    return PluginRegistry().describe()


def _candidate_domains(entity: CanonicalEntity) -> list[str]:
    candidates: list[str] = []
    for key in ("organizer_domain", "domain", "company_domain"):
        value = entity.attributes.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip().lower())
    for url in entity.source_urls:
        parsed = urlparse(url)
        if parsed.netloc:
            candidates.append(parsed.netloc.lower())
    cleaned = []
    seen = set()
    for candidate in candidates:
        normalized = candidate.removeprefix("www.").strip(".")
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned


def _first_domain(entity: CanonicalEntity) -> str | None:
    candidates = _candidate_domains(entity)
    return candidates[0] if candidates else None


def _spiderfoot_target(entity: CanonicalEntity) -> str | None:
    domain = _first_domain(entity)
    if domain:
        return domain
    for key in ("email", "organizer_email", "username", "person_name"):
        value = entity.attributes.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if entity.source_urls:
        parsed = urlparse(entity.source_urls[0])
        if parsed.netloc:
            return parsed.netloc
    if entity.title.strip():
        return entity.title.strip()
    return None


def _rank_enrichment_targets(entities: list[CanonicalEntity]) -> list[CanonicalEntity]:
    scored = list(enumerate(entities))
    scored.sort(key=lambda item: (_enrichment_score(item[1]), -item[0]), reverse=True)
    return [entity for _index, entity in scored]


def _enrichment_score(entity: CanonicalEntity) -> float:
    status_bonus = {
        "qualified": 3.0,
        "reviewed": 2.0,
        "new": 1.0,
    }.get((entity.status or "").lower(), 1.0)
    type_bonus = {
        "lead": 3.0,
        "company": 3.0,
        "event": 2.5,
        "activity_signal": 1.5,
        "document": 1.0,
        "source": 1.0,
        "person": 2.0,
    }.get(entity.entity_type, 1.0)
    evidence_bonus = min(len(entity.evidence), 5) * 0.5
    source_bonus = min(len(entity.source_urls), 5) * 0.25
    return (entity.score * 2.0) + entity.confidence + status_bonus + type_bonus + evidence_bonus + source_bonus


def _spiderfoot_requested_types(entity: CanonicalEntity, request: DiscoveryRequest) -> list[str]:
    requested: list[str] = []
    if request.objective == "find_events" or entity.entity_type == "event":
        requested.extend(["event", "content", "location"])
    elif entity.entity_type in {"lead", "company"}:
        requested.extend(["company", "email", "host", "website"])
    elif entity.entity_type == "activity_signal":
        requested.extend(["company", "event", "website"])
    seen: set[str] = set()
    result: list[str] = []
    for item in requested:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _parse_spiderfoot_events(raw_output: str) -> list[dict[str, object]]:
    text = raw_output.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except Exception:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except Exception:
            return []
    if isinstance(parsed, list):
        return [event for event in parsed if isinstance(event, dict)]
    if isinstance(parsed, dict):
        events = parsed.get("results") or parsed.get("events") or parsed.get("data")
        if isinstance(events, list):
            return [event for event in events if isinstance(event, dict)]
    return []


def _coalesce_output(stdout: str, stderr: str) -> str:
    output = (stdout or "").strip()
    if output:
        return output
    return (stderr or "").strip()
