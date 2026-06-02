"""
Multi-Round Controller — the orchestration heart of Salva.

From SALVA_V2_ARCHITECTURE_REVIEW:
    Round 1: seed queries
    Round 2: expansion
    Round 3: noise filtering
    Each round uses telemetry feedback.

The controller:
1. Builds a QueryFamily from the KeywordGraph
2. Dispatches to the appropriate Retriever (dive/anchor/radar)
3. Runs extraction + dedup + scoring
4. Feeds telemetry back into the KeywordGraph
5. Repeats until max_rounds or convergence
"""
from __future__ import annotations
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from collections.abc import Mapping
from typing import Protocol, cast

from core.types import Intent, QueryFamily, SearchTelemetry, UnifiedResult
from core.keyword_graph import KeywordGraph
from salva_core.routes import PROFILE_ROUTE_HINTS

logger = logging.getLogger("salva.controller")


# ---------------------------------------------------------------------------
# Protocol interfaces (duck-typed, no heavy ABC)
# ---------------------------------------------------------------------------

class Retriever(Protocol):
    strategy: str
    def search(self, query: str, n: int) -> list[dict]: ...


class Extractor(Protocol):
    def extract(self, raw: dict, query: str, round_num: int, strategy: str) -> UnifiedResult | None: ...


class Deduplicator(Protocol):
    def is_duplicate(self, result: UnifiedResult) -> bool: ...
    def register(self, result: UnifiedResult) -> None: ...


class Scorer(Protocol):
    def score(self, result: UnifiedResult, intent: Intent, context: dict[str, object] | None = None) -> float: ...


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------

@dataclass
class RoundSummary:
    round_num: int
    strategy: str
    queries_run: int
    raw_hits: int
    qualified: int
    telemetry: list[SearchTelemetry] = field(default_factory=list)
    content_weights: dict[str, float] = field(default_factory=dict)
    source_hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class RunSummary:
    intent_domain: str
    started_at: datetime
    ended_at: datetime | None = None
    rounds: list[RoundSummary] = field(default_factory=list)
    total_qualified: int = 0
    total_raw: int = 0

    @property
    def elapsed_seconds(self) -> float:
        if not self.ended_at:
            return 0.0
        return (self.ended_at - self.started_at).total_seconds()


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class SalvaController:
    """
    Orchestrates the multi-round retrieval pipeline.

    Strategy rotation (default):
        Round 1 → dive    (precision: seed exact queries)
        Round 2 → anchor  (recall: keyword-graph expansion)
        Round 3 → radar   (discovery: semantic/signal exploration)

    Convergence check:
        If qualified_rate < convergence_threshold for two consecutive rounds,
        stop early (the search space has been exhausted).
    """

    # Default rotation when no experience profile is provided.
    STRATEGY_ROTATION = ["dive", "anchor", "radar"]

    def __init__(
        self,
        intent: Intent,
        retrievers: Mapping[str, Retriever],
        extractor: Extractor,
        deduplicator: Deduplicator,
        scorer: Scorer,
        qualify_threshold: float = 0.4,
        convergence_threshold: float = 0.05,
        results_per_query: int = 10,
        keyword_graph: KeywordGraph | None = None,
        experience_profile: str = "",
    ):
        self.intent = intent
        self.retrievers = retrievers
        self.extractor = extractor
        self.deduplicator = deduplicator
        self.scorer = scorer
        self.qualify_threshold = qualify_threshold
        self.convergence_threshold = convergence_threshold
        self.results_per_query = results_per_query
        self.graph = keyword_graph or KeywordGraph(intent)
        route_hints = PROFILE_ROUTE_HINTS.get(experience_profile, {})
        self._strategy_rotation: list[str] = (
            list(cast(list[str], route_hints.get("strategy_rotation", [])))
            or self.STRATEGY_ROTATION
        )

        self._all_results: list[UnifiedResult] = []
        self._run: RunSummary | None = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> tuple[list[UnifiedResult], RunSummary]:
        self._run = RunSummary(self.intent.domain, started_at=datetime.now(UTC))
        prev_rate = 1.0

        for round_num in range(1, self.intent.max_rounds + 1):
            rotation = self._strategy_rotation
            strategy = rotation[(round_num - 1) % len(rotation)]
            retriever = self.retrievers.get(strategy) or next(iter(self.retrievers.values()))

            query_family = self.graph.next_round_queries(
                round_num, strategy=strategy,
                max_queries=min(8, self.intent.results_per_round // self.results_per_query)
            )

            logger.info(
                "Round %d/%d [%s] — %d queries",
                round_num, self.intent.max_rounds, strategy, len(query_family.queries)
            )

            round_summary, telemetries = self._execute_round(
                round_num, strategy, query_family, retriever
            )
            self._run.rounds.append(round_summary)

            # Feed telemetry back into keyword graph
            for t in telemetries:
                self.graph.apply_telemetry(t)

            # Prune low-value nodes after round 2+
            if round_num >= 2:
                pruned = self.graph.prune()
                if pruned:
                    logger.debug("Pruned %d low-value keyword nodes", pruned)

            # Convergence check
            rate = (
                round_summary.qualified / round_summary.raw_hits
                if round_summary.raw_hits > 0 else 0.0
            )
            if round_num > 1 and rate < self.convergence_threshold and prev_rate < self.convergence_threshold:
                logger.info("Converged early at round %d (rate=%.2f)", round_num, rate)
                break
            prev_rate = rate

        qualified = [r for r in self._all_results if r.qualified]
        self._run.ended_at = datetime.now(UTC)
        self._run.total_qualified = len(qualified)
        self._run.total_raw = len(self._all_results)

        logger.info(
            "Run complete: %d qualified / %d raw in %.1fs",
            len(qualified), len(self._all_results), self._run.elapsed_seconds
        )
        return qualified, self._run

    # ------------------------------------------------------------------
    # Round execution
    # ------------------------------------------------------------------

    def _execute_round(
        self,
        round_num: int,
        strategy: str,
        query_family: QueryFamily,
        retriever: Retriever,
    ) -> tuple[RoundSummary, list[SearchTelemetry]]:
        round_summary = RoundSummary(
            round_num,
            strategy,
            0,
            0,
            0,
            content_weights=dict(query_family.content_weights),
            source_hints=list(query_family.source_hints),
            notes=list(query_family.notes),
        )
        telemetries: list[SearchTelemetry] = []

        for query in query_family.queries:
            raw_hits = retriever.search(query, n=self.results_per_query)
            content_type_counts: Counter[str] = Counter()
            source_kind_counts: Counter[str] = Counter()
            prefilter_rejected = 0
            prefilter_reasons: Counter[str] = Counter()
            telemetry = SearchTelemetry(
                query,
                round_num,
                strategy,
                results_total=len(raw_hits),
                metadata={
                    "query_family_strategy": query_family.strategy,
                    "content_weights": dict(query_family.content_weights),
                    "source_hints": list(query_family.source_hints),
                    "notes": list(query_family.notes),
                    "source_nodes": list(query_family.source_nodes),
                },
            )

            qualified_in_query = 0
            for raw in raw_hits:
                prefilter_reason = None
                pipeline = getattr(self.extractor, "pipeline", None)
                if pipeline is not None:
                    _, prefilter_reason = pipeline.prefilter(raw, query, strategy)
                result = self.extractor.extract(raw, query, round_num, strategy)
                if result is None:
                    prefilter_rejected += 1
                    prefilter_reasons.update([prefilter_reason or "prefilter_rejected"])
                    continue
                if result.tags:
                    content_type_counts.update([result.tags[0]])
                if len(result.tags) > 1:
                    source_kind_counts.update([result.tags[1]])
                if self.deduplicator.is_duplicate(result):
                    continue

                result.relevance_score = self.scorer.score(
                    result,
                    self.intent,
                    context=telemetry.metadata,
                )
                result.qualified = result.relevance_score >= self.qualify_threshold

                if not result.qualified:
                    telemetry.reject_reasons.extend(result.reject_reasons)
                    # Track noise domains for Rocchio feedback
                    if result.source_url:
                        from urllib.parse import urlparse
                        dom = urlparse(result.source_url).netloc
                        telemetry.noise_domains.append(dom)
                else:
                    qualified_in_query += 1

                self.deduplicator.register(result)
                self._all_results.append(result)

            telemetry.results_qualified = qualified_in_query
            telemetry.avg_score = (
                sum(r.relevance_score for r in self._all_results[-len(raw_hits):])
                / max(len(raw_hits), 1)
            )
            telemetry.metadata.update(
                {
                    "pipeline_stage": "fetch_extract_normalize_dedupe_classify_score",
                    "raw_evidence_total": len(raw_hits),
                    "prefilter_rejected_total": prefilter_rejected,
                    "prefilter_reasons": dict(prefilter_reasons),
                    "content_type_counts": dict(content_type_counts),
                    "source_kind_counts": dict(source_kind_counts),
                }
            )
            telemetries.append(telemetry)

            round_summary.queries_run += 1
            round_summary.raw_hits += len(raw_hits)
            round_summary.qualified += qualified_in_query

        round_summary.telemetry = telemetries
        return round_summary, telemetries
