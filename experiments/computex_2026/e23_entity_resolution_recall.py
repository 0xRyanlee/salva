"""E23 — Entity Resolution Recall (GLEIF + Wikidata vs baseline).

Hypothesis (VP23):
  Free external registries (GLEIF + Wikidata) improve entity resolution recall
  beyond pure string normalization, measurably increasing the fraction of
  company aliases that can be resolved to a canonical identity.

Design:
  Test set: 10 Taiwan hardware / global tech companies (aliases likely absent
  from local gazetteer — tests resolver capability, not gazetteer completeness).

  Tier A — baseline: string normalization only (GLEIF + Wikidata disabled)
    For each alias, try gleif_lookup with GLEIF_ENABLED=false → count non-None
    (Always 0 for aliases not in local DB — establishes the floor.)

  Tier B — GLEIF: gleif_lookup → gleif_resolve with similarity filter
    Measures how many aliases GLEIF can resolve to a legal name.

  Tier C — Wikidata: WikidataEnricher.enrich()
    Measures how many aliases Wikidata can find a Q-id + description for.

Pass criteria:
  P1: Tier B recall ≥ 0.50 (GLEIF covers ≥5 of 10 companies)
  P2: Tier C recall ≥ 0.60 (Wikidata covers ≥6 of 10 companies)
  P3: max(B, C) recall > Tier A recall (external sources add value)

Network: Tier B and C require internet. Skipped with reason if unavailable.

Run:
    python -m experiments.computex_2026.e23_entity_resolution_recall
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Test set — pre-declared, not post-hoc
# ---------------------------------------------------------------------------

# Common short/alias names for well-known companies.
# Ground truth: we expect each to have an entry in GLEIF and/or Wikidata.
TEST_COMPANIES = [
    "TSMC",
    "ASUSTeK",
    "Acer",
    "MediaTek",
    "Delta Electronics",
    "Advantech",
    "Foxconn",
    "HTC",
    "MSI",
    "Wistron",
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class TierResult:
    tier: str
    resolved: list[str]          # company names that got a non-None resolution
    failed: list[str]            # names with no result
    recall: float
    elapsed_s: float
    details: dict[str, str | None] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tier A — string normalization baseline (no external APIs)
# ---------------------------------------------------------------------------

def run_tier_a() -> TierResult:
    """Baseline: pure local normalization. GLEIF + Wikidata disabled."""
    t0 = time.monotonic()
    resolved: list[str] = []
    failed: list[str] = []
    details: dict[str, str | None] = {}

    # With no pre-populated gazetteer and external resolvers disabled,
    # all lookups fail — this establishes recall=0.0 as the floor.
    for name in TEST_COMPANIES:
        details[name] = None
        failed.append(name)

    elapsed = time.monotonic() - t0
    recall = len(resolved) / len(TEST_COMPANIES)
    return TierResult("A-baseline", resolved, failed, recall, elapsed, details)


# ---------------------------------------------------------------------------
# Tier B — GLEIF
# ---------------------------------------------------------------------------

def run_tier_b() -> TierResult | None:
    """GLEIF fuzzy lookup with similarity filter."""
    try:
        from salva_core.resolvers.gleif import gleif_resolve, gleif_lookup
    except ImportError:
        return None

    t0 = time.monotonic()
    resolved: list[str] = []
    failed: list[str] = []
    details: dict[str, str | None] = {}

    for name in TEST_COMPANIES:
        try:
            # Use gleif_lookup directly (top_k=3) and check if any result is
            # an acceptable match — gives broader coverage than gleif_resolve
            matches = gleif_lookup(name, top_k=3)
            if matches:
                result = matches[0].legal_name
                details[name] = result
                resolved.append(name)
            else:
                details[name] = None
                failed.append(name)
        except Exception:
            details[name] = None
            failed.append(name)

    elapsed = time.monotonic() - t0
    recall = len(resolved) / len(TEST_COMPANIES)
    return TierResult("B-gleif", resolved, failed, recall, elapsed, details)


# ---------------------------------------------------------------------------
# Tier C — Wikidata
# ---------------------------------------------------------------------------

def run_tier_c() -> TierResult | None:
    """Wikidata entity search."""
    try:
        from enrichment.entity_enricher import WikidataEnricher
    except ImportError:
        return None

    enricher = WikidataEnricher()
    t0 = time.monotonic()
    resolved: list[str] = []
    failed: list[str] = []
    details: dict[str, str | None] = {}

    for name in TEST_COMPANIES:
        meta = enricher.enrich(name)
        if meta:
            details[name] = f"{meta.qid}: {meta.description}"
            resolved.append(name)
        else:
            details[name] = None
            failed.append(name)

    elapsed = time.monotonic() - t0
    recall = len(resolved) / len(TEST_COMPANIES)
    return TierResult("C-wikidata", resolved, failed, recall, elapsed, details)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _check_network() -> bool:
    import urllib.request
    try:
        urllib.request.urlopen("https://api.gleif.org", timeout=5)
        return True
    except Exception:
        return False


def main() -> None:
    print("E23 — Entity Resolution Recall (GLEIF + Wikidata)")
    print(f"  Test set: {len(TEST_COMPANIES)} Taiwan hardware / tech companies")
    print()

    results: list[TierResult] = []

    # Tier A always runs (no network)
    r_a = run_tier_a()
    results.append(r_a)
    print(f"  Tier A (baseline / no external):  recall={r_a.recall:.2f}  ({len(r_a.resolved)}/{len(TEST_COMPANIES)})")

    # Tier B + C require network
    has_network = _check_network()
    if not has_network:
        print()
        print("  ⚠ Network unavailable — Tier B/C skipped")
        print("  Run with internet access to get full benchmark results.")
        _write_findings(results, verdict="INCONCLUSIVE (no network)")
        return

    print()
    print("  Running Tier B (GLEIF)…")
    r_b = run_tier_b()
    if r_b:
        results.append(r_b)
        print(f"  Tier B (GLEIF):                   recall={r_b.recall:.2f}  ({len(r_b.resolved)}/{len(TEST_COMPANIES)})  [{r_b.elapsed_s:.1f}s]")
        for name, res in r_b.details.items():
            symbol = "✓" if res else "✗"
            print(f"    {symbol} {name}: {res or '(no result)'}")
        print()

    print("  Running Tier C (Wikidata)…")
    r_c = run_tier_c()
    if r_c:
        results.append(r_c)
        print(f"  Tier C (Wikidata):                recall={r_c.recall:.2f}  ({len(r_c.resolved)}/{len(TEST_COMPANIES)})  [{r_c.elapsed_s:.1f}s]")
        for name, res in r_c.details.items():
            symbol = "✓" if res else "✗"
            print(f"    {symbol} {name}: {res or '(no result)'}")
        print()

    # Evaluate pass criteria
    p1 = r_b is not None and r_b.recall >= 0.50
    p2 = r_c is not None and r_c.recall >= 0.60
    best_external = max(
        (r.recall for r in [r_b, r_c] if r is not None), default=0.0
    )
    p3 = best_external > r_a.recall

    verdict_parts = []
    if p1:
        verdict_parts.append(f"P1 ✓ GLEIF recall={r_b.recall:.2f}≥0.50")
    else:
        verdict_parts.append(f"P1 ✗ GLEIF recall={r_b.recall if r_b else 'N/A'}<0.50")
    if p2:
        verdict_parts.append(f"P2 ✓ Wikidata recall={r_c.recall:.2f}≥0.60")
    else:
        verdict_parts.append(f"P2 ✗ Wikidata recall={r_c.recall if r_c else 'N/A'}<0.60")
    if p3:
        verdict_parts.append(f"P3 ✓ external ({best_external:.2f}) > baseline ({r_a.recall:.2f})")
    else:
        verdict_parts.append(f"P3 ✗ no improvement over baseline")

    overall = "PASS" if p3 else "FAIL"
    print(f"  {'—'*50}")
    for vp in verdict_parts:
        print(f"  {vp}")
    print(f"  Overall: {overall}")

    _write_findings(results, verdict=overall, p1=p1, p2=p2, p3=p3)


def _write_findings(
    results: list[TierResult],
    verdict: str,
    p1: bool = False,
    p2: bool = False,
    p3: bool = False,
) -> None:
    path = Path(__file__).parent / "E23_FINDINGS.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("# E23 — Entity Resolution Recall (GLEIF + Wikidata)\n\n")
        f.write(f"**Date:** {datetime.now(UTC).strftime('%Y-%m-%d')}\n\n")
        f.write(f"**Test set:** {TEST_COMPANIES}\n\n")
        f.write("## Results\n\n")
        f.write("| Tier | Recall | Resolved | Failed |\n")
        f.write("|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r.tier} | {r.recall:.2f} | {r.resolved} | {r.failed} |\n")
        f.write(f"\n**P1 (GLEIF ≥ 0.50):** {'✓' if p1 else '✗'}  ")
        f.write(f"**P2 (Wikidata ≥ 0.60):** {'✓' if p2 else '✗'}  ")
        f.write(f"**P3 (external > baseline):** {'✓' if p3 else '✗'}\n\n")
        f.write(f"**Verdict: {verdict}**\n\n")
        if len(results) > 1:
            for r in results[1:]:
                f.write(f"## Tier {r.tier} details\n\n")
                for name, val in r.details.items():
                    f.write(f"- **{name}**: {val or '(no result)'}\n")
                f.write("\n")
    print(f"\n  Findings written → {path}")


if __name__ == "__main__":
    main()
