"""
Domain Vocabulary Registry.

DomainVocab holds the linguistic knowledge needed to expand a raw intent
into a rich keyword graph for a given discovery direction.

Design rules:
- `events` and `bd_leads` are reference implementations, not privileged types.
- Any domain not in the registry silently falls back to `general`.
- Callers can inject a custom DomainVocab at runtime without touching this file.
- `source_hints` live here, not scattered in query_strategy.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DomainVocab:
    """
    All linguistic knowledge needed to bootstrap a KeywordGraph for one domain.

    synonym_groups:  canonical term → list of variants / aliases
    region_variants: region display name → list of abbreviations / native forms
    signal_terms:    high-value trigger phrases that indicate target relevance
    source_hints:    domains to prefer for site: search operators (radar/anchor)
    noise_terms:     extra negative terms beyond the global list
    """
    synonym_groups:  dict[str, list[str]] = field(default_factory=dict)
    region_variants: dict[str, list[str]] = field(default_factory=dict)
    signal_terms:    list[str]            = field(default_factory=list)
    source_hints:    list[str]            = field(default_factory=list)
    noise_terms:     list[str]            = field(default_factory=list)

    def merge(self, hints: "DomainVocab") -> "DomainVocab":
        """
        Return a new DomainVocab with caller-supplied hints overlaid on top.
        Caller additions extend lists; they do not replace them.
        """
        merged_synonyms = dict(self.synonym_groups)
        for canonical, variants in hints.synonym_groups.items():
            merged_synonyms.setdefault(canonical, [])
            merged_synonyms[canonical] = list({*merged_synonyms[canonical], *variants})

        merged_regions = dict(self.region_variants)
        for region, variants in hints.region_variants.items():
            merged_regions.setdefault(region, [])
            merged_regions[region] = list({*merged_regions[region], *variants})

        return DomainVocab(
            synonym_groups  = merged_synonyms,
            region_variants = merged_regions,
            signal_terms    = list({*self.signal_terms,  *hints.signal_terms}),
            source_hints    = list({*self.source_hints,  *hints.source_hints}),
            noise_terms     = list({*self.noise_terms,   *hints.noise_terms}),
        )


# ---------------------------------------------------------------------------
# Built-in domain registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, DomainVocab] = {

    "events": DomainVocab(
        synonym_groups={
            "meetup":   ["小聚", "交流", "聚會", "networking", "gathering"],
            "workshop": ["工作坊", "課程", "培訓", "lab", "hands-on"],
            "event":    ["活動", "講座", "演講", "talk", "forum"],
            "popup":    ["快閃", "限時", "快閃活動", "pop-up"],
            "conference": ["summit", "congress", "symposium", "convention"],
        },
        region_variants={
            "台北": ["台北市", "Taipei", "TPE"],
            "台中": ["台中市", "Taichung"],
            "高雄": ["高雄市", "Kaohsiung"],
            "Singapore": ["SG", "新加坡"],
            "Tokyo": ["東京", "JP", "Japan"],
        },
        signal_terms=[
            "報名", "免費", "付費", "線上", "線下", "限額",
            "free", "register", "sign up", "event", "meetup", "tickets",
        ],
        source_hints=[
            "lu.ma", "eventbrite.com", "meetup.com", "facebook.com",
            "kktix.com", "accupass.com",
        ],
        noise_terms=["job", "求職", "招募", "shopping", "ecommerce"],
    ),

    "bd_leads": DomainVocab(
        synonym_groups={
            "distributor":   ["wholesaler", "importer", "dealer", "reseller", "supplier"],
            "channel partner": ["official distributor", "partner program", "dealer network"],
            "manufacturer":  ["OEM", "ODM", "factory", "producer"],
        },
        region_variants={
            "Europe":  ["EU", "European"],
            "Germany": ["DE", "German", "Deutschland"],
            "Japan":   ["JP", "Japanese", "日本"],
            "US":      ["USA", "United States", "North America"],
            "Taiwan":  ["TW", "台灣"],
            "Southeast Asia": ["SEA", "ASEAN"],
        },
        signal_terms=[
            "looking for distributor", "become a distributor",
            "wholesale inquiry", "B2B", "bulk order",
            "trade fair", "exhibitor", "partner program",
            "exclusive distribution", "authorized reseller",
        ],
        source_hints=[
            "linkedin.com", "crunchbase.com", "clutch.co", "g2.com",
            "kompass.com", "globalsources.com",
        ],
        noise_terms=["blog", "review", "reddit", "amazon", "retail", "consumer"],
    ),

    "companies": DomainVocab(
        synonym_groups={
            "startup":   ["early-stage", "seed-stage", "series-a", "venture-backed"],
            "enterprise": ["Fortune 500", "large-cap", "multinational", "corporation"],
            "funding":   ["investment", "raise", "series", "round", "capital"],
        },
        region_variants={
            "Silicon Valley": ["Bay Area", "SF", "San Francisco"],
            "Europe":  ["EU", "European"],
            "Germany": ["DE", "Berlin", "Munich"],
            "Singapore": ["SG", "Southeast Asia"],
            "Taiwan":  ["TW", "台灣", "Taipei"],
        },
        signal_terms=[
            "founded", "headquarters", "employees", "revenue", "funding",
            "series A", "series B", "IPO", "acquired", "merger",
            "CEO", "CTO", "leadership", "team", "headcount",
        ],
        source_hints=[
            "crunchbase.com", "linkedin.com", "pitchbook.com",
            "bloomberg.com", "techcrunch.com", "builtin.com",
        ],
        noise_terms=["review", "reddit", "job posting", "salary", "glassdoor"],
    ),

    "market_intel": DomainVocab(
        synonym_groups={
            "launch":   ["release", "announced", "unveiled", "debut", "rollout"],
            "trend":    ["shift", "movement", "momentum", "adoption", "growth"],
            "competitor": ["rival", "alternative", "incumbent", "challenger"],
        },
        region_variants={
            "global": ["worldwide", "international"],
            "US":     ["United States", "North America", "American market"],
            "Europe": ["EU", "European market", "EMEA"],
            "Asia":   ["APAC", "Asia Pacific"],
        },
        signal_terms=[
            "market share", "growth rate", "industry report", "analyst",
            "forecast", "Q1", "Q2", "Q3", "Q4", "annual report",
            "press release", "product launch", "partnership announcement",
            "acquisition", "expansion", "hiring surge",
        ],
        source_hints=[
            "techcrunch.com", "reuters.com", "bloomberg.com", "wsj.com",
            "gartner.com", "forrester.com", "statista.com", "marketwatch.com",
        ],
        noise_terms=["reddit", "forum", "opinion", "personal blog", "tutorial"],
    ),

    "partnerships": DomainVocab(
        synonym_groups={
            "partnership": ["collaboration", "alliance", "joint venture", "MOU", "co-marketing"],
            "integration": ["API", "connector", "plugin", "embed", "sync"],
            "co-branding": ["co-marketing", "joint campaign", "co-sell", "co-develop"],
        },
        region_variants={
            "global": ["worldwide", "international"],
            "US":     ["United States", "North America"],
            "Europe": ["EU", "European"],
            "Asia":   ["APAC", "Asia Pacific"],
        },
        signal_terms=[
            "partnership", "collaboration", "joint", "co-founder", "strategic alliance",
            "memorandum of understanding", "signed agreement", "integration partner",
            "ecosystem partner", "technology partner", "go-to-market",
        ],
        source_hints=[
            "linkedin.com", "businesswire.com", "prnewswire.com",
            "crunchbase.com", "techcrunch.com", "venturebeat.com",
        ],
        noise_terms=["personal", "blog", "reddit", "forum", "review"],
    ),

    # General fallback — used when objective has no domain mapping.
    # Intentionally thin: no industry assumptions, pure structure.
    "general": DomainVocab(
        synonym_groups={},
        region_variants={
            "US":      ["United States", "North America", "USA"],
            "Europe":  ["EU", "European"],
            "Asia":    ["APAC", "Asia Pacific"],
            "global":  ["worldwide", "international"],
        },
        signal_terms=[
            "official", "contact", "about", "team", "press",
        ],
        source_hints=[
            "linkedin.com", "crunchbase.com", "bloomberg.com",
        ],
        noise_terms=[],
    ),
}


def get_vocab(domain: str) -> DomainVocab:
    """
    Look up domain vocab from the registry.
    Unknown domains silently return `general` — never raise, never default to bd_leads.
    """
    return _REGISTRY.get(domain, _REGISTRY["general"])


def list_domains() -> list[str]:
    return list(_REGISTRY.keys())


def register_domain(name: str, vocab: DomainVocab) -> None:
    """Register a custom domain at runtime (e.g., from plugin or test setup)."""
    _REGISTRY[name] = vocab
