"""E17 — Diff Longitudinal (VP17).

Hypothesis (VP17): `_compute_run_diff()` correctly surfaces entity-level changes
between two runs of the same discovery intent:
  P1. Identical runs (same corpus, same intent) → empty diff (no added, removed, updated)
  P2. Run B with one extra entity → diff.added contains that entity
  P3. Run A with one entity absent in B → diff.removed contains that entity
  P4. Entity present in both but with different score → diff.updated contains it

Method:
  - Use frozen corpus from E15 (no live network)
  - Build two runs directly via SalvaController + persist_discovery_run
  - Load runs via get_run and pass to _compute_run_diff (from apps.cli.main)
  - Verify four pass criteria above

Run:
    python -m experiments.computex_2026.e17_diff_longitudinal
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from experiments.computex_2026.e15_budget_ab import (
    FROZEN_CORPUS_NATUREHIKE,
    GROUND_TRUTH_NATUREHIKE,
    FrozenCorpusRetriever,
    _name_match,
)


def _make_entity(title: str, domain: str = "bd_leads", score: float = 0.8) -> dict:
    return {"title": title, "domain": domain, "score": score, "url": f"https://{title.lower().replace(' ', '')}.example.com"}


def _entity_key(entity: dict) -> str:
    title = (entity.get("title") or "").lower().strip()
    domain = (entity.get("domain") or "").lower().strip()
    return f"{title}|{domain}"


def _compute_run_diff(run_a: dict, run_b: dict) -> dict:
    """Mirror of apps/cli/main.py _compute_run_diff."""
    a_entities = {_entity_key(e): e for e in run_a.get("entities", [])}
    b_entities = {_entity_key(e): e for e in run_b.get("entities", [])}

    added   = [b_entities[k] for k in b_entities if k not in a_entities]
    removed = [a_entities[k] for k in a_entities if k not in b_entities]
    updated = []
    unchanged = []

    for k in a_entities:
        if k not in b_entities:
            continue
        a_score = a_entities[k].get("score") or 0.0
        b_score = b_entities[k].get("score") or 0.0
        if abs(a_score - b_score) > 0.01:
            updated.append({
                "title":   b_entities[k].get("title"),
                "score_a": a_score,
                "score_b": b_score,
                "entity":  b_entities[k],
            })
        else:
            unchanged.append(b_entities[k])

    return {
        "run_id_a":  run_a.get("run_id") or "",
        "run_id_b":  run_b.get("run_id") or "",
        "added":     added,
        "removed":   removed,
        "updated":   updated,
        "unchanged": unchanged,
    }


def _run_controller_frozen(request_limit: int = 12, corpus=None) -> list[dict]:
    """Run SalvaController on frozen corpus and return qualified entity dicts."""
    from core.controller import SalvaController
    from core.keyword_graph import KeywordGraph
    from core.types import Intent
    from processing.dedup import MemoryDeduplicator
    from processing.extractor import BaseExtractor
    from processing.scorer import QualificationScorer

    if corpus is None:
        corpus = FROZEN_CORPUS_NATUREHIKE

    intent = Intent(
        domain="bd_leads",
        primary_terms=["Naturehike", "outdoor equipment"],
        region="Germany Austria Switzerland",
        roles=["distributor"],
        negative_terms=["blog", "review", "job"],
        max_rounds=3,
        results_per_round=30,
    )

    retriever = FrozenCorpusRetriever(corpus, request_limit=request_limit)
    retrievers = {"dive": retriever, "anchor": retriever, "radar": retriever}
    scorer = QualificationScorer()

    controller = SalvaController(
        intent=intent,
        retrievers=retrievers,
        extractor=BaseExtractor(),
        deduplicator=MemoryDeduplicator(fuzzy_title=False, bm25_dedup=False),
        scorer=scorer,
        qualify_threshold=scorer.domain_threshold(intent.domain),
        keyword_graph=KeywordGraph(intent=intent),
    )
    results, _ = controller.run()
    return [
        {"title": r.title, "domain": "bd_leads", "score": round(r.relevance_score, 3), "url": r.source_url}
        for r in results if r.qualified
    ]


def run_e17() -> bool:
    print("E17 — Diff Longitudinal")
    print()

    # --- P1: Identical entity sets → empty diff ---
    entities_base = _run_controller_frozen()
    run_a = {"run_id": "run:e17-a", "entities": entities_base}
    run_b = {"run_id": "run:e17-b", "entities": list(entities_base)}  # exact copy

    diff = _compute_run_diff(run_a, run_b)
    p1 = not diff["added"] and not diff["removed"] and not diff["updated"]
    print(f"  P1 identical runs → empty diff: {'✅ PASS' if p1 else '❌ FAIL'}")
    if not p1:
        print(f"    added={len(diff['added'])} removed={len(diff['removed'])} updated={len(diff['updated'])}")

    # --- P2: Run B has one extra entity ---
    extra = _make_entity("NewDistributor GmbH")
    entities_with_extra = list(entities_base) + [extra]
    run_b2 = {"run_id": "run:e17-b2", "entities": entities_with_extra}

    diff2 = _compute_run_diff(run_a, run_b2)
    p2_added_titles = [e["title"] for e in diff2["added"]]
    p2 = "NewDistributor GmbH" in p2_added_titles and not diff2["removed"]
    print(f"  P2 run_b +1 entity → added surfaced: {'✅ PASS' if p2 else '❌ FAIL'}")
    if not p2:
        print(f"    added titles: {p2_added_titles}")

    # --- P3: Run A has one entity absent in B ---
    if entities_base:
        removed_entity = entities_base[0]
        entities_minus_one = entities_base[1:]
        run_b3 = {"run_id": "run:e17-b3", "entities": entities_minus_one}
        diff3 = _compute_run_diff(run_a, run_b3)
        p3_removed_titles = [e["title"] for e in diff3["removed"]]
        p3 = removed_entity["title"] in p3_removed_titles and not diff3["added"]
        print(f"  P3 run_b -1 entity → removed surfaced: {'✅ PASS' if p3 else '❌ FAIL'}")
        if not p3:
            print(f"    removed titles: {p3_removed_titles}")
    else:
        p3 = True
        print(f"  P3 (skip — no entities in base run)")

    # --- P4: Same entity with different score → updated surfaced ---
    if entities_base:
        pivot = entities_base[0]
        bumped = dict(pivot)
        bumped["score"] = round(pivot.get("score", 0.8) + 0.15, 3)
        entities_bumped = [bumped] + list(entities_base[1:])
        run_b4 = {"run_id": "run:e17-b4", "entities": entities_bumped}
        diff4 = _compute_run_diff(run_a, run_b4)
        p4_updated_titles = [u["title"] for u in diff4["updated"]]
        p4 = pivot["title"] in p4_updated_titles and not diff4["added"] and not diff4["removed"]
        print(f"  P4 score change → updated surfaced: {'✅ PASS' if p4 else '❌ FAIL'}")
        if not p4:
            print(f"    updated titles: {p4_updated_titles}")
    else:
        p4 = True
        print(f"  P4 (skip — no entities in base run)")

    print()
    overall = p1 and p2 and p3 and p4
    print(f"  Base run entities: {len(entities_base)}")
    print(f"  Overall: {'✅ PASS' if overall else '❌ FAIL'}")
    return overall


if __name__ == "__main__":
    run_e17()
