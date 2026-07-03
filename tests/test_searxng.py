from __future__ import annotations

from retrieval.models import RetrievalAttempt
from retrieval.sources.searxng import SearXNGRetriever
from salva_core.schemas import RetrievalPolicy


def _retriever() -> SearXNGRetriever:
    return SearXNGRetriever(policy=RetrievalPolicy(), base_url="http://localhost:8080")


class TestProbeInconclusive:
    def test_no_attempts_at_all_is_inconclusive(self):
        r = _retriever()
        r.last_attempts = []
        assert r.probe_inconclusive is True

    def test_all_attempts_errored_is_inconclusive(self):
        r = _retriever()
        r.last_attempts = [
            RetrievalAttempt(
                provider="searxng", base_url="http://localhost:8080", mode="resilient",
                result_count=0, succeeded=False, error="Connection refused",
            ),
            RetrievalAttempt(
                provider="searxng", base_url="https://searx.be", mode="resilient",
                result_count=0, succeeded=False, error="timeout",
            ),
        ]
        assert r.probe_inconclusive is True

    def test_genuine_empty_result_is_not_inconclusive(self):
        r = _retriever()
        r.last_attempts = [
            RetrievalAttempt(
                provider="searxng", base_url="http://localhost:8080", mode="resilient",
                result_count=0, succeeded=False, error=None,
            ),
        ]
        assert r.probe_inconclusive is False

    def test_one_error_one_genuine_empty_is_not_inconclusive(self):
        r = _retriever()
        r.last_attempts = [
            RetrievalAttempt(
                provider="searxng", base_url="http://localhost:8080", mode="resilient",
                result_count=0, succeeded=False, error="Connection refused",
            ),
            RetrievalAttempt(
                provider="searxng", base_url="https://searx.be", mode="resilient",
                result_count=0, succeeded=False, error=None,
            ),
        ]
        assert r.probe_inconclusive is False

    def test_successful_result_is_not_inconclusive(self):
        r = _retriever()
        r.last_attempts = [
            RetrievalAttempt(
                provider="searxng", base_url="http://localhost:8080", mode="resilient",
                result_count=5, succeeded=True, error=None,
            ),
        ]
        assert r.probe_inconclusive is False
