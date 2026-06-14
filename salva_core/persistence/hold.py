"""Typed n-ary incidence store, canonical entity registry, and routing memory persistence."""
from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from .db import DEFAULT_DB_PATH, get_conn

# ---------------------------------------------------------------------------
# Entity alias normalisation (for fuzzy canonical resolution)
# ---------------------------------------------------------------------------

_LEGAL_SUFFIXES = re.compile(
    r"[\s,\.]*(?:co[\.,]+\s*ltd[\.,]*|ltd|limited|inc|corp|corporation|co|gmbh|ag|sa|llc|plc|bv|nv)"
    r"[\.,]*\s*$",
    re.IGNORECASE,
)
_CJK_LEGAL_SUFFIXES = re.compile(
    r"(?:股份有限公司|有限公司|集团控股有限公司|集团控股|控股有限公司|精密工業股份有限公司|精密工業|工業|集团|控股)$"
)


def normalize_alias(text: str) -> str:
    """Canonical form for fuzzy alias matching: NFKC, lowercase, strip legal suffixes."""
    text = unicodedata.normalize("NFKC", text).strip()
    text = _CJK_LEGAL_SUFFIXES.sub("", text).strip()
    text = _LEGAL_SUFFIXES.sub("", text).strip()
    return text.lower()

# ---------------------------------------------------------------------------
# Hyperedge incidences (C1)
# ---------------------------------------------------------------------------

def upsert_hyperedge_incidence(
    hyperedge_id: str,
    node_id: str,
    role: str,
    percentage: float | None = None,
    order_index: int = 0,
    props: dict[str, Any] | None = None,
    confidence: float = 1.0,
    path: str = DEFAULT_DB_PATH,
) -> None:
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """INSERT INTO hyperedge_incidences
               (hyperedge_id, node_id, role, percentage, order_index, props_json,
                confidence, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(hyperedge_id, node_id, role) DO UPDATE SET
               percentage=excluded.percentage,
               order_index=excluded.order_index,
               props_json=excluded.props_json,
               confidence=excluded.confidence,
               updated_at=excluded.updated_at""",
            (hyperedge_id, node_id, role, percentage, order_index,
             json.dumps(props or {}, ensure_ascii=False), confidence, now, now),
        )


def list_incidences_for_edge(
    hyperedge_id: str,
    path: str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    with get_conn(path) as conn:
        rows = conn.execute(
            "SELECT node_id, role, percentage, order_index, props_json "
            "FROM hyperedge_incidences WHERE hyperedge_id = ? ORDER BY order_index",
            (hyperedge_id,),
        ).fetchall()
    return [
        {
            "node_id": r[0], "role": r[1], "percentage": r[2],
            "order_index": r[3], "props": json.loads(r[4]),
        }
        for r in rows
    ]


def list_edges_for_node(
    node_id: str,
    role: str | None = None,
    path: str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    with get_conn(path) as conn:
        if role:
            rows = conn.execute(
                "SELECT hyperedge_id, role, percentage FROM hyperedge_incidences "
                "WHERE node_id = ? AND role = ?", (node_id, role),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT hyperedge_id, role, percentage FROM hyperedge_incidences "
                "WHERE node_id = ?", (node_id,),
            ).fetchall()
    return [{"hyperedge_id": r[0], "role": r[1], "percentage": r[2]} for r in rows]


# ---------------------------------------------------------------------------
# Canonical entity registry + alias table (C2)
# ---------------------------------------------------------------------------

def upsert_canonical_entity(
    canonical_id: str,
    entity_type: str,
    primary_label: str,
    jurisdiction: str | None = None,
    props: dict[str, Any] | None = None,
    path: str = DEFAULT_DB_PATH,
) -> str:
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """INSERT INTO canonical_entities
               (canonical_id, entity_type, primary_label, jurisdiction, props_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(canonical_id) DO UPDATE SET
               primary_label=excluded.primary_label,
               jurisdiction=excluded.jurisdiction,
               props_json=excluded.props_json""",
            (canonical_id, entity_type, primary_label, jurisdiction,
             json.dumps(props or {}, ensure_ascii=False), now),
        )
    return canonical_id


def add_entity_alias(
    canonical_id: str,
    alias: str,
    script: str | None = None,
    source: str | None = None,
    path: str = DEFAULT_DB_PATH,
) -> None:
    alias_id = f"alias:{uuid.uuid4()}"
    normalized = normalize_alias(alias)
    with get_conn(path) as conn:
        # Avoid duplicate aliases for the same canonical entity
        existing = conn.execute(
            "SELECT alias_id FROM entity_aliases WHERE canonical_id = ? AND alias = ?",
            (canonical_id, alias),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO entity_aliases "
                "(alias_id, canonical_id, alias, normalized_alias, script, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (alias_id, canonical_id, alias, normalized, script, source),
            )


def resolve_canonical_id(
    alias: str,
    path: str = DEFAULT_DB_PATH,
) -> str | None:
    """Look up canonical_id for a given alias string (exact match)."""
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT canonical_id FROM entity_aliases WHERE alias = ? LIMIT 1",
            (alias,),
        ).fetchone()
    return row[0] if row else None


def resolve_entity_normalized(
    alias: str,
    path: str = DEFAULT_DB_PATH,
) -> str | None:
    """Resolve alias to canonical_id: exact match, then normalized index, then GLEIF.

    Handles legal-suffix variation (TSMC Ltd → TSMC) and NFKC form differences.
    Uses the normalized_alias index (added in L1-A) — O(log N) instead of O(N) scan.
    Falls back to full-scan for rows written before L1-A migration (NULL normalized_alias).
    Returns None if no match found.
    """
    exact = resolve_canonical_id(alias, path=path)
    if exact:
        return exact

    normalized = normalize_alias(alias)
    with get_conn(path) as conn:
        # Fast path: normalized_alias index (populated for all new aliases)
        row = conn.execute(
            "SELECT canonical_id FROM entity_aliases WHERE normalized_alias = ? LIMIT 1",
            (normalized,),
        ).fetchone()
        if row:
            return row[0]

        # Slow path: backfill scan for pre-L1-A rows with NULL normalized_alias
        legacy_rows = conn.execute(
            "SELECT canonical_id, alias FROM entity_aliases WHERE normalized_alias IS NULL",
        ).fetchall()
    for canonical_id, stored_alias in legacy_rows:
        if normalize_alias(stored_alias) == normalized:
            return canonical_id

    # External fallback: GLEIF legal entity database (2.5M+ entities, free)
    import os as _os
    if _os.getenv("GLEIF_IN_RESOLUTION", "true").lower() not in ("0", "false", "no"):
        try:
            from salva_core.resolvers.gleif import gleif_resolve
            gleif_name = gleif_resolve(alias)
            if gleif_name:
                return gleif_name
        except Exception:
            pass

    return None


def get_aliases_for_canonical(
    canonical_id: str,
    path: str = DEFAULT_DB_PATH,
) -> list[dict[str, str | None]]:
    with get_conn(path) as conn:
        rows = conn.execute(
            "SELECT alias, script, source FROM entity_aliases WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchall()
    return [{"alias": r[0], "script": r[1], "source": r[2]} for r in rows]


# ---------------------------------------------------------------------------
# Routing memory (C4)
# ---------------------------------------------------------------------------

def record_source_attempt(
    source_url: str,
    succeeded: bool,
    path: str = DEFAULT_DB_PATH,
) -> None:
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        existing = conn.execute(
            "SELECT success_count, failure_count, authority_boost FROM routing_memory "
            "WHERE source_url = ?", (source_url,),
        ).fetchone()
        if existing:
            sc, fc, boost = existing
            if succeeded:
                new_sc = sc + 1
                new_fc = fc
                new_boost = min(1.0, boost + 0.05)
                conn.execute(
                    "UPDATE routing_memory SET success_count=?, failure_count=?, "
                    "authority_boost=?, last_success_at=?, updated_at=? WHERE source_url=?",
                    (new_sc, new_fc, new_boost, now, now, source_url),
                )
            else:
                new_sc = sc
                new_fc = fc + 1
                new_boost = max(-0.5, boost - 0.1)
                conn.execute(
                    "UPDATE routing_memory SET success_count=?, failure_count=?, "
                    "authority_boost=?, last_failure_at=?, updated_at=? WHERE source_url=?",
                    (new_sc, new_fc, new_boost, now, now, source_url),
                )
        else:
            if succeeded:
                conn.execute(
                    "INSERT INTO routing_memory "
                    "(source_url, success_count, failure_count, authority_boost, "
                    "last_success_at, updated_at) VALUES (?, 1, 0, 0.05, ?, ?)",
                    (source_url, now, now),
                )
            else:
                conn.execute(
                    "INSERT INTO routing_memory "
                    "(source_url, success_count, failure_count, authority_boost, "
                    "last_failure_at, updated_at) VALUES (?, 0, 1, -0.1, ?, ?)",
                    (source_url, now, now),
                )


def get_routing_boost(
    source_url: str,
    path: str = DEFAULT_DB_PATH,
) -> float:
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT authority_boost FROM routing_memory WHERE source_url = ?",
            (source_url,),
        ).fetchone()
    return float(row[0]) if row else 0.0


def list_routing_memory(
    top_k: int = 20,
    path: str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    with get_conn(path) as conn:
        rows = conn.execute(
            "SELECT source_url, success_count, failure_count, authority_boost, "
            "last_success_at, last_failure_at, updated_at "
            "FROM routing_memory ORDER BY authority_boost DESC LIMIT ?",
            (top_k,),
        ).fetchall()
    return [
        {
            "source_url": r[0], "success_count": r[1], "failure_count": r[2],
            "authority_boost": r[3], "last_success_at": r[4],
            "last_failure_at": r[5], "updated_at": r[6],
        }
        for r in rows
    ]


def record_probe_result(
    source_url: str,
    result_count: int,
    latency_ms: float,
    path: str = DEFAULT_DB_PATH,
) -> None:
    """Persist a live probe observation alongside the success/failure signal.

    Writes avg_latency_ms and last_probe_at (L1-A columns). Delegates the
    authority_boost update to record_source_attempt so the boost logic stays
    in one place.
    """
    now = datetime.now(UTC).isoformat()
    record_source_attempt(source_url, result_count > 0, path=path)
    with get_conn(path) as conn:
        # avg_latency_ms: rolling average — (old * n + new) / (n + 1)
        row = conn.execute(
            "SELECT success_count, failure_count, avg_latency_ms FROM routing_memory "
            "WHERE source_url = ?", (source_url,)
        ).fetchone()
        if row:
            sc, fc, old_avg = row
            n = sc + fc
            new_avg = ((old_avg or 0.0) * (n - 1) + latency_ms) / n if n > 0 else latency_ms
            conn.execute(
                "UPDATE routing_memory SET avg_latency_ms=?, last_probe_at=?, updated_at=? "
                "WHERE source_url=?",
                (new_avg, now, now, source_url),
            )


def backfill_normalized_aliases(path: str = DEFAULT_DB_PATH) -> int:
    """One-time migration: populate normalized_alias for pre-L1-A rows.

    Returns the number of rows updated. Safe to call repeatedly — only
    touches rows where normalized_alias IS NULL.
    """
    with get_conn(path) as conn:
        rows = conn.execute(
            "SELECT alias_id, alias FROM entity_aliases WHERE normalized_alias IS NULL"
        ).fetchall()
        for alias_id, alias in rows:
            conn.execute(
                "UPDATE entity_aliases SET normalized_alias=? WHERE alias_id=?",
                (normalize_alias(alias), alias_id),
            )
    return len(rows)
