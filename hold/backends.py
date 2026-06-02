from __future__ import annotations

from pydantic import BaseModel, Field


class HoldBackendDescriptor(BaseModel):
    name: str
    kind: str
    status: str
    description: str
    strengths: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HoldBackendCatalogResponse(BaseModel):
    current_backend: str
    items: list[HoldBackendDescriptor] = Field(default_factory=list)
    total: int = 0
    notes: list[str] = Field(default_factory=list)


def build_hold_backend_catalog() -> HoldBackendCatalogResponse:
    items = [
        HoldBackendDescriptor(
            name="sqlite",
            kind="sqlite",
            status="available",
            description="Current embedded runtime store used by the Hold container.",
            strengths=[
                "Single-file deployment",
                "Simple migrations",
                "Best fit for local and agent-native runs",
            ],
            tradeoffs=[
                "Not a graph-native execution engine",
                "Graph traversal is materialized in application code",
            ],
            notes=[
                "This is the current source of truth in the repo.",
            ],
        ),
        HoldBackendDescriptor(
            name="duckdb_graph",
            kind="duckdb_graph",
            status="planned",
            description="Columnar analytics engine with graph-oriented extensions or companion relations.",
            strengths=[
                "Good for ad hoc analytics and scan-heavy workloads",
                "Potentially useful for graph-style analytical queries",
            ],
            tradeoffs=[
                "Less mature as an operational graph store than dedicated graph engines",
                "Would require a new projection and migration layer",
            ],
            notes=[
                "Good evaluation target when the workload shifts toward analytical graph queries.",
            ],
        ),
        HoldBackendDescriptor(
            name="neo4j",
            kind="neo4j",
            status="planned",
            description="Dedicated graph database backend for relation-first retrieval and graph traversal.",
            strengths=[
                "Native graph traversals",
                "Strong fit for relation-aware retrieval APIs",
            ],
            tradeoffs=[
                "Operationally heavier than embedded storage",
                "Would split the current single-file deployment model",
            ],
            notes=[
                "Best if traversal depth and graph queries become the dominant workload.",
            ],
        ),
        HoldBackendDescriptor(
            name="kuzu",
            kind="kuzu",
            status="planned",
            description="Embedded graph database backend for lightweight relation traversal.",
            strengths=[
                "Embedded and graph-native",
                "Potentially preserves a local-first deployment model",
            ],
            tradeoffs=[
                "Would still require a dedicated adapter and data projection layer",
                "Ecosystem maturity may lag the current SQLite path",
            ],
            notes=[
                "Interesting middle ground between embedded simplicity and graph-native traversal.",
            ],
        ),
    ]
    return HoldBackendCatalogResponse(
        current_backend="sqlite",
        items=items,
        total=len(items),
        notes=[
            "The current implementation is SQLite-backed and projection-first.",
            "Backend replacement should preserve the Hold snapshot and walk contracts.",
        ],
    )
