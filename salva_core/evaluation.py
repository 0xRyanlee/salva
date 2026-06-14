from __future__ import annotations

from collections import Counter
from typing import Any

from salva_core.persistence import (
    get_run,
    list_plugin_reports,
    list_source_attempts,
    list_telemetry,
)
from salva_core.schemas import AuditComparison, AuditReport


def build_audit_report(run_id: str, path: str | None = None) -> AuditReport:
    detail = get_run(run_id, path=path) if path is not None else get_run(run_id)
    if detail is None:
        raise KeyError(f"run not found: {run_id}")

    telemetry, telemetry_total = _list_telemetry(run_id=run_id, path=path)
    source_attempts, source_total = _list_source_attempts(run_id=run_id, path=path)
    _plugin_reports, plugin_total = _list_plugin_reports(run_id=run_id, path=path)

    entity_count = len(detail["entities"])
    relation_count = len(detail["relations"])
    raw_count = int(detail["meta"].get("raw_count", 0) or 0)
    qualified_count = int(detail["meta"].get("qualified_count", 0) or 0)
    total_score = sum(item.avg_score for item in telemetry)
    avg_score = total_score / telemetry_total if telemetry_total else 0.0
    qualified_rate = qualified_count / max(raw_count, 1)
    noise_count = sum(len(item.noise_domains) for item in telemetry)
    noise_rate = noise_count / max(raw_count, 1)
    source_success_rate = sum(1 for item in source_attempts if item.succeeded) / max(source_total, 1)
    source_class_counts = Counter(item.source_class or "unknown" for item in source_attempts)
    round_profiles = Counter(
        _round_profile_label(item.metadata) for item in telemetry if item.metadata
    )
    provider_kinds = list(dict.fromkeys(detail["meta"].get("provider_kinds", [])))

    metrics = {
        "raw_count": float(raw_count),
        "qualified_count": float(qualified_count),
        "qualified_rate": round(qualified_rate, 4),
        "avg_score": round(avg_score, 4),
        "noise_rate": round(noise_rate, 4),
        "entity_density": round(entity_count / max(raw_count, 1), 4),
        "relation_density": round(relation_count / max(entity_count, 1), 4),
        "source_success_rate": round(source_success_rate, 4),
        "plugin_report_count": float(plugin_total),
        "telemetry_count": float(telemetry_total),
    }

    notes: list[str] = []
    if qualified_rate < 0.1:
        notes.append("low_qualified_rate")
    if noise_rate > 0.5:
        notes.append("high_noise_rate")
    if source_success_rate < 0.5:
        notes.append("weak_source_reliability")
    if plugin_total == 0 and detail["meta"].get("enrichment_mode") != "disabled":
        notes.append("no_plugin_activity")

    return AuditReport(
        run_id=run_id,
        objective=detail["objective"],
        output_profile=detail["output_profile"],
        created_at=_coerce_created_at(detail.get("created_at")),
        entity_count=entity_count,
        relation_count=relation_count,
        telemetry_count=telemetry_total,
        source_attempt_count=source_total,
        plugin_report_count=plugin_total,
        metrics=metrics,
        notes=notes,
        round_profiles=dict(round_profiles),
        provider_kinds=provider_kinds,
        source_classes=dict(source_class_counts),
    )


def compare_audits(left_run_id: str, right_run_id: str, path: str | None = None) -> AuditComparison:
    left = build_audit_report(left_run_id, path=path)
    right = build_audit_report(right_run_id, path=path)
    comparable_keys = (
        "qualified_rate",
        "avg_score",
        "noise_rate",
        "entity_density",
        "relation_density",
        "source_success_rate",
    )
    deltas = {
        key: round(right.metrics.get(key, 0.0) - left.metrics.get(key, 0.0), 4)
        for key in comparable_keys
    }
    winner = _pick_winner(left, right)
    return AuditComparison(
        left_run_id=left_run_id,
        right_run_id=right_run_id,
        left=left,
        right=right,
        deltas=deltas,
        winner=winner,
    )


def _round_profile_label(metadata: dict[str, Any]) -> str:
    notes = metadata.get("notes", [])
    if "precision_first" in notes:
        return "precision_first"
    if "graph_expansion" in notes:
        return "graph_expansion"
    if "source_discovery" in notes:
        return "source_discovery"
    return "other"


def _pick_winner(left: AuditReport, right: AuditReport) -> str | None:
    left_score = (
        left.metrics.get("qualified_rate", 0.0) * 2.0
        + left.metrics.get("avg_score", 0.0)
        + left.metrics.get("source_success_rate", 0.0)
        - left.metrics.get("noise_rate", 0.0)
    )
    right_score = (
        right.metrics.get("qualified_rate", 0.0) * 2.0
        + right.metrics.get("avg_score", 0.0)
        + right.metrics.get("source_success_rate", 0.0)
        - right.metrics.get("noise_rate", 0.0)
    )
    if right_score > left_score:
        return right.run_id
    if left_score > right_score:
        return left.run_id
    return None


def _list_telemetry(run_id: str, path: str | None) -> tuple[list[Any], int]:
    if path is not None:
        return list_telemetry(run_id=run_id, path=path)
    return list_telemetry(run_id=run_id)


def _list_source_attempts(run_id: str, path: str | None) -> tuple[list[Any], int]:
    if path is not None:
        return list_source_attempts(run_id=run_id, path=path)
    return list_source_attempts(run_id=run_id)


def _list_plugin_reports(run_id: str, path: str | None) -> tuple[list[Any], int]:
    if path is not None:
        return list_plugin_reports(run_id=run_id, path=path)
    return list_plugin_reports(run_id=run_id)


def _coerce_created_at(value: Any) -> Any:
    return value
