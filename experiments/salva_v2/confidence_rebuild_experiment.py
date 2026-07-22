"""Offline ranking experiment: flat-score gate vs retrieval-derived confidence.

Independent variable: the function used to ORDER the frozen accumulated
candidate pool.
  - baseline  = processing/scorer.py flat composite (result.relevance_score)
  - treatment = processing/confidence.py rank_candidates (content + corroboration
                + source_trust)

Held constant: retrieval (frozen fixtures, recorded at qualify_threshold=0.0 so
the pool is identical for both arms), dedup, extraction, embedding backend.

The candidate pool and its RetrievalProvenance are read straight off the
controller the replay actually runs (its _all_results / _provenance), so both
arms rank the exact same objects.

Ground truth is used for EVALUATION ONLY (recall / precision / primary-source
hit). It is never fed into either ranking function -- the confidence scorer
never sees a GT signal.

Run offline (no network):
    .venv/bin/python3 -m experiments.salva_v2.confidence_rebuild_experiment
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

from core.controller import SalvaController
from core.types import Intent, UnifiedResult
from experiments.salva_v2.harness.fixture_store import FIXTURES_ROOT
from experiments.salva_v2.harness.replay_retriever import ReplayRetriever, no_network_guard
from experiments.salva_v2.harness.task_request import build_discovery_request
from processing.confidence import (
    RetrievalProvenance,
    corroboration_saturation,
    rank_candidates,
    registered_domain,
)

TASK_SET = Path(__file__).resolve().parent / "task_set_v2.json"

# Generic tokens stripped before entity-name matching so "Inc"/"Ltd"/"Company"
# don't produce spurious matches. Evaluation-only heuristic.
_GENERIC_TOKENS = frozenset({
    "inc", "ltd", "llc", "plc", "co", "corp", "corporation", "company",
    "limited", "foundation", "group", "holdings", "technologies", "technology",
    "the", "and", "of", "gmbh", "ag", "incorporated", "precision", "industry",
    "global", "international", "cloud", "computing", "web", "services",
})


def _load_tasks() -> list[dict[str, Any]]:
    data = json.loads(TASK_SET.read_text(encoding="utf-8"))
    return data["tasks"]


def _capture_pool(task: dict[str, Any]) -> tuple[list[UnifiedResult], Intent, RetrievalProvenance] | None:
    """Replay the task offline and return the controller's full frozen pool,
    the intent, and the provenance it accumulated. Returns None if fixtures
    are missing for this task."""
    if not (FIXTURES_ROOT / task["task_id"] / "dive").exists() and not any(
        (FIXTURES_ROOT / task["task_id"]).glob("*/*.json")
    ):
        return None

    from salva_core.service import execute_discovery

    request = build_discovery_request(task, qualify_threshold=0.0)
    captured: dict[str, SalvaController] = {}
    original_run = SalvaController.run

    def run_capture(self: SalvaController) -> Any:
        captured["controller"] = self
        return original_run(self)

    def factory(policy: Any, strategy: str, retrieval_mode: str = "sequential", **kw: Any) -> ReplayRetriever:
        return ReplayRetriever(
            policy, strategy, retrieval_mode, task_id=task["task_id"], fixtures_root=FIXTURES_ROOT
        )

    try:
        with no_network_guard(), \
                patch("salva_core.service.RoutedRetriever", factory), \
                patch.object(SalvaController, "run", run_capture):
            execute_discovery(request)
    except Exception as exc:  # FixtureMissingError etc. -- skip, report separately
        print(f"  ! {task['task_id']}: replay failed ({type(exc).__name__}: {str(exc)[:80]})")
        return None

    controller = captured["controller"]
    return controller._all_results, controller.intent, controller._provenance


def _name_tokens(name: str) -> set[str]:
    toks = {t for t in re.findall(r"[a-z0-9]+", name.lower()) if len(t) >= 2}
    return {t for t in toks if t not in _GENERIC_TOKENS}


def _cjk_terms(name: str) -> list[str]:
    return re.findall(r"[一-鿿]{2,}", name)


def _matches_gt(result: UnifiedResult, gt: dict[str, Any]) -> tuple[bool, bool]:
    """Return (mention_match, primary_source_hit).

    mention_match: candidate is about this GT entity (domain match OR the
    entity's distinctive name appears in the candidate's title/snippet).
    primary_source_hit: candidate's domain equals the GT primary source_url's.
    """
    cand_domain = registered_domain(result.source_url)
    gt_source = gt.get("source_url") or ""
    gt_domain = registered_domain(gt_source)
    primary = bool(gt_domain) and cand_domain == gt_domain

    text = f"{result.title} {result.description}".lower()
    tokens = _name_tokens(gt.get("name", ""))
    # Require a distinctive multi-char token match; single-token names must
    # appear whole. Also match Chinese names directly.
    name_hit = False
    if tokens:
        name_hit = any(re.search(rf"\b{re.escape(t)}\b", text) for t in tokens)
    for cjk in _cjk_terms(gt.get("name", "")) + _cjk_terms(gt.get("chinese_name", "")):
        if cjk in f"{result.title} {result.description}":
            name_hit = True

    mention = primary or name_hit or (bool(gt_domain) and gt_domain in text)
    return mention, primary


def _eval_ranking(
    ranked: list[UnifiedResult], gts: list[dict[str, Any]], k: int
) -> dict[str, float]:
    topk = ranked[:k]
    matched_gt = 0
    primary_gt = 0
    for gt in gts:
        if any(_matches_gt(r, gt)[0] for r in topk):
            matched_gt += 1
        if any(_matches_gt(r, gt)[1] for r in topk):
            primary_gt += 1
    matching_candidates = sum(1 for r in topk if any(_matches_gt(r, gt)[0] for gt in gts))
    n_gt = max(len(gts), 1)
    return {
        "recall": matched_gt / n_gt,
        "primary_hit": primary_gt / n_gt,
        "precision": matching_candidates / max(len(topk), 1),
    }


def _recall_at_all(pool: list[UnifiedResult], gts: list[dict[str, Any]]) -> float:
    matched = sum(1 for gt in gts if any(_matches_gt(r, gt)[0] for r in pool))
    return matched / max(len(gts), 1)


def run() -> dict[str, Any]:
    tasks = _load_tasks()
    per_task: list[dict[str, Any]] = []

    for task in tasks:
        captured = _capture_pool(task)
        if captured is None:
            continue
        pool, intent, provenance = captured
        gts = task["ground_truth_entities"]
        n_gt = len(gts)

        baseline = sorted(pool, key=lambda r: r.relevance_score, reverse=True)
        treatment_ranked = rank_candidates(pool, intent, provenance)
        treatment = [r for r, _, _ in treatment_ranked]

        k = n_gt
        base_k = _eval_ranking(baseline, gts, k)
        treat_k = _eval_ranking(treatment, gts, k)
        base_10 = _eval_ranking(baseline, gts, 10)
        treat_10 = _eval_ranking(treatment, gts, 10)

        per_task.append({
            "task_id": task["task_id"],
            "tier": task["difficulty_tier"],
            "pool_size": len(pool),
            "n_gt": n_gt,
            "recall_at_all": round(_recall_at_all(pool, gts), 3),
            "saturation": round(corroboration_saturation(treatment_ranked), 3),
            "baseline@gt": {k2: round(v, 3) for k2, v in base_k.items()},
            "treatment@gt": {k2: round(v, 3) for k2, v in treat_k.items()},
            "baseline@10": {k2: round(v, 3) for k2, v in base_10.items()},
            "treatment@10": {k2: round(v, 3) for k2, v in treat_10.items()},
        })

    return {"per_task": per_task, "aggregate": _aggregate(per_task)}


def _aggregate(per_task: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(per_task)
    if n == 0:
        return {}

    def mean(path: str, field: str) -> float:
        return round(sum(t[path][field] for t in per_task) / n, 3)

    recall_improved = sum(1 for t in per_task if t["treatment@gt"]["recall"] > t["baseline@gt"]["recall"])
    recall_regressed = sum(1 for t in per_task if t["treatment@gt"]["recall"] < t["baseline@gt"]["recall"])
    primary_improved = sum(1 for t in per_task if t["treatment@gt"]["primary_hit"] > t["baseline@gt"]["primary_hit"])
    primary_regressed = sum(1 for t in per_task if t["treatment@gt"]["primary_hit"] < t["baseline@gt"]["primary_hit"])

    return {
        "n_tasks": n,
        "mean_recall_at_all": round(sum(t["recall_at_all"] for t in per_task) / n, 3),
        "baseline_mean_recall@gt": mean("baseline@gt", "recall"),
        "treatment_mean_recall@gt": mean("treatment@gt", "recall"),
        "baseline_mean_primary@gt": mean("baseline@gt", "primary_hit"),
        "treatment_mean_primary@gt": mean("treatment@gt", "primary_hit"),
        "baseline_mean_precision@gt": mean("baseline@gt", "precision"),
        "treatment_mean_precision@gt": mean("treatment@gt", "precision"),
        "baseline_mean_recall@10": mean("baseline@10", "recall"),
        "treatment_mean_recall@10": mean("treatment@10", "recall"),
        "recall_improved_tasks": recall_improved,
        "recall_regressed_tasks": recall_regressed,
        "primary_improved_tasks": primary_improved,
        "primary_regressed_tasks": primary_regressed,
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, ensure_ascii=False))
