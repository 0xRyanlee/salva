from __future__ import annotations

import hashlib
import json
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from salva_core.evaluation import build_audit_report
from salva_core.persistence import get_run
from salva_core.schemas import (
    BenchmarkExportResult,
    BenchmarkReport,
    BenchmarkRequest,
    BenchmarkRunRecord,
    BenchmarkSeriesPoint,
)


def build_benchmark_report(payload: BenchmarkRequest, path: str | None = None) -> BenchmarkReport:
    runs: list[BenchmarkRunRecord] = []
    for run_id in payload.run_ids:
        detail = get_run(run_id, path=path) if path is not None else get_run(run_id)
        if detail is None:
            raise KeyError(f"run not found: {run_id}")
        audit = build_audit_report(run_id, path=path)
        experience_profile = detail["meta"].get("experience_profile") or _infer_profile(
            detail["objective"], detail["output_profile"]
        )
        runs.append(
            BenchmarkRunRecord(
                run_id=run_id,
                objective=detail["objective"],
                output_profile=detail["output_profile"],
                experience_profile=experience_profile,
                created_at=_coerce_created_at(detail.get("created_at")),
                metrics=_metric_bundle(audit.metrics, detail["meta"]),
                notes=list(audit.notes),
                provider_kinds=list(detail["meta"].get("provider_kinds", [])),
            )
        )

    by_experience_profile = _aggregate_series(runs, "experience_profile")
    by_objective = _aggregate_series(runs, "objective")
    chart_data = {
        "runs": [run.model_dump(mode="json") for run in runs],
        "by_experience_profile": [point.model_dump(mode="json") for point in by_experience_profile],
        "by_objective": [point.model_dump(mode="json") for point in by_objective],
    }

    return BenchmarkReport(
        label=payload.label,
        generated_at=datetime.now(UTC),
        total_runs=len(runs),
        runs=runs,
        by_experience_profile=by_experience_profile,
        by_objective=by_objective,
        chart_data=chart_data,
    )


def write_benchmark_report(
    payload: BenchmarkRequest,
    output_path: str | None = None,
    path: str | None = None,
) -> BenchmarkExportResult:
    report = build_benchmark_report(payload, path=path)
    export_path = _resolve_export_path(payload.label, output_path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
    export_path.write_text(serialized, encoding="utf-8")
    data = serialized.encode("utf-8")
    return BenchmarkExportResult(
        report=report,
        export_path=str(export_path),
        bytes_written=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def render_benchmark_markdown(report: BenchmarkReport) -> str:
    lines: list[str] = []
    lines.append("# Salva Benchmark Report")
    lines.append("")
    if report.label:
        lines.append(f"- label: `{report.label}`")
    lines.append(f"- generated_at: `{report.generated_at.isoformat()}`")
    lines.append(f"- total_runs: `{report.total_runs}`")
    lines.append("")

    lines.append("## Profile Summary")
    lines.append("")
    lines.extend(_render_series_table("experience_profile", report.by_experience_profile))
    lines.append("")
    lines.extend(_render_series_table("objective", report.by_objective))
    lines.append("")

    lines.append("## Runs")
    lines.append("")
    lines.append("| run_id | objective | profile | qualified_rate | avg_score | noise_rate | source_success_rate |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for run in report.runs:
        lines.append(
            "| {run_id} | {objective} | {profile} | {qualified_rate:.4f} | {avg_score:.4f} | {noise_rate:.4f} | {source_success_rate:.4f} |".format(
                run_id=run.run_id,
                objective=run.objective,
                profile=run.experience_profile,
                qualified_rate=run.metrics.get("qualified_rate", 0.0),
                avg_score=run.metrics.get("avg_score", 0.0),
                noise_rate=run.metrics.get("noise_rate", 0.0),
                source_success_rate=run.metrics.get("source_success_rate", 0.0),
            )
        )

    return "\n".join(lines)


def write_benchmark_bundle(
    payload: BenchmarkRequest,
    output_dir: str | None = None,
    path: str | None = None,
) -> tuple[BenchmarkReport, Path, Path]:
    report = build_benchmark_report(payload, path=path)
    root = _resolve_bundle_dir(payload.label, output_dir)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{_bundle_stem(payload.label)}.json"
    md_path = root / f"{_bundle_stem(payload.label)}.md"

    json_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_benchmark_markdown(report), encoding="utf-8")
    return report, json_path, md_path


def build_benchmark_bundle(
    payload: BenchmarkRequest,
    output_dir: str | None = None,
    path: str | None = None,
) -> tuple[BenchmarkReport, Path, Path]:
    return write_benchmark_bundle(payload, output_dir=output_dir, path=path)


def _aggregate_series(runs: list[BenchmarkRunRecord], key: str) -> list[BenchmarkSeriesPoint]:
    buckets: dict[str, list[BenchmarkRunRecord]] = defaultdict(list)
    for run in runs:
        buckets[getattr(run, key)].append(run)

    series: list[BenchmarkSeriesPoint] = []
    for bucket_key, items in sorted(buckets.items(), key=lambda pair: pair[0]):
        series.append(
            BenchmarkSeriesPoint(
                key=bucket_key,
                count=len(items),
                metrics={
                    "qualified_rate": round(mean(item.metrics.get("qualified_rate", 0.0) for item in items), 4),
                    "avg_score": round(mean(item.metrics.get("avg_score", 0.0) for item in items), 4),
                    "noise_rate": round(mean(item.metrics.get("noise_rate", 0.0) for item in items), 4),
                    "source_success_rate": round(mean(item.metrics.get("source_success_rate", 0.0) for item in items), 4),
                    "entity_density": round(mean(item.metrics.get("entity_density", 0.0) for item in items), 4),
                    "relation_density": round(mean(item.metrics.get("relation_density", 0.0) for item in items), 4),
                },
            )
        )
    return series


def _render_series_table(title: str, series: list[BenchmarkSeriesPoint]) -> list[str]:
    lines: list[str] = []
    lines.append(f"### By {title}")
    lines.append("")
    lines.append("| key | count | qualified_rate | avg_score | noise_rate | source_success_rate |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for point in series:
        lines.append(
            "| {key} | {count} | {qualified_rate:.4f} | {avg_score:.4f} | {noise_rate:.4f} | {source_success_rate:.4f} |".format(
                key=point.key,
                count=point.count,
                qualified_rate=point.metrics.get("qualified_rate", 0.0),
                avg_score=point.metrics.get("avg_score", 0.0),
                noise_rate=point.metrics.get("noise_rate", 0.0),
                source_success_rate=point.metrics.get("source_success_rate", 0.0),
            )
        )
    return lines


def _metric_bundle(metrics: dict[str, float], meta: dict[str, Any]) -> dict[str, float]:
    bundle = dict(metrics)
    bundle["elapsed_seconds"] = float(meta.get("elapsed_seconds", 0.0) or 0.0)
    bundle["rounds"] = float(meta.get("rounds", 0) or 0)
    bundle["provider_count"] = float(meta.get("provider_count", 0) or 0)
    bundle["plugin_report_count"] = float(meta.get("plugin_report_count", 0) or 0)
    bundle["source_attempt_count"] = float(meta.get("source_attempt_count", 0) or 0)
    return bundle


def _infer_profile(objective: str, output_profile: str) -> str:
    if objective == "find_events":
        return "event_discovery"
    if objective == "find_exhibitors":
        return "event_discovery"
    if output_profile in {"company", "company_profile"}:
        return "company_research"
    if output_profile in {"crm_contact", "lead"}:
        return "lead_focus"
    return "quick_scan"


def _resolve_export_path(label: str | None, output_path: str | None) -> Path:
    if output_path:
        return Path(output_path).expanduser()
    suffix = f"{label}.json" if label else "benchmark.json"
    return Path(tempfile.gettempdir()) / "salva-benchmarks" / suffix


def _resolve_bundle_dir(label: str | None, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir).expanduser()
    suffix = label or "benchmark"
    return Path(tempfile.gettempdir()) / "salva-benchmarks" / suffix


def _bundle_stem(label: str | None) -> str:
    return label or "benchmark"


def _coerce_created_at(value: Any) -> Any:
    return value
