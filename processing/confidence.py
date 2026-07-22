"""Retrieval-derived confidence ranking.

Replaces QualificationScorer's flat, hand-tuned per-domain gate as the signal
that orders candidates for the downstream scoped rerank. The gate admitted or
rejected each candidate in isolation against a per-domain keyword-tuned
threshold; when the gate is removed every candidate becomes "qualified" and the
ordering collapses. This module instead ranks the whole accumulated pool by
signals derived from the retrieval process itself -- how many independent query
formulations / providers converged on a source -- combined with query-content
match, so the rerank sees an ordered, bounded pool instead of an all-or-nothing
dump.

The corroboration signal needs the raw pre-dedup hits (RetrievalProvenance),
which the controller accumulates during its rounds; it is not recoverable from
the post-dedup survivor list alone.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from urllib.parse import urlparse

from core.types import Intent, UnifiedResult
from processing.scorer import (
    DEFAULT_NOISE_DOMAINS,
    DEFAULT_TRUSTED_SOURCES,
    QualificationScorer,
)


def registered_domain(url: str) -> str:
    if not url:
        return ""
    netloc = urlparse(url).netloc.lower()
    return netloc.removeprefix("www.")


@dataclass
class RankingWeights:
    content: float = 0.55
    corroboration: float = 0.30
    source_trust: float = 0.15


# Support beyond this many distinct (provider, query) formulations adds no
# further corroboration confidence -- convergence saturates.
_CORROBORATION_SATURATION = 4.0


@dataclass
class RetrievalProvenance:
    """domain -> distinct (provider, strategy, query) formulations that surfaced
    at least one URL on that domain across the whole run.

    Built from the raw pre-dedup hits so corroboration counts how often the
    retrieval layer independently re-converged on a source, not how many
    post-dedup survivors happen to share a domain.
    """
    by_domain: dict[str, set[tuple[str, str, str]]] = field(
        default_factory=lambda: defaultdict(set)
    )

    def observe(self, url: str, provider: str, strategy: str, query: str) -> None:
        dom = registered_domain(url)
        if dom:
            self.by_domain[dom].add((provider, strategy, query))

    def support(self, url: str) -> set[tuple[str, str, str]]:
        return self.by_domain.get(registered_domain(url), set())


@dataclass
class ConfidenceSignals:
    content_match: float
    corroboration: float
    source_trust: float
    query_support: int          # distinct (provider, strategy, query) formulations
    provider_diversity: int     # distinct providers that surfaced the domain


def _corroboration_score(query_support: int) -> float:
    """0 when only one formulation found the source; saturates toward 1 as
    more independent formulations converge on it."""
    if query_support <= 1:
        return 0.0
    return min(
        1.0,
        math.log1p(query_support - 1) / math.log1p(_CORROBORATION_SATURATION),
    )


def _source_trust(url: str, trusted: frozenset[str], noise: frozenset[str]) -> float:
    domain = registered_domain(url)
    if not domain:
        return 0.0
    if any(t in domain for t in noise):
        return 0.0
    if any(t in domain for t in trusted):
        return 1.0
    return 0.5


def candidate_confidence(
    result: UnifiedResult,
    intent: Intent,
    provenance: RetrievalProvenance,
    weights: RankingWeights,
    trusted: frozenset[str],
    noise: frozenset[str],
) -> tuple[float, ConfidenceSignals]:
    text = f"{result.title} {result.description}".lower()
    content = QualificationScorer._content_match(text, intent)

    support = provenance.support(result.source_url)
    query_support = len(support)
    provider_diversity = len({provider for (provider, _, _) in support})
    corroboration = _corroboration_score(query_support)

    trust = _source_trust(result.source_url, trusted, noise)

    confidence = (
        weights.content * content
        + weights.corroboration * corroboration
        + weights.source_trust * trust
    )
    signals = ConfidenceSignals(
        content_match=round(content, 4),
        corroboration=round(corroboration, 4),
        source_trust=trust,
        query_support=query_support,
        provider_diversity=provider_diversity,
    )
    return round(confidence, 4), signals


def rank_candidates(
    results: list[UnifiedResult],
    intent: Intent,
    provenance: RetrievalProvenance,
    weights: RankingWeights | None = None,
    trusted: frozenset[str] | None = None,
    noise: frozenset[str] | None = None,
) -> list[tuple[UnifiedResult, float, ConfidenceSignals]]:
    """Score every candidate, write result.confidence, return desc-sorted."""
    weights = weights or RankingWeights()
    trusted = trusted if trusted is not None else DEFAULT_TRUSTED_SOURCES
    noise = noise if noise is not None else DEFAULT_NOISE_DOMAINS

    scored: list[tuple[UnifiedResult, float, ConfidenceSignals]] = []
    for result in results:
        confidence, signals = candidate_confidence(
            result, intent, provenance, weights, trusted, noise
        )
        result.confidence = confidence
        scored.append((result, confidence, signals))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def corroboration_saturation(
    ranked: list[tuple[UnifiedResult, float, ConfidenceSignals]],
) -> float:
    """Pool-level exhaustion signal: fraction of candidates that carry
    multi-formulation corroboration. High -> retrieval kept re-converging on
    the same sources (pool likely exhausted, safe to stop). Low -> most
    candidates were seen once (pool is thin, more retrieval may help).
    """
    if not ranked:
        return 0.0
    corroborated = sum(1 for (_, _, signals) in ranked if signals.query_support > 1)
    return corroborated / len(ranked)
