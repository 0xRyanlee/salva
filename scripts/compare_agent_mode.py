#!/usr/bin/env python3
"""Evaluate independently collected Agent-only and Salva research observations."""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

QUALITY_METRICS = (
    "precision",
    "pooled_recall",
    "evidence_completeness",
    "country_coverage",
    "channel_coverage",
    "contamination_safety",
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _candidate_key(candidate: dict[str, Any]) -> str:
    if candidate.get("entity_id"):
        return str(candidate["entity_id"]).casefold()
    domain = urlparse(str(candidate.get("url", ""))).netloc.casefold()
    return f"{_slug(str(candidate.get('name', '')))}|{domain}"


def _source_domains(candidate: dict[str, Any]) -> set[str]:
    urls = [candidate.get("url"), *candidate.get("sources", [])]
    return {
        urlparse(str(url)).netloc.casefold()
        for url in urls
        if url and urlparse(str(url)).netloc
    }


def validate_experiment(payload: dict[str, Any]) -> list[str]:
    observations = payload.get("observations", [])
    conditions = {str(item.get("condition", "")).strip() for item in observations}
    if len(conditions) < 2:
        raise ValueError("experiment requires at least two independent conditions")
    if any(int(item.get("round", 0)) < 1 for item in observations):
        raise ValueError("every observation requires round >= 1")
    for observation in observations:
        for candidate in observation.get("candidates", []):
            if not candidate.get("entity_id") and not str(candidate.get("name", "")).strip():
                raise ValueError("every candidate requires name or entity_id")

    warnings: list[str] = []
    design = payload.get("design", {})
    if not design.get("same_task", False):
        warnings.append("same_task is not asserted")
    if not design.get("independent_collection", False):
        warnings.append("independent_collection is not asserted")
    if not design.get("budget_parity", False):
        warnings.append("request and time budgets are not matched")
    if not design.get("raw_result_capture", False):
        warnings.append("one or more conditions lack complete raw-result capture")
    if not design.get("elapsed_time_comparable", False):
        warnings.append("elapsed time is not comparable across conditions")
    reference_method = str(design.get("reference_set_method", "")).strip()
    if reference_method != "predeclared_external":
        warnings.append(
            "pooled recall uses a verified union, not predeclared external ground truth"
        )
    if not payload.get("reference_entities"):
        warnings.append("reference_entities is empty; pooled recall will be reported as 0")

    rounds_by_condition: dict[str, set[int]] = defaultdict(set)
    for item in observations:
        rounds_by_condition[str(item["condition"])].add(int(item["round"]))
    if len({tuple(sorted(rounds)) for rounds in rounds_by_condition.values()}) > 1:
        warnings.append("conditions do not contain the same round set")
    return warnings


def _evaluate_snapshot(
    candidates: list[dict[str, Any]],
    *,
    reference_entities: set[str],
    expected_countries: set[str],
    expected_channels: set[str],
    elapsed_seconds: float,
    request_count: int,
) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = _candidate_key(candidate)
        existing = unique.get(key)
        if existing is None:
            unique[key] = {
                **candidate,
                "evidence": list(candidate.get("evidence", [])),
                "sources": list(candidate.get("sources", [])),
            }
            continue
        existing["verified"] = bool(existing.get("verified") or candidate.get("verified"))
        existing["relevant"] = bool(existing.get("relevant") or candidate.get("relevant"))
        existing["contaminated"] = bool(
            existing.get("contaminated") or candidate.get("contaminated")
        )
        existing["evidence"] = sorted({
            *existing.get("evidence", []),
            *candidate.get("evidence", []),
        })
        existing["sources"] = sorted({
            *existing.get("sources", []),
            *candidate.get("sources", []),
        })

    items = list(unique.values())
    relevant = [item for item in items if item.get("relevant")]
    verified_relevant = [
        item for item in relevant if item.get("verified") and item.get("evidence")
    ]
    matched_reference = {
        _slug(str(item.get("name", "")))
        for item in relevant
        if _slug(str(item.get("name", ""))) in reference_entities
    }
    evidence_scores = [
        min(1.0, len(set(item.get("evidence", []))) / 2)
        for item in relevant
    ]
    countries = {
        str(item.get("country", "")).casefold()
        for item in relevant
        if item.get("country")
    }
    channels = {
        str(item.get("channel_type", "")).casefold()
        for item in relevant
        if item.get("channel_type")
    }
    source_domains = set().union(*(_source_domains(item) for item in relevant)) if relevant else set()
    raw_count = len(candidates)
    contamination_rate = (
        sum(1 for item in items if item.get("contaminated")) / len(items)
        if items else 0.0
    )

    return {
        "raw_candidates": raw_count,
        "unique_candidates": len(items),
        "relevant_candidates": len(relevant),
        "verified_relevant": len(verified_relevant),
        "precision": round(len(relevant) / len(items), 4) if items else 0.0,
        "pooled_recall": (
            round(len(matched_reference) / len(reference_entities), 4)
            if reference_entities else 0.0
        ),
        "evidence_completeness": (
            round(sum(evidence_scores) / len(evidence_scores), 4)
            if evidence_scores else 0.0
        ),
        "source_diversity": len(source_domains),
        "country_coverage": (
            round(len(countries & expected_countries) / len(expected_countries), 4)
            if expected_countries else 0.0
        ),
        "channel_coverage": (
            round(len(channels & expected_channels) / len(expected_channels), 4)
            if expected_channels else 0.0
        ),
        "duplicate_rate": round(1 - len(items) / raw_count, 4) if raw_count else 0.0,
        "contamination_rate": round(contamination_rate, 4),
        "contamination_safety": round(1 - contamination_rate, 4),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "request_count": request_count,
        "matched_reference": sorted(matched_reference),
    }


def evaluate_experiment(payload: dict[str, Any]) -> dict[str, Any]:
    warnings = validate_experiment(payload)
    target = payload.get("target", {})
    reference_entities = {
        _slug(str(value)) for value in payload.get("reference_entities", [])
    }
    expected_countries = {
        str(value).casefold() for value in target.get("countries", [])
    }
    expected_channels = {
        str(value).casefold() for value in target.get("channel_types", [])
    }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in payload["observations"]:
        grouped[str(observation["condition"])].append(observation)

    series: list[dict[str, Any]] = []
    for condition, observations in sorted(grouped.items()):
        cumulative_candidates: list[dict[str, Any]] = []
        elapsed_seconds = 0.0
        request_count = 0
        for observation in sorted(observations, key=lambda item: int(item["round"])):
            if observation.get("result_mode", "incremental") == "snapshot":
                cumulative_candidates = list(observation.get("candidates", []))
                elapsed_seconds = float(observation.get("elapsed_seconds", 0.0))
                request_count = int(observation.get("request_count", 0))
            else:
                cumulative_candidates.extend(observation.get("candidates", []))
                elapsed_seconds += float(observation.get("elapsed_seconds", 0.0))
                request_count += int(observation.get("request_count", 0))
            metrics = _evaluate_snapshot(
                cumulative_candidates,
                reference_entities=reference_entities,
                expected_countries=expected_countries,
                expected_channels=expected_channels,
                elapsed_seconds=elapsed_seconds,
                request_count=request_count,
            )
            series.append({
                "condition": condition,
                "round": int(observation["round"]),
                "label": f"{condition} R{int(observation['round'])}",
                "metrics": metrics,
            })

    return {
        "experiment_id": payload.get("experiment_id", "unnamed"),
        "target": target,
        "design": payload.get("design", {}),
        "warnings": warnings,
        "series": series,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Experiment: {report['experiment_id']}",
        "",
        "| Condition | Round | Unique | Verified relevant | Precision | Pooled recall | Evidence | Countries | Channels | Contamination | Requests | Seconds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["series"]:
        metrics = item["metrics"]
        lines.append(
            "| {condition} | {round} | {unique_candidates} | {verified_relevant} | "
            "{precision:.1%} | {pooled_recall:.1%} | {evidence_completeness:.1%} | "
            "{country_coverage:.1%} | {channel_coverage:.1%} | "
            "{contamination_rate:.1%} | {request_count} | {elapsed_seconds:.1f} |".format(
                condition=item["condition"],
                round=item["round"],
                **metrics,
            )
        )
    if report["warnings"]:
        lines.extend(["", "## Validity warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines) + "\n"


def render_svg(report: dict[str, Any], width: int = 1280, height: int = 720) -> str:
    series = report["series"]
    margin_left, margin_top, margin_bottom = 85, 70, 120
    chart_width = width - margin_left - 30
    chart_height = height - margin_top - margin_bottom
    group_width = chart_width / max(len(QUALITY_METRICS), 1)
    bar_gap = 3
    bar_width = max(4, (group_width - 28) / max(len(series), 1) - bar_gap)
    colors = ("#2563eb", "#7c3aed", "#059669", "#d97706", "#dc2626", "#0891b2")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{margin_left}" y="35" font-family="sans-serif" font-size="22" font-weight="700">'
        f'{escape(str(report["experiment_id"]))}</text>',
    ]
    for tick in range(0, 101, 20):
        y = margin_top + chart_height - chart_height * tick / 100
        parts.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width - 30}" y2="{y:.1f}" '
            'stroke="#e5e7eb" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-family="sans-serif" font-size="12" fill="#4b5563">{tick}%</text>'
        )

    for metric_index, metric in enumerate(QUALITY_METRICS):
        group_x = margin_left + metric_index * group_width
        label = metric.replace("_", " ")
        parts.append(
            f'<text x="{group_x + group_width / 2:.1f}" y="{height - margin_bottom + 28}" '
            'text-anchor="middle" font-family="sans-serif" font-size="12" '
            f'fill="#111827">{escape(label)}</text>'
        )
        for series_index, item in enumerate(series):
            value = max(0.0, min(1.0, float(item["metrics"][metric])))
            bar_height = chart_height * value
            x = group_x + 14 + series_index * (bar_width + bar_gap)
            y = margin_top + chart_height - bar_height
            color = colors[series_index % len(colors)]
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
                f'height="{bar_height:.1f}" fill="{color}"><title>'
                f'{escape(str(item["label"]))}: {escape(label)} {value:.1%}</title></rect>'
            )

    legend_y = height - 52
    for index, item in enumerate(series):
        x = margin_left + (index % 4) * 285
        y = legend_y + (index // 4) * 24
        color = colors[index % len(colors)]
        parts.append(f'<rect x="{x}" y="{y - 11}" width="12" height="12" fill="{color}"/>')
        parts.append(
            f'<text x="{x + 18}" y="{y}" font-family="sans-serif" '
            f'font-size="12" fill="#111827">{escape(str(item["label"]))}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def write_outputs(
    payload: dict[str, Any],
    *,
    json_path: Path,
    markdown_path: Path,
    svg_path: Path,
) -> dict[str, Any]:
    report = evaluate_experiment(payload)
    for path in (json_path, markdown_path, svg_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    markdown_path.write_text(render_markdown(report))
    svg_path.write_text(render_svg(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate independent Agent-only vs Salva research observations."
    )
    parser.add_argument("input", type=Path, help="Experiment observation JSON.")
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    parser.add_argument("--svg-out", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text())
    report = write_outputs(
        payload,
        json_path=args.json_out,
        markdown_path=args.markdown_out,
        svg_path=args.svg_out,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
