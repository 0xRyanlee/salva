"""Ownership/control penetration over the n-ary hypergraph.

The hypergraph keeps "acting in concert" as a property of a single control
hyperedge, so penetration can recognise a *controlling bloc* even when no single
member holds a majority. It also layers effective ownership through corporate
holders (percentage products).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from experiments.hg_penetration.store import HypergraphStore

CONTROL_THRESHOLD = 50.0


@dataclass
class ControlFinding:
    target: str
    controller_kind: str          # "concert_bloc" | "majority_holder" | "none"
    bloc_members: list[tuple[str, float]] = field(default_factory=list)
    bloc_pct: float = 0.0
    basis: str | None = None


def _direct_holders(store: HypergraphStore, target: str) -> list[tuple[str, str, bool, str]]:
    """Return (edge_id, edge_type, acting_in_concert, ...) facts where `target` is held.

    Yields (holder_id, percentage, concert, edge_id) tuples flattened.
    """
    out: list[tuple[str, float, bool, str]] = []
    for held_role, holder_role in (("controlled", "controller"), ("asset", "owner")):
        for edge_id, _etype in store.edges_with_node_in_role(target, held_role):
            concert = bool(store.edge_props(edge_id).get("acting_in_concert"))
            for inc in store.incidences(edge_id):
                if inc.role == holder_role and inc.percentage is not None:
                    out.append((inc.node_id, inc.percentage, concert, edge_id))
    return out


def analyze_control(store: HypergraphStore, target: str) -> ControlFinding:
    holders = _direct_holders(store, target)
    if not holders:
        return ControlFinding(target, "none")

    # group concert holders sharing a control edge into a single bloc
    concert_edges: dict[str, list[tuple[str, float]]] = {}
    singles: list[tuple[str, float]] = []
    for holder, pct, concert, edge_id in holders:
        if concert:
            concert_edges.setdefault(edge_id, []).append((holder, pct))
        else:
            singles.append((holder, pct))

    for edge_id, members in concert_edges.items():
        total = sum(p for _, p in members)
        if total > CONTROL_THRESHOLD:
            basis = store.edge_props(edge_id).get("basis")
            return ControlFinding(target, "concert_bloc", members, total, basis)

    for holder, pct in singles:
        if pct > CONTROL_THRESHOLD:
            return ControlFinding(target, "majority_holder", [(holder, pct)], pct)

    return ControlFinding(target, "none")


def effective_ownership(
    store: HypergraphStore, target: str, fraction: float = 1.0,
    acc: dict[str, float] | None = None, visited: set[str] | None = None,
) -> dict[str, float]:
    """Effective ultimate-person ownership %, layering through corporate holders."""
    acc = {} if acc is None else acc
    visited = set() if visited is None else visited
    if target in visited:
        return acc
    visited = visited | {target}

    for holder, pct, _concert, _edge in _direct_holders(store, target):
        share = fraction * (pct / 100.0)
        node = store.node(holder)
        if node is not None and node["type"] == "person":
            acc[holder] = acc.get(holder, 0.0) + share * 100.0
        else:
            effective_ownership(store, holder, share, acc, visited)
    return acc
