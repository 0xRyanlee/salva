from __future__ import annotations

from typing import Any, Literal, Protocol, cast
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed, Future

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
    ):
        self.policy = policy
        self.strategy = strategy
        self.retrieval_mode = retrieval_mode
        self.last_attempts: list[RetrievalAttempt] = []
        self.providers: list[RetrieverProtocol] = _build_provider_chain(policy, strategy)

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        self.last_attempts = []
        if not self.providers:
            return []

        if self.retrieval_mode == "sequential":
            return self._search_sequential(query, n)
        elif self.retrieval_mode == "adaptive":
            return self._search_adaptive(query, n)
        else:
            return self._search_parallel(query, n)

    def _search_sequential(self, query: str, n: int) -> list[dict[str, Any]]:
        """Sequential fallback: try providers one by one, stop on first success."""
        results: list[dict[str, Any]] = []

        for provider in self.providers:
            try:
                provider_results = provider.search(query, n)
                self.last_attempts.extend(provider.last_attempts)
                if provider_results:
                    results.extend(provider_results)
                    break
            except Exception:
                self.last_attempts.extend(provider.last_attempts)
                continue

        return _dedupe_results(results)[:n]

    def _search_adaptive(self, query: str, n: int) -> list[dict[str, Any]]:
        """Adaptive: start parallel but stop early if enough results."""
        results: list[dict[str, Any]] = []
        target_count = n * 2

        with ThreadPoolExecutor(max_workers=min(3, len(self.providers))) as executor:
            futures = {
                executor.submit(provider.search, query, n): provider
                for provider in self.providers
            }

            for future in as_completed(futures, timeout=self.policy.request_timeout * 2):
                provider = futures[future]
                try:
                    provider_results = future.result()
                except Exception:
                    provider_results = []

                self.last_attempts.extend(provider.last_attempts)

                if provider_results:
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

        with ThreadPoolExecutor(max_workers=len(self.providers)) as executor:
            futures = {
                executor.submit(provider.search, query, n): provider
                for provider in self.providers
            }

            try:
                for future in as_completed(futures, timeout=time_budget):
                    provider = futures[future]
                    try:
                        provider_results = future.result()
                    except Exception:
                        provider_results = []

                    self.last_attempts.extend(provider.last_attempts)
                    if provider_results:
                        results.extend(provider_results)
            except FuturesTimeout:
                pass

            for f in futures:
                if not f.done():
                    f.cancel()

        return _dedupe_results(results)[:n]


def _build_provider_chain(policy: RetrievalPolicy, strategy: str) -> list[RetrieverProtocol]:
    return cast(list[RetrieverProtocol], build_provider_chain(policy, strategy))  # backward-compatible alias


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
