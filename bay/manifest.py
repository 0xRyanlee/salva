from __future__ import annotations

from pydantic import BaseModel, Field

from hold.schema import HoldSchema, build_hold_schema


class BayCapability(BaseModel):
    name: str
    method: str
    path: str
    description: str
    response_model: str | None = None


class BayManifest(BaseModel):
    name: str = "bay"
    version: str = "0.1.0"
    status: str = "draft"
    description: str = (
        "Self-describing access surface for Hold. Exposes schema, capability, "
        "and projection boundaries to agents and callers."
    )
    hold: HoldSchema = Field(default_factory=build_hold_schema)
    capabilities: list[BayCapability] = Field(default_factory=list)
    exposed_views: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def build_bay_manifest() -> BayManifest:
    return BayManifest(
        capabilities=[
            BayCapability(
                name="bay_manifest",
                method="GET",
                path="/v1/bay",
                description="Expose the self-describing runtime surface.",
                response_model="BayManifest",
            ),
            BayCapability(
                name="hold_schema",
                method="GET",
                path="/v1/hold/schema",
                description="Expose the logical hypergraph container contract.",
                response_model="HoldSchema",
            ),
            BayCapability(
                name="hold_entity_schema",
                method="GET",
                path="/v1/hold/schema/entities",
                description="Expose the canonical entity schema catalog.",
                response_model="HoldEntitySchemasResponse",
            ),
            BayCapability(
                name="hold_relation_schema",
                method="GET",
                path="/v1/hold/schema/relations",
                description="Expose the canonical relation schema catalog.",
                response_model="HoldRelationSchemasResponse",
            ),
            BayCapability(
                name="output_profiles",
                method="GET",
                path="/v1/output-profiles",
                description="Expose the canonical output transform catalog.",
                response_model="OutputTransformCatalog",
            ),
            BayCapability(
                name="presets",
                method="GET",
                path="/v1/presets",
                description="Expose reusable experience/preset profiles for different callers and projects.",
                response_model="PresetCatalogResponse",
            ),
            BayCapability(
                name="preset",
                method="GET",
                path="/v1/presets/{preset_name}",
                description="Resolve one preset profile by name.",
                response_model="PresetProfile",
            ),
            BayCapability(
                name="routes",
                method="GET",
                path="/v1/routes",
                description="Expose the discovery route index for agents and callers.",
                response_model="RouteCatalogResponse",
            ),
            BayCapability(
                name="topology_probe",
                method="POST",
                path="/v1/topology/probe",
                description="Probe the retrieval shape and emit a route plan.",
                response_model="TopologyProbeResponse",
            ),
            BayCapability(
                name="planner",
                method="POST",
                path="/v1/planner",
                description="Generate a research plan with clarification and round budgeting.",
                response_model="PlannerResponse",
            ),
            BayCapability(
                name="route",
                method="GET",
                path="/v1/routes/{route_name}",
                description="Resolve one route entry by name or experience profile.",
                response_model="RouteCatalogEntry",
            ),
            BayCapability(
                name="provider_catalog",
                method="GET",
                path="/v1/providers/catalog",
                description="Expose the full provider interface catalog across search, LLM, vector, relational, and OSINT planes.",
                response_model="ProviderCatalogResponse",
            ),
            BayCapability(
                name="hold_views",
                method="GET",
                path="/v1/hold/views",
                description="List the readable projections available from Hold.",
                response_model="HoldViewsResponse",
            ),
            BayCapability(
                name="hold_migrations",
                method="GET",
                path="/v1/hold/migrations",
                description="List the recorded Hold schema versions and migration state.",
                response_model="HoldMigrationsResponse",
            ),
            BayCapability(
                name="hold_storage",
                method="GET",
                path="/v1/hold/storage",
                description="Expose the logical storage and index catalog for Hold.",
                response_model="HoldStorageCatalog",
            ),
            BayCapability(
                name="hold_backends",
                method="GET",
                path="/v1/hold/backends",
                description="Expose the Hold backend evaluation catalog.",
                response_model="HoldBackendCatalogResponse",
            ),
            BayCapability(
                name="relations",
                method="GET",
                path="/v1/relations",
                description="Query versioned typed relations persisted by Hold.",
                response_model="RelationsResponse",
            ),
            BayCapability(
                name="semantic_query_families",
                method="GET",
                path="/v1/semantic/query-families",
                description="Query similar successful query families through the semantic vector plane.",
                response_model="SemanticQueryFamilySearchResponse",
            ),
            BayCapability(
                name="semantic_indexes",
                method="GET",
                path="/v1/semantic/indexes",
                description="Expose the available semantic memory index backends.",
                response_model="SemanticVectorCatalogResponse",
            ),
            BayCapability(
                name="semantic_benchmark",
                method="POST",
                path="/v1/semantic/benchmark",
                description="Benchmark semantic backend behavior on sampled query-family records.",
                response_model="SemanticBackendBenchmarkResponse",
            ),
            BayCapability(
                name="usage",
                method="GET",
                path="/v1/usage",
                description="Aggregate tenant-aware usage telemetry from runs and jobs.",
                response_model="UsageTelemetryResponse",
            ),
            BayCapability(
                name="quota",
                method="GET",
                path="/v1/quota",
                description="Evaluate tenant quota and rate-limit status.",
                response_model="TenantQuotaResponse",
            ),
            BayCapability(
                name="hold_view",
                method="GET",
                path="/v1/hold/views/{view_name}",
                description="Project a run into a specific Hold view.",
                response_model="HoldProjectionResponse",
            ),
            BayCapability(
                name="hold_walk",
                method="GET",
                path="/v1/hold/walk",
                description="Walk the Hold graph from one or more seed entities.",
                response_model="HoldGraphWalkResponse",
            ),
            BayCapability(
                name="evidence_chains",
                method="GET",
                path="/v1/evidence/chains",
                description="Query persisted evidence chains for a run or entity.",
                response_model="EvidenceChainsResponse",
            ),
            BayCapability(
                name="hyperedges",
                method="GET",
                path="/v1/hyperedges",
                description="Query typed hyperedges persisted by Hold.",
                response_model="HyperedgesResponse",
            ),
            BayCapability(
                name="discover",
                method="POST",
                path="/v1/discover",
                description="Run multi-round discovery and return canonical outputs.",
                response_model="DiscoveryResponse",
            ),
            BayCapability(
                name="jobs",
                method="POST",
                path="/v1/jobs",
                description="Create a tracked voyage with events and optional worker handoff.",
                response_model="JobRecord",
            ),
            BayCapability(
                name="mate",
                method="POST",
                path="/v1/mate/{run_id}",
                description="Estimate savings, token impact, and cost value for a voyage.",
                response_model="MateReport",
            ),
            BayCapability(
                name="pilot",
                method="POST",
                path="/v1/pilot",
                description="Suggest next route adjustments and follow-up queries.",
                response_model="PilotAdvice",
            ),
        ],
        exposed_views=[
            "entity_view",
            "query_view",
            "hyperedge_view",
            "audit_view",
        ],
        notes=[
            "Hold is a logical container, not a backend choice.",
            "Bay is the discovery and exposure layer, not the fact store.",
            "Hold schema and migration state are explicitly versioned.",
            "Entity and relation schema catalogs are exposed as readable contracts.",
            "Output profiles are exposed as a stable contract for caller-specific transforms.",
            "Hold storage and index catalogs are exposed as stable read models.",
            "Hold backend evaluation is exposed as a read model for future storage swaps.",
            "Current implementation is draft-compatible and backend-agnostic.",
            "Semantic vector search is available for query-family reuse.",
            "Tenant-aware usage telemetry is exposed as an aggregate read model.",
            "Tenant quota evaluation is exposed as a read model and is enforced on tenant-scoped job and discovery calls when limits are enabled.",
            "Topology probe and planner are exposed as read models for route-shape inference and research planning.",
        ],
    )
