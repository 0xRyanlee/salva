from __future__ import annotations

import json

import retrieval.sources.whoogle as whoogle_module
from retrieval.sources.whoogle import WhoogleRetriever
from salva_core.schemas import RetrievalPolicy


def test_whoogle_returns_empty_without_base_url() -> None:
    retriever = WhoogleRetriever(policy=RetrievalPolicy(), base_url="")

    results = retriever.search("salva runtime", n=5)

    assert results == []
    assert retriever.last_attempts == []


def test_whoogle_search_parses_results_and_records_attempt(monkeypatch) -> None:
    payload = {
        "results": [
            {"text": "Alpha", "href": "https://alpha.example"},
            {"text": "Missing URL"},
        ]
    }

    monkeypatch.setattr(whoogle_module.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(whoogle_module.time, "sleep", lambda _: None)
    monkeypatch.setattr(whoogle_module, "http_get", lambda url, headers=None, timeout=15.0: json.dumps(payload).encode())

    retriever = WhoogleRetriever(policy=RetrievalPolicy(request_timeout=3.0), base_url="https://whoogle.example")
    results = retriever.search("salva runtime", n=5)

    assert results == [
        {
            "title": "Alpha",
            "url": "https://alpha.example",
            "snippet": "Alpha",
            "engine": "whoogle",
            "retrieval_instance": "https://whoogle.example",
        }
    ]
    assert len(retriever.last_attempts) == 1
    attempt = retriever.last_attempts[0]
    assert attempt.provider == "whoogle"
    assert attempt.base_url == "https://whoogle.example"
    assert attempt.result_count == 1
    assert attempt.succeeded is True
    assert attempt.format_used == "json"


def test_whoogle_failure_records_attempt(monkeypatch) -> None:
    monkeypatch.setattr(whoogle_module.random, "choice", lambda seq: seq[0])
    monkeypatch.setattr(whoogle_module.time, "sleep", lambda _: None)

    def _boom(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(whoogle_module, "http_get", _boom)

    retriever = WhoogleRetriever(policy=RetrievalPolicy(request_timeout=3.0), base_url="https://whoogle.example")
    results = retriever.search("salva runtime", n=5)

    assert results == []
    assert len(retriever.last_attempts) == 1
    attempt = retriever.last_attempts[0]
    assert attempt.provider == "whoogle"
    assert attempt.result_count == 0
    assert attempt.succeeded is False
    assert "boom" in (attempt.error or "")
