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

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

from core.types import Intent, UnifiedResult
from salva_core.vector_backends import resolve_semantic_vector_backend

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# BM25 Okapi TF-saturation constants (standard defaults).
_BM25_K1 = 1.5
_BM25_B = 0.75
# Reference document length for the (1 - b + b * doc_len/avgdl) length-norm
# term -- there's no run-level corpus available at single-result scoring
# time to compute a real average, so this approximates a typical title +
# snippet token count instead.
_BM25_AVG_DOC_LEN = 40.0

# Blend weight between the BM25 lexical signal and semantic vector
# similarity in _content_match. Starting point, not load-bearing elsewhere --
# ranking/gating on top of this signal is a separate card's scope.
_CONTENT_MATCH_ALPHA = 0.5


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _bm25_tf_saturation(text_tokens: list[str], query_tokens: list[str]) -> float:
    """BM25-style term-frequency saturation, normalized to [0, 1].

    Each candidate result is scored independently (no batch/corpus available
    at this call site), so this omits real corpus IDF -- every query term is
    weighted equally. What it adds over naive substring presence-checking:
    repeated occurrences saturate with diminishing returns instead of being
    ignored, multi-word terms match on constituent tokens rather than exact
    phrase, and document length is normalized against a fixed reference.
    """
    if not text_tokens or not query_tokens:
        return 0.0
    doc_len = len(text_tokens)
    counts = Counter(text_tokens)
    length_norm = _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_len / _BM25_AVG_DOC_LEN)
    total = 0.0
    for term in query_tokens:
        tf = counts.get(term, 0)
        if tf == 0:
            continue
        total += (tf * (_BM25_K1 + 1)) / (tf + length_norm)
    max_possible = len(query_tokens) * (_BM25_K1 + 1)
    return min(1.0, total / max_possible) if max_possible > 0 else 0.0


def _semantic_content_score(text: str, intent: Intent) -> float:
    if not intent.primary_terms or not text.strip():
        return 0.0
    backend = resolve_semantic_vector_backend()
    query_text = " ".join(intent.primary_terms)
    score = backend.score(backend.embed(query_text), backend.embed(text))
    return max(0.0, min(1.0, score))


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

    # Optional stability-gating term (see salva_core/schemas.py::StabilityPolicy).
    # Default 0.0 -- inert until a caller opts in and passes penalty_strength
    # through. Not part of the "must sum to 1.0" default weights above; when
    # non-zero it participates in _apply_context()'s renormalization.
    w_stability: float = 0.0

    # Per-domain qualify threshold; read by QualificationScorer.domain_threshold()
    qualify_threshold: float = 0.40


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
        high_signals=[
            "distributor", "wholesale", "wholesaler", "supplier", "bulk", "b2b",
            "buying group", "retail alliance", "verbundgruppe", "distribution network",
        ],
        med_signals=[
            "importer", "exporter", "trading", "dealer", "manufacturer", "reseller",
            "partner", "retailer", "sport",
        ],
        negative_signals=["blog", "review", "reddit", "amazon"],
        trusted_sources=frozenset({
            "linkedin.com", "crunchbase.com", "clutch.co",
        }),
        # B2B distributor snippets rarely surface email — don't penalise missing contact
        w_content=0.30,
        w_contact=0.05,
        w_signal=0.35,
        w_region=0.15,
        w_source=0.10,
        w_recency=0.05,
        qualify_threshold=0.35,
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
    "partnerships": ScorerConfig(
        high_signals=[
            "partnership", "strategic alliance", "memorandum of understanding",
            "MOU", "joint venture", "signed agreement", "collaboration agreement",
        ],
        med_signals=[
            "collaboration", "integration partner", "ecosystem partner",
            "technology partner", "go-to-market", "co-marketing", "alliance",
        ],
        negative_signals=["blog", "reddit", "forum", "review", "personal"],
        trusted_sources=frozenset({
            "linkedin.com", "businesswire.com", "prnewswire.com",
            "crunchbase.com", "techcrunch.com", "venturebeat.com",
        }),
        # Partnership signals are harder to surface explicitly in snippets
        # than basic company facts -- lower bar, matches bd_leads/taiwan_hardware.
        qualify_threshold=0.35,
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
        qualify_threshold=0.35,
    ),
}


class QualificationScorer:

    def __init__(self, config: ScorerConfig | None = None):
        self.config = config

    @staticmethod
    def domain_threshold(domain: str) -> float:
        """Return the recommended qualify_threshold for a domain.

        Falls back to 0.40 for unknown domains. Callers can pass this as
        qualify_threshold to SalvaController to get domain-calibrated gating.
        """
        cfg = DOMAIN_CONFIGS.get(domain)
        return cfg.qualify_threshold if cfg is not None else 0.40

    def score(self, result: UnifiedResult, intent: Intent, context: dict[str, Any] | None = None) -> float:
        cfg = self.config or DOMAIN_CONFIGS.get(intent.domain, ScorerConfig())
        cfg = self._apply_context(cfg, context)
        text = f"{result.title} {result.description}".lower()

        # No snippet → classifier is blind; cap below qualify_threshold to prevent
        # title-only noise from passing as qualified results.
        if not result.description:
            result.reject_reasons.append("no_snippet")
            partial = (
                cfg.w_content * self._content_match(text, intent)
                + cfg.w_source * self._source_trust(result.source_url, cfg)
            )
            return round(min(0.30, partial), 4)

        content_score = self._content_match(text, intent)
        contact_score = self._contact_completeness(result)
        signal_score = self._signal_strength(text, cfg)
        region_score = self._region_match(text, result, intent)
        source_score = self._source_trust(result.source_url, cfg)
        recency_score = self._recency(result)

        # Negative signals hard-penalize (case-insensitive, text is pre-lowercased)
        if any(neg.lower() in text for neg in cfg.negative_signals):
            return max(0.0, signal_score * 0.3)

        composite = (
            cfg.w_content  * content_score
            + cfg.w_contact  * contact_score
            + cfg.w_signal   * signal_score
            + cfg.w_region   * region_score
            + cfg.w_source   * source_score
            + cfg.w_recency  * recency_score
        )

        # Opt-in stability gating (see StabilityPolicy / w_stability docstring
        # above). cfg.w_stability is 0.0 unless a caller explicitly enabled it
        # via context["w_stability"] in _apply_context(), so this is a no-op
        # for every existing caller.
        if cfg.w_stability > 0 and isinstance(context, dict):
            stability_score = context.get("stability_score")
            if stability_score is not None:
                composite += cfg.w_stability * float(stability_score)

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
            w_stability=cfg.w_stability,
            qualify_threshold=cfg.qualify_threshold,
        )

        # Note-based presets apply only when using the default ScorerConfig weights.
        # Domain-specific configs (bd_leads, taiwan_hardware, …) already encode
        # calibrated weights and must not be overridden by strategy presets.
        _is_default_weights = (
            abs(cfg.w_content - 0.25) < 1e-6
            and abs(cfg.w_contact - 0.20) < 1e-6
            and abs(cfg.w_signal - 0.20) < 1e-6
        )
        if _is_default_weights:
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

        # Opt-in stability gating: only a caller that explicitly sets
        # context["w_stability"] (see StabilityPolicy.penalty_strength) can
        # move this off its 0.0 default. Absent that, behavior is identical
        # to before this feature existed.
        if isinstance(context, dict) and context.get("w_stability") is not None:
            adjusted.w_stability = float(context["w_stability"])

        total = (
            adjusted.w_content
            + adjusted.w_contact
            + adjusted.w_signal
            + adjusted.w_region
            + adjusted.w_source
            + adjusted.w_recency
            + adjusted.w_stability
        )
        if total > 0:
            adjusted.w_content /= total
            adjusted.w_contact /= total
            adjusted.w_signal /= total
            adjusted.w_region /= total
            adjusted.w_source /= total
            adjusted.w_recency /= total
            adjusted.w_stability /= total
        return adjusted

    # ------------------------------------------------------------------

    @staticmethod
    def _content_match(text: str, intent: Intent) -> float:
        query_tokens = _tokenize(" ".join(intent.primary_terms))
        bm25_score = _bm25_tf_saturation(_tokenize(text), query_tokens)
        semantic_score = _semantic_content_score(text, intent)
        return round(
            _CONTENT_MATCH_ALPHA * bm25_score + (1 - _CONTENT_MATCH_ALPHA) * semantic_score, 6
        )

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
        # text is pre-lowercased; normalize keywords to match case-insensitively
        high = sum(2 for kw in cfg.high_signals if kw.lower() in text)
        med = sum(1 for kw in cfg.med_signals if kw.lower() in text)
        return min(1.0, (high + med) / 6.0)

    @staticmethod
    def _region_match(text: str, result: UnifiedResult, intent: Intent) -> float:
        if not intent.region:
            return 0.5
        # Split compound regions ("Germany Austria Switzerland") and match any part.
        # Single-token regions work unchanged; multi-token regions no longer return 0.
        region_tokens = [t.strip().lower() for t in intent.region.replace(",", " ").split() if len(t.strip()) > 1]
        for token in region_tokens:
            if token in text:
                return 1.0
            if result.city and token in result.city.lower():
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
        from datetime import datetime
        now = datetime.now(UTC)
        starts = result.starts_at
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=UTC)
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
