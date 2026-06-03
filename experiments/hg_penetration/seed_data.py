"""Illustrative ownership dataset + Jurisdiction Source Registry seed.

The dataset is SYNTHETIC (clearly invented names) but structured to exhibit the
n-ary phenomena that distinguish a hypergraph from a binary (FtM-style) graph:

  1. ACTING-IN-CONCERT control (一致行動人): TargetCo is controlled by a bloc of
     three parties holding 30/25/20% who act in concert (=75%). In a hypergraph
     this is ONE control fact (a hyperedge). Decomposed into binary ownership
     edges, the "they act as one control bloc" semantic is lost — a binary
     penetration sees only minority holders (max 30%) and reports NO controller.

  2. A multi-role event (acquisition with acquirer/seller/advisor) as a single
     hyperedge vs. several disconnected binary edges.

Real-company acquisition (CN gsxt / TW MOPS etc.) is the NEXT increment; this
isolates the representation variable.
"""
from __future__ import annotations

from experiments.hg_penetration.store import HypergraphStore

# (jurisdiction, fact_type) -> authoritative public sources, ranked.
# This is the seed of the self-optimising route map: source_attempts telemetry
# would later re-rank these by which actually yielded valid facts.
JURISDICTION_SOURCES: dict[tuple[str, str], list[dict[str, str]]] = {
    ("CN", "equity"): [
        {"source": "gsxt.gov.cn", "access": "web", "reliability": "high", "legal": "public_registry"},
        {"source": "qcc/tyc-style aggregator", "access": "web", "reliability": "medium", "legal": "secondary_public"},
        {"source": "news", "access": "web", "reliability": "low", "legal": "public"},
    ],
    ("TW", "equity_listed"): [
        {"source": "MOPS (mops.twse.com.tw)", "access": "api", "reliability": "high", "legal": "public_disclosure"},
    ],
    ("TW", "equity_private"): [
        {"source": "商工登記公示資料查詢 (gcis)", "access": "web", "reliability": "medium", "legal": "public_partial"},
        {"source": "TDCC 主要股東/受益人平臺", "access": "web", "reliability": "medium", "legal": "public_restricted"},
        # NOTE: full private shareholder roster is NOT public in TW (公司法 §210) — not routable.
    ],
    ("US", "equity"): [
        {"source": "SEC EDGAR", "access": "api", "reliability": "high", "legal": "public_disclosure"},
        {"source": "state registry", "access": "web", "reliability": "medium", "legal": "public_incorporation"},
    ],
    ("UK", "ownership"): [
        {"source": "Companies House PSC register", "access": "api", "reliability": "high", "legal": "public_registry"},
    ],
}


def build_store() -> HypergraphStore:
    s = HypergraphStore()

    # ---- entities (illustrative) ----
    s.add_node("targetco", "company", "TargetCo Ltd")
    s.add_node("personA", "person", "Person A")
    s.add_node("personB", "person", "Person B")
    s.add_node("personC", "person", "Person C")
    s.add_node("holdco1", "company", "HoldCo One")
    s.add_node("startupx", "company", "StartupX")
    s.add_node("founderF", "person", "Founder F")
    s.add_node("bankD", "company", "Bank D")

    # ---- (1) acting-in-concert control of TargetCo: ONE n-ary fact ----
    s.add_hyperedge("e_control_target", "control", acting_in_concert=True, basis="shareholder agreement")
    s.add_incidence("e_control_target", "targetco", role="controlled", order_index=0)
    s.add_incidence("e_control_target", "personA", role="controller", percentage=30.0, order_index=1)
    s.add_incidence("e_control_target", "personB", role="controller", percentage=25.0, order_index=2)
    s.add_incidence("e_control_target", "holdco1", role="controller", percentage=20.0, order_index=3)
    s.add_evidence("e_control_target", "MOPS (mops.twse.com.tw)", "TW", "public_disclosure",
                   snippet="董監事持股申報 + 一致行動人協議揭露")

    # ---- (2) HoldCo1 cap table: n-ary ownership (two owners), not concerted ----
    s.add_hyperedge("e_own_holdco1", "ownership")
    s.add_incidence("e_own_holdco1", "holdco1", role="asset", order_index=0)
    s.add_incidence("e_own_holdco1", "personA", role="owner", percentage=60.0, order_index=1)
    s.add_incidence("e_own_holdco1", "personC", role="owner", percentage=40.0, order_index=2)
    s.add_evidence("e_own_holdco1", "商工登記公示資料查詢 (gcis)", "TW", "public_partial",
                   snippet="股東登記資料")

    # ---- (3) multi-role acquisition event: ONE fact, four roles ----
    s.add_hyperedge("e_acq", "acquisition_event", date="2025-09")
    s.add_incidence("e_acq", "holdco1", role="acquirer", order_index=0)
    s.add_incidence("e_acq", "startupx", role="target", order_index=1)
    s.add_incidence("e_acq", "founderF", role="seller", order_index=2)
    s.add_incidence("e_acq", "bankD", role="advisor", order_index=3)
    s.add_evidence("e_acq", "news", "TW", "public", snippet="併購新聞稿")

    s.conn.commit()
    return s
