"""Canonical relation ontology — FtM-aligned, stored as data.

Each entry maps surface forms (multilingual) to a canonical relation type
with role definitions. The ontology is data, not code — extend by adding
entries to RELATIONS without changing pipeline logic.

Usage:
    from salva_core.relation_ontology import normalize_relation, ROLES

    canonical = normalize_relation("持股")  # → "ownership"
    roles = ROLES["ownership"]              # → ["owner", "owned", "intermediary"]
"""
from __future__ import annotations

# canonical_type → list of surface forms (multilingual, case-insensitive match)
_RELATION_MAP: dict[str, list[str]] = {
    "ownership": [
        "持股", "控股", "owns", "owns stake in", "holds stake in", "shareholding",
        "beneficial ownership", "ownership", "股权", "持有", "入股",
    ],
    "directorship": [
        "董事長", "董事", "chairman", "director", "board member", "ceo", "president",
        "managing director", "執行長", "總裁", "監察人",
    ],
    "investment": [
        "投資", "investment", "invested in", "invested", "stake", "equity interest",
        "venture investment",
    ],
    "acting_in_concert": [
        "一致行動人", "acting in concert", "concert group", "group filing",
        "§13(d)(3)", "section 13d3", "coordinated holding",
    ],
    "subsidiary": [
        "子公司", "subsidiary", "wholly owned subsidiary", "controlled entity",
        "affiliate", "关联公司", "關聯公司",
    ],
    "partnership": [
        "合夥", "partnership", "joint venture", "合資", "策略聯盟", "strategic alliance",
    ],
    "creditor": [
        "債權人", "creditor", "lender", "loan to", "借款", "授信",
    ],
}

# canonical_type → ordered list of participant roles (FtM-inspired)
ROLES: dict[str, list[str]] = {
    "ownership":          ["owner", "owned", "intermediary"],
    "directorship":       ["director", "company"],
    "investment":         ["investor", "investee"],
    "acting_in_concert":  ["group_lead", "group_member", "target"],
    "subsidiary":         ["parent", "subsidiary"],
    "partnership":        ["partner_a", "partner_b"],
    "creditor":           ["creditor", "debtor"],
}

# Build reverse lookup: surface_form_lower → canonical_type
_SURFACE_TO_CANONICAL: dict[str, str] = {}
for _canonical, _surfaces in _RELATION_MAP.items():
    for _s in _surfaces:
        _SURFACE_TO_CANONICAL[_s.lower()] = _canonical


def normalize_relation(surface: str) -> str | None:
    """Return canonical relation type for a surface form, or None if unknown."""
    return _SURFACE_TO_CANONICAL.get(surface.strip().lower())


def canonical_relation_types() -> list[str]:
    return list(_RELATION_MAP.keys())


def surface_forms(canonical: str) -> list[str]:
    return list(_RELATION_MAP.get(canonical, []))
