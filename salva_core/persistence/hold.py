"""Typed n-ary incidence store, canonical entity registry, and routing memory persistence."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from .db import DEFAULT_DB_PATH, get_conn

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
    path: str = DEFAULT_DB_PATH,
) -> None:
    with get_conn(path) as conn:
        conn.execute(
            """INSERT INTO hyperedge_incidences
               (hyperedge_id, node_id, role, percentage, order_index, props_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(hyperedge_id, node_id, role) DO UPDATE SET
               percentage=excluded.percentage,
               order_index=excluded.order_index,
               props_json=excluded.props_json""",
            (hyperedge_id, node_id, role, percentage, order_index,
             json.dumps(props or {}, ensure_ascii=False)),
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
    with get_conn(path) as conn:
        # Avoid duplicate aliases for the same canonical entity
        existing = conn.execute(
            "SELECT alias_id FROM entity_aliases WHERE canonical_id = ? AND alias = ?",
            (canonical_id, alias),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO entity_aliases (alias_id, canonical_id, alias, script, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (alias_id, canonical_id, alias, script, source),
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
