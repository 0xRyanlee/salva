"""Canonical dataclass types for Salva's retrieval pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Intent:
    """
    Structured representation of a retrieval goal.

    Callers express what they want semantically; the KeywordGraph + QueryFamily
    generator translates this into concrete search queries.
    """
    domain: str
    primary_terms: list[str]
    region: str | None = None
    roles: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    max_rounds: int = 3
    results_per_round: int = 30


@dataclass
class KeywordNode:
    phrase: str
    node_type: str      # "primary" | "synonym" | "role" | "region" | "signal" | "memory"
    weight: float = 0.0
    market: str | None = None

    freq_score: float = 0.0
    cooccur_score: float = 0.0
    lead_score: float = 0.0
    source_score: float = 0.0

    def composite_score(self) -> float:
        return (
            0.25 * self.freq_score
            + 0.20 * self.cooccur_score
            + 0.20 * self.lead_score
            + 0.15 * self.source_score
            + 0.10 * self.weight
        )


@dataclass
class KeywordEdge:
    source: str
    target: str
    relation: str       # "synonym" | "specialization" | "region" | "co-occurrence"
    weight: float = 1.0


@dataclass
class QueryFamily:
    """A set of related query strings from a KeywordNode cluster per round."""
    round_num: int
    queries: list[str]
    strategy: str       # "dive" | "anchor" | "radar"
    source_nodes: list[str] = field(default_factory=list)
    content_weights: dict[str, float] = field(default_factory=dict)
    source_hints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class SearchTelemetry:
    """Per-query telemetry driving Rocchio-style feedback between rounds."""
    query: str
    round_num: int
    strategy: str
    results_total: int = 0
    results_qualified: int = 0
    avg_score: float = 0.0
    reject_reasons: list[str] = field(default_factory=list)
    noise_domains: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedResult:
    """
    Domain-agnostic result object produced by the retrieval pipeline.

    source_url is the dedup key. Adapters map UnifiedResult fields into
    their domain-specific canonical schemas.
    """
    source_name: str
    source_url: str
    external_id: str | None = None

    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)

    location_name: str | None = None
    location_address: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str = "Asia/Taipei"

    price_amount: float = 0.0
    currency: str = "TWD"
    capacity: int | None = None

    cover_image_url: str | None = None

    organizer_name: str | None = None
    organizer_email: str | None = None
    organizer_domain: str | None = None

    relevance_score: float = 0.0
    qualified: bool = False
    reject_reasons: list[str] = field(default_factory=list)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    round_num: int = 1
    query_used: str = ""
    strategy_used: str = ""

    ai_type: str | None = None
    ai_summary: str | None = None
    ai_tags: list[str] = field(default_factory=list)
    ai_language: str | None = None
    ai_target_audience: str | None = None
    raw_evidence: dict[str, Any] = field(default_factory=dict)
