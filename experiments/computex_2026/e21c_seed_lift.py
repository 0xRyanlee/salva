"""E21c — VP21c Seed URL Lift Benchmark.

Hypothesis (VP21c):
  With seed_urls pointing to a static Wikipedia page containing company names,
  seed_fetcher injects those names into KeywordGraph, enabling entity-specific
  sub-queries that raise recall from ~0.0 to ≥ 0.40 — validated on live DDG.

Design:
  Task C: CNCF founding/early member companies (taiwan_hardware domain)
    seed_url: https://en.wikipedia.org/wiki/Cloud_Native_Computing_Foundation
    Ground truth: companies explicitly mentioned in article as founding/early members

  A/B comparison per task:
    Condition A — no seed_urls (baseline, cold start)
    Condition B — with seed_urls (Wikipedia page injection)

  Pass criteria:
    Condition B: P ≥ 0.60 AND R ≥ 0.40
    Recall lift B > A by ≥ 0.15 (seed_urls contribution)

Run:
    python -m experiments.computex_2026.e21c_seed_lift [--budget 20] [--condition a|b|all]
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from experiments.computex_2026.e15_budget_ab import (
    BenchmarkResult,
    _name_match,
)

# ---------------------------------------------------------------------------
# Ground truth — pre-declared, not post-hoc
# ---------------------------------------------------------------------------

# Companies explicitly mentioned as founding or early members in the CNCF Wikipedia article.
# Verified 2026-06-11: https://en.wikipedia.org/wiki/Cloud_Native_Computing_Foundation
GROUND_TRUTH_CNCF = [
    "Google",
    "CoreOS",
    "Red Hat",
    "Cisco",
    "Intel",
    "Huawei",
    "IBM",
    "Docker",
    "VMware",
    "Lyft",
    "Twitter",
    "Oracle",
    "Samsung",
    "Fujitsu",
    "NEC",
]

# ---------------------------------------------------------------------------
# Run task
# ---------------------------------------------------------------------------

def run_task(
    condition: str,
    request_limit: int = 20,
) -> BenchmarkResult:
    from core.controller import SalvaController
    from core.keyword_graph import KeywordGraph
    from core.types import Intent
    from processing.dedup import MemoryDeduplicator, BM25_DOMAIN_THRESHOLDS
    from processing.extractor import BaseExtractor
    from processing.scorer import QualificationScorer
    from retrieval.router import RoutedRetriever
    from salva_core.schemas import RetrievalPolicy

    seed_urls = (
        ["https://en.wikipedia.org/wiki/Cloud_Native_Computing_Foundation"]
        if condition == "b" else []
    )

    intent = Intent(
        domain="taiwan_hardware",
        primary_terms=["CNCF", "Cloud Native Computing Foundation", "cloud native", "member company"],
        region="Global",
        roles=["member", "founding member", "platinum member", "gold member"],
        negative_terms=["job", "blog", "tutorial"],
        max_rounds=4,
        results_per_round=50,
        seed_urls=seed_urls,
    )

    policy = RetrievalPolicy()
    request_count = [0]

    def _make_counted(r: RoutedRetriever) -> RoutedRetriever:
        orig = r._search_sequential
        def _counted(query: str, n: int) -> list[dict]:
            if request_count[0] >= request_limit:
                return []
            request_count[0] += 1
            return orig(query, n)
        r._search_sequential = _counted
        return r

    retrievers = {
        "dive":   _make_counted(RoutedRetriever(policy=policy, strategy="dive")),
        "anchor": _make_counted(RoutedRetriever(policy=policy, strategy="anchor")),
        "radar":  _make_counted(RoutedRetriever(policy=policy, strategy="radar")),
    }

    scorer = QualificationScorer()
    effective_threshold = scorer.domain_threshold(intent.domain)
    graph = KeywordGraph(intent=intent)
    bm25_threshold = BM25_DOMAIN_THRESHOLDS.get(intent.domain, 0.85)
    controller = SalvaController(
        intent=intent,
        retrievers=retrievers,
        extractor=BaseExtractor(),
        deduplicator=MemoryDeduplicator(fuzzy_title=True, bm25_threshold=bm25_threshold),
        scorer=scorer,
        qualify_threshold=effective_threshold,
        keyword_graph=graph,
        convergence_threshold=0.0,
    )
    results, _ = controller.run()

    found_names = [r.title for r in results if r.qualified]
    tps = [n for n in found_names if _name_match(n, GROUND_TRUTH_CNCF)]
    p = len(tps) / len(found_names) if found_names else 0.0
    r_score = len(tps) / len(GROUND_TRUTH_CNCF) if GROUND_TRUTH_CNCF else 0.0
    f1 = 2 * p * r_score / (p + r_score) if p + r_score else 0.0

    return BenchmarkResult(
        task=f"cncf_members_{condition}",
        condition=f"salva_e21c_{condition}",
        entities_found=found_names,
        true_positives=tps,
        precision=round(p, 3),
        recall=round(r_score, 3),
        f1=round(f1, 3),
        requests_used=request_count[0],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="E21c Seed URL Lift Benchmark")
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument("--condition", choices=["a", "b", "all"], default="all")
    args = parser.parse_args()

    conditions: list[tuple[str, str]] = []
    if args.condition in ("a", "all"):
        conditions.append(("a", "No seed_urls (baseline)"))
    if args.condition in ("b", "all"):
        conditions.append(("b", "With Wikipedia seed_urls"))

    print("E21c — VP21c Seed URL Lift Benchmark")
    print(f"  Budget: {args.budget} per condition | Ground truth: {len(GROUND_TRUTH_CNCF)} entities")
    print()

    results: list[BenchmarkResult] = []
    for cond, label in conditions:
        print(f"  Condition {cond.upper()}: {label}")
        start = time.time()
        result = run_task(cond, request_limit=args.budget)
        elapsed = time.time() - start

        if result.requests_used == 0 or (result.requests_used <= 2 and not result.entities_found):
            print("    ⚠ SKIP — no network results")
            continue

        verdict = "PASS" if result.precision >= 0.60 and result.recall >= 0.40 else "FAIL"
        print(f"    Requests: {result.requests_used}/{args.budget}")
        print(f"    Found: {len(result.entities_found)} | TP: {len(result.true_positives)}")
        print(f"    P={result.precision:.3f}  R={result.recall:.3f}  F1={result.f1:.3f}")
        print(f"    Verdict: {'✓' if verdict == 'PASS' else '✗'} {verdict}  ({elapsed:.1f}s)")
        if result.true_positives:
            print(f"    TPs: {result.true_positives[:5]}")
        elif result.entities_found:
            print(f"    Found (not GT): {result.entities_found[:3]}")
        print()
        results.append(result)

    if len(results) == 2:
        r_a = next(r for r in results if "condition_a" in r.condition or "_a" in r.condition)
        r_b = next(r for r in results if "condition_b" in r.condition or "_b" in r.condition)
        lift = round(r_b.recall - r_a.recall, 3)
        lift_verdict = "PASS" if lift >= 0.15 else "FAIL"
        print(f"  Recall lift (B - A): {lift:+.3f}  → {lift_verdict}")

    # Save findings
    findings_path = Path(__file__).parent / "E21c_FINDINGS.md"
    with open(findings_path, "w", encoding="utf-8") as f:
        f.write("# E21c — VP21c Seed URL Lift Benchmark\n\n")
        f.write(f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}\n\n")
        f.write(f"**Task:** CNCF founding/early member companies\n")
        f.write(f"**Seed URL:** `https://en.wikipedia.org/wiki/Cloud_Native_Computing_Foundation`\n\n")
        for r in results:
            verdict = "PASS" if r.precision >= 0.60 and r.recall >= 0.40 else "FAIL"
            f.write(f"## Condition {r.condition.split('_')[-1].upper()}\n\n")
            f.write(f"- P={r.precision:.3f}  R={r.recall:.3f}  F1={r.f1:.3f}\n")
            f.write(f"- requests_used={r.requests_used}\n")
            f.write(f"- found: {r.entities_found[:10]}\n")
            f.write(f"- true_positives: {r.true_positives}\n")
            f.write(f"- **Verdict: {verdict}**\n\n")
        if len(results) == 2:
            f.write(f"## Seed URL Lift\n\n- Recall lift: {lift:+.3f}  → {lift_verdict}\n")
    print(f"  Findings written → {findings_path}")


if __name__ == "__main__":
    main()
