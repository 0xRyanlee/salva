"""Run the hypergraph-vs-binary penetration comparison.

    python -m experiments.hg_penetration.run
"""
from __future__ import annotations

from experiments.hg_penetration.ftm_baseline import (
    analyze_control_binary,
    effective_ownership_binary,
    to_binary_edges,
)
from experiments.hg_penetration.penetrate import analyze_control, effective_ownership
from experiments.hg_penetration.seed_data import JURISDICTION_SOURCES, build_store

TARGET = "targetco"


def _fmt(store, owners: dict[str, float]) -> str:
    return ", ".join(f"{store.label(n)} {p:.0f}%" for n, p in sorted(owners.items(), key=lambda x: -x[1]))


def main() -> None:
    store = build_store()

    print("=" * 70)
    print("Penetration target:", store.label(TARGET))
    print("=" * 70)

    # ---- Hypergraph (n-ary, concert-aware) ----
    cf = analyze_control(store, TARGET)
    hg_eff = effective_ownership(store, TARGET)
    print("\n[HYPERGRAPH]  n-ary, role-typed, concert-aware")
    if cf.controller_kind == "concert_bloc":
        members = ", ".join(f"{store.label(m)} {p:.0f}%" for m, p in cf.bloc_members)
        print(f"  → CONTROLLED by acting-in-concert bloc = {cf.bloc_pct:.0f}%  [{members}]")
        print(f"    basis: {cf.basis}")
    elif cf.controller_kind == "majority_holder":
        m, p = cf.bloc_members[0]
        print(f"  → CONTROLLED by {store.label(m)} ({p:.0f}%)")
    else:
        print("  → no controller detected")
    print(f"  effective ultimate ownership: {_fmt(store, hg_eff)}")

    # ---- FtM-style binary baseline ----
    edges, lost = to_binary_edges(store)
    kind, direct = analyze_control_binary(edges, TARGET)
    bin_eff = effective_ownership_binary(edges, TARGET)
    print("\n[FtM BINARY]  reified-but-binary ownership edges")
    if kind == "majority_holder":
        m, p = direct[0]
        print(f"  → CONTROLLED by {store.label(m)} ({p:.0f}%)")
    else:
        top = ", ".join(f"{store.label(m)} {p:.0f}%" for m, p in direct)
        print(f"  → NO controlling shareholder (largest minority: {top})")
    print(f"  effective ultimate ownership: {_fmt(store, bin_eff)}")
    print("  lost in decomposition:")
    for note in lost:
        print(f"    - {note}")

    # ---- verdict ----
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    same_eff = {k: round(v) for k, v in hg_eff.items()} == {k: round(v) for k, v in bin_eff.items()}
    print(f"  effective-ownership numbers identical: {same_eff}  "
          "(layering works in both — NOT the differentiator)")
    print(f"  control conclusion differs: "
          f"hypergraph='{cf.controller_kind}' vs binary='{kind}'")
    if cf.controller_kind == "concert_bloc" and kind == "none":
        print("  → DEMONSTRATED: the n-ary 'acting-in-concert' control fact is preserved")
        print("    as one hyperedge but is INVISIBLE after binary decomposition.")
        print("    Binary penetration wrongly reports 'no controller'.")

    # ---- jurisdiction source routing (the self-optimisation substrate) ----
    print("\n" + "=" * 70)
    print("JURISDICTION SOURCE REGISTRY (seed — would learn from source_attempts)")
    print("=" * 70)
    for (juris, fact), sources in JURISDICTION_SOURCES.items():
        s0 = sources[0]
        print(f"  ({juris}, {fact}) → {s0['source']}  [{s0['reliability']}/{s0['legal']}]"
              + (f"  +{len(sources)-1} more" if len(sources) > 1 else ""))


if __name__ == "__main__":
    main()
