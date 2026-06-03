"""Source-routing self-optimisation: re-rank the Jurisdiction Source Registry
from observed source_attempts.

The seed registry is domain knowledge ("gsxt is the highest-authority CN source").
But authority != reachability: an automated attempt against gsxt fails (anti-bot),
while SEC EDGAR yields cleanly. Recording real attempts lets routing LEARN to
prefer the source that actually delivers — the honest, concrete form of "the
pipeline self-optimises; future searches have a learned path to choose."
"""
from __future__ import annotations

from dataclasses import dataclass

_RELIABILITY = {"high": 3.0, "medium": 2.0, "low": 1.0}


@dataclass
class SourceAttempt:
    jurisdiction: str
    fact_type: str
    source: str
    hit: bool
    result_count: int = 0


def source_score(entry: dict, attempts: list[SourceAttempt]) -> tuple[float, str]:
    base = _RELIABILITY.get(entry["reliability"], 1.0)
    rel = [a for a in attempts if a.source == entry["source"]]
    if not rel:
        return base, "seed-only"
    hits = [a for a in rel if a.hit]
    if not hits:
        return base - 5.0, f"learned: {len(rel)} attempt(s), all FAILED → demoted"
    rate = len(hits) / len(rel)
    yield_bonus = min(2.0, sum(a.result_count for a in hits) / len(hits) / 10.0)
    total = sum(a.result_count for a in hits)
    return base + rate * 2.0 + yield_bonus, f"learned: hit-rate {rate:.0%}, yield {total} → boosted"


def rerank(
    registry: dict[tuple[str, str], list[dict]], attempts: list[SourceAttempt],
) -> dict[tuple[str, str], list[tuple[dict, float, str]]]:
    out: dict[tuple[str, str], list[tuple[dict, float, str]]] = {}
    for key, sources in registry.items():
        scored = [(s, *source_score(s, attempts)) for s in sources]
        scored.sort(key=lambda x: -x[1])
        out[key] = scored
    return out
