# E22c — Free Provider Reliability Benchmark

**Date:** 2026-06-12

**Hypothesis:** Free-first retrieval layer degrades gracefully under blocked/rate-limited/timeout provider failures.

## Results

| Scenario | Result | Details |
|---|---|---|
| S1 circuit breaker opens | ✓ PASS | BlockedProv.call_count=0 after circuit open (want 0) |
| S2 sequential fallthrough | ✓ PASS | GoodSeq.call_count=1 (want 1) | results=2 (want 2) |
| S3 cache hit skips provider | ✓ PASS | CacheProv.call_count=1 across 2 identical queries (want 1) |
| S4 parallel tolerates N-1 failures | ✓ PASS | results=2 (want ≥1) | ParGood.call_count=1 (want 1) |
| S5 empty result not cached | ✓ PASS | EmptyProv.call_count=2 (want 2; empty must not cache) |
| S6 mixed chain error classification | ✓ PASS | RateLimited.error=ProviderErrorType.RATE_LIMIT (want RATE_LIMIT) | TimedOut.error=ProviderErrorType.TIMEOUT (want TIMEOUT) | Healthy.successes=1 (want 1) | results=2 (want ≥1) |

**Overall: 6/6 → PASS**

## Architecture Properties Verified

- S1: ProviderHealth circuit breaker opens after ≥3 consecutive failures
- S2: `_search_sequential` falls through on exception to next healthy provider
- S3: SERPCache prevents redundant provider calls on identical queries
- S4: `_search_parallel` returns results even when N-1 providers raise
- S5: Empty result sets are not written to cache (no false-negative persistence)
- S6: `_classify_error` maps HTTP status codes to correct `ProviderErrorType`
