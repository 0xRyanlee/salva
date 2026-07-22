"""Replay salva_v2 task_set tasks from recorded fixtures -- no live network.

Usage:
    python -m experiments.salva_v2.harness.run_replay --task-id single-01-tsmc
    python -m experiments.salva_v2.harness.run_replay --task-id single-01-tsmc --compare
"""
from __future__ import annotations

import argparse
import functools
import json
from pathlib import Path
from typing import Any

from experiments.salva_v2.harness.fixture_store import FIXTURES_ROOT
from experiments.salva_v2.harness.replay_retriever import ReplayRetriever, no_network_guard
from experiments.salva_v2.harness.task_request import build_discovery_request
from salva_core.schemas import CanonicalEntity, CanonicalRelation, TelemetryRecord
from salva_core.service import execute_discovery

DEFAULT_TASK_SET = Path(__file__).resolve().parent.parent / "task_set_v1.json"


def _load_tasks(task_set_path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(task_set_path.read_text(encoding="utf-8"))
    return {t["task_id"]: t for t in data["tasks"]}


def replay_task(
    task: dict[str, Any], *, fixtures_root: Path = FIXTURES_ROOT
) -> tuple[
    list[CanonicalEntity], list[CanonicalRelation], list[TelemetryRecord], dict[str, Any]
]:
    from unittest.mock import patch

    request = build_discovery_request(task)
    factory = functools.partial(
        ReplayRetriever, task_id=task["task_id"], fixtures_root=fixtures_root
    )
    with no_network_guard(), patch("salva_core.service.RoutedRetriever", factory):
        entities, relations, telemetry, meta, source_attempts = execute_discovery(request)
    return entities, relations, telemetry, meta


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay salva_v2 task_set tasks from recorded fixtures -- no network."
    )
    parser.add_argument("--task-id", action="append", required=True, dest="task_ids")
    parser.add_argument("--task-set", type=Path, default=DEFAULT_TASK_SET)
    parser.add_argument(
        "--compare", action="store_true",
        help="diff replayed entity titles against the recorded run summary",
    )
    args = parser.parse_args()

    tasks = _load_tasks(args.task_set)
    for task_id in args.task_ids:
        if task_id not in tasks:
            raise SystemExit(f"unknown task_id: {task_id}")
        entities, relations, telemetry, meta = replay_task(tasks[task_id])
        print(
            f"replayed {task_id}: qualified_count={meta.get('qualified_count')} "
            f"raw_count={meta.get('raw_count')}"
        )
        for e in entities:
            print(f"  - {e.title} score={e.score:.3f} {e.source_urls}")

        if args.compare:
            summary_path = FIXTURES_ROOT / task_id / "_recorded_run_summary.json"
            if not summary_path.exists():
                print(f"  no recorded summary at {summary_path} -- run record_fixtures.py first")
                continue
            recorded = json.loads(summary_path.read_text(encoding="utf-8"))
            replayed_titles = sorted(e.title for e in entities)
            recorded_titles = sorted(e["title"] for e in recorded["entities"])
            if replayed_titles == recorded_titles:
                print(
                    f"  MATCH: replay reproduced {len(replayed_titles)} entities "
                    "identical to the recorded run"
                )
            else:
                print("  MISMATCH")
                print(f"    recorded: {recorded_titles}")
                print(f"    replayed: {replayed_titles}")


if __name__ == "__main__":
    main()
