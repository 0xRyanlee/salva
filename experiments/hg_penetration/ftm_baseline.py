"""FtM-style binary baseline.

FollowTheMoney models relationships as reified-but-BINARY entities (an Ownership
has owner + asset + percentage). To represent the same facts we decompose each
n-ary hyperedge into binary edges. Two things are lost in the decomposition:

  - the `acting_in_concert` property (it belongs to the GROUP, not to any single
    owner→asset edge), so a controlling bloc becomes indistinguishable from
    unrelated minority holders;
  - the coherence of a multi-role event (acquirer/seller/advisor) — it shatters
    into disconnected binary links.
"""
from __future__ import annotations

from dataclasses import dataclass

from experiments.hg_penetration.penetrate import CONTROL_THRESHOLD
from experiments.hg_penetration.store import HypergraphStore


@dataclass
class BinaryEdge:
    owner: str
    asset: str
    percentage: float | None


def to_binary_edges(store: HypergraphStore) -> tuple[list[BinaryEdge], list[str]]:
    """Decompose hyperedges into binary ownership edges. Returns (edges, lost_notes)."""
    edges: list[BinaryEdge] = []
    lost: list[str] = []
    rows = store.conn.execute("SELECT id, type FROM hyperedges").fetchall()
    for r in rows:
        edge_id, etype = r["id"], r["type"]
        incs = store.incidences(edge_id)
        if etype in ("control", "ownership"):
            held = next((i for i in incs if i.role in ("controlled", "asset")), None)
            if held is None:
                continue
            if store.edge_props(edge_id).get("acting_in_concert"):
                lost.append(f"{edge_id}: 'acting_in_concert' bloc semantic dropped (no home on a binary edge)")
            for inc in incs:
                if inc.role in ("controller", "owner"):
                    edges.append(BinaryEdge(inc.node_id, held.node_id, inc.percentage))
        else:
            # n-ary event: cannot be faithfully represented; roles collapse.
            roles = ", ".join(f"{i.role}={store.label(i.node_id)}" for i in incs)
            lost.append(f"{edge_id} ({etype}): multi-role event shattered ({roles})")
    return edges, lost


def analyze_control_binary(edges: list[BinaryEdge], target: str) -> tuple[str, list[tuple[str, float]]]:
    direct = [(e.owner, e.percentage or 0.0) for e in edges if e.asset == target]
    direct.sort(key=lambda x: -x[1])
    for owner, pct in direct:
        if pct > CONTROL_THRESHOLD:
            return "majority_holder", [(owner, pct)]
    return "none", direct


def effective_ownership_binary(
    edges: list[BinaryEdge], target: str, fraction: float = 1.0,
    acc: dict[str, float] | None = None, visited: set[str] | None = None,
    is_person=lambda n: n.startswith("person") or n == "founderF",
) -> dict[str, float]:
    acc = {} if acc is None else acc
    visited = set() if visited is None else visited
    if target in visited:
        return acc
    visited = visited | {target}
    for e in edges:
        if e.asset != target or e.percentage is None:
            continue
        share = fraction * (e.percentage / 100.0)
        if is_person(e.owner):
            acc[e.owner] = acc.get(e.owner, 0.0) + share * 100.0
        else:
            effective_ownership_binary(edges, e.owner, share, acc, visited, is_person)
    return acc
