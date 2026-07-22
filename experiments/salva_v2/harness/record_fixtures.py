"""Record live retrieval fixtures for salva_v2 task_set tasks.

REQUIRES live network access -- this is the one script in the harness that
is allowed to touch the network. Run once per task; the resulting fixtures
are then replayed offline by run_replay.py for every future gate/scorer/
confidence experiment.

Usage:
    python -m experiments.salva_v2.harness.record_fixtures --task-id single-01-tsmc
    python -m experiments.salva_v2.harness.record_fixtures \
        --task-id single-01-tsmc --task-id crosslang-01-tsmc
"""
from __future__ import annotations

import argparse
import functools
import json
from pathlib import Path
from typing import Any

from experiments.salva_v2.harness.fixture_store import FIXTURES_ROOT
from experiments.salva_v2.harness.recording_retriever import RecordingRetriever
from experiments.salva_v2.harness.task_request import build_discovery_request
from salva_core.service import execute_discovery

DEFAULT_TASK_SET = Path(__file__).resolve().parent.parent / "task_set_v2.json"


def _load_tasks(task_set_path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(task_set_path.read_text(encoding="utf-8"))
    return {t["task_id"]: t for t in data["tasks"]}


def record_task(
    task: dict[str, Any],
    *,
    fixtures_root: Path = FIXTURES_ROOT,
    qualify_threshold: float | None = None,
) -> dict[str, Any]:
    from unittest.mock import patch

    request = build_discovery_request(task, qualify_threshold=qualify_threshold)
    factory = functools.partial(
        RecordingRetriever, task_id=task["task_id"], fixtures_root=fixtures_root
    )
    with patch("salva_core.service.RoutedRetriever", factory):
        entities, relations, telemetry, meta, source_attempts = execute_discovery(request)

    summary = {
        "task_id": task["task_id"],
        "entities": [
            {
                "title": e.title,
                "source_urls": e.source_urls,
                "score": e.score,
                "confidence": e.confidence,
            }
            for e in entities
        ],
        "meta": {
            k: meta[k]
            for k in ("qualified_count", "raw_count", "rounds", "domain")
            if k in meta
        },
    }
    out_path = fixtures_root / task["task_id"] / "_recorded_run_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record live retrieval fixtures for salva_v2 task_set tasks."
    )
    parser.add_argument("--task-id", action="append", dest="task_ids")
    parser.add_argument("--all", action="store_true", help="record every task in the task set")
    parser.add_argument("--task-set", type=Path, default=DEFAULT_TASK_SET)
    parser.add_argument(
        "--qualify-threshold", type=float, default=None,
        help="override the per-domain qualify gate (0.0 = accumulate every candidate)",
    )
    args = parser.parse_args()

    tasks = _load_tasks(args.task_set)
    task_ids = list(tasks) if args.all else (args.task_ids or [])
    if not task_ids:
        raise SystemExit("pass --task-id <id> (repeatable) or --all")
    for task_id in task_ids:
        if task_id not in tasks:
            raise SystemExit(f"unknown task_id: {task_id}")
        summary = record_task(tasks[task_id], qualify_threshold=args.qualify_threshold)
        print(f"recorded {task_id}: {summary['meta']}")
        for e in summary["entities"]:
            print(f"  - {e['title']} score={e['score']:.3f} {e['source_urls']}")


if __name__ == "__main__":
    main()
