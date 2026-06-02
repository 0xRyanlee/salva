from dataclasses import dataclass

import retrieval.router as router_module
from retrieval.models import RetrievalAttempt
from retrieval.router import RoutedRetriever
from salva_core.schemas import RetrievalPolicy


@dataclass
class DummyProvider:
    name: str
    results: list[dict]

    def __post_init__(self) -> None:
        self.strategy = "radar"
        self.last_attempts: list[RetrievalAttempt] = []

    def search(self, query: str, n: int = 10) -> list[dict]:
        self.last_attempts = [
            RetrievalAttempt(
                provider=self.name,
                base_url=self.name,
                mode="resilient",
                result_count=len(self.results),
                succeeded=bool(self.results),
                format_used="json",
            )
        ]
        return self.results


def test_routed_retriever_merges_provider_results(monkeypatch) -> None:
    providers = [
        DummyProvider("one", [{"title": "A", "url": "https://a.example", "snippet": ""}]),
        DummyProvider("two", [{"title": "B", "url": "https://b.example", "snippet": ""}]),
    ]
    monkeypatch.setattr(router_module, "_build_provider_chain", lambda policy, strategy: providers)

    retriever = RoutedRetriever(policy=RetrievalPolicy(), strategy="radar")
    results = retriever.search("software expo", n=10)

    assert len(results) == 2
    assert {item["title"] for item in results} == {"A", "B"}
    assert len(retriever.last_attempts) == 2
