"""
Qualification Scorer.

Composite scoring formula:

    Lead Score =
        0.25 * content_match
      + 0.20 * contact_completeness
      + 0.20 * signal_strength
      + 0.15 * region_match
      + 0.10 * source_trust
      + 0.10 * recency

Domain-specific signal lists and source trust lists are injected via ScorerConfig,
not hardcoded — callers control which domains are noise or trusted for their use case.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from core.types import Intent, UnifiedResult

# Defaults — override via ScorerConfig to match your domain and retrieval targets.
DEFAULT_NOISE_DOMAINS: frozenset[str] = frozenset({
    "reddit.com", "wikipedia.org", "youtube.com", "amazon.com",
    "ebay.com", "medium.com",
})

DEFAULT_TRUSTED_SOURCES: frozenset[str] = frozenset({
    "lu.ma", "eventbrite.com", "facebook.com", "meetup.com", "linkedin.com",
})


@dataclass
class ScorerConfig:
    # Domain-specific signal keywords
    high_signals: list[str] = field(default_factory=list)
    med_signals: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)

    # Source trust lists — injectable per-caller so no domain is hardcoded globally
    noise_domains: frozenset[str] = field(default_factory=lambda: DEFAULT_NOISE_DOMAINS)
    trusted_sources: frozenset[str] = field(default_factory=lambda: DEFAULT_TRUSTED_SOURCES)

    # Weights (must sum to 1.0)
    w_content: float = 0.25
    w_contact: float = 0.20
    w_signal: float = 0.20
    w_region: float = 0.15
    w_source: float = 0.10
    w_recency: float = 0.10


DOMAIN_CONFIGS: dict[str, ScorerConfig] = {
    "events": ScorerConfig(
        high_signals=["報名", "register", "sign up", "meetup", "workshop", "活動", "講座"],
        med_signals=["免費", "free", "限額", "event", "forum"],
        negative_signals=["job", "求職", "招募", "shopping", "店面"],
        trusted_sources=frozenset({
            "lu.ma", "eventbrite.com", "meetup.com", "facebook.com",
        }),
    ),
    "bd_leads": ScorerConfig(
        high_signals=["distributor", "wholesale", "wholesaler", "supplier", "bulk", "b2b"],
        med_signals=["importer", "exporter", "trading", "dealer", "manufacturer", "reseller", "partner"],
        negative_signals=["blog", "review", "reddit", "amazon", "retail"],
        trusted_sources=frozenset({
            "linkedin.com", "crunchbase.com", "clutch.co",
        }),
    ),
    "companies": ScorerConfig(
        high_signals=["founded", "headquarters", "employees", "revenue", "funding",
                      "series A", "series B", "IPO", "acquired", "merger",
                      "CEO", "CTO", "leadership", "team", "headcount", "valuation"],
        med_signals=["startup", "enterprise", "SaaS", "platform", "investor", "VC", "portfolio"],
        negative_signals=["review", "reddit", "job posting", "salary", "glassdoor", "consumer"],
        trusted_sources=frozenset({
            "crunchbase.com", "linkedin.com", "pitchbook.com",
            "bloomberg.com", "techcrunch.com", "builtin.com",
        }),
    ),
    "market_intel": ScorerConfig(
        high_signals=["launch", "release", "announced", "unveiled", "debut", "rollout",
                      "partnership", "acquisition", "funding round", "IPO", "merger"],
        med_signals=["trend", "growth", "adoption", "market share", "competitor", "disruption"],
        negative_signals=["reddit", "blog", "opinion", "speculation"],
        trusted_sources=frozenset({
            "bloomberg.com", "reuters.com", "techcrunch.com", "forbes.com",
        }),
    ),
    # Taiwan hardware manufacturers / Computex exhibitors
    "taiwan_hardware": ScorerConfig(
        high_signals=[
            "展商", "參展", "廠商", "IC設計", "半導體", "伺服器", "主機板", "製造商",
            "exhibitor", "manufacturer", "OEM", "ODM", "foundry", "fab",
            "Computex", "台灣大廠", "AI server", "GPU server", "AIoT",
        ],
        med_signals=[
            "科技", "電子", "hardware", "server", "chip", "PCB", "DRAM",
            "notebook", "networking", "embedded", "industrial",
        ],
        negative_signals=["blog", "review", "求職", "招募", "salary", "消費者"],
        trusted_sources=frozenset({
            "computextaipei.com.tw", "computex.biz",
            "digitimes.com", "ithome.com.tw",
            "taitra.org.tw", "ctee.com.tw",
            "teema.org.tw", "teeia.org.tw",
        }),
        # Lower weight on contact (snippets rarely have contact info) — up region+signal
        w_content=0.30,
        w_contact=0.05,
        w_signal=0.30,
        w_region=0.20,
        w_source=0.10,
        w_recency=0.05,
    ),
}


class QualificationScorer:

    def __init__(self, config: ScorerConfig | None = None):
        self.config = config

    def score(self, result: UnifiedResult, intent: Intent, context: dict[str, Any] | None = None) -> float:
        cfg = self.config or DOMAIN_CONFIGS.get(intent.domain, ScorerConfig())
        cfg = self._apply_context(cfg, context)
        text = f"{result.title} {result.description}".lower()

        content_score = self._content_match(text, intent)
        contact_score = self._contact_completeness(result)
        signal_score = self._signal_strength(text, cfg)
        region_score = self._region_match(text, result, intent)
        source_score = self._source_trust(result.source_url, cfg)
        recency_score = self._recency(result)

        # Negative signals hard-penalize
        if any(neg in text for neg in cfg.negative_signals):
            return max(0.0, signal_score * 0.3)

        composite = (
            cfg.w_content  * content_score
            + cfg.w_contact  * contact_score
            + cfg.w_signal   * signal_score
            + cfg.w_region   * region_score
            + cfg.w_source   * source_score
            + cfg.w_recency  * recency_score
        )

        # Tag reject reasons for telemetry
        if contact_score == 0:
            result.reject_reasons.append("no_contact")
        if signal_score < 0.2:
            result.reject_reasons.append("low_signal")
        if source_score < 0.2:
            result.reject_reasons.append("untrusted_source")

        return round(min(1.0, composite), 4)

    @staticmethod
    def _apply_context(cfg: ScorerConfig, context: dict[str, Any] | None) -> ScorerConfig:
        if not context:
            return cfg

        notes = set(context.get("notes", []))
        content_weights = context.get("content_weights", {}) if isinstance(context, dict) else {}

        adjusted = ScorerConfig(
            high_signals=list(cfg.high_signals),
            med_signals=list(cfg.med_signals),
            negative_signals=list(cfg.negative_signals),
            noise_domains=cfg.noise_domains,
            trusted_sources=cfg.trusted_sources,
            w_content=cfg.w_content,
            w_contact=cfg.w_contact,
            w_signal=cfg.w_signal,
            w_region=cfg.w_region,
            w_source=cfg.w_source,
            w_recency=cfg.w_recency,
        )

        if "precision_first" in notes:
            adjusted.w_content = 0.30
            adjusted.w_contact = 0.20
            adjusted.w_signal = 0.22
            adjusted.w_region = 0.16
            adjusted.w_source = 0.07
            adjusted.w_recency = 0.05
        elif "graph_expansion" in notes:
            adjusted.w_content = 0.24
            adjusted.w_contact = 0.18
            adjusted.w_signal = 0.20
            adjusted.w_region = 0.16
            adjusted.w_source = 0.10
            adjusted.w_recency = 0.12
        elif "source_discovery" in notes:
            adjusted.w_content = 0.18
            adjusted.w_contact = 0.14
            adjusted.w_signal = 0.16
            adjusted.w_region = 0.10
            adjusted.w_source = 0.24
            adjusted.w_recency = 0.18

        if isinstance(content_weights, dict):
            platform_weight = float(content_weights.get("platform", 0.0) or 0.0)
            title_weight = float(content_weights.get("title", 0.0) or 0.0)
            document_weight = float(content_weights.get("document", 0.0) or 0.0)

            adjusted.w_source = min(0.35, adjusted.w_source + platform_weight * 0.08)
            adjusted.w_recency = min(0.25, adjusted.w_recency + platform_weight * 0.04)
            adjusted.w_content = min(0.40, adjusted.w_content + title_weight * 0.04)
            adjusted.w_signal = min(0.30, adjusted.w_signal + document_weight * 0.03)

        total = (
            adjusted.w_content
            + adjusted.w_contact
            + adjusted.w_signal
            + adjusted.w_region
            + adjusted.w_source
            + adjusted.w_recency
        )
        if total > 0:
            adjusted.w_content /= total
            adjusted.w_contact /= total
            adjusted.w_signal /= total
            adjusted.w_region /= total
            adjusted.w_source /= total
            adjusted.w_recency /= total
        return adjusted

    # ------------------------------------------------------------------

    @staticmethod
    def _content_match(text: str, intent: Intent) -> float:
        hits = sum(1 for t in intent.primary_terms if t.lower() in text)
        return min(1.0, hits / max(len(intent.primary_terms), 1))

    @staticmethod
    def _contact_completeness(result: UnifiedResult) -> float:
        score = 0.0
        # Events: organizer contact
        if result.organizer_email:
            score += 0.5
        if result.organizer_domain:
            score += 0.3
        if result.starts_at:
            score += 0.2
        # Companies: location completeness
        if result.location_name or result.city or result.country:
            score += 0.4
        if result.city and result.country:
            score += 0.3
        if result.location_address:
            score += 0.2
        return min(1.0, score)

    @staticmethod
    def _signal_strength(text: str, cfg: ScorerConfig) -> float:
        high = sum(2 for kw in cfg.high_signals if kw in text)
        med = sum(1 for kw in cfg.med_signals if kw in text)
        return min(1.0, (high + med) / 6.0)

    @staticmethod
    def _region_match(text: str, result: UnifiedResult, intent: Intent) -> float:
        if not intent.region:
            return 0.5
        region = intent.region.lower()
        if region in text:
            return 1.0
        if result.city and region in result.city.lower():
            return 1.0
        return 0.0

    @staticmethod
    def _source_trust(url: str, cfg: ScorerConfig) -> float:
        if not url:
            return 0.0
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        if any(t in domain for t in cfg.noise_domains):
            return 0.0
        if any(t in domain for t in cfg.trusted_sources):
            return 1.0
        return 0.5

    @staticmethod
    def _recency(result: UnifiedResult) -> float:
        if not result.starts_at:
            return 0.3
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        starts = result.starts_at
        if starts.tzinfo is None:
            from datetime import timezone
            starts = starts.replace(tzinfo=timezone.utc)
        days_ahead = (starts - now).days
        if days_ahead < 0:
            return 0.0      # past event
        if days_ahead <= 7:
            return 1.0
        if days_ahead <= 30:
            return 0.8
        if days_ahead <= 90:
            return 0.5
        return 0.2
