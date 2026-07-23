"""Round 2 實驗執行器（見 EXPERIMENT_PROTOCOL_ROUND2.md）。

用既有 frozen-corpus fixture harness 對 B/E/F/G 四個 arm 做 replay 比較
——四個 arm 共用同一份錄製好的 raw pool，唯一變異是 env var 控制的
selection 邏輯（admission_policy/entity_resolution），徹底避開 v1 草案被
fable 審視抓到的 live drift 混淆問題。

用法：
    uv run python -m experiments.salva_v2.round2_runner
"""
from __future__ import annotations

import functools
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from core.controller import SalvaController
from experiments.salva_v2.harness.replay_retriever import ReplayRetriever, no_network_guard
from experiments.salva_v2.harness.run_replay import _load_tasks
from experiments.salva_v2.harness.task_request import build_discovery_request

TASK_SET_V2 = Path(__file__).parent / "task_set_v2.json"
RESULTS_DIR = Path(__file__).parent / "raw_results_round2"

ARMS: dict[str, dict[str, str]] = {
    "B": {},
    "E": {"SALVA_ENABLE_ENTITY_RESOLUTION": "true"},
    "F": {"SALVA_ADMISSION_POLICY": "rank"},
    "G": {"SALVA_ENABLE_ENTITY_RESOLUTION": "true", "SALVA_ADMISSION_POLICY": "rank"},
}
ENV_KEYS = ("SALVA_ENABLE_ENTITY_RESOLUTION", "SALVA_ADMISSION_POLICY")


def normalize_url(url: str) -> str:
    url = url.strip().rstrip("/").lower().split("?")[0]
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    return url


def gt_urls_for(gt_entity: dict) -> set[str]:
    urls = {normalize_url(u) for u in gt_entity.get("source_urls", [])}
    if gt_entity.get("source_url"):
        urls.add(normalize_url(gt_entity["source_url"]))
    return urls


def is_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def infer_merge_groups(pre_merge_entities: list, post_merge_entities: list) -> list[dict]:
    """entity_resolution.py 不直接回傳 merge group，這裡用 source_urls 的
    集合包含關係反推：一個合併後的 entity 的 source_urls 是所有被併入它的
    pre-merge entity 的 source_urls 聯集，所以只要看哪些 pre-merge entity
    的 source_urls 是某個 post-merge entity 的子集，就能還原分組。"""
    groups = []
    for post in post_merge_entities:
        post_urls = set(post.source_urls)
        members = [
            pre for pre in pre_merge_entities
            if pre.source_urls and set(pre.source_urls) <= post_urls
        ]
        if len(members) > 1:
            titles = [m.title for m in members]
            cross_script = len({is_cjk(t) for t in titles}) > 1
            groups.append({
                "survivor_title": post.title,
                "merged_titles": titles,
                "cross_script": cross_script,
            })
    return groups


def run_arm(task: dict, arm_name: str, env_overrides: dict, gate_entities_cache: dict) -> dict:
    task_id = task["task_id"]
    request = build_discovery_request(task)
    replay_factory = functools.partial(ReplayRetriever, task_id=task_id)
    captured: dict = {}

    def controller_factory(*args, **kwargs):
        controller = SalvaController(*args, **kwargs)
        captured["controller"] = controller
        return controller

    saved_env = {key: os.environ.get(key) for key in ENV_KEYS}
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    os.environ.update(env_overrides)
    try:
        from salva_core.service import execute_discovery

        with no_network_guard(), \
             patch("salva_core.service.RoutedRetriever", replay_factory), \
             patch("salva_core.service.SalvaController", controller_factory):
            entities, _relations, _telemetry, meta, _source_attempts = execute_discovery(request)
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    controller = captured["controller"]
    raw_pool = controller._all_results
    raw_urls = {normalize_url(r.source_url) for r in raw_pool if r.source_url}
    admitted_urls: set[str] = set()
    for entity in entities:
        admitted_urls.update(normalize_url(u) for u in entity.source_urls)

    gt_entities = task["ground_truth_entities"]
    recall_all, recall_admitted = [], []
    for gt in gt_entities:
        urls = gt_urls_for(gt)
        recall_all.append(bool(urls & raw_urls))
        recall_admitted.append(bool(urls & admitted_urls))

    if arm_name == "B":
        gate_entities_cache[task_id] = entities

    merge_groups = []
    if arm_name in ("E", "G") and task_id in gate_entities_cache:
        merge_groups = infer_merge_groups(gate_entities_cache[task_id], entities)

    return {
        "task_id": task_id,
        "arm": arm_name,
        "env_overrides": env_overrides,
        "difficulty_tier": task["difficulty_tier"],
        "raw_count": len(raw_pool),
        "admitted_count": len(entities),
        "gt_count": len(gt_entities),
        "recall_all": recall_all,
        "recall_all_rate": sum(recall_all) / len(recall_all) if recall_all else None,
        "recall_admitted": recall_admitted,
        "recall_admitted_rate": sum(recall_admitted) / len(recall_admitted) if recall_admitted else None,
        "entities_merged_count": meta.get("entities_merged_count", 0),
        "merge_groups": merge_groups,
        "recorded_at": datetime.now(UTC).isoformat(),
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tasks = _load_tasks(TASK_SET_V2)
    gate_entities_cache: dict[str, list] = {}

    for task_id, task in tasks.items():
        for arm_name in ("B", "E", "F", "G"):  # B first: caches gate-mode entities for merge inference
            env_overrides = ARMS[arm_name]
            try:
                result = run_arm(task, arm_name, env_overrides, gate_entities_cache)
            except Exception as exc:  # noqa: BLE001 -- record failures, don't abort the sweep
                result = {
                    "task_id": task_id, "arm": arm_name, "env_overrides": env_overrides,
                    "error": f"{type(exc).__name__}: {exc}",
                    "recorded_at": datetime.now(UTC).isoformat(),
                }
            out_path = RESULTS_DIR / f"{task_id}_{arm_name}.json"
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            status = "OK" if "error" not in result else f"ERROR: {result['error']}"
            print(f"{task_id:30s} {arm_name}  {status}")


if __name__ == "__main__":
    main()
