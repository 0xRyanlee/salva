"""E22c — Free Provider Reliability Benchmark (VP-free).

Hypothesis (VP-free):
  The free-first retrieval layer (ProviderHealth + CircuitBreaker + SERPCache +
  RoutedRetriever) degrades gracefully under realistic provider failure patterns:
  blocked instances are skipped, results are cached, and at least one healthy
  provider is always attempted in a mixed chain.

Design:
  Six controlled scenarios using mock providers — no live network required.
  Each scenario verifies one specific resilience property.

  S1  Circuit breaker opens after 3 consecutive failures of same error type
  S2  Sequential mode skips blocked provider, falls through to healthy one
  S3  SERP cache hit skips all providers on repeated query
  S4  Parallel mode tolerates N-1 failures and returns from survivor
  S5  Empty results are never cached (cache miss on next call still hits provider)
  S6  Mixed chain: rate-limited + timeout + healthy → healthy provider returns results
      and health records are updated correctly per provider

Pass criteria (all six must pass):
  P1  S1: blocked provider call_count == 0 after cooldown opens
  P2  S2: fallback provider is called exactly once, result returned
  P3  S3: provider call_count == 1 across two identical queries (second is cache hit)
  P4  S4: parallel mode returns ≥ 1 result when only 1 of 3 providers is healthy
  P5  S5: empty result not cached — second call still hits provider
  P6  S6: correct error types recorded per provider (RATE_LIMIT / TIMEOUT / success)

Run:
    python -m experiments.computex_2026.e22c_free_provider_reliability
"""
from __future__ import annotations

import time
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from retrieval.cache import SERPCache
from retrieval.health import ProviderErrorType, ProviderHealthRegistry
from retrieval.router import RoutedRetriever, _provider_id
from salva_core.schemas import RetrievalPolicy


# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------

class _Mock:
    """Base mock provider."""
    strategy = "dive"
    last_attempts: list = []

    def __init__(self, label: str, results: list[dict] | None = None,
                 raises: Exception | None = None):
        self._label = label
        self._results = results or []
        self._raises = raises
        self.call_count = 0

    def search(self, query: str, n: int) -> list[dict]:
        self.call_count += 1
        if self._raises:
            raise self._raises
        return self._results


def _good(label: str, n: int = 2) -> _Mock:
    return type(label, (_Mock,), {})(
        label,
        results=[
            {"title": f"{label} Result {i}", "url": f"https://{label.lower()}.example/{i}",
             "snippet": f"content from {label}"}
            for i in range(n)
        ],
    )


def _bad(label: str, exc: Exception) -> _Mock:
    return type(label, (_Mock,), {})(label, raises=exc)


def _empty(label: str) -> _Mock:
    return type(label, (_Mock,), {})(label, results=[])


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    name: str
    passed: bool
    details: str
    elapsed_ms: float


def _fresh(tmp: str) -> tuple[ProviderHealthRegistry, SERPCache]:
    return ProviderHealthRegistry(), SERPCache(cache_dir=tmp, ttl=3600)


def _retriever(health: ProviderHealthRegistry, cache: SERPCache,
               mode: str = "sequential") -> RoutedRetriever:
    r = RoutedRetriever(
        policy=RetrievalPolicy(),
        strategy="dive",
        retrieval_mode=mode,  # type: ignore[arg-type]
        health=health,
        cache=cache,
    )
    r.providers = []
    return r


# ---------------------------------------------------------------------------
# S1 — Circuit breaker opens after consecutive failures
# ---------------------------------------------------------------------------

def run_s1(tmp: str) -> ScenarioResult:
    t0 = time.monotonic()
    health, cache = _fresh(tmp)
    r = _retriever(health, cache)

    blocker = _bad("BlockedProv", OSError("403 Forbidden"))
    helper = _good("HelperProv")
    r.providers = [blocker, helper]

    pid = _provider_id(blocker)

    # Trigger 3 failures to open the circuit
    for _ in range(3):
        health.record_failure(pid, ProviderErrorType.BLOCKED)

    r.search("anything", 5)
    calls_after_open = blocker.call_count

    passed = calls_after_open == 0
    details = f"BlockedProv.call_count={calls_after_open} after circuit open (want 0)"
    return ScenarioResult("S1 circuit breaker opens", passed, details,
                          (time.monotonic() - t0) * 1000)


# ---------------------------------------------------------------------------
# S2 — Sequential falls through blocked provider to healthy one
# ---------------------------------------------------------------------------

def run_s2(tmp: str) -> ScenarioResult:
    t0 = time.monotonic()
    health, cache = _fresh(tmp)
    r = _retriever(health, cache)

    bad = _bad("BadSeq", OSError("429 Too Many Requests"))
    good = _good("GoodSeq")
    r.providers = [bad, good]

    results = r.search("fallthrough query", 5)

    passed = good.call_count == 1 and len(results) == 2
    details = (
        f"GoodSeq.call_count={good.call_count} (want 1) | "
        f"results={len(results)} (want 2)"
    )
    return ScenarioResult("S2 sequential fallthrough", passed, details,
                          (time.monotonic() - t0) * 1000)


# ---------------------------------------------------------------------------
# S3 — SERP cache hit skips all providers on second identical query
# ---------------------------------------------------------------------------

def run_s3(tmp: str) -> ScenarioResult:
    t0 = time.monotonic()
    health, cache = _fresh(tmp)
    r = _retriever(health, cache)

    prov = _good("CacheProv")
    r.providers = [prov]

    r.search("repeated query", 5)     # call 1 — cache miss, hits provider
    r.search("repeated query", 5)     # call 2 — cache hit, skips provider

    passed = prov.call_count == 1
    details = f"CacheProv.call_count={prov.call_count} across 2 identical queries (want 1)"
    return ScenarioResult("S3 cache hit skips provider", passed, details,
                          (time.monotonic() - t0) * 1000)


# ---------------------------------------------------------------------------
# S4 — Parallel mode returns results when 1 of 3 providers is healthy
# ---------------------------------------------------------------------------

def run_s4(tmp: str) -> ScenarioResult:
    t0 = time.monotonic()
    health, cache = _fresh(tmp)
    r = _retriever(health, cache, mode="parallel")

    p1 = _bad("ParFail1", OSError("403 Forbidden"))
    p2 = _bad("ParFail2", OSError("timeout"))
    p3 = _good("ParGood")
    r.providers = [p1, p2, p3]

    results = r.search("parallel resilience", 5)

    passed = len(results) >= 1 and p3.call_count == 1
    details = (
        f"results={len(results)} (want ≥1) | "
        f"ParGood.call_count={p3.call_count} (want 1)"
    )
    return ScenarioResult("S4 parallel tolerates N-1 failures", passed, details,
                          (time.monotonic() - t0) * 1000)


# ---------------------------------------------------------------------------
# S5 — Empty results are not cached; second call still hits provider
# ---------------------------------------------------------------------------

def run_s5(tmp: str) -> ScenarioResult:
    t0 = time.monotonic()
    health, cache = _fresh(tmp)
    r = _retriever(health, cache)

    empty = _empty("EmptyProv")
    r.providers = [empty]

    r.search("empty query", 5)   # returns []
    r.search("empty query", 5)   # should NOT be cached — hits provider again

    passed = empty.call_count == 2
    details = f"EmptyProv.call_count={empty.call_count} (want 2; empty must not cache)"
    return ScenarioResult("S5 empty result not cached", passed, details,
                          (time.monotonic() - t0) * 1000)


# ---------------------------------------------------------------------------
# S6 — Mixed chain: error types recorded correctly per provider
# ---------------------------------------------------------------------------

def run_s6(tmp: str) -> ScenarioResult:
    t0 = time.monotonic()
    health, cache = _fresh(tmp)
    r = _retriever(health, cache)

    rl = _bad("RateLimited", OSError("429 Too Many Requests"))
    to = _bad("TimedOut",    OSError("Connection timed out"))
    ok = _good("Healthy")
    r.providers = [rl, to, ok]

    results = r.search("mixed chain", 5)

    pid_rl = _provider_id(rl)
    pid_to = _provider_id(to)
    pid_ok = _provider_id(ok)

    h_rl = health.get(pid_rl)
    h_to = health.get(pid_to)
    h_ok = health.get(pid_ok)

    rl_correct = h_rl.last_error_type == ProviderErrorType.RATE_LIMIT
    to_correct = h_to.last_error_type == ProviderErrorType.TIMEOUT
    ok_correct = h_ok.total_successes == 1

    passed = rl_correct and to_correct and ok_correct and len(results) >= 1
    details = (
        f"RateLimited.error={h_rl.last_error_type} (want RATE_LIMIT) | "
        f"TimedOut.error={h_to.last_error_type} (want TIMEOUT) | "
        f"Healthy.successes={h_ok.total_successes} (want 1) | "
        f"results={len(results)} (want ≥1)"
    )
    return ScenarioResult("S6 mixed chain error classification", passed, details,
                          (time.monotonic() - t0) * 1000)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SCENARIOS = [run_s1, run_s2, run_s3, run_s4, run_s5, run_s6]


def main() -> None:
    print("E22c — Free Provider Reliability Benchmark")
    print(f"  Scenarios: {len(SCENARIOS)}  |  No live network required")
    print()

    results: list[ScenarioResult] = []
    with tempfile.TemporaryDirectory() as tmp:
        for fn in SCENARIOS:
            sr = fn(tmp)
            status = "✓ PASS" if sr.passed else "✗ FAIL"
            print(f"  {status}  {sr.name}")
            print(f"         {sr.details}  ({sr.elapsed_ms:.1f}ms)")
            results.append(sr)

    print()
    passed_n = sum(1 for r in results if r.passed)
    total = len(results)
    overall = "PASS" if passed_n == total else "FAIL"
    print(f"  Overall: {passed_n}/{total}  →  {overall}")

    # -----------------------------------------------------------------------
    # Write findings
    # -----------------------------------------------------------------------
    findings_path = Path(__file__).parent / "E22c_FINDINGS.md"
    with open(findings_path, "w", encoding="utf-8") as f:
        f.write("# E22c — Free Provider Reliability Benchmark\n\n")
        f.write(f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}\n\n")
        f.write("**Hypothesis:** Free-first retrieval layer degrades gracefully under ")
        f.write("blocked/rate-limited/timeout provider failures.\n\n")
        f.write("## Results\n\n")
        f.write("| Scenario | Result | Details |\n")
        f.write("|---|---|---|\n")
        for r in results:
            verdict = "✓ PASS" if r.passed else "✗ FAIL"
            f.write(f"| {r.name} | {verdict} | {r.details} |\n")
        f.write(f"\n**Overall: {passed_n}/{total} → {overall}**\n\n")
        f.write("## Architecture Properties Verified\n\n")
        f.write("- S1: ProviderHealth circuit breaker opens after ≥3 consecutive failures\n")
        f.write("- S2: `_search_sequential` falls through on exception to next healthy provider\n")
        f.write("- S3: SERPCache prevents redundant provider calls on identical queries\n")
        f.write("- S4: `_search_parallel` returns results even when N-1 providers raise\n")
        f.write("- S5: Empty result sets are not written to cache (no false-negative persistence)\n")
        f.write("- S6: `_classify_error` maps HTTP status codes to correct `ProviderErrorType`\n")
    print(f"\n  Findings written → {findings_path}")


if __name__ == "__main__":
    main()
