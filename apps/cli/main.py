"""
Salva CLI — skill wrapper for terminal agents and pipeline use.

Usage:
    salva find --market Germany --industry software --role reseller
    salva find --market US --industry fintech --max-results 20 --json
    salva job status <job_id>
    salva run show <run_id>
    salva audit <run_id>
    salva pilot <run_id>
    salva vocab list
    salva vocab show <domain>

--json flag outputs pure JSON to stdout for agent pipeline consumption.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

try:
    from typing import Annotated

    import typer
except ImportError:
    print(
        "ERROR: typer not installed.\n"
        "Install with: pip install 'salva-runtime[cli]'\n"
        "or: pip install typer rich",
        file=sys.stderr,
    )
    sys.exit(1)

app = typer.Typer(
    name="salva",
    help="Salva discovery intelligence CLI",
    no_args_is_help=True,
)
vocab_app = typer.Typer(help="Domain vocabulary commands")
job_app   = typer.Typer(help="Job queue commands")
run_app   = typer.Typer(help="Run result commands")
graph_app = typer.Typer(help="Graph export commands")
app.add_typer(vocab_app, name="vocab")
app.add_typer(job_app,   name="job")
app.add_typer(run_app,   name="run")
app.add_typer(graph_app, name="graph")


# ---------------------------------------------------------------------------
# salva find
# ---------------------------------------------------------------------------

@app.command()
def find(
    market:   Annotated[str, typer.Option("--market",   "-m", help="Target market / region")],
    industry: Annotated[str, typer.Option("--industry", "-i", help="Industry or topic")],
    objective:          str = typer.Option("find_companies",   help="Discovery objective"),
    product:            str = typer.Option("",                 help="Specific product type"),
    role:               str = typer.Option("",                 help="Specific role to target"),
    max_results:        int = typer.Option(10,                 help="Max results (1–200)"),
    output_profile:     str = typer.Option("company_profile",  help="Output profile"),
    extra_keywords:     str = typer.Option("",                 help="Comma-separated extra keywords"),
    negative_keywords:  str = typer.Option("",                 help="Comma-separated exclusions"),
    domain_hints:       str = typer.Option("",                 help="JSON domain hints"),
    project_id:         str = typer.Option("",                 help="Project scope for isolation"),
    campaign_id:        str = typer.Option("",                 help="Research campaign scope"),
    continuation_id:    str = typer.Option("",                 help="Research continuation ID"),
    memory_read_scope:  str = typer.Option("none",             help="Memory read scope"),
    memory_write_mode:  str = typer.Option("quarantine",       help="Memory write mode"),
    persistence:        str = typer.Option("audit",            help="Persistence: audit or none"),
    as_json: bool           = typer.Option(False, "--json",    help="Output raw JSON"),
) -> None:
    """Run a synchronous discovery search."""
    from salva_core.schemas import (
        DiscoveryIntent,
        DiscoveryRequest,
        DomainHints,
        ExecutionContext,
        MemoryPolicy,
    )
    from salva_core.service import run_discovery

    hints: DomainHints | None = None
    if domain_hints.strip():
        value = domain_hints.strip()
        if value.startswith("@"):
            file_path = value[1:].strip()
            try:
                with open(file_path, encoding="utf-8") as f:
                    value = f.read()
            except Exception as e:
                typer.echo(f"Error reading --domain-hints file: {e}", err=True)
                raise typer.Exit(1)
        try:
            hints = DomainHints.model_validate(json.loads(value))
        except Exception as e:
            typer.echo(f"Error parsing --domain-hints: {e}", err=True)
            raise typer.Exit(1)

    request = DiscoveryRequest(
        objective=objective,
        output_profile=output_profile,
        max_results=max(1, min(200, max_results)),
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
            extra_keywords=[k.strip() for k in extra_keywords.split(",") if k.strip()],
            negative_keywords=[k.strip() for k in negative_keywords.split(",") if k.strip()],
            domain_hints=hints,
        ),
    )

    with _spinner("Searching...", as_json):
        entities, relations, telemetry, meta = run_discovery(request)

    if as_json:
        typer.echo(json.dumps(
            {
                "run_id": meta.get("run_id"),
                "entity_count": len(entities),
                "qualified_count": meta.get("qualified_count", 0),
                "domain": meta.get("domain"),
                "memory_seeds_used": meta.get("memory_seeds_used", 0),
                "execution": meta.get("execution", {}),
                "entities": [e.model_dump(mode="json") for e in entities],
            },
            ensure_ascii=False,
            default=str,
        ))
    else:
        _print_run_summary(entities, meta)


@app.command("discover")
def discover(
    market:   Annotated[str, typer.Option("--market",   "-m", help="Target market / region")],
    industry: Annotated[str, typer.Option("--industry", "-i", help="Industry or topic")],
    objective:          str = typer.Option("find_companies",   help="Discovery objective"),
    product:            str = typer.Option("",                 help="Specific product type"),
    role:               str = typer.Option("",                 help="Specific role to target"),
    max_results:        int = typer.Option(10,                 help="Max results (1–200)"),
    output_profile:     str = typer.Option("company_profile",  help="Output profile"),
    extra_keywords:     str = typer.Option("",                 help="Comma-separated extra keywords"),
    negative_keywords:  str = typer.Option("",                 help="Comma-separated exclusions"),
    domain_hints:       str = typer.Option("",                 help="JSON domain hints or @file path"),
    campaign_id:        str = typer.Option("",                 help="Research campaign scope"),
    continuation_id:    str = typer.Option("",                 help="Research continuation ID"),
    memory_read_scope:  str = typer.Option("none",             help="Memory read scope"),
    memory_write_mode:  str = typer.Option("quarantine",       help="Memory write mode"),
    persistence:        str = typer.Option("audit",            help="Persistence: audit or none"),
    as_json: bool           = typer.Option(False, "--json",    help="Output raw JSON"),
) -> None:
    """Run a synchronous discovery search (alias for find)."""
    find(
        market,
        industry,
        objective,
        product,
        role,
        max_results,
        output_profile,
        extra_keywords,
        negative_keywords,
        domain_hints,
        campaign_id,
        continuation_id,
        memory_read_scope,
        memory_write_mode,
        persistence,
        as_json,
    )


# ---------------------------------------------------------------------------
# salva job status / salva job list
# ---------------------------------------------------------------------------

@job_app.command("status")
def job_status(
    job_id:  str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show status of a background job."""
    from salva_core.persistence import get_job
    job = get_job(job_id)
    if job is None:
        typer.echo(f"Job not found: {job_id}", err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(job.model_dump(mode="json"), default=str))
    else:
        typer.echo(f"job_id  : {job.job_id}")
        typer.echo(f"status  : {job.status}")
        typer.echo(f"run_id  : {job.run_id or '—'}")
        typer.echo(f"updated : {job.updated_at.isoformat()}")
        if job.error:
            typer.echo(f"error   : {job.error}", err=True)


@job_app.command("list")
def job_list(
    status:     str | None = typer.Option(None, help="Filter by status"),
    project_id: str | None = typer.Option(None, "--project-id", help="Filter by project"),
    limit:   int           = typer.Option(20),
    as_json: bool          = typer.Option(False, "--json"),
) -> None:
    """List recent jobs."""
    from salva_core.persistence import list_jobs
    items, total = list_jobs(limit=limit, status=status, project_id=project_id)
    if as_json:
        typer.echo(json.dumps(
            {"items": [j.model_dump(mode="json") for j in items], "total": total},
            default=str,
        ))
    else:
        typer.echo(f"{'job_id':<50} {'status':<12} {'objective':<25} {'updated'}")
        for j in items:
            typer.echo(f"{j.job_id:<50} {j.status:<12} {j.objective:<25} {j.updated_at.isoformat()}")
        typer.echo(f"\nTotal: {total}")


@job_app.command("cancel")
def job_cancel(
    job_id:  str,
    force:  bool = typer.Option(False, "--force", help="Force cancel even if running"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Cancel a queued or running job."""
    from salva_core.persistence import get_job, update_job_status

    job = get_job(job_id)
    if job is None:
        typer.echo(f"Job not found: {job_id}", err=True)
        raise typer.Exit(1)

    if job.status == "completed":
        typer.echo(f"Job already completed: {job_id}", err=True)
        raise typer.Exit(1)
    if job.status == "failed" and not force:
        typer.echo(f"Job already failed: {job_id}", err=True)
        raise typer.Exit(1)
    if job.status == "running" and not force:
        typer.echo(f"Job is running. Use --force to cancel: {job_id}", err=True)
        raise typer.Exit(1)

    update_job_status(job_id, "cancelled", meta={"cancelled_at": datetime.now().isoformat()})

    if as_json:
        typer.echo(json.dumps({"ok": True, "job_id": job_id, "status": "cancelled"}))
    else:
        typer.echo(f"Job cancelled: {job_id}")


# ---------------------------------------------------------------------------
# salva run show
# ---------------------------------------------------------------------------

@run_app.command("diff")
def run_diff(
    run_id_a: str,
    run_id_b: str,
    as_json:  bool = typer.Option(False, "--json"),
) -> None:
    """Compare two discovery runs — show added, removed, and updated entities."""
    from salva_core.persistence import get_run

    run_a = get_run(run_id_a)
    run_b = get_run(run_id_b)
    if run_a is None:
        typer.echo(f"Run not found: {run_id_a}", err=True)
        raise typer.Exit(1)
    if run_b is None:
        typer.echo(f"Run not found: {run_id_b}", err=True)
        raise typer.Exit(1)

    diff = _compute_run_diff(run_a, run_b)

    if as_json:
        typer.echo(json.dumps(diff, ensure_ascii=False, default=str))
    else:
        typer.echo(f"Diff: {run_id_a} → {run_id_b}")
        typer.echo(f"  added   : {len(diff['added'])}")
        typer.echo(f"  removed : {len(diff['removed'])}")
        typer.echo(f"  updated : {len(diff['updated'])}")
        typer.echo(f"  unchanged: {len(diff['unchanged'])}")
        if diff["added"]:
            typer.echo("\nAdded:")
            for e in diff["added"][:10]:
                typer.echo(f"  + [{e.get('score', 0):.2f}] {e.get('title')}")
        if diff["removed"]:
            typer.echo("\nRemoved:")
            for e in diff["removed"][:10]:
                typer.echo(f"  - [{e.get('score', 0):.2f}] {e.get('title')}")
        if diff["updated"]:
            typer.echo("\nUpdated (score changed):")
            for u in diff["updated"][:10]:
                typer.echo(f"  ~ {u['title']}: {u['score_a']:.2f} → {u['score_b']:.2f}")


def _entity_key(entity: dict) -> str:
    title = (entity.get("title") or "").lower().strip()
    domain = (entity.get("domain") or "").lower().strip()
    return f"{title}|{domain}"


def _compute_run_diff(run_a: dict, run_b: dict) -> dict:
    a_entities = {_entity_key(e): e for e in run_a.get("entities", [])}
    b_entities = {_entity_key(e): e for e in run_b.get("entities", [])}

    added   = [b_entities[k] for k in b_entities if k not in a_entities]
    removed = [a_entities[k] for k in a_entities if k not in b_entities]
    updated = []
    unchanged = []

    for k in a_entities:
        if k not in b_entities:
            continue
        a_score = a_entities[k].get("score") or a_entities[k].get("confidence") or 0.0
        b_score = b_entities[k].get("score") or b_entities[k].get("confidence") or 0.0
        if abs(a_score - b_score) > 0.01:
            updated.append({
                "title":   b_entities[k].get("title"),
                "score_a": a_score,
                "score_b": b_score,
                "entity":  b_entities[k],
            })
        else:
            unchanged.append(b_entities[k])

    return {
        "run_id_a":  run_a.get("run_id") or "",
        "run_id_b":  run_b.get("run_id") or "",
        "added":     added,
        "removed":   removed,
        "updated":   updated,
        "unchanged": unchanged,
    }


@run_app.command("show")
def run_show(
    run_id:       str,
    max_entities: int  = typer.Option(20),
    as_json:      bool = typer.Option(False, "--json"),
) -> None:
    """Show the result of a completed discovery run."""
    from salva_core.persistence import get_run
    run = get_run(run_id)
    if run is None:
        typer.echo(f"Run not found: {run_id}", err=True)
        raise typer.Exit(1)

    entities = run.get("entities", [])[:max_entities]
    meta = run.get("meta", {})

    if as_json:
        typer.echo(json.dumps(
            {
                "run_id": run_id,
                "entity_count": len(run.get("entities", [])),
                "entities": entities,
                "meta": meta,
            },
            ensure_ascii=False,
            default=str,
        ))
    else:
        typer.echo(f"run_id          : {run_id}")
        typer.echo(f"objective       : {run.get('objective')}")
        typer.echo(f"domain          : {meta.get('domain')}")
        typer.echo(f"entities found  : {len(run.get('entities', []))}")
        typer.echo(f"qualified       : {meta.get('qualified_count', 0)}")
        typer.echo(f"rounds          : {meta.get('rounds', 0)}")
        typer.echo("")
        for i, e in enumerate(entities, 1):
            title   = e.get("title", "(no title)")
            conf    = e.get("confidence", 0.0)
            urls    = e.get("source_urls", [])
            first_url = urls[0] if urls else "—"
            typer.echo(f"  {i:>3}. [{conf:.2f}] {title}")
            typer.echo(f"        {first_url}")


# ---------------------------------------------------------------------------
# salva audit
# ---------------------------------------------------------------------------

@app.command()
def audit(
    run_id:  str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show quality audit for a discovery run."""
    from salva_core.evaluation import build_audit_report
    try:
        report = build_audit_report(run_id)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    if as_json:
        typer.echo(json.dumps(report.model_dump(mode="json"), default=str))
    else:
        d = report.model_dump(mode="json")
        typer.echo(f"run_id           : {run_id}")
        typer.echo(f"qualified_count  : {d.get('qualified_count', 0)}")
        typer.echo(f"avg_score        : {d.get('avg_score', 0.0):.3f}")
        typer.echo(f"rounds           : {d.get('round_count', 0)}")
        typer.echo(f"top_sources      : {', '.join(d.get('top_sources', [])[:5])}")


# ---------------------------------------------------------------------------
# salva pilot
# ---------------------------------------------------------------------------

@app.command()
def pilot(
    run_id:           str,
    max_suggestions:  int  = typer.Option(5),
    as_json:          bool = typer.Option(False, "--json"),
) -> None:
    """Get next-step search recommendations based on a run."""
    from salva_core.navigation import build_pilot_advice
    from salva_core.persistence import get_run
    from salva_core.schemas import DiscoveryRequest, PilotRequest

    run = get_run(run_id)
    if run is None:
        typer.echo(f"Run not found: {run_id}", err=True)
        raise typer.Exit(1)

    try:
        pilot_request = PilotRequest(
            run_id=run_id,
            discovery=DiscoveryRequest.model_validate(run.get("request", {})),
            max_suggestions=max_suggestions,
        )
        advice = build_pilot_advice(pilot_request)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    if as_json:
        typer.echo(json.dumps(advice.model_dump(mode="json"), default=str))
    else:
        d = advice.model_dump(mode="json")
        typer.echo(f"Pilot advice for run: {run_id}")
        typer.echo("")
        for i, q in enumerate(d.get("suggested_queries", [])[:max_suggestions], 1):
            typer.echo(f"  {i}. {q}")
        if d.get("guidance_summary"):
            typer.echo(f"\n{d['guidance_summary']}")


# ---------------------------------------------------------------------------
# salva vocab list / show
# ---------------------------------------------------------------------------

@vocab_app.command("list")
def vocab_list(as_json: bool = typer.Option(False, "--json")) -> None:
    """List all registered domain vocabularies."""
    from core.domain_vocab import get_vocab, list_domains
    domains = list_domains()
    if as_json:
        typer.echo(json.dumps({
            "domains": [
                {
                    "name": d,
                    "signal_terms_count": len(get_vocab(d).signal_terms),
                    "source_hints_count": len(get_vocab(d).source_hints),
                    "synonym_groups_count": len(get_vocab(d).synonym_groups),
                }
                for d in domains
            ]
        }))
    else:
        typer.echo(f"{'domain':<20} {'signals':>8} {'sources':>8} {'synonyms':>9}")
        typer.echo("─" * 48)
        for d in sorted(domains):
            v = get_vocab(d)
            typer.echo(f"{d:<20} {len(v.signal_terms):>8} {len(v.source_hints):>8} {len(v.synonym_groups):>9}")


@vocab_app.command("show")
def vocab_show(
    domain:  str,
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show the full vocabulary for a domain."""
    from core.domain_vocab import get_vocab
    vocab = get_vocab(domain)
    if as_json:
        typer.echo(json.dumps({
            "domain": domain,
            "signal_terms": vocab.signal_terms,
            "source_hints": vocab.source_hints,
            "noise_terms": vocab.noise_terms,
            "synonym_groups": vocab.synonym_groups,
            "region_variants": vocab.region_variants,
        }, ensure_ascii=False))
    else:
        typer.echo(f"Domain: {domain}")
        typer.echo(f"\nSignal terms ({len(vocab.signal_terms)}):")
        for t in vocab.signal_terms:
            typer.echo(f"  {t}")
        typer.echo(f"\nSource hints ({len(vocab.source_hints)}):")
        for h in vocab.source_hints:
            typer.echo(f"  {h}")
        if vocab.synonym_groups:
            typer.echo(f"\nSynonym groups ({len(vocab.synonym_groups)}):")
            for k, vs in vocab.synonym_groups.items():
                typer.echo(f"  {k}: {', '.join(vs)}")
        if vocab.noise_terms:
            typer.echo(f"\nNoise terms ({len(vocab.noise_terms)}):")
            for t in vocab.noise_terms:
                typer.echo(f"  {t}")


# ---------------------------------------------------------------------------
# salva plugins / salva providers
# ---------------------------------------------------------------------------

@app.command()
def plugins(as_json: bool = typer.Option(False, "--json")) -> None:
    """List available enrichment plugins."""
    from enrichment.plugins import list_plugin_descriptors

    items = list_plugin_descriptors()
    if as_json:
        typer.echo(json.dumps({"items": [p.model_dump(mode="json") for p in items]}))
    else:
        typer.echo(f"{'name':<15} {'enabled':<8} {'mode':<20} {'entity_types'}")
        typer.echo("─" * 70)
        for p in items:
            types_str = ", ".join(p.supported_entity_types[:4])
            typer.echo(f"{p.name:<15} {str(p.default_auto_enabled):<8} {p.execution_mode:<20} {types_str}")


@app.command()
def providers(as_json: bool = typer.Option(False, "--json")) -> None:
    """List available retrieval providers."""
    from retrieval.registry import list_provider_descriptors

    items = list_provider_descriptors()
    if as_json:
        typer.echo(json.dumps({"items": [p.model_dump(mode="json") for p in items]}))
    else:
        typer.echo(f"{'name':<15} {'kind':<15} {'status':<10}")
        typer.echo("─" * 45)
        for p in items:
            typer.echo(f"{p.name:<15} {p.kind:<15} {p.status:<10}")


# ---------------------------------------------------------------------------
# salva graph export
# ---------------------------------------------------------------------------

@graph_app.command("export")
def graph_export(
    run_id:  str,
    fmt:     str  = typer.Option("hif", "--format", "-f", help="Output format: hif or dot"),
    out:     str  = typer.Option("", "--out", "-o", help="Output file path (default: stdout)"),
) -> None:
    """Export the entity/relation graph of a run as HIF JSON or DOT."""
    from salva_core.persistence import get_run

    run = get_run(run_id)
    if run is None:
        typer.echo(f"Run not found: {run_id}", err=True)
        raise typer.Exit(1)

    entities = run.get("entities", [])
    relations = run.get("relations", [])

    if fmt == "dot":
        output = _build_dot(run_id, entities, relations)
    else:
        output = json.dumps(_build_hif(run_id, entities, relations), ensure_ascii=False, indent=2)

    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(output)
        typer.echo(f"Written to {out}", err=True)
    else:
        typer.echo(output)


def _build_hif(run_id: str, entities: list, relations: list) -> dict:
    nodes = [
        {
            "id": e.get("entity_id") or e.get("title", "").replace(" ", "_"),
            "attrs": {
                "title":       e.get("title"),
                "entity_type": e.get("entity_type"),
                "domain":      e.get("domain"),
                "score":       e.get("score") or e.get("confidence"),
                "source_url":  (e.get("source_urls") or [None])[0],
            },
        }
        for e in entities
    ]
    edges = [
        {
            "source": r.get("subject_id") or r.get("source_entity_id"),
            "target": r.get("object_id") or r.get("target_entity_id"),
            "type":   r.get("relation_type") or r.get("type"),
            "attrs":  {"weight": r.get("weight", 1.0)},
        }
        for r in relations
    ]
    return {"run_id": run_id, "format": "hif", "nodes": nodes, "edges": edges}


def _build_dot(run_id: str, entities: list, relations: list) -> str:
    lines = [f'digraph "{run_id}" {{', '  rankdir=LR;']
    for e in entities:
        nid = (e.get("entity_id") or e.get("title", "node")).replace('"', '\\"')
        label = (e.get("title") or nid).replace('"', '\\"')
        score = e.get("score") or e.get("confidence") or 0.0
        lines.append(f'  "{nid}" [label="{label}\\n{score:.2f}"];')
    for r in relations:
        src = (r.get("subject_id") or r.get("source_entity_id") or "").replace('"', '\\"')
        tgt = (r.get("object_id") or r.get("target_entity_id") or "").replace('"', '\\"')
        rel = r.get("relation_type") or r.get("type") or "related"
        if src and tgt:
            lines.append(f'  "{src}" -> "{tgt}" [label="{rel}"];')
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# salva topology
# ---------------------------------------------------------------------------

@app.command()
def topology(
    market:   Annotated[str, typer.Option("--market",   "-m", help="Target market / region")],
    industry: Annotated[str, typer.Option("--industry", "-i", help="Industry or topic")],
    objective:          str = typer.Option("find_companies",   help="Discovery objective"),
    max_results:        int = typer.Option(50,                 help="Expected max results"),
    preset:             str = typer.Option("",                 help="Experience preset"),
    as_json: bool           = typer.Option(False, "--json",    help="Output raw JSON"),
) -> None:
    """Probe query topology and get recommended route."""
    from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, TopologyProbeRequest
    from salva_core.topology import build_topology_probe_response

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

    if as_json:
        typer.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    else:
        p = result.probe
        typer.echo(f"topology       : {p.topology}")
        typer.echo(f"confidence     : {p.confidence:.2f}")
        typer.echo(f"reasoning     : {p.reasoning}")
        typer.echo(f"\nrecommended_route: {result.plan.route_name}")
        typer.echo(f"strategy_bias : {result.plan.strategy_bias}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def _spinner(message: str, suppress: bool):
    if suppress:
        yield
        return
    try:
        from rich.console import Console
        console = Console(stderr=True)
        with console.status(message):
            yield
    except ImportError:
        typer.echo(message, err=True)
        yield


def _print_run_summary(entities, meta):
    typer.echo(f"\nrun_id    : {meta.get('run_id', '—')}")
    typer.echo(f"domain    : {meta.get('domain', '—')}")
    typer.echo(f"qualified : {meta.get('qualified_count', 0)} / {meta.get('raw_count', 0)}")
    typer.echo(f"rounds    : {meta.get('rounds', 0)}")
    typer.echo(f"seeds     : {meta.get('memory_seeds_used', 0)} from memory")
    typer.echo("")
    for i, e in enumerate(entities, 1):
        title = e.title or "(no title)"
        conf  = e.confidence
        url   = e.source_urls[0] if e.source_urls else "—"
        typer.echo(f"  {i:>3}. [{conf:.2f}] {title}")
        typer.echo(f"        {url}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
