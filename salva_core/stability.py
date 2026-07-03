"""Domain-level stability signals for the opt-in stability-gating feature.

See salva_core/schemas.py::StabilityPolicy and processing/scorer.py::
ScorerConfig.w_stability for the policy toggle and the scoring term this
is intended to feed (wiring happens in a separate follow-up card -- this
module is pure computation, not wired into any scoring path yet).

MVP scope is deliberately domain-level, not per-node/per-hyperedge: Salva's
persisted history (salva_core.persistence.memory.query_family_memory) only
has multi-record, timestamped history at the query-family/domain grain, not
finer-grained structures. See DEVELOPMENT_PROGRESS.md for the fuller
scoping note.
"""
from __future__ import annotations

import statistics

from salva_core.persistence.memory import _normalize_domain, list_query_family_memory


def compute_stability_signals(
    domain: str,
    min_history: int = 3,
    limit: int = 10,
    path: str | None = None,
) -> dict[str, float] | None:
    """Compute drift + volatility over a domain's recent query-family history.

    Returns None when fewer than min_history records exist for the domain --
    not enough data to say anything meaningful; callers should treat this as
    "unknown," not "stable."

    list_query_family_memory() has no domain filter (only run_id/objective/
    strategy/campaign_id/continuation_id/memory_status), so this over-fetches
    a broader recent window (ordered by created_at DESC) and filters
    client-side by record.domain, rather than adding a new domain-filtered
    SQL query function with no other consumer.
    """
    normalized = _normalize_domain(domain)
    fetch_limit = max(limit * 5, 50)
    if path is not None:
        records, _total = list_query_family_memory(limit=fetch_limit, path=path)
    else:
        records, _total = list_query_family_memory(limit=fetch_limit)

    domain_records = [r for r in records if _normalize_domain(r.domain or "") == normalized][:limit]
    if len(domain_records) < min_history:
        return None

    # list_query_family_memory returns created_at DESC; walk oldest -> newest.
    ordered = list(reversed(domain_records))

    # Intentionally NOT zip(..., strict=True): ordered[1:] is always exactly
    # one element shorter than ordered -- that's the pairwise-consecutive
    # walk, not a shape mismatch.
    drift_values = [
        _content_nodes_drift(prev.content_nodes, curr.content_nodes)
        for prev, curr in zip(ordered, ordered[1:], strict=False)
    ]
    drift = sum(drift_values) / len(drift_values) if drift_values else 0.0

    success_scores = [r.success_score for r in ordered]
    volatility = statistics.pstdev(success_scores) if len(success_scores) > 1 else 0.0

    return {"drift": drift, "volatility": volatility}


def _content_nodes_drift(prev_nodes: list[str], curr_nodes: list[str]) -> float:
    """1 - Jaccard similarity between two content_nodes term sets."""
    prev_set, curr_set = set(prev_nodes), set(curr_nodes)
    union = prev_set | curr_set
    if not union:
        return 0.0
    return 1.0 - len(prev_set & curr_set) / len(union)
