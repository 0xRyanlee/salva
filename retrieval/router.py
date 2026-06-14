from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any, Literal, Protocol, cast

from retrieval.cache import SERPCache, get_serp_cache
from retrieval.health import (
    ProviderErrorType,
    ProviderHealthRegistry,
    get_health_registry,
)
from retrieval.models import RetrievalAttempt
from retrieval.registry import build_provider_chain
from salva_core.schemas import RetrievalPolicy

RetrievalStrategy = Literal["sequential", "parallel", "adaptive"]


class RetrieverProtocol(Protocol):
    strategy: str
    last_attempts: list[RetrievalAttempt]

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]: ...


class RoutedRetriever:
    def __init__(
        self,
        policy: RetrievalPolicy,
        strategy: str,
        retrieval_mode: RetrievalStrategy = "sequential",
        health: ProviderHealthRegistry | None = None,
        cache: SERPCache | None = None,
    ):
        self.policy = policy
        self.strategy = strategy
        self.retrieval_mode = retrieval_mode
        self.last_attempts: list[RetrievalAttempt] = []
        self.providers: list[RetrieverProtocol] = _build_provider_chain(policy, strategy)
        self._health = health if health is not None else get_health_registry()
        self._cache = cache if cache is not None else get_serp_cache()

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        if not self.providers:
            return []

        # Tier 0: SERP cache — skip all providers if we have a fresh result
        region = self.policy.region_hint or ""
        cached = self._cache.get(self.strategy, query, region=region)
        if cached is not None:
            return cached[:n]

        if self.retrieval_mode == "sequential":
            results = self._search_sequential(query, n)
        elif self.retrieval_mode == "adaptive":
            results = self._search_adaptive(query, n)
        else:
            results = self._search_parallel(query, n)

        if results:
            self._cache.set(self.strategy, query, results, region=region)

        return results

    def _search_sequential(self, query: str, n: int) -> list[dict[str, Any]]:
        """Sequential fallback: try providers one by one, skipping those in cooldown.

        Falls through to the next provider when results have no snippet content.
        Keeps the first non-empty set as a last-resort fallback.
        Records provider health: success on first usable hit, failure on exception.
        """
        fallback_results: list[dict[str, Any]] = []
        fallback_pid: str | None = None

        for provider in self.providers:
            pid = _provider_id(provider)
            if not self._health.is_usable(pid):
                continue

            try:
                provider_results = provider.search(query, n)
                self.last_attempts.extend(getattr(provider, "last_attempts", []))
                if not provider_results:
                    continue
                if _has_content(provider_results):
                    self._health.record_success(pid)
                    return _dedupe_results(provider_results)[:n]
                if not fallback_results:
                    fallback_results = provider_results
                    fallback_pid = pid
            except Exception as exc:
                self.last_attempts.extend(getattr(provider, "last_attempts", []))
                self._health.record_failure(pid, _classify_error(str(exc)))
                continue

        if fallback_results and fallback_pid:
            self._health.record_success(fallback_pid)
        return _dedupe_results(fallback_results)[:n]

    def _search_adaptive(self, query: str, n: int) -> list[dict[str, Any]]:
        """Adaptive: start parallel but stop early if enough results."""
        results: list[dict[str, Any]] = []
        target_count = n * 2

        usable = [p for p in self.providers if self._health.is_usable(_provider_id(p))]
        if not usable:
            return []

        with ThreadPoolExecutor(max_workers=min(3, len(usable))) as executor:
            futures = {
                executor.submit(provider.search, query, n): provider
                for provider in usable
            }

            for future in as_completed(futures, timeout=self.policy.request_timeout * 2):
                provider = futures[future]
                pid = _provider_id(provider)
                try:
                    provider_results = future.result()
                except Exception as exc:
                    self.last_attempts.extend(getattr(provider, "last_attempts", []))
                    self._health.record_failure(pid, _classify_error(str(exc)))
                    continue

                self.last_attempts.extend(getattr(provider, "last_attempts", []))
                if provider_results:
                    self._health.record_success(pid)
                    results.extend(provider_results)
                    if len(results) >= target_count:
                        for f in futures:
                            f.cancel()
                        break

        return _dedupe_results(results)[:n]

    def _search_parallel(self, query: str, n: int) -> list[dict[str, Any]]:
        """Parallel with time budget: wait for all providers, bounded by a timeout."""
        results: list[dict[str, Any]] = []
        time_budget = self.policy.request_timeout * 1.5

        usable = [p for p in self.providers if self._health.is_usable(_provider_id(p))]
        if not usable:
            return []

        with ThreadPoolExecutor(max_workers=len(usable)) as executor:
            futures = {
                executor.submit(provider.search, query, n): provider
                for provider in usable
            }

            try:
                for future in as_completed(futures, timeout=time_budget):
                    provider = futures[future]
                    pid = _provider_id(provider)
                    try:
                        provider_results = future.result()
                    except Exception as exc:
                        self.last_attempts.extend(getattr(provider, "last_attempts", []))
                        self._health.record_failure(pid, _classify_error(str(exc)))
                        continue

                    self.last_attempts.extend(getattr(provider, "last_attempts", []))
                    if provider_results:
                        self._health.record_success(pid)
                        results.extend(provider_results)
            except FuturesTimeout:
                pass

            for f in futures:
                if not f.done():
                    f.cancel()

        return _dedupe_results(results)[:n]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _provider_id(provider: Any) -> str:
    """Stable health-registry key for a provider: class name."""
    return type(provider).__name__


def _classify_error(err_str: str) -> ProviderErrorType:
    err = err_str.lower()
    if "429" in err or "rate" in err or "too many" in err or "ratelimit" in err:
        return ProviderErrorType.RATE_LIMIT
    if "403" in err or "forbidden" in err or "blocked" in err:
        return ProviderErrorType.BLOCKED
    if "timeout" in err or "timed out" in err:
        return ProviderErrorType.TIMEOUT
    if "empty" in err or "no result" in err:
        return ProviderErrorType.EMPTY_RESULT
    return ProviderErrorType.NETWORK_ERROR


def _has_content(results: list[dict[str, Any]]) -> bool:
    """True if ≥40% of results carry a non-empty snippet."""
    if not results:
        return False
    with_snippet = sum(1 for r in results if str(r.get("snippet", "")).strip())
    return with_snippet / len(results) >= 0.4


def _build_provider_chain(policy: RetrievalPolicy, strategy: str) -> list[RetrieverProtocol]:
    return cast(list[RetrieverProtocol], build_provider_chain(policy, strategy))


def _dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in results:
        url = str(result.get("url", "")).strip()
        key = url or f"{result.get('engine', '')}:{result.get('title', '')}"
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped
