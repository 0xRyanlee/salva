"""Controller wiring for the optional bounded LLM query-proposal follow-up
step (amended 2026-07-21, see CLAUDE.md "Deterministic Pipeline First").

Covers: off-by-default no-op, saturation-gated trigger, one extra round
executed on a genuine proposal, dedup against already-seen queries, and
graceful degradation when the proposer raises.
"""
from __future__ import annotations

from datetime import UTC, datetime

from core.controller import RunSummary, SalvaController
from core.query_proposal import PoolItem, QueryProposal
from core.types import Intent, UnifiedResult
from processing.confidence import ConfidenceSignals


class _StaticRetriever:
    def __init__(self, strategy: str, hits: list[dict]):
        self.strategy = strategy
        self.hits = hits
        self.calls: list[str] = []

    def search(self, query: str, n: int) -> list[dict]:
        self.calls.append(query)
        return list(self.hits)


class _PassthroughExtractor:
    def extract(self, raw: dict, query: str, round_num: int, strategy: str) -> UnifiedResult | None:
        url = raw.get("url", "")
        title = raw.get("title", "")
        if not url or not title:
            return None
        return UnifiedResult(
            source_name="stub", source_url=url, title=title, description=raw.get("snippet", "")
        )


class _NoDedup:
    def is_duplicate(self, result: UnifiedResult) -> bool:
        return False

    def register(self, result: UnifiedResult) -> None:
        pass


class _AlwaysPassScorer:
    def score(self, result: UnifiedResult, intent: Intent, context=None) -> float:
        return 0.85


def _make_intent(max_rounds: int = 1) -> Intent:
    return Intent(
        domain="companies", primary_terms=["CNCF", "founders"], region="global",
        max_rounds=max_rounds, results_per_round=10,
    )


def _make_controller(**kwargs) -> tuple[SalvaController, _StaticRetriever]:
    retriever = _StaticRetriever(
        "dive",
        [{
            "title": "Wikipedia CNCF list",
            "url": "https://en.wikipedia.org/wiki/CNCF",
            "snippet": "secondary summary",
        }],
    )
    controller = SalvaController(
        intent=_make_intent(),
        retrievers={"dive": retriever},
        extractor=_PassthroughExtractor(),
        deduplicator=_NoDedup(),
        scorer=_AlwaysPassScorer(),
        qualify_threshold=0.4,
        **kwargs,
    )
    return controller, retriever


def _fake_ranked(query_support: int) -> list[tuple[UnifiedResult, float, ConfidenceSignals]]:
    result = UnifiedResult(
        source_name="stub", source_url="https://en.wikipedia.org/wiki/CNCF", title="x"
    )
    signals = ConfidenceSignals(
        content_match=0.5, corroboration=0.0, source_trust=0.5,
        query_support=query_support, provider_diversity=1,
    )
    return [(result, 0.5, signals)]


class TestDisabledByDefault:
    def test_proposer_never_called_when_disabled(self):
        called = {"n": 0}

        def proposer(pool, intent, saturation):
            called["n"] += 1
            return QueryProposal(need_followup=True, query="should never run", llm_available=True)

        controller, retriever = _make_controller(query_proposal_fn=proposer)
        assert controller.enable_query_proposal is False
        controller.run()
        assert called["n"] == 0
        assert len(retriever.calls) == 1  # only the one scheduled round


class TestSaturationGate:
    def test_high_saturation_pool_skips_proposal(self):
        controller, _ = _make_controller(enable_query_proposal=True)
        # multi-formulation -> high corroboration -> saturated
        ranked = _fake_ranked(query_support=5)
        controller._run = RunSummary(intent_domain="companies", started_at=datetime.now(UTC))
        controller._all_results = [ranked[0][0]]
        called = {"n": 0}

        def proposer(pool, intent, saturation):
            called["n"] += 1
            return QueryProposal(False, None, True)

        controller._query_proposal_fn = proposer
        ran = controller._run_followup_query(ranked)
        assert ran is False
        assert called["n"] == 0

    def test_low_saturation_pool_consults_proposer(self):
        controller, _ = _make_controller(enable_query_proposal=True)
        ranked = _fake_ranked(query_support=1)  # single formulation -> thin pool
        controller._run = RunSummary(intent_domain="companies", started_at=datetime.now(UTC))
        controller._all_results = [ranked[0][0]]
        called = {"n": 0}

        def proposer(pool, intent, saturation):
            called["n"] += 1
            assert isinstance(pool[0], PoolItem)
            return QueryProposal(need_followup=False, query=None, llm_available=True)

        controller._query_proposal_fn = proposer
        ran = controller._run_followup_query(ranked)
        assert ran is False  # proposer said no
        assert called["n"] == 1

    def test_llm_unavailable_no_followup_is_logged_not_silent(self, caplog):
        """salva-enrichment-failure-telemetry：LLM 不可用的降級必須在日誌
        裡看得到，不能是一個跟「飽和度本來就夠」無法區分的靜默 no-op。"""
        controller, _ = _make_controller(enable_query_proposal=True)
        ranked = _fake_ranked(query_support=1)
        controller._run = RunSummary(intent_domain="companies", started_at=datetime.now(UTC))
        controller._all_results = [ranked[0][0]]

        def proposer(pool, intent, saturation):
            return QueryProposal(
                need_followup=False, query=None, llm_available=False,
                notes=["llm_unavailable_no_followup"],
            )

        controller._query_proposal_fn = proposer
        with caplog.at_level("INFO"):
            ran = controller._run_followup_query(ranked)
        assert ran is False
        assert any("llm_unavailable_no_followup" in record.message for record in caplog.records)


class TestFollowupExecution:
    def test_genuine_proposal_runs_one_extra_round(self):
        def proposer(pool, intent, saturation):
            return QueryProposal(
                need_followup=True,
                query="CNCF founding members 2015 press release site:cncf.io",
                llm_available=True,
            )

        controller, retriever = _make_controller(
            enable_query_proposal=True, query_proposal_fn=proposer
        )
        # After the extra round runs, the retriever returns the same fixed hit list
        # regardless of query -- enough to prove the round executed and merged.
        selected, summary = controller.run()
        assert len(summary.rounds) == 2
        assert summary.rounds[-1].notes == ["llm_query_proposal_followup"]
        assert "CNCF founding members 2015 press release site:cncf.io" in retriever.calls

    def test_proposal_for_already_seen_query_is_skipped(self):
        seen_query = None

        def proposer(pool, intent, saturation):
            return QueryProposal(need_followup=True, query=seen_query, llm_available=True)

        controller, retriever = _make_controller(
            enable_query_proposal=True, query_proposal_fn=proposer
        )
        # run once normally to discover the seed query, then rerun with it as the "proposal"
        controller.run()
        first_round_query = retriever.calls[0]
        rounds_before = len(controller._run.rounds)

        def repeat_proposer(pool, intent, saturation):
            return QueryProposal(need_followup=True, query=first_round_query, llm_available=True)

        controller._query_proposal_fn = repeat_proposer
        ranked = _fake_ranked(query_support=1)
        ran = controller._run_followup_query(ranked)
        assert ran is False
        assert len(controller._run.rounds) == rounds_before

    def test_proposer_exception_degrades_gracefully(self):
        def broken_proposer(pool, intent, saturation):
            raise RuntimeError("network unreachable")

        controller, retriever = _make_controller(
            enable_query_proposal=True, query_proposal_fn=broken_proposer
        )
        selected, summary = controller.run()
        assert len(summary.rounds) == 1  # only the scheduled round; follow-up degraded to no-op
