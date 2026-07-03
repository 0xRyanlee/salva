"""
Salva MCP Server

Exposes Salva discovery intelligence as MCP tools for use with
Claude Code, Claude Desktop, and any MCP-compatible agent framework.

Run with:
    python3 -m apps.mcp              # stdio (Claude Code / Claude Desktop)
    python3 -m apps.mcp --transport http --port 8001  # HTTP (for testing / other clients)

All tools import directly from salva_core — no running HTTP server required.
"""
from __future__ import annotations

import json
import os
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    class _MissingFastMCP:
        available = False

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.name = args[0] if args else kwargs.get("name", "salva-runtime")
            self.instructions = kwargs.get("instructions", "")

        def tool(self, *args: Any, **kwargs: Any):
            def decorator(fn):
                return fn

            return decorator

        def run(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "mcp package not installed. Install with: pip install 'salva-runtime[mcp]' "
                "or: pip install mcp"
            )

    FastMCP = _MissingFastMCP

from salva_core.evaluation import build_audit_report
from salva_core.navigation import build_pilot_advice
from salva_core.persistence import (
    create_job,
    get_job,
    get_run,
)
from salva_core.schemas import (
    DiscoveryIntent,
    DiscoveryRequest,
    DomainHints,
    ExecutionContext,
    MemoryPolicy,
    PilotRequest,
    TopologyProbeRequest,
)
from salva_core.service import run_discovery

mcp = FastMCP(
    "salva-runtime",
    instructions=(
        "Salva is a discovery intelligence runtime. Use salva_discover for quick "
        "synchronous searches (≤20 results). Use salva_job_create + salva_job_status "
        "for larger async runs. salva_run_result fetches full entity + evidence data. "
        "salva_audit gives quality analysis of a completed run. "
        "salva_pilot suggests next search actions based on what was found."
    ),
)


# ---------------------------------------------------------------------------
# salva_discover — synchronous discovery
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_discover(
    market: str,
    industry: str,
    objective: str = "find_companies",
    product: str = "",
    role: str = "",
    max_results: int = 10,
    output_profile: str = "company_profile",
    extra_keywords: str = "",
    negative_keywords: str = "",
    domain_hints_json: str = "",
    project_id: str = "",
    campaign_id: str = "",
    continuation_id: str = "",
    memory_read_scope: str = "none",
    memory_write_mode: str = "quarantine",
    persistence: str = "audit",
) -> str:
    """
    Run a synchronous discovery search and return scored entities.

    Use this for quick, focused searches (max_results ≤ 20).
    For larger or background runs use salva_job_create instead.

    Args:
        market: Geographic market (e.g. "Germany", "US", "Southeast Asia")
        industry: Industry or topic (e.g. "legal tech", "B2B SaaS", "AI hardware")
        objective: Discovery goal. One of: find_companies, find_leads, find_events,
                   find_exhibitors, find_market_activity, find_partnership_signals
        product: Specific product type to find (e.g. "contract management software")
        role: Specific role to target (e.g. "reseller", "CTO", "procurement manager")
        max_results: Maximum number of entities to return (1–20, default 10)
        output_profile: Output shape. One of: company_profile, lead, event,
                        crm_contact, activity_signal
        extra_keywords: Comma-separated additional search keywords
        negative_keywords: Comma-separated keywords to exclude from results
        domain_hints_json: Optional JSON to inject custom vocabulary. Example:
                           {"signal_terms": ["compliance", "e-signature"],
                            "source_hints": ["law360.com"]}
    """
    domain_hints = _parse_domain_hints(domain_hints_json)
    extra_kw = [k.strip() for k in extra_keywords.split(",") if k.strip()]
    negative_kw = [k.strip() for k in negative_keywords.split(",") if k.strip()]

    request = DiscoveryRequest(
        objective=objective,
        output_profile=output_profile,
        max_results=max(1, min(20, max_results)),
        execution=ExecutionContext(
            project_id=project_id or None,
            campaign_id=campaign_id or None,
            continuation_id=continuation_id or None,
            persistence=persistence,
            memory=MemoryPolicy(
                read_scope=memory_read_scope,
                write_mode=memory_write_mode,
            ),
        ),
        intent=DiscoveryIntent(
            market=market,
            industry=industry,
            product=product or None,
            role=role or None,
            extra_keywords=extra_kw,
            negative_keywords=negative_kw,
            domain_hints=domain_hints,
        ),
    )

    try:
        entities, relations, telemetry, meta = run_discovery(request)
    except Exception as exc:
        return json.dumps({"error": str(exc), "ok": False})

    return json.dumps(
        {
            "ok": True,
            "run_id": meta.get("run_id"),
            "entity_count": len(entities),
            "qualified_count": meta.get("qualified_count", 0),
            "rounds": meta.get("rounds", 0),
            "domain": meta.get("domain"),
            "memory_seeds_used": meta.get("memory_seeds_used", 0),
            "retrieval_health": meta.get("retrieval_health", "ok"),
            "execution": meta.get("execution", {}),
            "entities": [_compact_entity(e.model_dump(mode="json")) for e in entities],
            "feedback": {
                "mate": meta.get("feedback", {}).get("mate", {}),
                "pilot_queries": (
                    meta.get("feedback", {})
                    .get("pilot", {})
                    .get("suggested_queries", [])
                ),
            },
        },
        ensure_ascii=False,
        default=str,
    )


# ---------------------------------------------------------------------------
# salva_job_create — async job creation
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_job_create(
    market: str,
    industry: str,
    objective: str = "find_companies",
    product: str = "",
    role: str = "",
    max_results: int = 50,
    output_profile: str = "company_profile",
    extra_keywords: str = "",
    negative_keywords: str = "",
    domain_hints_json: str = "",
    campaign_id: str = "",
    continuation_id: str = "",
    memory_read_scope: str = "none",
    memory_write_mode: str = "quarantine",
    persistence: str = "audit",
) -> str:
    """
    Create a background discovery job and return the job_id immediately.

    Use this for larger searches (max_results > 20) or when you don't want
    to wait for results. Poll status with salva_job_status(job_id).

    Args:
        market: Geographic market (e.g. "Germany", "US")
        industry: Industry or topic to search
        objective: Discovery goal (same options as salva_discover)
        product: Specific product type
        role: Specific role to target
        max_results: Maximum results (up to 200)
        output_profile: Output shape (same options as salva_discover)
        extra_keywords: Comma-separated additional keywords
        negative_keywords: Comma-separated keywords to exclude
        domain_hints_json: Optional JSON for custom vocabulary injection
    """
    domain_hints = _parse_domain_hints(domain_hints_json)
    extra_kw = [k.strip() for k in extra_keywords.split(",") if k.strip()]
    negative_kw = [k.strip() for k in negative_keywords.split(",") if k.strip()]

    request = DiscoveryRequest(
        objective=objective,
        output_profile=output_profile,
        max_results=max(1, min(200, max_results)),
        execution=ExecutionContext(
            campaign_id=campaign_id or None,
            continuation_id=continuation_id or None,
            persistence=persistence,
            memory=MemoryPolicy(
                read_scope=memory_read_scope,
                write_mode=memory_write_mode,
            ),
        ),
        intent=DiscoveryIntent(
            market=market,
            industry=industry,
            product=product or None,
            role=role or None,
            extra_keywords=extra_kw,
            negative_keywords=negative_kw,
            domain_hints=domain_hints,
        ),
    )

    try:
        job_id = create_job(request)
    except Exception as exc:
        return json.dumps({"error": str(exc), "ok": False})

    return json.dumps(
        {
            "ok": True,
            "job_id": job_id,
            "status": "queued",
            "message": (
                f"Job created. Poll status with salva_job_status('{job_id}'). "
                "A worker must be running to process this job."
            ),
        }
    )


# ---------------------------------------------------------------------------
# salva_job_status — job polling
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_job_status(job_id: str) -> str:
    """
    Get the current status of a background discovery job.

    Args:
        job_id: The job ID returned by salva_job_create
    """
    job = get_job(job_id)
    if job is None:
        return json.dumps({"error": f"job not found: {job_id}", "ok": False})

    result: dict[str, Any] = {
        "ok": True,
        "job_id": job.job_id,
        "status": job.status,
        "objective": job.objective,
        "output_profile": job.output_profile,
        "run_id": job.run_id,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }
    if job.status == "completed" and job.run_id:
        result["message"] = f"Done. Fetch results with salva_run_result('{job.run_id}')"
    elif job.status == "failed":
        result["message"] = f"Job failed: {job.error}"
    else:
        result["message"] = f"Job is {job.status}. Check again soon."

    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# salva_job_cancel — cancel a job
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_job_cancel(job_id: str, force: bool = False) -> str:
    """
    Cancel a queued or running job.

    Args:
        job_id: The job ID to cancel
        force: Force cancel even if job is running (default False)
    """
    from datetime import datetime

    job = get_job(job_id)
    if job is None:
        return json.dumps({"error": f"job not found: {job_id}", "ok": False})

    if job.status == "completed":
        return json.dumps({"error": f"job already completed: {job_id}", "ok": False})
    if job.status == "failed" and not force:
        return json.dumps({"error": f"job already failed: {job_id}", "ok": False})
    if job.status == "running" and not force:
        return json.dumps({"error": "job is running, use force=true to cancel", "ok": False})

    from salva_core.persistence import update_job_status
    update_job_status(job_id, "cancelled", meta={"cancelled_at": datetime.now().isoformat()})

    return json.dumps({"ok": True, "job_id": job_id, "status": "cancelled"})


# ---------------------------------------------------------------------------
# salva_run_result — fetch run entities and evidence
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_run_result(run_id: str, max_entities: int = 20) -> str:
    """
    Fetch the full result of a completed discovery run.

    Returns entities with evidence, relations count, and run metadata.

    Args:
        run_id: The run ID from salva_discover or a completed salva_job_create
        max_entities: Maximum number of entities to include (default 20)
    """
    run = get_run(run_id)
    if run is None:
        return json.dumps({"error": f"run not found: {run_id}", "ok": False})

    entities = run.get("entities", [])[:max_entities]
    relations = run.get("relations", [])
    meta = run.get("meta", {})

    return json.dumps(
        {
            "ok": True,
            "run_id": run_id,
            "objective": run.get("objective"),
            "output_profile": run.get("output_profile"),
            "created_at": run.get("created_at"),
            "entity_count": len(run.get("entities", [])),
            "relation_count": len(relations),
            "qualified_count": meta.get("qualified_count", 0),
            "domain": meta.get("domain"),
            "rounds": meta.get("rounds", 0),
            "entities": [_compact_entity(e) for e in entities],
        },
        ensure_ascii=False,
        default=str,
    )


# ---------------------------------------------------------------------------
# salva_audit — run quality analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_audit(run_id: str) -> str:
    """
    Get a quality audit report for a completed discovery run.

    Returns scoring breakdown, source analysis, round-by-round performance,
    and signal-to-noise metrics.

    Args:
        run_id: The run ID to audit
    """
    try:
        report = build_audit_report(run_id)
    except Exception as exc:
        return json.dumps({"error": str(exc), "ok": False})

    return json.dumps(
        {
            "ok": True,
            "run_id": run_id,
            "audit": report.model_dump(mode="json"),
        },
        ensure_ascii=False,
        default=str,
    )


# ---------------------------------------------------------------------------
# salva_pilot — next-step guidance
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_pilot(
    run_id: str,
    market: str = "",
    industry: str = "",
    objective: str = "find_companies",
    max_suggestions: int = 5,
) -> str:
    """
    Get next-step search recommendations based on a completed run.

    Returns suggested queries, source hints, and strategic guidance for
    what to search next given what was found.

    Args:
        run_id: The run ID to base recommendations on
        market: Market context for suggestions (defaults to run's market)
        industry: Industry context (defaults to run's industry)
        objective: Discovery objective (defaults to run's objective)
        max_suggestions: Maximum number of suggested queries (default 5)
    """
    run = get_run(run_id)
    if run is None:
        return json.dumps({"error": f"run not found: {run_id}", "ok": False})

    try:
        request_data = run.get("request", {})
        pilot_request = PilotRequest(
            run_id=run_id,
            discovery=DiscoveryRequest.model_validate(request_data),
            market=market or None,
            industry=industry or None,
            objective=objective,
            max_suggestions=max_suggestions,
        )
        advice = build_pilot_advice(pilot_request)
    except Exception as exc:
        return json.dumps({"error": str(exc), "ok": False})

    return json.dumps(
        {
            "ok": True,
            "run_id": run_id,
            "pilot": advice.model_dump(mode="json"),
        },
        ensure_ascii=False,
        default=str,
    )


# ---------------------------------------------------------------------------
# salva_research_report — aggregate research report for a run
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_research_report(run_id: str, max_entities: int = 50) -> str:
    """
    Generate a structured research report for a completed discovery run.

    Returns executive summary, key findings, coverage map, source attribution,
    and identified gaps. Analogous to GPT deep-research schema output.

    Args:
        run_id: The run ID to report on
        max_entities: Max entities to include in analysis (default 50)
    """
    run = get_run(run_id)
    if run is None:
        return json.dumps({"error": f"run not found: {run_id}", "ok": False})

    try:
        from salva_core.schemas import CanonicalEntity
        from salva_core.transforms import build_research_report
        raw_entities = run.get("entities", [])[:max_entities]
        entities = [CanonicalEntity.model_validate(e) for e in raw_entities]
        meta = run.get("meta", {})
        meta["run_id"] = run_id
        report = build_research_report(entities, meta)
    except Exception as exc:
        return json.dumps({"error": str(exc), "ok": False})

    return json.dumps({"ok": True, "run_id": run_id, "report": report},
                      ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# salva_run_diff — compare two runs
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_run_diff(run_id_a: str, run_id_b: str) -> str:
    """
    Compare two discovery runs and return added, removed, and updated entities.

    Useful for tracking changes across repeated searches on the same topic.

    Args:
        run_id_a: The baseline run ID
        run_id_b: The comparison run ID
    """
    run_a = get_run(run_id_a)
    run_b = get_run(run_id_b)
    if run_a is None:
        return json.dumps({"error": f"run not found: {run_id_a}", "ok": False})
    if run_b is None:
        return json.dumps({"error": f"run not found: {run_id_b}", "ok": False})

    def entity_key(e: dict) -> str:
        title = (e.get("title") or "").lower().strip()
        domain = (e.get("domain") or "").lower().strip()
        return f"{title}|{domain}"

    a_map = {entity_key(e): e for e in run_a.get("entities", [])}
    b_map = {entity_key(e): e for e in run_b.get("entities", [])}

    added   = [b_map[k] for k in b_map if k not in a_map]
    removed = [a_map[k] for k in a_map if k not in b_map]
    updated, unchanged = [], []
    for k in a_map:
        if k not in b_map:
            continue
        a_s = a_map[k].get("score") or a_map[k].get("confidence") or 0.0
        b_s = b_map[k].get("score") or b_map[k].get("confidence") or 0.0
        if abs(a_s - b_s) > 0.01:
            updated.append({"title": b_map[k].get("title"), "score_a": a_s, "score_b": b_s})
        else:
            unchanged.append(b_map[k])

    return json.dumps({
        "ok": True,
        "run_id_a": run_id_a,
        "run_id_b": run_id_b,
        "added_count":     len(added),
        "removed_count":   len(removed),
        "updated_count":   len(updated),
        "unchanged_count": len(unchanged),
        "added":   [_compact_entity(e) for e in added[:20]],
        "removed": [_compact_entity(e) for e in removed[:20]],
        "updated": updated[:20],
    }, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# salva_graph_export — export run as HIF JSON
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_graph_export(run_id: str, fmt: str = "hif") -> str:
    """
    Export the entity/relation graph of a run as HIF JSON or DOT.

    Args:
        run_id: The run ID to export
        fmt: Output format — "hif" (default) or "dot"
    """
    run = get_run(run_id)
    if run is None:
        return json.dumps({"error": f"run not found: {run_id}", "ok": False})

    entities  = run.get("entities", [])
    relations = run.get("relations", [])

    nodes = [
        {
            "id": e.get("entity_id") or (e.get("title") or "").replace(" ", "_"),
            "attrs": {
                "title":       e.get("title"),
                "entity_type": e.get("entity_type"),
                "score":       e.get("score") or e.get("confidence"),
            },
        }
        for e in entities
    ]
    edges = [
        {
            "source": r.get("subject_id") or r.get("source_entity_id"),
            "target": r.get("object_id") or r.get("target_entity_id"),
            "type":   r.get("relation_type") or r.get("type"),
        }
        for r in relations
    ]

    if fmt == "dot":
        lines = [f'digraph "{run_id}" {{', '  rankdir=LR;']
        for n in nodes:
            nid   = (n["id"] or "").replace('"', '\\"')
            label = (n["attrs"].get("title") or nid).replace('"', '\\"')
            score = n["attrs"].get("score") or 0.0
            lines.append(f'  "{nid}" [label="{label}\\n{score:.2f}"];')
        for e in edges:
            src = (e.get("source") or "").replace('"', '\\"')
            tgt = (e.get("target") or "").replace('"', '\\"')
            rel = e.get("type") or "related"
            if src and tgt:
                lines.append(f'  "{src}" -> "{tgt}" [label="{rel}"];')
        lines.append("}")
        return json.dumps({"ok": True, "run_id": run_id, "format": "dot", "dot": "\n".join(lines)})

    return json.dumps({
        "ok": True,
        "run_id": run_id,
        "format": "hif",
        "nodes": nodes,
        "edges": edges,
    }, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# salva_vocab — domain vocabulary query
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_vocab(domain: str = "", list_all: bool = False) -> str:
    """
    Query domain vocabulary registry.

    Args:
        domain: Specific domain to show (e.g., "events", "bd_leads", "companies")
        list_all: If True, list all available domains (default False)
    """
    try:
        from core.domain_vocab import get_vocab, list_domains
    except Exception as exc:
        return json.dumps({"error": f"failed to import domain_vocab: {exc}", "ok": False})

    if list_all:
        domains = list_domains()
        return json.dumps({
            "ok": True,
            "domains": [
                {
                    "name": d,
                    "signal_terms_count": len(get_vocab(d).signal_terms),
                    "source_hints_count": len(get_vocab(d).source_hints),
                    "synonym_groups_count": len(get_vocab(d).synonym_groups),
                }
                for d in domains
            ]
        })

    if not domain:
        return json.dumps({"error": "domain required when list_all=false", "ok": False})

    vocab = get_vocab(domain)
    return json.dumps({
        "ok": True,
        "domain": domain,
        "signal_terms": vocab.signal_terms,
        "source_hints": vocab.source_hints,
        "noise_terms": vocab.noise_terms,
        "synonym_groups": vocab.synonym_groups,
        "region_variants": vocab.region_variants,
}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# salva_topology — probe query topology
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_topology(
    market: str,
    industry: str,
    objective: str = "find_companies",
    max_results: int = 50,
    preset: str = "",
) -> str:
    """
    Probe a query to determine its topology and get recommended route.

    Args:
        market: Geographic market (e.g. "Germany", "US")
        industry: Industry or topic
        objective: Discovery goal (same options as salva_discover)
        max_results: Expected number of results
        preset: Optional experience preset (e.g., "quick_scan", "lead_focus")
    """
    try:
        from salva_core.topology import build_topology_probe_response
    except Exception as exc:
        return json.dumps({"error": f"failed to import topology: {exc}", "ok": False})

    try:
        request = DiscoveryRequest(
            objective=objective,
            max_results=max_results,
            intent=DiscoveryIntent(market=market, industry=industry),
        )
        probe_req = TopologyProbeRequest(
            discovery=request,
            caller_preset=preset or None,
        )
        result = build_topology_probe_response(probe_req)
    except Exception as exc:
        return json.dumps({"error": str(exc), "ok": False})

    return json.dumps({
        "ok": True,
        "probe": result.probe.model_dump(mode="json"),
        "plan": result.plan.model_dump(mode="json"),
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
# salva_plugins — list enrichment plugins
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_plugins() -> str:
    """
    List available enrichment plugins with their status and capabilities.
    """
    try:
        from enrichment.plugins import list_plugin_descriptors
    except Exception as exc:
        return json.dumps({"error": f"failed to import plugins: {exc}", "ok": False})

    items = list_plugin_descriptors()
    return json.dumps({
        "ok": True,
        "plugins": [p.model_dump(mode="json") for p in items]
    })


# ---------------------------------------------------------------------------
# salva_providers — list retrieval providers
# ---------------------------------------------------------------------------

@mcp.tool()
def salva_providers() -> str:
    """
    List available retrieval providers with their status and capabilities.
    """
    try:
        from retrieval.registry import list_provider_descriptors
    except Exception as exc:
        return json.dumps({"error": f"failed to import providers: {exc}", "ok": False})

    items = list_provider_descriptors()
    return json.dumps({
        "ok": True,
        "providers": [p.model_dump(mode="json") for p in items]
    })


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_domain_hints(hints_json: str) -> DomainHints | None:
    if not hints_json.strip():
        return None
    value = hints_json.strip()
    if value.startswith("@"):
        file_path = value[1:].strip()
        try:
            with open(file_path, encoding="utf-8") as f:
                value = f.read()
        except Exception:
            return None
    try:
        data = json.loads(value)
        return DomainHints.model_validate(data)
    except Exception:
        return None


def _compact_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_id":    entity.get("entity_id", ""),
        "title":        entity.get("title", ""),
        "entity_type":  entity.get("entity_type", ""),
        "domain":       entity.get("domain", ""),
        "confidence":   entity.get("confidence", 0.0),
        "source_urls":  entity.get("source_urls", [])[:3],
        "description":  (entity.get("description") or "")[:300],
        "location":     entity.get("location"),
        "contact":      entity.get("contact"),
        "tags":         entity.get("tags", [])[:8],
    }


def validate_auth_environment(transport: str) -> None:
    """
    Enforce the MCP deployment auth boundary at process start.

    MCP transport does not provide a universal request-auth hook, so the runtime
    requires the HTTP deployment to be backed by an explicit shared secret. When
    SALVA_API_KEY is configured, SALVA_MCP_API_KEY must also be configured and
    match it so the API and MCP surfaces stay aligned.
    """
    if transport != "http":
        return

    api_key = os.getenv("SALVA_API_KEY", "")
    mcp_key = os.getenv("SALVA_MCP_API_KEY", "")

    if api_key and not mcp_key:
        raise RuntimeError(
            "SALVA_MCP_API_KEY must be set when SALVA_API_KEY is enabled for MCP HTTP transport."
        )
    if api_key and mcp_key and api_key != mcp_key:
        raise RuntimeError(
            "SALVA_MCP_API_KEY must match SALVA_API_KEY for MCP HTTP transport."
        )
