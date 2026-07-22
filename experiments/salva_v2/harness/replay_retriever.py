"""Fixture-backed replacement for retrieval.router.RoutedRetriever.

Implements the same duck-typed shape controller.py's Retriever protocol
expects (strategy, last_attempts, search()) plus the (policy, providers)
attributes salva_core.service._collect_source_attempts/_collect_provider_kinds
read defensively -- so it is a drop-in substitute wherever RoutedRetriever is
constructed, with zero changes to core/controller.py or salva_core/service.py.
"""
from __future__ import annotations

import logging
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from experiments.salva_v2.harness.fixture_store import FIXTURES_ROOT, load_fixtures
from retrieval.models import RetrievalAttempt
from salva_core.schemas import RetrievalPolicy

logger = logging.getLogger("salva.harness.replay")


class FixtureMissingError(RuntimeError):
    pass


class NetworkCallBlocked(RuntimeError):
    pass


@contextmanager
def no_network_guard() -> Iterator[None]:
    """Hard-block outbound sockets and disable the SearXNG live topology
    probe for the duration of the block. Any code path that still tries to
    reach the network (a bug, or a future change to core code that adds a
    new network call) fails loudly with NetworkCallBlocked instead of
    silently succeeding -- that failure IS the proof replay stayed offline.
    """
    original_connect = socket.socket.connect
    original_searxng_enabled = os.environ.get("SEARXNG_ENABLED")
    os.environ["SEARXNG_ENABLED"] = "false"

    def _blocked_connect(self: socket.socket, address: Any, *a: Any, **kw: Any) -> Any:
        raise NetworkCallBlocked(
            f"replay harness attempted a live network connection to {address!r} -- "
            "fixture-driven replay must never touch the network. If this fires, "
            "either a fixture is missing (should surface as FixtureMissingError "
            "instead) or new code added a network call outside the retriever layer."
        )

    socket.socket.connect = _blocked_connect  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        if original_searxng_enabled is None:
            os.environ.pop("SEARXNG_ENABLED", None)
        else:
            os.environ["SEARXNG_ENABLED"] = original_searxng_enabled


class ReplayRetriever:
    strategy: str
    last_attempts: list[RetrievalAttempt]

    def __init__(
        self,
        policy: RetrievalPolicy,
        strategy: str,
        retrieval_mode: str = "sequential",
        *,
        task_id: str,
        fixtures_root: Any = FIXTURES_ROOT,
        **_: Any,
    ):
        self.policy = policy
        self.strategy = strategy
        self.providers: list[Any] = []
        self.last_attempts = []
        self._task_id = task_id
        self._fixtures = load_fixtures(task_id, strategy, root=fixtures_root)

    def search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        entry = self._fixtures.get(query)
        if entry is None:
            available = sorted(self._fixtures.keys())
            raise FixtureMissingError(
                f"no recorded fixture for task_id={self._task_id!r} strategy={self.strategy!r} "
                f"query={query!r}.\nRecorded queries for this (task_id, strategy):\n  "
                + "\n  ".join(available or ["<none recorded>"])
                + "\nRe-run record_fixtures.py for this task if the pipeline now generates a "
                "different query for this round (e.g. after a scorer/gate change that alters "
                "keyword-graph telemetry feedback and therefore round 2+ query expansion)."
            )
        results = list(entry["results"])[:n]
        self.last_attempts = [
            RetrievalAttempt(
                provider="replay-fixture",
                base_url=f"replay://{self._task_id}/{self.strategy}",
                mode=self.policy.mode,
                result_count=len(results),
                succeeded=bool(results),
                format_used="fixture",
            )
        ]
        logger.info(
            "replay: task=%s strategy=%s query=%r -> %d fixture results",
            self._task_id, self.strategy, query, len(results),
        )
        return results
