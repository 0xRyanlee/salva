"""E22 — Memory Longitudinal (VP-longitudinal).

Hypothesis: Running the same discovery intent N times with memory persistence
enabled shows increasing memory_seeds_used across runs, confirming the
compounding mechanism is real (not hollow).

Method:
- Reuse frozen corpus from E15 (no live DDG variance, reproducible)
- Run N=5 iterations on bd_leads/Naturehike intent
- After each run, persist query family records to a temporary SQLite
- Before each subsequent run, seed the graph from memory (read_scope="global")
- Track per-run: seeds_injected, qualified_count, precision, recall, node_count

Pass criteria (VP-longitudinal):
  P1. memory_seeds_used increases at least once across 5 runs (compounding active)
  P2. Recall does not drop below E15 baseline (R ≥ 0.50) in any run after run 1
  P3. Node count in graph grows across runs (memory adds new discovery angles)

Run:
    python -m experiments.computex_2026.e22_memory_longitudinal
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Re-use E15 frozen corpus and helpers
# ---------------------------------------------------------------------------

from experiments.computex_2026.e15_budget_ab import (
    FROZEN_CORPUS_NATUREHIKE,
    GROUND_TRUTH_NATUREHIKE,
    FrozenCorpusRetriever,
    _name_match,
)

# ---------------------------------------------------------------------------
# Per-run result
# ---------------------------------------------------------------------------

@dataclass
class LongitudinalRunResult:
    run_num: int
    seeds_injected: int
    graph_node_count: int
    qualified_count: int
    entities_found: list[str] = field(default_factory=list)
    true_positives: list[str] = field(default_factory=list)
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    requests_used: int = 0


# ---------------------------------------------------------------------------
# Memory persistence helpers
# ---------------------------------------------------------------------------

def _save_query_families_to_db(
    db_path: str,
    domain: str,
    objective: str,
    telemetry_records,
    run_id: str,
) -> int:
    """
    Persist query family rows from a completed controller run to the SQLite DB.
    Uses the same schema as persist_discovery_run() but without the full request chain.
    """
    from salva_core.persistence.db import get_conn
    now = datetime.now(UTC).isoformat()
    saved = 0
    with get_conn(db_path) as conn:
        for record in telemetry_records:
            if record.results_qualified == 0:
                continue
            memory_id = f"query_family:{uuid.uuid4()}"
            metadata = record.metadata or {}
            source_nodes = list(metadata.get("source_nodes", []))
            content_nodes = list(metadata.get("content_terms", []))
            success_score = round(
                record.results_qualified / max(record.results_total, 1), 4
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO query_family_memory (
                    memory_id, run_id, campaign_id, continuation_id, memory_status,
                    promoted_at, domain, objective, output_profile, round_num, strategy,
                    query, query_signature, source_nodes_json, content_weights_json,
                    source_hints_json, notes_json, raw_total, qualified_total,
                    avg_score, success_score, created_at, content_nodes_json
                ) VALUES (?, ?, NULL, NULL, 'quarantine', NULL, ?, ?, 'company_profile',
                          ?, ?, ?, ?, ?, '{}', '[]', '[]', ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id, run_id, domain, objective,
                    record.round_num, record.strategy,
                    record.query,
                    f"{record.strategy}:{hash(record.query) & 0xFFFFFF:06x}",
                    json.dumps(source_nodes, ensure_ascii=False),
                    record.results_total, record.results_qualified,
                    record.avg_score, success_score, now,
                    json.dumps(content_nodes, ensure_ascii=False),
                ),
            )
            saved += 1
    return saved


def _read_seeds_from_db(db_path: str, domain: str, objective: str) -> list[dict]:
    from salva_core.persistence import read_top_query_families_for_seeding
    return read_top_query_families_for_seeding(
        domain=domain,
        objective=objective,
        campaign_id=None,
        memory_status=None,
        top_k=10,
        min_success_score=0.1,
        path=db_path,
    )


# ---------------------------------------------------------------------------
# Single longitudinal run
# ---------------------------------------------------------------------------

def run_one(
    run_num: int,
    db_path: str,
    request_limit: int = 12,
) -> LongitudinalRunResult:
    from core.controller import SalvaController
    from core.keyword_graph import KeywordGraph
    from core.types import Intent
    from processing.dedup import MemoryDeduplicator
    from processing.extractor import BaseExtractor
    from processing.scorer import QualificationScorer

    intent = Intent(
        domain="bd_leads",
        primary_terms=["Naturehike", "outdoor equipment"],
        region="Germany Austria Switzerland",
        roles=["distributor"],
        negative_terms=["blog", "review", "job"],
        max_rounds=3,
        results_per_round=30,
    )

    scorer = QualificationScorer()
    qualify_threshold = scorer.domain_threshold(intent.domain)

    graph = KeywordGraph(intent=intent)

    # Inject memory seeds from prior runs
    seeds_injected = 0
    if run_num > 1:
        prior_records = _read_seeds_from_db(db_path, intent.domain, "find_leads")
        if prior_records:
            def memory_reader(d: str, k: int) -> list[dict]:
                return prior_records[:k]
            seeds_injected = graph.seed_from_memory(memory_reader=memory_reader, top_k=10)

    # Measure node count post-seed, pre-controller (controller may prune nodes)
    node_count = len(graph.nodes)

    retriever = FrozenCorpusRetriever(FROZEN_CORPUS_NATUREHIKE, request_limit=request_limit)
    retrievers = {"dive": retriever, "anchor": retriever, "radar": retriever}

    controller = SalvaController(
        intent=intent,
        retrievers=retrievers,
        extractor=BaseExtractor(),
        deduplicator=MemoryDeduplicator(fuzzy_title=False, bm25_dedup=False),
        scorer=scorer,
        qualify_threshold=qualify_threshold,
        keyword_graph=graph,
    )
    results, summary = controller.run()

    found_names = [r.title for r in results if r.qualified]
    tps = [n for n in found_names if _name_match(n, GROUND_TRUTH_NATUREHIKE)]
    p = len(tps) / len(found_names) if found_names else 0.0
    r = len(tps) / len(GROUND_TRUTH_NATUREHIKE) if GROUND_TRUTH_NATUREHIKE else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0

    # Persist telemetry to memory DB for subsequent runs
    # summary.rounds[i].telemetry — each RoundSummary carries its query-level telemetry
    run_id = f"run:e22-{uuid.uuid4()}"
    all_telemetry = [t for rs in summary.rounds for t in rs.telemetry]
    _save_query_families_to_db(db_path, intent.domain, "find_leads", all_telemetry, run_id)

    return LongitudinalRunResult(
        run_num=run_num,
        seeds_injected=seeds_injected,
        graph_node_count=node_count,
        qualified_count=len(found_names),
        entities_found=found_names,
        true_positives=tps,
        precision=round(p, 3),
        recall=round(r, 3),
        f1=round(f1, 3),
        requests_used=retriever.request_count,
    )


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run_e22(n_runs: int = 5) -> list[LongitudinalRunResult]:
    from salva_core.persistence.db import get_conn
    results_list = []

    # Temporary SQLite DB for this experiment
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    # Initialise schema
    with get_conn(db_path):
        pass

    print(f"E22 — Memory Longitudinal ({n_runs} runs, Naturehike bd_leads frozen corpus)")
    print(f"  DB: {db_path}")
    print(f"  Ground truth: {len(GROUND_TRUTH_NATUREHIKE)} entities | Corpus: {len(FROZEN_CORPUS_NATUREHIKE)} items")
    print()

    for i in range(1, n_runs + 1):
        result = run_one(run_num=i, db_path=db_path)
        results_list.append(result)
        print(
            f"  Run {i}: seeds={result.seeds_injected:>2}  nodes={result.graph_node_count:>2}  "
            f"qualified={result.qualified_count:>2}  "
            f"P={result.precision:.3f}  R={result.recall:.3f}  F1={result.f1:.3f}  "
            f"req={result.requests_used}"
        )

    print()
    # Evaluate pass criteria
    seed_counts = [r.seeds_injected for r in results_list]
    node_counts = [r.graph_node_count for r in results_list]
    recalls = [r.recall for r in results_list]

    p1 = any(seed_counts[i] > seed_counts[i - 1] for i in range(1, len(seed_counts)))
    p2 = all(r >= 0.50 for r in recalls[1:]) if len(recalls) > 1 else True
    p3 = max(node_counts) > min(node_counts)

    print(f"  P1 seeds grow across runs: {'✅ PASS' if p1 else '⚠️  FAIL'} — {seed_counts}")
    print(f"  P2 recall ≥ 0.50 (runs 2–{n_runs}): {'✅ PASS' if p2 else '⚠️  FAIL'} — {[round(r, 3) for r in recalls]}")
    print(f"  P3 node count grows: {'✅ PASS' if p3 else '⚠️  FAIL'} — {node_counts}")

    overall = "PASS" if (p1 and p2) else "FAIL (see above)"
    print(f"\n  Overall: {'✅' if p1 and p2 else '⚠️'} {overall}")

    # Clean up temp DB
    try:
        os.unlink(db_path)
    except OSError:
        pass

    return results_list


if __name__ == "__main__":
    run_e22()
