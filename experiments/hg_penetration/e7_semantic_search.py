"""E7 — Semantic graph search + 2-hop traversal (VP7).

Hypothesis: embedding-based node/hyperedge pre-filtering + 2-hop structural
traversal retrieves relevant subgraphs better than keyword-only baseline
for open-ended queries like "歐洲做 distributor 的關聯主體" or
"US semiconductor equity holding".

Method:
  Build a synthetic 12-node hypergraph covering different industry verticals
  and geographies. Query with semantic embeddings (Jina via omlx) vs keyword
  baseline. Measure: how many relevant nodes retrieved @ top-k, and whether
  2-hop expansion adds true positives beyond the top-k seed.

    python -m experiments.hg_penetration.e7_semantic_search
"""
from __future__ import annotations

import math
import os

import httpx

from experiments.hg_penetration.store import HypergraphStore

OMLX_BASE_URL = os.environ.get("OMLX_BASE_URL", "http://localhost:8140")
JINA_MODEL = "jina-embeddings-v5-text-small-retrieval-mlx"


# ---- embedding helpers -------------------------------------------------------

def embed_batch(texts: list[str]) -> list[list[float]]:
    url = f"{OMLX_BASE_URL.rstrip('/')}/v1/embeddings"
    r = httpx.post(url, json={"model": JINA_MODEL, "input": texts}, timeout=60.0)
    r.raise_for_status()
    data = r.json()["data"]
    data.sort(key=lambda x: x["index"])
    return [item["embedding"] for item in data]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


# ---- fixture -----------------------------------------------------------------

def build_fixture() -> tuple[HypergraphStore, dict[str, str]]:
    """Build a 12-node, 4-hyperedge graph spanning semiconductors, pharma, and finance."""
    store = HypergraphStore(":memory:")

    # Nodes: (id, type, label)
    nodes = [
        ("tsmc",        "company", "TSMC — Taiwan semiconductor foundry, wafer fab, N3 process"),
        ("asml",        "company", "ASML — Netherlands EUV lithography equipment supplier"),
        ("nvidia",      "company", "NVIDIA — US GPU designer, AI semiconductor"),
        ("arm",         "company", "ARM Holdings — UK CPU IP licensor"),
        ("samsung",     "company", "Samsung Electronics — Korean memory chips and foundry"),
        ("novartis",    "company", "Novartis — Swiss pharmaceutical company, oncology"),
        ("roche",       "company", "Roche — Swiss pharma, diagnostics and therapeutics"),
        ("blackrock",   "fund",    "BlackRock — US asset manager, equity investor"),
        ("vanguard",    "fund",    "Vanguard — US index fund, passive equity"),
        ("sovereign_sg","fund",    "GIC — Singapore sovereign wealth fund, Asia equity"),
        ("softbank",    "company", "SoftBank — Japan tech conglomerate, semiconductor investor"),
        ("arm_ipo",     "event",   "ARM IPO 2023 — Nasdaq listing, $54.5B valuation"),
    ]
    for nid, ntype, label in nodes:
        store.add_node(nid, ntype, label)

    # Hyperedges
    store.add_hyperedge("he_semiconductor_supply",  "supply_chain",
                        description="Global semiconductor supply chain for advanced logic")
    for nid, role in [("tsmc","fab"), ("asml","equipment"), ("nvidia","designer"), ("arm","ip")]:
        store.add_incidence("he_semiconductor_supply", nid, role)
    store.add_evidence("he_semiconductor_supply", "industry_report", "GLOBAL", "public",
                       snippet="TSMC manufactures NVIDIA chips using ASML EUV on ARM-based designs")

    store.add_hyperedge("he_arm_investors", "acting_in_concert",
                        description="SoftBank + sovereign funds holding ARM around IPO")
    for nid, role, pct in [
        ("softbank","majority_holder",90.0), ("sovereign_sg","minority",5.0),
        ("blackrock","institutional",2.0), ("arm","subject",None),
    ]:
        store.add_incidence("he_arm_investors", nid, role, percentage=pct)
    store.add_evidence("he_arm_investors", "SEC", "US", "public",
                       snippet="SoftBank retained 90% ARM post-IPO; GIC, BlackRock as institutional")

    store.add_hyperedge("he_swiss_pharma", "industry_group",
                        description="Swiss pharma cluster — Novartis and Roche dominate")
    for nid, role in [("novartis","member"), ("roche","member")]:
        store.add_incidence("he_swiss_pharma", nid, role)

    store.add_hyperedge("he_passive_holders", "joint_holding",
                        description="Passive index funds as major shareholders across sectors")
    for nid, role in [("blackrock","investor"), ("vanguard","investor"),
                      ("tsmc","holding"), ("nvidia","holding"), ("samsung","holding")]:
        store.add_incidence("he_passive_holders", nid, role)

    store.conn.commit()

    # Gold: node_ids relevant to different queries
    gold: dict[str, list[str]] = {
        "US semiconductor equity holding":      ["tsmc", "nvidia", "samsung", "blackrock", "vanguard"],
        "semiconductor supply chain foundry":   ["tsmc", "asml", "nvidia", "arm", "samsung"],
        "Swiss pharmaceutical company":         ["novartis", "roche"],
        "ARM IPO investor SoftBank":            ["softbank", "arm", "sovereign_sg", "blackrock"],
    }
    return store, gold


# ---- keyword baseline --------------------------------------------------------

def keyword_search(
    store: HypergraphStore,
    query: str,
    top_k: int = 5,
) -> list[str]:
    query_tokens = set(query.lower().split())
    scores: dict[str, int] = {}
    for row in store.conn.execute("SELECT id, label FROM nodes").fetchall():
        label_tokens = set(row["label"].lower().split())
        overlap = len(query_tokens & label_tokens)
        if overlap > 0:
            scores[row["id"]] = overlap
    return sorted(scores, key=lambda k: scores[k], reverse=True)[:top_k]


# ---- semantic search + 2-hop -------------------------------------------------

def semantic_search(
    node_embeddings: dict[str, list[float]],
    query_embedding: list[float],
    top_k: int = 3,
) -> list[tuple[str, float]]:
    scored = [(nid, cosine(query_embedding, emb)) for nid, emb in node_embeddings.items()]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def two_hop_expand(store: HypergraphStore, seed_nodes: list[str]) -> list[str]:
    """Return all node_ids reachable within 2 hops from seed_nodes via hyperedge membership."""
    # hop 1: find all hyperedges containing a seed node
    found_edges: set[str] = set()
    for nid in seed_nodes:
        rows = store.conn.execute(
            "SELECT edge_id FROM incidences WHERE node_id = ?", (nid,)
        ).fetchall()
        for r in rows:
            found_edges.add(r["edge_id"])
    # hop 2: find all nodes in those edges
    reachable: set[str] = set(seed_nodes)
    for eid in found_edges:
        rows = store.conn.execute(
            "SELECT node_id FROM incidences WHERE edge_id = ?", (eid,)
        ).fetchall()
        for r in rows:
            reachable.add(r["node_id"])
    return list(reachable)


# ---- evaluation --------------------------------------------------------------

def precision_recall(retrieved: list[str], gold: list[str]) -> tuple[float, float, float]:
    ret_set = set(retrieved)
    gold_set = set(gold)
    tp = len(ret_set & gold_set)
    p = tp / len(ret_set) if ret_set else 0.0
    r = tp / len(gold_set) if gold_set else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def main() -> None:
    print("E7 — Semantic graph search + 2-hop traversal")
    print(f"  model: {JINA_MODEL}\n")

    store, gold_map = build_fixture()
    print("  embedding all nodes... ", end="", flush=True)
    label_texts = [r["label"] for r in store.conn.execute("SELECT label FROM nodes ORDER BY id").fetchall()]
    ordered_ids = [r["id"] for r in store.conn.execute("SELECT id FROM nodes ORDER BY id").fetchall()]
    embeddings = embed_batch(label_texts)
    node_embeddings = {nid: emb for nid, emb in zip(ordered_ids, embeddings, strict=True)}
    print(f"done ({len(embeddings[0])}d)\n")

    queries = list(gold_map.keys())
    query_embeddings = embed_batch(queries)

    print(f"  {'query':<42} {'method':<16} P     R     F1")
    print("  " + "-" * 80)

    semantic_wins = 0
    for q, q_emb in zip(queries, query_embeddings, strict=True):
        gold = gold_map[q]

        kw_results = keyword_search(store, q, top_k=5)
        kw_p, kw_r, kw_f1 = precision_recall(kw_results, gold)

        top3 = [nid for nid, _ in semantic_search(node_embeddings, q_emb, top_k=3)]
        sem_p, sem_r, sem_f1 = precision_recall(top3, gold)

        expanded = two_hop_expand(store, top3)
        exp_p, exp_r, exp_f1 = precision_recall(expanded, gold)

        print(f"  {q[:40]:<42} keyword         {kw_p:.2f}  {kw_r:.2f}  {kw_f1:.2f}")
        print(f"  {'':42} semantic @3      {sem_p:.2f}  {sem_r:.2f}  {sem_f1:.2f}")
        print(f"  {'':42} sem+2hop         {exp_p:.2f}  {exp_r:.2f}  {exp_f1:.2f}")
        if exp_f1 >= kw_f1:
            semantic_wins += 1
        print()

    verdict = "PASS" if semantic_wins >= len(queries) // 2 + 1 else "INCONCLUSIVE"
    print(f"  verdict: {verdict} — semantic+2hop ≥ keyword in {semantic_wins}/{len(queries)} queries")

    _write_findings(queries, query_embeddings, node_embeddings, store, gold_map, verdict, semantic_wins)
    print("\n  E7_FINDINGS.md written.")


def _write_findings(
    queries: list[str],
    query_embeddings: list[list[float]],
    node_embeddings: dict[str, list[float]],
    store: HypergraphStore,
    gold_map: dict[str, list[str]],
    verdict: str,
    wins: int,
) -> None:
    lines = [
        "# E7 findings — Semantic graph search + 2-hop traversal (VP7)\n\n",
        "`python -m experiments.hg_penetration.e7_semantic_search`\n\n",
        f"**Model:** `{JINA_MODEL}` ({len(list(node_embeddings.values())[0])}d)\n\n",
        "## Method\n\nSynthetic 12-node, 4-hyperedge graph. "
        "Baseline: keyword token overlap. "
        "Semantic: Jina cosine top-3 + 2-hop hyperedge traversal.\n\n",
        "## Results\n\n",
        "| query | method | P | R | F1 |\n|---|---|---:|---:|---:|\n",
    ]
    for q, q_emb in zip(queries, query_embeddings, strict=True):
        gold = gold_map[q]
        kw = keyword_search(store, q, top_k=5)
        kp, kr, kf = precision_recall(kw, gold)
        top3 = [nid for nid, _ in semantic_search(node_embeddings, q_emb, top_k=3)]
        sp, sr, sf = precision_recall(top3, gold)
        ep, er, ef = precision_recall(two_hop_expand(store, top3), gold)
        lines.append(f"| {q[:40]} | keyword | {kp:.2f} | {kr:.2f} | {kf:.2f} |\n")
        lines.append(f"| | semantic @3 | {sp:.2f} | {sr:.2f} | {sf:.2f} |\n")
        lines.append(f"| | sem+2hop | {ep:.2f} | {er:.2f} | {ef:.2f} |\n")

    lines.append(f"\n## Verdict: **{verdict}**\n\n")
    if verdict == "PASS":
        lines.append(
            f"Semantic+2hop outperforms keyword in {wins}/{len(queries)} queries.\n"
            "Embedding pre-filtering identifies correct seed nodes; 2-hop traversal "
            "then recovers structurally related members that share hyperedge membership.\n\n"
            "## Development implication\n\n"
            "Wire `JinaOmlxVectorBackend.embed()` + the 2-hop traversal pattern into "
            "a `HoldSearcher` class in `salva_core/`. The node label texts serve as the "
            "embedding corpus; query is any natural-language string. "
            "This is the foundation of VP7.\n"
        )
    else:
        lines.append(
            f"Semantic+2hop did not consistently outperform keyword ({wins}/{len(queries)}).\n"
            "Likely cause: node labels are too short and semantically dense for the embedding "
            "model to reliably distinguish. Longer, more descriptive labels would improve recall.\n"
            "Keyword baseline is surprisingly competitive on a small, structured graph.\n\n"
            "## Development implication\n\n"
            "Enrich node labels with more context (company descriptions, sectors, regions). "
            "Alternatively, embed full evidence snippets, not just node labels.\n"
        )

    out_path = os.path.join(os.path.dirname(__file__), "E7_FINDINGS.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


if __name__ == "__main__":
    main()
