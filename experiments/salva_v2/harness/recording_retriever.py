"""Records live retrieval.router.RoutedRetriever calls to fixture files.

Wraps a real RoutedRetriever and passes every call through unchanged --
recording is a transparent side effect, not a substitute for the real
provider chain. Used only by record_fixtures.py; production code never
imports this module.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from experiments.salva_v2.harness.fixture_store import FIXTURES_ROOT, write_fixture
from retrieval.models import RetrievalAttempt
from retrieval.router import RetrievalStrategy, RoutedRetriever
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.harness.record")


class RecordingRetriever:
    strategy: str
    last_attempts: list[RetrievalAttempt]

    def __init__(
        self,
        policy: RetrievalPolicy,
        strategy: str,
        retrieval_mode: RetrievalStrategy = "sequential",
        *,
        task_id: str,
        fixtures_root: Any = FIXTURES_ROOT,
        **kwargs: Any,
    ):
        self._real = RoutedRetriever(
            policy=policy, strategy=strategy, retrieval_mode=retrieval_mode, **kwargs
        )
        self.policy = policy
        self.strategy = strategy
        self.providers = self._real.providers
        self.last_attempts = []
        self._task_id = task_id
        self._fixtures_root = fixtures_root

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        results = self._real.search(query, n)
        self.last_attempts = self._real.last_attempts
        path = write_fixture(
            self._task_id, self.strategy, query, n, results,
            recorded_at=datetime.now(UTC).isoformat(),
            root=self._fixtures_root,
        )
        logger.info(
            "recorded: task=%s strategy=%s query=%r -> %d results (%s)",
            self._task_id, self.strategy, query, len(results), path,
        )
        return results
