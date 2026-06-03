"""E6 — cross-semantic relation/fact merging (VP6).

Hypothesis: equivalent relations/roles across languages normalise to one schema,
and multi-source records of the SAME fact merge into one hyperedge with multiple
evidence (provenance preserved, conflicts surfaced) — whereas naive handling
treats them as fragmented distinct facts.

Stdlib only. Mirrors E5's finding: a curated ontology + entity bridge collapses
known multilingual phrasings; unseen phrasings need embedding/LLM (same gap).

    python -m experiments.hg_penetration.e6_relation_merge
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

# ---- entity gazetteer (cross-lingual → canonical id; the E5 bridge, curated) ----
ENTITY = {
    "甲控股": "ent:holdco_a", "甲控股有限公司": "ent:holdco_a", "holdco a": "ent:holdco_a",
    "乙公司": "ent:target_b", "target b": "ent:target_b",
    "丙公司": "ent:c_co",
    "張三": "ent:zhang_san", "zhang san": "ent:zhang_san",
}

# ---- relation/role ontology (multilingual surface → canonical FtM-aligned) ----
RELATION = {
    "持股": ("ownership", "owner", "asset"),
    "控股": ("ownership", "owner", "asset"),
    "owns": ("ownership", "owner", "asset"),
    "holds stake in": ("ownership", "owner", "asset"),
    "投資": ("investment", "investor", "investee"),       # distinct relation — must NOT merge with ownership
    "董事長": ("directorship", "chairman", "organization"),
    "chairman": ("directorship", "chairman", "organization"),
    "董事": ("directorship", "director", "organization"),
    "director": ("directorship", "director", "organization"),
}


@dataclass
class RawFact:
    source: str
    lang: str
    subject: str
    relation: str       # surface term, any language
    object: str
    value: str | None = None


# multi-source, multilingual records of (mostly) the same facts
RECORDS = [
    RawFact("gsxt", "zh", "甲控股", "持股", "乙公司", "70%"),
    RawFact("news_en", "en", "HoldCo A", "owns", "Target B", "70%"),
    RawFact("filing", "zh", "甲控股有限公司", "控股", "乙公司", "70%"),
    RawFact("stale_news", "en", "HoldCo A", "holds stake in", "Target B", "65%"),  # CONFLICT on %
    RawFact("mops", "zh", "張三", "董事長", "乙公司", None),
    RawFact("news_en", "en", "Zhang San", "chairman", "Target B", None),
    RawFact("news", "zh", "甲控股", "投資", "丙公司", None),                        # distinct fact
]


def _eid(surface: str) -> str:
    return ENTITY.get(surface.strip().lower(), ENTITY.get(surface.strip(), f"raw:{surface}"))


def _rel(surface: str):
    return RELATION.get(surface.strip().lower(), RELATION.get(surface.strip()))


def naive_fact_count() -> int:
    """No normalisation: a fact is keyed by raw surface strings."""
    keys = {(r.subject, r.relation, r.object) for r in RECORDS}
    return len(keys)


def merge() -> dict[tuple, dict]:
    """Normalise relation + entities, key by (subject_id, canonical_relation, object_id)."""
    facts: dict[tuple, dict] = defaultdict(lambda: {"evidence": [], "values": set()})
    for r in RECORDS:
        rel = _rel(r.relation)
        if rel is None:
            continue
        canon, role_s, role_o = rel
        key = (_eid(r.subject), canon, _eid(r.object))
        facts[key]["roles"] = (role_s, role_o)
        facts[key]["evidence"].append(f"{r.source}/{r.lang}: '{r.relation}'")
        if r.value:
            facts[key]["values"].add(r.value)
    return facts


def main() -> None:
    print("E6 — cross-semantic relation/fact merging")
    print(f"  {len(RECORDS)} raw multilingual source records\n")

    print(f"  [NAIVE]  distinct facts (raw surface keys): {naive_fact_count()}")
    print("    → 持股 / owns / 控股 look like 3 different relations; 甲控股 / HoldCo A like 2 entities.")
    print("    → the same ownership fact is fragmented across sources/languages.\n")

    facts = merge()
    print(f"  [NORMALISED + MERGED]  canonical hyperedges: {len(facts)}")
    for (subj, rel, obj), f in facts.items():
        line = f"    • {rel}({subj} → {obj})  [{len(f['evidence'])} evidence]"
        if f["values"]:
            vals = ", ".join(sorted(f["values"]))
            line += f"  value={{{vals}}}" + ("  ⚠ CONFLICT" if len(f["values"]) > 1 else "")
        print(line)
        for e in f["evidence"]:
            print(f"        ← {e}")

    print("\n  verdict (honest):")
    print("  • ontology + entity bridge collapses multilingual same-fact records into ONE")
    print("    canonical hyperedge, PROVENANCE preserved (all sources kept), CONFLICTS surfaced")
    print("    (70% vs 65% flagged, not silently overwritten).")
    print("  • 投資 stays a SEPARATE relation — semantic distinction preserved (no over-merge).")
    print("  • limit (same as E5): relies on a curated relation ontology + entity gazetteer;")
    print("    unseen phrasings need multilingual embedding / LLM normalisation.")
    print("  → DEVELOPMENT IMPLICATION: canonical relation ontology (FtM-aligned) + the E5")
    print("    entity bridge + conflict-preserving merge are required; build the ontology as data.")


if __name__ == "__main__":
    main()
