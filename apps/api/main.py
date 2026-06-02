import asyncio
import json
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from bay.manifest import BayManifest, build_bay_manifest
from enrichment.plugins import list_plugin_descriptors
from hold.schema import (
    HoldEntitySchemasResponse,
    HoldRelationSchemasResponse,
    HoldSchema,
    build_hold_entity_schemas,
    build_hold_relation_schemas,
    build_hold_schema,
)
from hold.projection import HoldProjectionResponse, HoldViewsResponse, build_hold_views, project_hold_view
from hold.backends import HoldBackendCatalogResponse, build_hold_backend_catalog
from hold.walk import HoldGraphWalkResponse, build_hold_graph_walk
from hold.storage import HoldStorageCatalog, build_hold_storage_catalog
from retrieval.registry import list_provider_descriptors
from salva_core import service
from salva_core.benchmark import build_benchmark_report, write_benchmark_report
from salva_core.evaluation import build_audit_report, compare_audits
from salva_core.exporting import build_run_snapshot, write_run_snapshot
from salva_core.llm import list_llm_provider_descriptors, probe_omlx_health
from salva_core.providers import build_provider_catalog
from salva_core.pricing import build_pricing_catalog_response
from salva_core.persistence import (
    create_job,
    get_job,
    get_run,
    list_evidence_chains,
    list_evidence_records,
    list_hold_schema_migrations,
    list_hyperedges,
    list_jobs,
    list_plugin_reports,
    list_query_family_memory,
    list_relations,
    search_query_family_memory,
    list_runs,
    list_source_attempts,
    list_stream_events,
    list_telemetry,
    list_usage_telemetry,
)
from salva_core.navigation import build_mate_report, build_pilot_advice
from salva_core.mode_resolver import explain_experience_plan
from salva_core.presets import build_preset_catalog, resolve_preset_profile
from salva_core.quotas import evaluate_tenant_quota, load_quota_policy
from salva_core.routes import build_route_catalog, resolve_route_entry
from salva_core.schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
    ExperiencePlanExplanation,
    ExperiencePlanRequest,
    LLMHealthResponse,
    LLMProvidersResponse,
    JobCreateRequest,
    JobRecord,
    JobsResponse,
    RunSnapshot,
    PluginsResponse,
    PluginReportsResponse,
    AuditReport,
    AuditComparison,
    BenchmarkExportResult,
    BenchmarkReport,
    BenchmarkRequest,
    MateRequest,
    MateReport,
    PilotAdvice,
    PilotRequest,
    PlannerRequest,
    PlannerResponse,
    PricingCatalogResponse,
    ProvidersResponse,
    SnapshotExportRequest,
    SnapshotExportResult,
    RunsResponse,
    EvidenceResponse,
    EvidenceChainsResponse,
    HyperedgesResponse,
    HoldMigrationsResponse,
    RelationsResponse,
    QueryFamilyMemoryResponse,
    OutputTransformCatalog,
    PresetCatalogResponse,
    PresetProfile,
    TopologyProbeRequest,
    TopologyProbeResponse,
    RouteCatalogEntry,
    RouteCatalogResponse,
    ProviderCatalogResponse,
    SourceAttemptsResponse,
    StreamEventsResponse,
    TelemetryResponse,
    TenantQuotaResponse,
    UsageTelemetryResponse,
)
from salva_core.semantic import (
    SemanticBackendBenchmarkRequest,
    SemanticBackendBenchmarkResponse,
    SemanticQueryFamilySearchResponse,
    SemanticVectorCatalogResponse,
    build_semantic_backend_benchmark,
    build_semantic_vector_catalog,
)
from salva_core.transforms import build_output_transform_catalog, transform_entities
from salva_core.planner import build_planner_response
from salva_core.topology import build_topology_probe_response
from salva_core.worker import run_job


from apps.api.auth import require_auth
from apps.api.errors import register_exception_handlers

app = FastAPI(
    title="Salva Runtime",
    version="0.1.0",
    description="Standalone discovery intelligence runtime for multi-agent use.",
    dependencies=[Depends(require_auth)],
)

# Register exception handlers
register_exception_handlers(app)

TERMINAL_JOB_STATUSES = {"completed", "failed"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "salva-runtime", "version": "0.1.0"}


@app.get("/v1/bay", response_model=BayManifest)
async def bay_manifest() -> BayManifest:
    return build_bay_manifest()


@app.get("/v1/hold/schema", response_model=HoldSchema)
async def hold_schema() -> HoldSchema:
    return build_hold_schema()


@app.get("/v1/hold/schema/entities", response_model=HoldEntitySchemasResponse)
async def hold_schema_entities() -> HoldEntitySchemasResponse:
    items = build_hold_entity_schemas()
    return HoldEntitySchemasResponse(items=items, total=len(items))


@app.get("/v1/hold/schema/relations", response_model=HoldRelationSchemasResponse)
async def hold_schema_relations() -> HoldRelationSchemasResponse:
    items = build_hold_relation_schemas()
    return HoldRelationSchemasResponse(items=items, total=len(items))


@app.get("/v1/hold/migrations", response_model=HoldMigrationsResponse)
async def hold_migrations(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HoldMigrationsResponse:
    items, total = list_hold_schema_migrations(limit=limit, offset=offset)
    return HoldMigrationsResponse(items=items, total=total)


@app.get("/v1/hold/storage", response_model=HoldStorageCatalog)
async def hold_storage() -> HoldStorageCatalog:
    return build_hold_storage_catalog()


@app.get("/v1/hold/backends", response_model=HoldBackendCatalogResponse)
async def hold_backends() -> HoldBackendCatalogResponse:
    return build_hold_backend_catalog()


@app.get("/v1/relations", response_model=RelationsResponse)
async def relations(
    run_id: Annotated[str | None, Query()] = None,
    relation_type: Annotated[str | None, Query()] = None,
    from_entity_id: Annotated[str | None, Query()] = None,
    to_entity_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RelationsResponse:
    items, total = list_relations(
        run_id=run_id,
        relation_type=relation_type,
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        limit=limit,
        offset=offset,
    )
    return RelationsResponse(items=items, total=total)


@app.get("/v1/hold/views", response_model=HoldViewsResponse)
async def hold_views() -> HoldViewsResponse:
    return build_hold_views()


@app.get("/v1/hold/views/{view_name}", response_model=HoldProjectionResponse)
async def hold_view(view_name: str, run_id: Annotated[str, Query()]) -> HoldProjectionResponse:
    try:
        snapshot = build_run_snapshot(run_id)
        return project_hold_view(snapshot, view_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/hold/walk", response_model=HoldGraphWalkResponse)
async def hold_walk(
    run_id: Annotated[str, Query()],
    seed_entity_id: Annotated[list[str] | None, Query()] = None,
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
    include_evidence: Annotated[bool, Query()] = True,
    include_sources: Annotated[bool, Query()] = True,
) -> HoldGraphWalkResponse:
    try:
        if not seed_entity_id:
            raise ValueError("seed_entity_id is required")
        snapshot = build_run_snapshot(run_id)
        return build_hold_graph_walk(
            snapshot,
            seed_entity_ids=seed_entity_id,
            depth=depth,
            include_evidence=include_evidence,
            include_sources=include_sources,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/discover", response_model=DiscoveryResponse)
async def discover(payload: DiscoveryRequest) -> DiscoveryResponse:
    tenant_id = _resolve_tenant_scope(payload.tenant_id, "discover")
    payload = payload.model_copy(update={"tenant_id": tenant_id})
    quota = evaluate_tenant_quota(tenant_id)
    _ensure_quota_allowed(quota, "discover")
    entities, relations, telemetry, meta = service.run_discovery(payload)
    transformed_items = transform_entities(entities, payload.output_profile, payload.transform)
    return DiscoveryResponse(
        objective=payload.objective,
        output_profile=payload.output_profile,
        entities=entities,
        transformed_items=transformed_items,
        relations=relations,
        telemetry=telemetry,
        meta=meta,
    )


@app.get("/v1/plugins", response_model=PluginsResponse)
async def plugins() -> PluginsResponse:
    items = list_plugin_descriptors()
    return PluginsResponse(items=items, total=len(items))


@app.get("/v1/providers", response_model=ProvidersResponse)
async def providers() -> ProvidersResponse:
    items = list_provider_descriptors()
    return ProvidersResponse(items=items, total=len(items))


@app.get("/v1/providers/catalog", response_model=ProviderCatalogResponse)
async def provider_catalog() -> ProviderCatalogResponse:
    return build_provider_catalog()


@app.get("/v1/llm/providers", response_model=LLMProvidersResponse)
async def llm_providers() -> LLMProvidersResponse:
    items = [item.model_dump(mode="json") for item in list_llm_provider_descriptors()]
    return LLMProvidersResponse(items=items, total=len(items))


@app.get("/v1/llm/health", response_model=LLMHealthResponse)
async def llm_health(model_name: str | None = None) -> LLMHealthResponse:
    health = probe_omlx_health(model_name=model_name)
    return LLMHealthResponse.model_validate(health.model_dump(mode="json"))


@app.post("/v1/jobs", response_model=JobRecord)
async def create_discovery_job(payload: JobCreateRequest) -> JobRecord:
    tenant_id = _resolve_tenant_scope(payload.discovery.tenant_id, "job")
    payload = payload.model_copy(
        update={"discovery": payload.discovery.model_copy(update={"tenant_id": tenant_id})}
    )
    quota = evaluate_tenant_quota(tenant_id)
    _ensure_quota_allowed(quota, "job")
    job_id = create_job(
        payload.discovery,
        meta={"wait_for_completion": payload.wait_for_completion},
    )

    if not payload.wait_for_completion:
        item = get_job(job_id)
        if item is None:
            raise HTTPException(status_code=500, detail="Job created but cannot be loaded")
        return item

    try:
        run_job(job_id, execution_mode="inline")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Job execution failed: {exc}") from exc

    item = get_job(job_id)
    if item is None:
        raise HTTPException(status_code=500, detail="Job completed but cannot be loaded")
    return item


@app.get("/v1/plugin-reports", response_model=PluginReportsResponse)
async def plugin_reports(
    run_id: Annotated[str | None, Query()] = None,
    plugin: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PluginReportsResponse:
    items, total = list_plugin_reports(run_id=run_id, plugin=plugin, limit=limit, offset=offset)
    return PluginReportsResponse(items=items, total=total)


@app.get("/v1/jobs", response_model=JobsResponse)
async def jobs(
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobsResponse:
    items, total = list_jobs(status=status, limit=limit, offset=offset)
    return JobsResponse(items=items, total=total)


@app.get("/v1/jobs/{job_id}", response_model=JobRecord)
async def job_detail(job_id: str) -> JobRecord:
    item = get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return item


@app.get("/v1/jobs/{job_id}/events", response_model=StreamEventsResponse)
async def job_events(
    job_id: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StreamEventsResponse:
    item = get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Job not found")
    items, total = list_stream_events(job_id=job_id, limit=limit, offset=offset)
    return StreamEventsResponse(items=items, total=total)


@app.get("/v1/jobs/{job_id}/stream")
async def job_stream(job_id: str) -> StreamingResponse:
    item = get_job(job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        sent = 0
        while True:
            events, total = list_stream_events(job_id=job_id, limit=500, offset=0)
            pending = events[sent:]
            for event in pending:
                payload = {
                    "job_id": event.job_id,
                    "event_type": event.event_type,
                    "message": event.message,
                    "created_at": event.created_at.isoformat(),
                    "data": event.data,
                }
                yield f"event: {event.event_type}\n"
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            sent = total

            current = get_job(job_id)
            if current is None:
                yield "event: job_failed\n"
                yield 'data: {"message":"job disappeared"}\n\n'
                break
            if current.status in TERMINAL_JOB_STATUSES and sent >= total:
                break

            yield "event: heartbeat\n"
            yield f'data: {json.dumps({"job_id": job_id, "status": current.status}, ensure_ascii=False)}\n\n'
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/v1/runs", response_model=RunsResponse)
async def runs(
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunsResponse:
    items, total = list_runs(limit=limit, offset=offset)
    return RunsResponse(items=items, total=total)


@app.get("/v1/runs/{run_id}")
async def run_detail(run_id: str) -> dict:
    item = get_run(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return item


@app.get("/v1/telemetry", response_model=TelemetryResponse)
async def telemetry(
    run_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TelemetryResponse:
    items, total = list_telemetry(run_id=run_id, limit=limit, offset=offset)
    return TelemetryResponse(items=items, total=total)


@app.get("/v1/output-profiles", response_model=OutputTransformCatalog)
async def output_profiles() -> OutputTransformCatalog:
    return build_output_transform_catalog()


@app.get("/v1/presets", response_model=PresetCatalogResponse)
async def presets() -> PresetCatalogResponse:
    return build_preset_catalog()


@app.get("/v1/presets/{preset_name}", response_model=PresetProfile)
async def preset(preset_name: str) -> PresetProfile:
    profile = resolve_preset_profile(preset_name)
    if profile is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    return profile


@app.get("/v1/routes", response_model=RouteCatalogResponse)
async def routes() -> RouteCatalogResponse:
    return build_route_catalog()


@app.get("/v1/routes/{route_name}", response_model=RouteCatalogEntry)
async def route(route_name: str) -> RouteCatalogEntry:
    entry = resolve_route_entry(route_name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Route not found")
    return entry


@app.get("/v1/retrieval-batches", response_model=TelemetryResponse)
async def retrieval_batches(
    run_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TelemetryResponse:
    items, total = list_telemetry(run_id=run_id, limit=limit, offset=offset)
    return TelemetryResponse(items=items, total=total)


@app.get("/v1/source-attempts", response_model=SourceAttemptsResponse)
async def source_attempts(
    run_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SourceAttemptsResponse:
    items, total = list_source_attempts(run_id=run_id, limit=limit, offset=offset)
    return SourceAttemptsResponse(items=items, total=total)


@app.get("/v1/evidence", response_model=EvidenceResponse)
async def evidence(
    run_id: Annotated[str | None, Query()] = None,
    entity_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvidenceResponse:
    items, total = list_evidence_records(run_id=run_id, entity_id=entity_id, limit=limit, offset=offset)
    return EvidenceResponse(items=items, total=total)


@app.get("/v1/evidence/chains", response_model=EvidenceChainsResponse)
async def evidence_chains(
    run_id: Annotated[str | None, Query()] = None,
    entity_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EvidenceChainsResponse:
    items, total = list_evidence_chains(run_id=run_id, entity_id=entity_id, limit=limit, offset=offset)
    return EvidenceChainsResponse(items=items, total=total)


@app.get("/v1/hyperedges", response_model=HyperedgesResponse)
async def hyperedges(
    run_id: Annotated[str | None, Query()] = None,
    hyperedge_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HyperedgesResponse:
    items, total = list_hyperedges(run_id=run_id, hyperedge_type=hyperedge_type, limit=limit, offset=offset)
    return HyperedgesResponse(items=items, total=total)


@app.get("/v1/query-families", response_model=QueryFamilyMemoryResponse)
async def query_families(
    run_id: Annotated[str | None, Query()] = None,
    objective: Annotated[str | None, Query()] = None,
    strategy: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> QueryFamilyMemoryResponse:
    items, total = list_query_family_memory(
        run_id=run_id,
        objective=objective,
        strategy=strategy,
        limit=limit,
        offset=offset,
    )
    return QueryFamilyMemoryResponse(items=items, total=total)


@app.get("/v1/semantic/query-families", response_model=SemanticQueryFamilySearchResponse)
async def semantic_query_families(
    query: Annotated[str, Query(min_length=1)],
    objective: Annotated[str | None, Query()] = None,
    strategy: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SemanticQueryFamilySearchResponse:
    matches, total = search_query_family_memory(
        query=query,
        objective=objective,
        strategy=strategy,
        limit=limit,
        offset=offset,
    )
    items = []
    for memory, score, vector_id in matches:
        items.append(
            {
                "score": score,
                "vector_id": vector_id,
                "query_family": memory,
                "matched_text": memory.query,
            }
        )
    return SemanticQueryFamilySearchResponse(
        query=query,
        objective=objective,
        strategy=strategy,
        dimensions=96,
        total=total,
        items=items,
        notes=["semantic vector search over successful query families"],
    )


@app.get("/v1/semantic/indexes", response_model=SemanticVectorCatalogResponse)
async def semantic_indexes() -> SemanticVectorCatalogResponse:
    return build_semantic_vector_catalog()


@app.post("/v1/semantic/benchmark", response_model=SemanticBackendBenchmarkResponse)
async def semantic_benchmark(payload: SemanticBackendBenchmarkRequest) -> SemanticBackendBenchmarkResponse:
    try:
        return build_semantic_backend_benchmark(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/v1/usage", response_model=UsageTelemetryResponse)
async def usage(tenant_id: Annotated[str | None, Query()] = None) -> UsageTelemetryResponse:
    resolved_tenant = _resolve_tenant_scope(tenant_id, "usage")
    return list_usage_telemetry(tenant_id=resolved_tenant)


@app.get("/v1/quota", response_model=TenantQuotaResponse)
async def quota(tenant_id: Annotated[str | None, Query()] = None) -> TenantQuotaResponse:
    resolved_tenant = _resolve_tenant_scope(tenant_id, "quota")
    return evaluate_tenant_quota(resolved_tenant)


@app.get("/v1/audits/compare", response_model=AuditComparison)
async def audit_compare(
    left_run_id: Annotated[str, Query()],
    right_run_id: Annotated[str, Query()],
) -> AuditComparison:
    try:
        return compare_audits(left_run_id, right_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/audits/{run_id}", response_model=AuditReport)
async def audit_run(run_id: str) -> AuditReport:
    try:
        return build_audit_report(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/snapshots/{run_id}", response_model=RunSnapshot)
async def snapshot_run(run_id: str) -> RunSnapshot:
    try:
        return build_run_snapshot(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _ensure_quota_allowed(quota: TenantQuotaResponse, action: str) -> None:
    if quota.allowed:
        return
    message = ", ".join(quota.violated) if quota.violated else "quota exceeded"
    raise HTTPException(
        status_code=429,
        detail=f"Tenant quota blocked {action}: {message}",
    )


def _resolve_tenant_scope(tenant_id: str | None, action: str) -> str | None:
    policy = load_quota_policy()
    if not policy.enabled:
        return tenant_id

    configured_tenant = os.getenv("SALVA_TENANT_ID", "").strip()
    if not configured_tenant:
        raise HTTPException(
            status_code=500,
            detail="SALVA_TENANT_ID must be set when tenant quota enforcement is enabled",
        )

    if tenant_id and tenant_id.strip() and tenant_id.strip() != configured_tenant:
        raise HTTPException(
            status_code=403,
            detail=f"tenant_id does not match configured tenant scope for {action}",
        )

    return configured_tenant


@app.post("/v1/snapshots/{run_id}/export", response_model=SnapshotExportResult)
async def export_run_snapshot(
    run_id: str,
    payload: SnapshotExportRequest | None = None,
) -> SnapshotExportResult:
    try:
        return write_run_snapshot(run_id, output_path=payload.output_path if payload else None)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/benchmarks/report", response_model=BenchmarkReport)
async def benchmark_report(payload: BenchmarkRequest) -> BenchmarkReport:
    try:
        return build_benchmark_report(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/benchmarks/export", response_model=BenchmarkExportResult)
async def benchmark_export(payload: BenchmarkRequest) -> BenchmarkExportResult:
    try:
        return write_benchmark_report(payload, output_path=payload.output_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/mate/{run_id}", response_model=MateReport, response_model_exclude_none=True)
async def mate_report(run_id: str, payload: MateRequest | None = None) -> MateReport:
    try:
        return build_mate_report(run_id, payload=payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/pilot", response_model=PilotAdvice)
async def pilot_advice(payload: PilotRequest) -> PilotAdvice:
    try:
        return build_pilot_advice(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/experience-plan", response_model=ExperiencePlanExplanation)
async def experience_plan(payload: ExperiencePlanRequest) -> ExperiencePlanExplanation:
    return explain_experience_plan(payload.discovery, caller_preset=payload.caller_preset)


@app.post("/v1/topology/probe", response_model=TopologyProbeResponse)
async def topology_probe(payload: TopologyProbeRequest) -> TopologyProbeResponse:
    return build_topology_probe_response(payload)


@app.post("/v1/planner", response_model=PlannerResponse)
async def planner(payload: PlannerRequest) -> PlannerResponse:
    return build_planner_response(payload)


@app.get("/v1/pricing-catalog", response_model=PricingCatalogResponse)
async def pricing_catalog(
    provider_name: Annotated[str | None, Query()] = None,
    model_name: Annotated[str | None, Query()] = None,
    catalog_path: Annotated[str | None, Query()] = None,
    catalog_url: Annotated[str | None, Query()] = None,
) -> PricingCatalogResponse:
    payload = build_pricing_catalog_response(
        provider_name=provider_name,
        model_name=model_name,
        catalog_path=catalog_path,
        catalog_url=catalog_url,
    )
    return PricingCatalogResponse.model_validate(payload)
