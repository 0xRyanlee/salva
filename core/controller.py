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
import re
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from core.keyword_graph import KeywordGraph
from core.query_proposal import PoolItem, QueryProposal, propose_followup_query
from core.types import Intent, QueryFamily, SearchTelemetry, UnifiedResult
from processing.confidence import (
    ConfidenceSignals,
    RankingWeights,
    RetrievalProvenance,
    corroboration_saturation,
    rank_candidates,
)
from retrieval.seed_fetcher import fetch_entity_names
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
        scoring_context: dict[str, Any] | None = None,
        admission_policy: str = "gate",
        max_admitted: int = 25,
        ranking_weights: RankingWeights | None = None,
        enable_query_proposal: bool = False,
        query_proposal_fn: Callable[[list[PoolItem], Intent, float], QueryProposal] | None = None,
        query_proposal_saturation_threshold: float = 0.4,
        round_checkpoint: Callable[[], None] | None = None,
    ):
        self.intent = intent
        self.retrievers = retrievers
        self.extractor = extractor
        self.deduplicator = deduplicator
        self.scorer = scorer
        self.qualify_threshold = qualify_threshold
        self.convergence_threshold = convergence_threshold
        self.results_per_query = results_per_query
        # "gate": final entity set = per-round qualify-flag (legacy default).
        # "rank": gate no longer selects output -- every candidate gets a
        # retrieval-derived confidence and the top max_admitted by confidence
        # are handed (ordered) to the downstream scoped rerank. The per-round
        # qualify flag still drives round-2+ keyword feedback either way.
        self.admission_policy = admission_policy
        self.max_admitted = max_admitted
        self.ranking_weights = ranking_weights
        # Optional bounded LLM query-proposal step (amended 2026-07-21, see
        # CLAUDE.md "Deterministic Pipeline First"). Off by default -- an
        # opt-in addition to the deterministic keyword-graph expansion, not a
        # replacement for it. Fires at most once, after the scheduled rounds,
        # only when the pool's corroboration signal looks thin.
        self.enable_query_proposal = enable_query_proposal
        self._query_proposal_fn = query_proposal_fn or propose_followup_query
        self.query_proposal_saturation_threshold = query_proposal_saturation_threshold
        # Called at the top of every round (job-queue cancellation checkpoint).
        # May raise to unwind the run early -- the controller has no opinion on
        # what it raises or why; that's the caller's (worker.py) job semantics,
        # not multi-round strategy.
        self.round_checkpoint = round_checkpoint
        self._provenance = RetrievalProvenance()
        # Extra key/value pairs merged into every round's telemetry.metadata,
        # which is the context dict passed to scorer.score(). Computed once
        # by the caller (e.g. stability signals -- one domain-level lookup
        # per discover() call, not per round/candidate) rather than per query.
        self.scoring_context: dict[str, Any] = dict(scoring_context or {})
        self.graph = keyword_graph or KeywordGraph(intent)
        route_hints = PROFILE_ROUTE_HINTS.get(experience_profile, {})
        self._strategy_rotation: list[str] = (
            list(cast(list[str], route_hints.get("strategy_rotation", [])))
            or self.STRATEGY_ROTATION
        )

        self._all_results: list[UnifiedResult] = []
        self._seen_queries: set[str] = set()
        self._run: RunSummary | None = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> tuple[list[UnifiedResult], RunSummary]:
        self._run = RunSummary(self.intent.domain, started_at=datetime.now(UTC))
        prev_rate = 1.0

        self._bootstrap_seed_urls()

        for round_num in range(1, self.intent.max_rounds + 1):
            if self.round_checkpoint is not None:
                self.round_checkpoint()

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

            # E14: Zero-yield recovery — if R1 produced no qualified results,
            # rotate to anchor strategy for R2 so fresh, broader queries are tried
            # rather than repeating the same precision-first dive queries.
            if round_num == 1 and round_summary.qualified == 0 and len(self._strategy_rotation) > 1:
                remaining = [s for s in self._strategy_rotation[1:] if s != "anchor"]
                self._strategy_rotation = ["anchor"] + remaining
                logger.info("R1 zero-qualified: rotating R2 strategy to 'anchor' for recovery")

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

        # Always rank the full pool by retrieval-derived confidence so every
        # candidate carries result.confidence downstream, regardless of policy.
        ranked = rank_candidates(
            self._all_results, self.intent, self._provenance,
            weights=self.ranking_weights,
        )

        if self.enable_query_proposal and self._run_followup_query(ranked):
            ranked = rank_candidates(
                self._all_results, self.intent, self._provenance,
                weights=self.ranking_weights,
            )

        if self.admission_policy == "rank":
            selected = [result for result, _, _ in ranked[: self.max_admitted]]
        else:
            selected = [r for r in self._all_results if r.qualified]

        self._run.ended_at = datetime.now(UTC)
        self._run.total_qualified = len(selected)
        self._run.total_raw = len(self._all_results)

        logger.info(
            "Run complete: %d selected (%s) / %d raw in %.1fs",
            len(selected), self.admission_policy, len(self._all_results),
            self._run.elapsed_seconds,
        )
        return selected, self._run

    # ------------------------------------------------------------------
    # Bounded LLM query-proposal follow-up (optional, off by default)
    # ------------------------------------------------------------------

    def _run_followup_query(
        self,
        ranked: list[tuple[UnifiedResult, float, ConfidenceSignals]],
    ) -> bool:
        """Consult the (possibly LLM-backed) proposer once, after the
        scheduled rounds, only when the pool's corroboration signal is thin.
        Returns True iff an extra round actually ran (so callers know to
        re-rank). Never raises on LLM/network failure -- degrades to no-op.
        """
        if self._run is None or not self._all_results:
            return False

        saturation = corroboration_saturation(ranked)
        if saturation >= self.query_proposal_saturation_threshold:
            return False

        pool = [
            PoolItem(title=result.title, url=result.source_url, snippet=result.description)
            for result, _, _ in ranked[:12]
        ]
        try:
            proposal = self._query_proposal_fn(pool, self.intent, saturation)
        except Exception:
            logger.exception("query-proposal step failed; skipping follow-up round")
            return False

        if not proposal.need_followup or not proposal.query:
            if not proposal.llm_available or proposal.notes:
                logger.info(
                    "query-proposal step degraded, no follow-up round: %s",
                    ", ".join(proposal.notes) or "no reason recorded",
                )
            return False
        query = proposal.query
        if query in self._seen_queries:
            return False

        strategy = self._run.rounds[-1].strategy if self._run.rounds else self._strategy_rotation[0]
        retriever = self.retrievers.get(strategy) or next(iter(self.retrievers.values()))
        round_num = len(self._run.rounds) + 1
        query_family = QueryFamily(
            round_num=round_num,
            queries=[query],
            strategy=strategy,
            notes=["llm_query_proposal_followup"],
        )

        logger.info(
            "query-proposal follow-up round %d [%s]: %r (saturation=%.2f)",
            round_num, strategy, query, saturation,
        )
        round_summary, telemetries = self._execute_round(
            round_num, strategy, query_family, retriever
        )
        self._run.rounds.append(round_summary)
        for t in telemetries:
            self.graph.apply_telemetry(t)
        return True

    # ------------------------------------------------------------------
    # Seed URL bootstrap
    # ------------------------------------------------------------------

    def _bootstrap_seed_urls(self) -> None:
        """Fetch seed_urls before the main loop and inject entity names into the graph."""
        if not self.intent.seed_urls:
            return
        policy = next(
            (
                getattr(r, "policy", None)
                for r in self.retrievers.values()
                if hasattr(r, "policy")
            ),
            None,
        )
        if policy is None:
            return
        all_names: list[str] = []
        for url in self.intent.seed_urls:
            names = fetch_entity_names(url, policy)
            logger.info("seed_url %s → %d candidate names", url, len(names))
            all_names.extend(names)
        injected = self.graph.seed_from_terms(all_names, node_type="seed", weight=0.9)
        logger.info("_bootstrap_seed_urls: injected %d nodes from %d seed URLs", injected, len(self.intent.seed_urls))

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

        # Deduplicate queries across rounds — prevents wasting budget on repeated searches
        fresh_queries = [q for q in query_family.queries if q not in self._seen_queries]
        if not fresh_queries and query_family.queries:
            # All queries already seen — force at least one attempt with a round-specific variant
            fresh_queries = [f"{query_family.queries[0]} {round_num}"]
        self._seen_queries.update(fresh_queries)

        for query in fresh_queries:
            raw_hits = retriever.search(query, n=self.results_per_query)
            for raw in raw_hits:
                url = raw.get("url", "") if isinstance(raw, dict) else ""
                if url:
                    provider = (
                        raw.get("retrieval_instance") or raw.get("engine") or strategy
                    )
                    self._provenance.observe(url, str(provider), strategy, query)
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
                    **self.scoring_context,
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
            # Extract content terms from results that passed the pipeline for this query.
            # These are fed back into the keyword graph so subsequent runs can seed new terms.
            round_results = self._all_results[-qualified_in_query:] if qualified_in_query else []
            content_terms = _extract_content_terms(round_results, existing_nodes=set(self.graph.nodes))
            telemetry.metadata.update(
                {
                    "pipeline_stage": "fetch_extract_normalize_dedupe_classify_score",
                    "raw_evidence_total": len(raw_hits),
                    "prefilter_rejected_total": prefilter_rejected,
                    "prefilter_reasons": dict(prefilter_reasons),
                    "content_type_counts": dict(content_type_counts),
                    "source_kind_counts": dict(source_kind_counts),
                    "content_terms": content_terms,
                }
            )
            telemetries.append(telemetry)

            round_summary.queries_run += 1
            round_summary.raw_hits += len(raw_hits)
            round_summary.qualified += qualified_in_query

        round_summary.telemetry = telemetries
        return round_summary, telemetries


_EN_STOPWORDS = frozenset(
    "a an the and or of in on at to for with by from as is are was were be been "
    "have has had do does did will would could should may might shall not no nor "
    "its it this that these those i we you he she they what which who when where "
    "how all any some more most other than then than so if but only just into about "
    "up out over after before between through during since until co inc ltd llc plc "
    "www http https com org net io gov".split()
)
_CJK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿]{2,}")
_EN_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9\-]{2,}")


def _extract_content_terms(
    results: list[UnifiedResult],
    existing_nodes: set[str],
    max_terms: int = 20,
) -> list[str]:
    counts: Counter[str] = Counter()
    for r in results:
        text = f"{r.title} {r.description}"
        for cjk in _CJK_RE.findall(text):
            counts[cjk] += 1
        for tok in _EN_TOKEN_RE.findall(text):
            lower = tok.lower()
            if lower not in _EN_STOPWORDS and len(lower) >= 3:
                counts[lower] += 1

    new_terms = [
        term for term, _ in counts.most_common(max_terms * 3)
        if term not in existing_nodes
    ]
    return new_terms[:max_terms]
