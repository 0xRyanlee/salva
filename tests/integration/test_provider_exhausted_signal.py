from dataclasses import dataclass

import retrieval.router as router_module
from retrieval.health import ProviderHealthRegistry
from retrieval.models import RetrievalAttempt
from retrieval.router import RoutedRetriever
from salva_core.schemas import RetrievalPolicy


@dataclass
class FailingProvider:
    name: str

    def __post_init__(self) -> None:
        self.strategy = "radar"
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict]:
        raise RuntimeError("simulated provider failure")


@dataclass
class OkProvider:
    name: str
    results: list[dict]

    def __post_init__(self) -> None:
        self.strategy = "radar"
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict]:
        return self.results


def _isolated_retriever(monkeypatch, tmp_path, providers, retrieval_mode) -> RoutedRetriever:
    monkeypatch.setattr(router_module, "_build_provider_chain", lambda policy, strategy: providers)
    from retrieval.cache import SERPCache

    fresh_cache = SERPCache(cache_dir=str(tmp_path / "cache"), ttl=3600)
    return RoutedRetriever(
        policy=RetrievalPolicy(), strategy="radar", retrieval_mode=retrieval_mode,
        health=ProviderHealthRegistry(), cache=fresh_cache,
    )


def test_sequential_all_providers_fail_marks_exhausted(monkeypatch, tmp_path) -> None:
    retriever = _isolated_retriever(
        monkeypatch, tmp_path, [FailingProvider("one"), FailingProvider("two")], "sequential",
    )
    results = retriever.search("query", n=10)
    assert results == []
    assert retriever.last_search_exhausted is True
    assert retriever.any_search_exhausted is True


def test_sequential_success_not_exhausted(monkeypatch, tmp_path) -> None:
    retriever = _isolated_retriever(
        monkeypatch, tmp_path,
        [OkProvider("one", [{"title": "A", "url": "https://a.example", "snippet": "s"}])],
        "sequential",
    )
    results = retriever.search("query", n=10)
    assert len(results) == 1
    assert retriever.last_search_exhausted is False
    assert retriever.any_search_exhausted is False


def test_parallel_all_providers_fail_marks_exhausted(monkeypatch, tmp_path) -> None:
    """_search_parallel 之前完全沒有設定 last_search_exhausted——用
    retrieval_mode="parallel" 的呼叫方永遠看不到 exhaustion。"""
    retriever = _isolated_retriever(
        monkeypatch, tmp_path, [FailingProvider("one"), FailingProvider("two")], "parallel",
    )
    results = retriever.search("query", n=10)
    assert results == []
    assert retriever.last_search_exhausted is True
    assert retriever.any_search_exhausted is True


def test_parallel_success_not_exhausted(monkeypatch, tmp_path) -> None:
    retriever = _isolated_retriever(
        monkeypatch, tmp_path,
        [OkProvider("one", [{"title": "A", "url": "https://a.example", "snippet": "s"}])],
        "parallel",
    )
    results = retriever.search("query", n=10)
    assert len(results) == 1
    assert retriever.last_search_exhausted is False


def test_any_search_exhausted_accumulates_across_calls(monkeypatch, tmp_path) -> None:
    """後面一次成功的呼叫不能抹掉「同一個 run 裡早先發生過 exhaustion」
    的證據——any_search_exhausted 是累積的，last_search_exhausted 只反映
    最近一次呼叫。"""
    providers = [FailingProvider("one")]
    retriever = _isolated_retriever(monkeypatch, tmp_path, providers, "sequential")
    retriever.search("first query", n=10)
    assert retriever.any_search_exhausted is True

    # Health registry now has "one" in cooldown after the failure; swap in a
    # provider that succeeds to simulate the next round using a healthy source.
    monkeypatch.setattr(
        router_module, "_build_provider_chain",
        lambda policy, strategy: [OkProvider("two", [{"title": "B", "url": "https://b.example", "snippet": "s"}])],
    )
    retriever.providers = router_module._build_provider_chain(retriever.policy, retriever.strategy)
    retriever.search("second query", n=10)
    assert retriever.last_search_exhausted is False
    assert retriever.any_search_exhausted is True
