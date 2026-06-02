#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from salva_core.mode_resolver import resolve_experience_plan
from salva_core.navigation import build_pilot_advice
from salva_core.persistence import get_run, persist_discovery_run
from salva_core.routes import resolve_route_entry
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, PilotRequest


def _default_db_path() -> str:
    return str(Path(tempfile.gettempdir()) / "salva_compare_demo.db")


def _make_request(objective: str, market: str, industry: str) -> DiscoveryRequest:
    return DiscoveryRequest(
        objective=objective,
        intent=DiscoveryIntent(market=market, industry=industry),
    )


def _ensure_run(
    *,
    db_path: str,
    run_id: str | None,
    objective: str,
    market: str,
    industry: str,
) -> str:
    if run_id:
        existing = get_run(run_id, path=db_path)
        if existing is None:
            raise KeyError(f"run not found: {run_id}")
        return run_id

    request = _make_request(objective, market, industry)
    meta = {
        "qualified_count": 0,
        "raw_count": 0,
        "provider_kinds": [],
        "experience_profile": resolve_experience_plan(request).profile,
    }
    return persist_discovery_run(
        request=request,
        entities=[],
        relations=[],
        telemetry=[],
        meta=meta,
        source_attempts=[],
        path=db_path,
    )


def compare_modes(
    *,
    db_path: str,
    run_id: str | None,
    market: str,
    industry: str,
    objective: str,
    agent_market: str,
    agent_industry: str,
    agent_objective: str,
    max_suggestions: int = 5,
) -> dict[str, Any]:
    resolved_run_id = _ensure_run(
        db_path=db_path,
        run_id=run_id,
        objective=objective,
        market=market,
        industry=industry,
    )
    run = get_run(resolved_run_id, path=db_path)
    if run is None:
        raise KeyError(f"run not found: {resolved_run_id}")

    discovery = DiscoveryRequest.model_validate(run.get("request", {}))
    direct_request = PilotRequest(
        run_id=resolved_run_id,
        discovery=discovery,
        max_suggestions=max_suggestions,
    )
    agent_request = direct_request.model_copy(
        update={
            "market": agent_market,
            "industry": agent_industry,
            "objective": agent_objective,
        }
    )

    direct = build_pilot_advice(direct_request, path=db_path)
    agent = build_pilot_advice(agent_request, path=db_path)
    plan = resolve_experience_plan(discovery)
    direct_route = resolve_route_entry(direct.recommended_experience_profile)
    agent_route = resolve_route_entry(agent.recommended_experience_profile)

    return {
        "run_id": resolved_run_id,
        "base_plan": plan.model_dump(mode="json"),
        "direct": {
            "objective": direct.objective,
            "experience_profile": direct.recommended_experience_profile,
            "retrieval_mode": direct.recommended_retrieval_mode,
            "enrichment_mode": direct.recommended_enrichment_mode,
            "output_profile": direct.recommended_output_profile,
            "next_queries": direct.next_queries[:max_suggestions],
            "guidance_summary": direct.guidance_summary,
            "route": direct_route.model_dump(mode="json") if direct_route else None,
        },
        "agent": {
            "objective": agent.objective,
            "experience_profile": agent.recommended_experience_profile,
            "retrieval_mode": agent.recommended_retrieval_mode,
            "enrichment_mode": agent.recommended_enrichment_mode,
            "output_profile": agent.recommended_output_profile,
            "next_queries": agent.next_queries[:max_suggestions],
            "guidance_summary": agent.guidance_summary,
            "route": agent_route.model_dump(mode="json") if agent_route else None,
        },
    }


def _print_report(report: dict[str, Any]) -> None:
    print(f"Run: {report['run_id']}")
    print(f"Base objective: {report['base_plan']['objective']}")
    print("")
    for label in ("direct", "agent"):
        block = report[label]
        print(label.upper())
        print(f"  objective          : {block['objective']}")
        print(f"  experience_profile  : {block['experience_profile']}")
        print(f"  retrieval_mode      : {block['retrieval_mode']}")
        print(f"  enrichment_mode     : {block['enrichment_mode']}")
        print(f"  output_profile      : {block['output_profile']}")
        route = block["route"]
        if route:
            print(f"  route_rotation      : {' -> '.join(route['strategy_rotation'])}")
        print("  next_queries:")
        for i, query in enumerate(block["next_queries"], 1):
            print(f"    {i}. {query}")
        if block["guidance_summary"]:
            print(f"  summary             : {block['guidance_summary']}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare direct vs agent-guided Salva advice.")
    parser.add_argument("--run-id", default=None, help="Existing run_id to compare against.")
    parser.add_argument("--db-path", default=_default_db_path(), help="SQLite path for run lookup/demo persistence.")
    parser.add_argument("--market", default="Germany", help="Base demo market or existing run context.")
    parser.add_argument("--industry", default="software", help="Base demo industry or existing run context.")
    parser.add_argument("--objective", default="find_leads", help="Base demo objective or existing run context.")
    parser.add_argument("--agent-market", default="Taiwan", help="Agent override market.")
    parser.add_argument("--agent-industry", default="hardware", help="Agent override industry.")
    parser.add_argument("--agent-objective", default="find_companies", help="Agent override objective.")
    parser.add_argument("--max-suggestions", type=int, default=5, help="How many suggestions to compare.")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text.")
    args = parser.parse_args()

    report = compare_modes(
        db_path=args.db_path,
        run_id=args.run_id,
        market=args.market,
        industry=args.industry,
        objective=args.objective,
        agent_market=args.agent_market,
        agent_industry=args.agent_industry,
        agent_objective=args.agent_objective,
        max_suggestions=max(1, args.max_suggestions),
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, default=str))
    else:
        _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
