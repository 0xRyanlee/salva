"""E21 — Live Budget-Matched Benchmark.

Hypothesis (VP21): Under equal budget (12 requests), live DDG retrieval,
and pre-declared ground truth, Salva achieves P ≥ 0.60 and R ≥ 0.40 —
validated on production infrastructure, not frozen corpus.

Design:
  - Pre-declared ground truth (same as E15 — not post-hoc)
  - Equal budget: 12 requests per task
  - Live DDG retrieval via RoutedRetriever (real network)
  - domain-calibrated qualify_threshold (bd_leads=0.35, taiwan_hardware=0.35)
  - Same ScorerConfig as E15

Targets:
  A. Naturehike DACH — distributor/importer search (bd_leads domain)
  B. Computex 2026 Taiwan hardware — exhibitor search (taiwan_hardware domain)

Pass criteria:
  P ≥ 0.60 AND R ≥ 0.40 for both tasks

Run:
    python -m experiments.computex_2026.e21_live_benchmark [--task a|b|all]
    python -m experiments.computex_2026.e21_live_benchmark --task a --budget 20

REQUIRES: live network access + DDG responding.
If DDG returns no results (network unavailable), the script will report SKIP.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from experiments.computex_2026.e15_budget_ab import (
    GROUND_TRUTH_COMPUTEX,
    GROUND_TRUTH_NATUREHIKE,
    BenchmarkResult,
    _name_match,
)

# ---------------------------------------------------------------------------
# Live benchmark run
# ---------------------------------------------------------------------------

def run_live_task(
    task: str,
    request_limit: int = 12,
    qualify_threshold: float | None = None,
) -> BenchmarkResult:
    from core.controller import SalvaController
    from core.keyword_graph import KeywordGraph
    from core.types import Intent
    from processing.dedup import MemoryDeduplicator, BM25_DOMAIN_THRESHOLDS
    from processing.extractor import BaseExtractor
    from processing.scorer import QualificationScorer
    from retrieval.router import RoutedRetriever
    from salva_core.schemas import RetrievalPolicy

    if task == "naturehike":
        intent = Intent(
            domain="bd_leads",
            primary_terms=["Naturehike", "outdoor equipment", "Naturehike Händler", "Naturehike Vertrieb"],
            region="Germany Austria Switzerland",
            roles=["distributor", "Händler", "Vertriebspartner", "Importeur"],
            negative_terms=["blog", "review", "job"],
            max_rounds=5,
            results_per_round=50,
        )
        ground_truth = GROUND_TRUTH_NATUREHIKE
    else:  # computex
        intent = Intent(
            domain="taiwan_hardware",
            primary_terms=["Computex 2026", "Taiwan hardware", "Taiwan PC manufacturer"],
            region="Taipei",
            roles=["exhibitor", "manufacturer", "硬體廠商"],
            negative_terms=["job", "review", "blog"],
            max_rounds=5,
            results_per_round=50,
        )
        ground_truth = GROUND_TRUTH_COMPUTEX

    scorer = QualificationScorer()
    effective_threshold = (
        qualify_threshold if qualify_threshold is not None
        else scorer.domain_threshold(intent.domain)
    )

    # Live retriever — real SearXNG (Bing+Mojeek from TW IP)
    # region_hint disabled: passing language=de/zh-tw to Bing via SearXNG causes totally
    # incorrect results (Korean YouTube pages). Let query terms carry geo-signal instead.
    policy = RetrievalPolicy()

    # Request count proxy — patch all strategy retrievers so budget is tracked accurately
    request_count = [0]
    _REQUEST_DELAY = float(os.getenv("E21_REQUEST_DELAY", "3.0"))  # seconds between requests

    def _make_counted(r: "RoutedRetriever") -> "RoutedRetriever":
        import time as _time
        orig = r._search_sequential
        def _counted(query: str, n: int) -> list[dict]:
            if request_count[0] >= request_limit:
                return []
            if request_count[0] > 0:
                _time.sleep(_REQUEST_DELAY)
            request_count[0] += 1
            return orig(query, n)
        r._search_sequential = _counted
        return r

    retrievers = {
        "dive":   _make_counted(RoutedRetriever(policy=policy, strategy="dive")),
        "anchor": _make_counted(RoutedRetriever(policy=policy, strategy="anchor")),
        "radar":  _make_counted(RoutedRetriever(policy=policy, strategy="radar")),
    }

    graph = KeywordGraph(intent=intent)
    bm25_threshold = BM25_DOMAIN_THRESHOLDS.get(intent.domain, 0.85)
    controller = SalvaController(
        intent=intent,
        retrievers=retrievers,
        extractor=BaseExtractor(),
        deduplicator=MemoryDeduplicator(
            fuzzy_title=True,
            bm25_threshold=bm25_threshold,
        ),
        scorer=scorer,
        qualify_threshold=effective_threshold,
        keyword_graph=graph,
        convergence_threshold=0.0,  # disable early-stop; exhaust full budget
    )
    results, summary = controller.run()

    found_names = [r.title for r in results if r.qualified]
    tps = [n for n in found_names if _name_match(n, ground_truth)]

    p = len(tps) / len(found_names) if found_names else 0.0
    r = len(tps) / len(ground_truth) if ground_truth else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0

    return BenchmarkResult(
        task=task,
        condition="salva_live_e21",
        entities_found=found_names,
        true_positives=tps,
        precision=round(p, 3),
        recall=round(r, 3),
        f1=round(f1, 3),
        requests_used=request_count[0],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="E21 Live Budget-Matched Benchmark")
    parser.add_argument("--task", choices=["a", "b", "all"], default="all")
    parser.add_argument("--budget", type=int, default=12)
    args = parser.parse_args()

    tasks_to_run: list[tuple[str, str]] = []
    if args.task in ("a", "all"):
        tasks_to_run.append(("naturehike", "Naturehike DACH"))
    if args.task in ("b", "all"):
        tasks_to_run.append(("computex", "Computex 2026"))

    print("E21 — Live Budget-Matched Benchmark")
    print(f"  Budget: {args.budget} requests per task")
    print(f"  Threshold: domain-calibrated")
    print()

    results: list[BenchmarkResult] = []
    for task_id, task_label in tasks_to_run:
        gt = GROUND_TRUTH_NATUREHIKE if task_id == "naturehike" else GROUND_TRUTH_COMPUTEX
        print(f"  Task: {task_label.upper()} | ground truth: {len(gt)} entities")
        start = time.time()
        result = run_live_task(task_id, request_limit=args.budget)
        elapsed = time.time() - start

        # Detect if DDG returned nothing (no-network signal)
        if result.requests_used == 0 or (result.requests_used <= 2 and len(result.entities_found) == 0):
            print(f"    ⚠️  SKIP — DDG returned no results (network unavailable or quota hit)")
            print()
            continue

        verdict = "PASS" if result.precision >= 0.60 and result.recall >= 0.40 else "FAIL"
        print(f"    Requests used: {result.requests_used}/{args.budget}")
        print(f"    Found: {len(result.entities_found)} entities | TP: {len(result.true_positives)}")
        print(f"    P={result.precision:.3f}  R={result.recall:.3f}  F1={result.f1:.3f}")
        print(f"    Verdict: {'✅' if verdict == 'PASS' else '❌'} {verdict}  (elapsed: {elapsed:.1f}s)")
        if result.true_positives:
            print(f"    TPs: {result.true_positives[:5]}")
        if result.entities_found and not result.true_positives:
            print(f"    Found (not GT): {result.entities_found[:3]}")
        print()
        results.append(result)

    # Save findings
    if results:
        findings_path = Path(__file__).parent / "E21_FINDINGS.md"
        with open(findings_path, "w", encoding="utf-8") as f:
            f.write("# E21 — Live Benchmark Findings\n\n")
            f.write(f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}\n\n")
            for r in results:
                verdict = "PASS" if r.precision >= 0.60 and r.recall >= 0.40 else "FAIL"
                f.write(f"## Task: {r.task}\n\n")
                f.write(f"- P={r.precision:.3f}  R={r.recall:.3f}  F1={r.f1:.3f}\n")
                f.write(f"- requests_used={r.requests_used}\n")
                f.write(f"- found: {r.entities_found}\n")
                f.write(f"- true_positives: {r.true_positives}\n")
                f.write(f"- **Verdict: {verdict}**\n\n")
        print(f"  Findings written → {findings_path}")


if __name__ == "__main__":
    main()
