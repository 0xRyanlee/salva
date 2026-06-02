"""
Query strategy helpers for Salva's iterative retrieval loop.

Keeps strategy-specific query generation and negative-term logic
out of the orchestration layer so the controller and graph stay small.

Source hints are now owned by DomainVocab (core/domain_vocab.py).
build_strategy_profile() accepts an optional vocab so callers don't
need to look up hints separately.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from core.types import Intent, KeywordNode, QueryFamily

if TYPE_CHECKING:
    from core.domain_vocab import DomainVocab


GLOBAL_NEGATIVES = [
    "blog",
    "museum",
    "review",
    "job",
    "news",
    "report",
    "reddit",
    "wikipedia",
    "youtube",
    "amazon",
    "ebay",
    "shopee",
]


def build_negative_terms(intent: Intent, limit: int = 6) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in [*intent.negative_terms, *GLOBAL_NEGATIVES]:
        normalized = term.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(normalized)
        if len(terms) >= limit:
            break
    return terms


def build_strategy_profile(
    intent: Intent,
    strategy: str,
    round_num: int,
    vocab: "DomainVocab | None" = None,
) -> dict[str, Any]:
    """
    Build a strategy profile dict for one retrieval round.

    vocab is passed in from the KeywordGraph so source_hints come from
    the resolved DomainVocab rather than a hardcoded domain lookup.
    """
    if strategy == "dive":
        content_weights = {
            "title":    0.45,
            "snippet":  0.25,
            "document": 0.20,
            "platform": 0.10,
        }
        notes = [
            "precision_first",
            "negative_terms_heavy",
            "document_followup" if round_num >= 2 else "seed_only",
        ]
    elif strategy == "anchor":
        content_weights = {
            "title":    0.30,
            "snippet":  0.30,
            "document": 0.20,
            "platform": 0.20,
        }
        notes = [
            "graph_expansion",
            "balance_title_snippet_document",
        ]
    elif strategy == "pirate":
        # Operator-heavy, document-probing, noise-tolerant.
        # Trades precision for maximum coverage via filetype/intitle/site: operators.
        content_weights = {
            "title":    0.15,
            "snippet":  0.20,
            "document": 0.45,
            "platform": 0.20,
        }
        notes = [
            "operator_heavy",
            "filetype_probing",
            "noise_tolerant",
            "source_saturate" if round_num >= 2 else "operator_seed",
        ]
    else:  # radar
        content_weights = {
            "title":    0.20,
            "snippet":  0.25,
            "document": 0.15,
            "platform": 0.40,
        }
        notes = [
            "source_discovery",
            "platform_heavy",
        ]

    # Source hints come from the vocab; fall back to a safe generic list
    if vocab is not None:
        source_hints = list(vocab.source_hints)
    else:
        from core.domain_vocab import get_vocab
        source_hints = get_vocab(intent.domain).source_hints

    return {
        "content_weights": content_weights,
        "source_hints":    source_hints,
        "notes":           notes,
    }


def build_query_family(
    intent: Intent,
    nodes: list[KeywordNode],
    round_num: int,
    strategy: str,
    max_queries: int = 10,
    profile: dict[str, Any] | None = None,
    vocab: "DomainVocab | None" = None,
) -> QueryFamily:
    profile = profile or build_strategy_profile(intent, strategy, round_num, vocab)
    queries = build_queries(intent, nodes, round_num, strategy, max_queries, profile)
    source_nodes = [node.phrase for node in nodes[:5]]
    return QueryFamily(
        round_num=round_num,
        queries=queries,
        strategy=strategy,
        source_nodes=source_nodes,
        content_weights=profile["content_weights"],
        source_hints=profile["source_hints"],
        notes=profile["notes"],
    )


def build_queries(
    intent: Intent,
    nodes: list[KeywordNode],
    round_num: int,
    strategy: str,
    max_queries: int,
    profile: dict[str, Any],
) -> list[str]:
    if strategy == "dive":
        queries = _build_dive_queries(intent, nodes, round_num, max_queries, profile)
    elif strategy == "anchor":
        queries = _build_anchor_queries(intent, nodes, round_num, max_queries, profile)
    elif strategy == "pirate":
        queries = _build_pirate_queries(intent, nodes, round_num, max_queries, profile)
    else:  # radar — also catches any future unknown strategy
        queries = _build_radar_queries(intent, nodes, round_num, max_queries, profile)
    return [query for query in queries if query][:max_queries]


def _build_dive_queries(
    intent: Intent,
    nodes: list[KeywordNode],
    round_num: int,
    n: int,
    profile: dict[str, Any],
) -> list[str]:
    primaries = [nd.phrase for nd in nodes if nd.node_type == "primary"][:2]
    regions   = [nd.phrase for nd in nodes if nd.node_type == "region"][:2]
    neg = " ".join(f"-{term}" for term in build_negative_terms(intent))

    queries: list[str] = []
    for primary in primaries:
        base = f'"{primary}"'
        if regions:
            for region in regions[:2]:
                queries.append(f"{base} {region} {neg}".strip())
        else:
            queries.append(f"{base} {neg}".strip())
        if round_num >= 2:
            queries.append(f"{base} filetype:pdf {neg}".strip())
            queries.append(f'intitle:"{primary}" {neg}'.strip())
        if round_num >= 3:
            for hint in profile["source_hints"][:2]:
                queries.append(f"site:{hint} {base} {neg}".strip())
    return queries[:n]


def _build_anchor_queries(
    intent: Intent,
    nodes: list[KeywordNode],
    round_num: int,
    n: int,
    profile: dict[str, Any],
) -> list[str]:
    primaries = [nd.phrase for nd in nodes if nd.node_type in ("primary", "synonym")][:3]
    roles     = [nd.phrase for nd in nodes if nd.node_type == "role"][:3]
    regions   = [nd.phrase for nd in nodes if nd.node_type == "region"][:2]
    signals   = [nd.phrase for nd in nodes if nd.node_type == "signal"][:2]

    queries: list[str] = []
    for primary in primaries:
        for role in (roles or [""]):
            combo = f"{primary} {role}".strip()
            if regions:
                for region in regions[:1]:
                    queries.append(f"{combo} {region}".strip())
            else:
                queries.append(combo)
        if signals:
            queries.append(f"{primary} {signals[0]}".strip())
        if round_num >= 2:
            queries.append(f"{primary} filetype:pdf".strip())
            for hint in profile["source_hints"][:1]:
                queries.append(f"site:{hint} {primary}".strip())
    return queries[:n]


def _build_pirate_queries(
    intent: Intent,
    nodes: list[KeywordNode],
    round_num: int,
    n: int,
    profile: dict[str, Any],
) -> list[str]:
    """
    Operator-heavy queries for deep investigation and OSINT-style discovery.

    Strategy: filetype:, intitle:, inurl:, site: operators from round 1.
    No negative terms — maximise recall, accept noise.
    Best paired with enrichment + strict post-scoring.
    """
    primaries = [nd.phrase for nd in nodes if nd.node_type == "primary"][:2]
    signals   = [nd.phrase for nd in nodes if nd.node_type == "signal"][:3]
    regions   = [nd.phrase for nd in nodes if nd.node_type == "region"][:1]
    region_str = regions[0] if regions else ""

    queries: list[str] = []
    for primary in primaries:
        # Document probing — PDFs and presentations often surface company/event data
        queries.append(f'filetype:pdf "{primary}" {region_str}'.strip())
        queries.append(f'(filetype:ppt OR filetype:pptx) "{primary}" {region_str}'.strip())
        # Title-anchor probing
        queries.append(f'intitle:"{primary}" {region_str}'.strip())
        # URL-pattern probing — about/company/team pages
        queries.append(f'inurl:about "{primary}" {region_str}'.strip())
        # Source-saturating: hit every configured source hint
        for hint in profile["source_hints"][:4]:
            queries.append(f'site:{hint} "{primary}" {region_str}'.strip())
        # Signal cross-combinations
        for signal in signals[:2]:
            queries.append(f'"{primary}" "{signal}" {region_str}'.strip())
        if round_num >= 2:
            # Broader document types in deeper rounds
            queries.append(f'filetype:docx OR filetype:xlsx "{primary}" {region_str}'.strip())
            queries.append(f'"{primary}" annual report OR whitepaper {region_str}'.strip())
            # Exhaustive source probing with exact phrases
            for hint in profile["source_hints"][4:8]:
                queries.append(f'site:{hint} "{primary}"'.strip())
    return queries[:n]


def _build_radar_queries(
    intent: Intent,
    nodes: list[KeywordNode],
    round_num: int,
    n: int,
    profile: dict[str, Any],
) -> list[str]:
    signals  = [nd.phrase for nd in nodes if nd.node_type == "signal"]
    primaries = [nd.phrase for nd in nodes if nd.node_type == "primary"][:2]
    regions  = [nd.phrase for nd in nodes if nd.node_type == "region"][:1]

    region_str = regions[0] if regions else ""
    queries: list[str] = []
    for primary in primaries:
        for signal in signals[:3]:
            queries.append(f"{primary} {signal} {region_str}".strip())

    if primaries:
        for hint in profile["source_hints"][:4]:
            queries.append(f"{primaries[0]} site:{hint} {region_str}".strip())
            if round_num >= 2:
                queries.append(f'"{primaries[0]}" site:{hint} {region_str}'.strip())
    return queries[:n]
