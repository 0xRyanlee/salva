"""Full-scale offline validation: does enrichment/rerank.py::scoped_rerank add
anything over the confidence-ranked pool, and how does the whole
accumulate+rerank variant compare to Salva's current gate pipeline?

Board card: `salva-p7-rerank-fullscale-validate`. Extends
`confidence_rebuild_experiment.py` (which only compared two orderings of the
frozen pool: flat scorer vs `rank_candidates`) with the piece that experiment
explicitly did not test: the LLM rerank stage itself, plus a real
"Salva-current" column (the actual default gate pipeline's output, not a
pool-slice proxy for it).

Three columns, all offline replay against the same frozen fixtures
(`experiments/salva_v2/fixtures/`, recorded at `qualify_threshold=0.0`):

  1. Salva-current  = `SalvaController` run with production defaults
                       (`qualify_threshold=None` -> domain-calibrated gate,
                       `admission_policy="gate"`). This is what the service
                       returns to a caller today.
  2. baseline        = accumulate every candidate (`qualify_threshold=0.0`,
                       `admission_policy="rank"`... well no gate at all),
                       ordered by the flat `processing/scorer.py` composite,
                       no rerank. Identical definition and identical numbers
                       to the "baseline" column in CONFIDENCE_REBUILD_FINDINGS.md.
  3. accumulate+rerank = the same accumulated pool, ordered by
                       `processing/confidence.py::rank_candidates`, then
                       passed through `enrichment/rerank.py::scoped_rerank`.

Ground truth is used for evaluation only, never fed into ranking/rerank.

Run offline (no network for retrieval; scoped_rerank may attempt a local
omlx call -- see README note on its observed behavior in this environment):
    .venv/bin/python3 -m experiments.salva_v2.rerank_fullscale_validation
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from core.controller import SalvaController
from core.types import UnifiedResult
from enrichment.rerank import RerankCandidate, RerankResult, scoped_rerank
from experiments.salva_v2.confidence_rebuild_experiment import (
    _capture_pool,
    _eval_ranking,
    _load_tasks,
    _recall_at_all,
)
from experiments.salva_v2.harness.fixture_store import FIXTURES_ROOT
from experiments.salva_v2.harness.replay_retriever import ReplayRetriever, no_network_guard
from experiments.salva_v2.harness.task_request import build_discovery_request
from processing.confidence import rank_candidates

_OBJECTIVE_QUESTIONS = {
    "find_companies": "Which companies satisfy this search intent?",
    "find_partnership_signals": "Which entities/partnership signals satisfy this search intent?",
}


def _capture_gate_selected(task: dict[str, Any]) -> tuple[list[UnifiedResult], str | None]:
    """Replay the task with production defaults (qualify_threshold=None,
    admission_policy="gate") and return exactly what SalvaController.run()
    selects -- the current production output, no k-slicing proxy.

    Fixtures were recorded at qualify_threshold=0.0 (every round-1 candidate
    qualifies), so replaying with the domain-calibrated default threshold can,
    per harness/README.md "Known limitation", make round-2+ query generation
    diverge and request a query that was never recorded. Returns the error
    string instead of raising so callers can report per-task status honestly.
    """
    if not (FIXTURES_ROOT / task["task_id"] / "dive").exists() and not any(
        (FIXTURES_ROOT / task["task_id"]).glob("*/*.json")
    ):
        return [], "no_fixtures"

    from salva_core.service import execute_discovery

    request = build_discovery_request(task)  # qualify_threshold=None -> domain-calibrated gate
    captured: dict[str, Any] = {}
    original_run = SalvaController.run

    def run_capture(self: SalvaController) -> Any:
        selected, summary = original_run(self)
        captured["selected"] = selected
        return selected, summary

    def factory(policy: Any, strategy: str, retrieval_mode: str = "sequential", **kw: Any) -> ReplayRetriever:
        return ReplayRetriever(
            policy, strategy, retrieval_mode, task_id=task["task_id"], fixtures_root=FIXTURES_ROOT
        )

    try:
        with no_network_guard(), \
                patch("salva_core.service.RoutedRetriever", factory), \
                patch.object(SalvaController, "run", run_capture):
            execute_discovery(request)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:160]}"

    return captured["selected"], None


def _run_rerank(
    task: dict[str, Any], pool: list[UnifiedResult], intent: Any, provenance: Any
) -> tuple[list[UnifiedResult], RerankResult]:
    ranked = rank_candidates(pool, intent, provenance)
    ranked_results = [r for r, _, _ in ranked]
    candidates = [
        RerankCandidate(
            name=r.title or r.source_url,
            url=r.source_url,
            snippet=r.description,
            confidence=r.confidence,
        )
        for r in ranked_results
    ]
    question = _OBJECTIVE_QUESTIONS.get(
        task["objective"], "Which entities satisfy this search intent?"
    )
    intent_payload = task["intent"]
    result = scoped_rerank(
        candidates,
        question=question,
        market=intent_payload.get("market", ""),
        industry=intent_payload.get("industry", ""),
        objective=task["objective"],
        keywords=list(intent_payload.get("extra_keywords", [])),
    )
    # scoped_rerank's {name, url, claim} schema is intentionally terse for the
    # LLM's own judgment call, not a lossy record of the candidate. Evaluating
    # recall on the raw {name, url, claim} stub would conflate "the LLM
    # dropped this" with "the eval heuristic lost its snippet-based match
    # signal" (e.g. crosslang-06-delta's GT match depends on a CJK term that
    # is only in the original description, not title/claim). Map kept URLs
    # back to the original full-fidelity candidate -- the sane way any real
    # caller would reconcile scoped_rerank's output with its input pool.
    by_url = {r.source_url: r for r in ranked_results}
    kept_results = [
        by_url[item["url"]] if item["url"] in by_url else
        UnifiedResult(source_name="rerank", source_url=item["url"], title=item["name"], description=item["claim"])
        for item in result.kept
    ]
    return kept_results, result


def run() -> dict[str, Any]:
    tasks = _load_tasks()
    per_task: list[dict[str, Any]] = []

    for task in tasks:
        task_id = task["task_id"]
        gts = task["ground_truth_entities"]
        n_gt = len(gts)

        captured = _capture_pool(task)
        if captured is None:
            per_task.append({
                "task_id": task_id, "tier": task["difficulty_tier"],
                "excluded": True, "reason": "pool replay failed (see console)",
            })
            continue
        pool, intent, provenance = captured

        baseline = sorted(pool, key=lambda r: r.relevance_score, reverse=True)
        base_gt = _eval_ranking(baseline, gts, n_gt)
        base_10 = _eval_ranking(baseline, gts, 10)

        rerank_kept, rerank_result = _run_rerank(task, pool, intent, provenance)
        rerank_gt = _eval_ranking(rerank_kept, gts, n_gt)
        rerank_10 = _eval_ranking(rerank_kept, gts, 10)

        gate_selected, gate_error = _capture_gate_selected(task)
        if gate_error:
            gate_eval = None
        else:
            gate_eval = _eval_ranking(gate_selected, gts, max(len(gate_selected), 1))

        per_task.append({
            "task_id": task_id,
            "tier": task["difficulty_tier"],
            "n_gt": n_gt,
            "pool_size": len(pool),
            "recall_at_all": round(_recall_at_all(pool, gts), 3),
            "gate": {
                "selected_count": len(gate_selected),
                "error": gate_error,
                "recall": round(gate_eval["recall"], 3) if gate_eval else None,
                "primary_hit": round(gate_eval["primary_hit"], 3) if gate_eval else None,
                "precision": round(gate_eval["precision"], 3) if gate_eval else None,
            },
            "baseline@gt": {k: round(v, 3) for k, v in base_gt.items()},
            "baseline@10": {k: round(v, 3) for k, v in base_10.items()},
            "rerank@gt": {k: round(v, 3) for k, v in rerank_gt.items()},
            "rerank@10": {k: round(v, 3) for k, v in rerank_10.items()},
            "rerank_llm_available": rerank_result.llm_available,
            "rerank_notes": rerank_result.notes,
            "rerank_dropped_count": rerank_result.dropped_count,
        })

    return {"per_task": per_task, "aggregate": _aggregate(per_task)}


def _aggregate(per_task: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [t for t in per_task if not t.get("excluded")]
    n = len(scored)
    if n == 0:
        return {}

    def mean(path: str, field: str) -> float:
        return round(sum(t[path][field] for t in scored) / n, 3)

    gate_scored = [t for t in scored if t["gate"]["error"] is None]
    gate_recall_mean = (
        round(sum(t["gate"]["recall"] for t in gate_scored) / len(gate_scored), 3)
        if gate_scored else None
    )

    recall_improved = sum(1 for t in scored if t["rerank@gt"]["recall"] > t["baseline@gt"]["recall"])
    recall_regressed = sum(1 for t in scored if t["rerank@gt"]["recall"] < t["baseline@gt"]["recall"])

    return {
        "n_tasks_scored": n,
        "n_tasks_gate_ok": len(gate_scored),
        "n_tasks_gate_error": n - len(gate_scored),
        "gate_mean_recall": gate_recall_mean,
        "baseline_mean_recall@gt": mean("baseline@gt", "recall"),
        "rerank_mean_recall@gt": mean("rerank@gt", "recall"),
        "baseline_mean_recall@10": mean("baseline@10", "recall"),
        "rerank_mean_recall@10": mean("rerank@10", "recall"),
        "recall_improved_tasks": recall_improved,
        "recall_regressed_tasks": recall_regressed,
        "rerank_llm_available_any": any(t["rerank_llm_available"] for t in scored),
    }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2, ensure_ascii=False))
