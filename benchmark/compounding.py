"""Compounding-memory benchmark.

Falsifiable test of Salva's core product thesis: "run #K on a domain beats
run #1" because query_family_memory seeds the keyword graph.

Method (fixture-corpus, deterministic):
  - A FixtureProvider serves a fixed corpus; the only thing that changes between
    runs is the memory state in a shared, fresh SQLite DB.
  - We run the same DiscoveryRequest K times under a small query budget and
    measure recall/precision/efficiency per run.

Because the env var SALVA_SQLITE_PATH is read at import time by the persistence
layer, run_benchmark() sets it BEFORE importing any salva module.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

from benchmark.corpus import CORPUS, GOLD_URLS, Doc


class FixtureProvider:
    """Deterministic provider: ranks corpus docs by query-token overlap."""

    def __init__(self, strategy: str, docs: list[Doc]):
        self.strategy = strategy
        self.docs = docs
        self.last_attempts: list[Any] = []
        self.calls: list[str] = []

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        from retrieval.models import RetrievalAttempt

        self.calls.append(query)
        q_tokens = {t for t in query.lower().split() if t}
        scored: list[tuple[int, str, Doc]] = []
        for doc in self.docs:
            haystack = f"{doc.title} {doc.snippet}".lower()
            overlap = sum(1 for t in q_tokens if t in haystack)
            if overlap:
                scored.append((overlap, doc.url, doc))
        scored.sort(key=lambda x: (-x[0], x[1]))
        hits = [d for _, _, d in scored[:n]]
        self.last_attempts = [
            RetrievalAttempt(
                provider="fixture",
                base_url="fixture",
                mode="resilient",
                result_count=len(hits),
                succeeded=bool(hits),
                format_used="json",
            )
        ]
        return [{"title": d.title, "url": d.url, "snippet": d.snippet} for d in hits]


@dataclass
class RunMetrics:
    run: int
    entities: int
    found_gold: int
    recall: float
    precision: float
    new_gold: int
    queries: int
    memory_seeds: int
    relevant_entities: int


@dataclass
class BenchmarkResult:
    runs: list[RunMetrics] = field(default_factory=list)

    def verdict(self) -> dict[str, Any]:
        if len(self.runs) < 2:
            return {"status": "insufficient", "detail": "need >= 2 runs"}
        first, last = self.runs[0], self.runs[-1]
        recall_delta = last.recall - first.recall
        # efficiency: recall per query issued (higher = reaches gold with less budget)
        eff_first = first.recall / first.queries if first.queries else 0.0
        eff_last = last.recall / last.queries if last.queries else 0.0
        return {
            "recall_run1": round(first.recall, 3),
            "recall_runK": round(last.recall, 3),
            "recall_delta": round(recall_delta, 3),
            "efficiency_run1": round(eff_first, 4),
            "efficiency_runK": round(eff_last, 4),
            "thesis_supported": recall_delta >= 0.05 or (eff_last - eff_first) >= 0.02,
        }


def _coverage(source_urls: set[str]) -> set[str]:
    return source_urls & GOLD_URLS


def run_benchmark(
    k_runs: int = 5,
    max_rounds: int = 2,
    results_per_round: int = 20,
    db_path: str | None = None,
) -> BenchmarkResult:
    db_path = db_path or os.path.join(tempfile.mkdtemp(prefix="salva_bench_"), "bench.db")
    os.environ["SALVA_SQLITE_PATH"] = db_path
    os.environ["SALVA_SQLITE_FALLBACK_PATH"] = db_path

    # Imports AFTER env is set so DEFAULT_DB_PATH binds to the fresh DB.
    import retrieval.router as router_module
    from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, EnrichmentPolicy
    from salva_core.service import run_discovery

    provider_holder: dict[str, FixtureProvider] = {}

    def fake_chain(policy: Any, strategy: str) -> list[Any]:
        provider_holder[strategy] = FixtureProvider(strategy, CORPUS)
        return [provider_holder[strategy]]

    router_module._build_provider_chain = fake_chain  # type: ignore[assignment]

    request = DiscoveryRequest(
        objective="find_companies",
        intent=DiscoveryIntent(
            market="Germany",
            industry="enterprise software",
            constraints={"max_rounds": max_rounds, "results_per_round": results_per_round},
        ),
        enrichment=EnrichmentPolicy(mode="disabled"),
        max_results=results_per_round,
    )

    result = BenchmarkResult()
    seen_gold: set[str] = set()

    for i in range(1, k_runs + 1):
        provider_holder.clear()
        entities, _relations, telemetry, meta = run_discovery(request)

        found_urls: set[str] = set()
        relevant_entities = 0
        for e in entities:
            urls = set(e.source_urls)
            covered = _coverage(urls)
            if covered:
                relevant_entities += 1
            found_urls |= urls

        found_gold = _coverage(found_urls)
        new_gold = len(found_gold - seen_gold)
        seen_gold |= found_gold

        queries_issued = sum(len(p.calls) for p in provider_holder.values())
        result.runs.append(
            RunMetrics(
                run=i,
                entities=len(entities),
                found_gold=len(found_gold),
                recall=len(found_gold) / len(GOLD_URLS),
                precision=relevant_entities / len(entities) if entities else 0.0,
                new_gold=new_gold,
                queries=queries_issued,
                memory_seeds=int(meta.get("memory_seeds_used", 0) or 0),
                relevant_entities=relevant_entities,
            )
        )

    return result


def _render(result: BenchmarkResult) -> str:
    lines = [
        "# Compounding-memory benchmark",
        "",
        f"Gold corpus: {len(GOLD_URLS)} relevant docs.",
        "",
        "| run | entities | gold found | recall | precision | new gold | queries | mem seeds |",
        "|----:|---------:|-----------:|-------:|----------:|---------:|--------:|----------:|",
    ]
    for r in result.runs:
        lines.append(
            f"| {r.run} | {r.entities} | {r.found_gold} | {r.recall:.2f} | "
            f"{r.precision:.2f} | {r.new_gold} | {r.queries} | {r.memory_seeds} |"
        )
    lines += ["", "## Verdict", "", "```json", json.dumps(result.verdict(), indent=2), "```"]
    return "\n".join(lines)


def main() -> None:
    result = run_benchmark()
    report = _render(result)
    print(report)
    out = os.path.join(os.path.dirname(__file__), "results.md")
    with open(out, "w") as f:
        f.write(report + "\n")
    print(f"\n[written] {out}")


if __name__ == "__main__":
    main()
