"""Typed n-ary incidence hypergraph store on SQLite.

This is the canonical hypergraph representation: a hyperedge connects N nodes,
each via an incidence carrying a ROLE and props (e.g. percentage). Mathematically
the incidence table IS the hypergraph (incidence structure) — not a property
graph pretending to be one.

Schema:
  nodes(id, type, label, props)
  hyperedges(id, type, props)            -- props may hold {"acting_in_concert": true, "date": ...}
  incidences(edge_id, node_id, role, percentage, order_index, props)
  evidence(edge_id, source, jurisdiction, legal_availability, url, snippet)

Evidence binding is first-class: every hyperedge can carry the public source it
came from, plus its legal_availability (so the pipeline only routes to lawful,
public sources by design).
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class Incidence:
    node_id: str
    role: str
    percentage: float | None
    order_index: int


_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    label TEXT NOT NULL,
    props TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS hyperedges (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    props TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS incidences (
    edge_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    role TEXT NOT NULL,
    percentage REAL,
    order_index INTEGER NOT NULL DEFAULT 0,
    props TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (edge_id, node_id, role)
);
CREATE TABLE IF NOT EXISTS evidence (
    edge_id TEXT NOT NULL,
    source TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    legal_availability TEXT NOT NULL,
    url TEXT,
    snippet TEXT
);
CREATE INDEX IF NOT EXISTS idx_inc_node ON incidences(node_id);
CREATE INDEX IF NOT EXISTS idx_inc_edge ON incidences(edge_id);
"""


class HypergraphStore:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)

    def add_node(self, node_id: str, type: str, label: str, **props: Any) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO nodes (id, type, label, props) VALUES (?, ?, ?, ?)",
            (node_id, type, label, json.dumps(props, ensure_ascii=False)),
        )

    def add_hyperedge(self, edge_id: str, type: str, **props: Any) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO hyperedges (id, type, props) VALUES (?, ?, ?)",
            (edge_id, type, json.dumps(props, ensure_ascii=False)),
        )

    def add_incidence(
        self, edge_id: str, node_id: str, role: str,
        percentage: float | None = None, order_index: int = 0, **props: Any,
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO incidences "
            "(edge_id, node_id, role, percentage, order_index, props) VALUES (?, ?, ?, ?, ?, ?)",
            (edge_id, node_id, role, percentage, order_index, json.dumps(props, ensure_ascii=False)),
        )

    def add_evidence(
        self, edge_id: str, source: str, jurisdiction: str,
        legal_availability: str, url: str | None = None, snippet: str | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO evidence (edge_id, source, jurisdiction, legal_availability, url, snippet) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (edge_id, source, jurisdiction, legal_availability, url, snippet),
        )

    # ---- reads ----
    def node(self, node_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()

    def label(self, node_id: str) -> str:
        row = self.node(node_id)
        return row["label"] if row else node_id

    def edge_props(self, edge_id: str) -> dict[str, Any]:
        row = self.conn.execute("SELECT props FROM hyperedges WHERE id = ?", (edge_id,)).fetchone()
        return json.loads(row["props"]) if row else {}

    def incidences(self, edge_id: str) -> list[Incidence]:
        rows = self.conn.execute(
            "SELECT node_id, role, percentage, order_index FROM incidences "
            "WHERE edge_id = ? ORDER BY order_index", (edge_id,),
        ).fetchall()
        return [Incidence(r["node_id"], r["role"], r["percentage"], r["order_index"]) for r in rows]

    def edges_with_node_in_role(self, node_id: str, role: str) -> list[tuple[str, str]]:
        """Return (edge_id, edge_type) where node participates in the given role."""
        rows = self.conn.execute(
            "SELECT i.edge_id, h.type FROM incidences i JOIN hyperedges h ON h.id = i.edge_id "
            "WHERE i.node_id = ? AND i.role = ?", (node_id, role),
        ).fetchall()
        return [(r["edge_id"], r["type"]) for r in rows]

    def evidence_for(self, edge_id: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM evidence WHERE edge_id = ?", (edge_id,)).fetchall()
