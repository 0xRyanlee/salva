#!/usr/bin/env python3
"""Collect one reproducible Salva observation without cross-run memory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from salva_core.schemas import (
    DiscoveryIntent,
    DiscoveryRequest,
    DomainHints,
    EnrichmentPolicy,
    ExecutionContext,
    MemoryPolicy,
    RetrievalPolicy,
)
from salva_core.service import execute_discovery


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--market", default="Germany Austria Switzerland")
    parser.add_argument("--industry", default="outdoor equipment")
    parser.add_argument("--product", default="camping equipment")
    parser.add_argument("--role", default="distributor")
    parser.add_argument(
        "--keywords",
        default="Naturehike,importer,wholesale,retailer,buying group",
    )
    parser.add_argument("--max-results", type=int, default=30)
    parser.add_argument("--qualify-threshold", type=float, default=0.15)
    parser.add_argument("--campaign-id", default="naturehike-dach-2026")
    args = parser.parse_args()

    request = DiscoveryRequest(
        objective="find_leads",
        output_profile="company_profile",
        max_results=args.max_results,
        qualify_threshold=args.qualify_threshold,
        intent=DiscoveryIntent(
            market=args.market,
            industry=args.industry,
            product=args.product,
            role=args.role,
            extra_keywords=[
                value.strip()
                for value in args.keywords.split(",")
                if value.strip()
            ],
            constraints={
                "max_rounds": args.rounds,
                "results_per_round": args.max_results,
            },
            domain_hints=DomainHints(
                signal_terms=[
                    "distributor",
                    "importer",
                    "wholesale",
                    "dealer network",
                    "retail group",
                    "buying group",
                    "outdoor brands",
                    "camping",
                ],
                noise_terms=[
                    "showroom",
                    "marketplace",
                    "consumer review",
                    "job",
                ],
            ),
        ),
        retrieval=RetrievalPolicy(
            mode="resilient",
            request_timeout=10,
            request_delay=0.2,
        ),
        enrichment=EnrichmentPolicy(mode="disabled"),
        execution=ExecutionContext(
            campaign_id=args.campaign_id,
            continuation_id=f"salva-r{args.rounds}",
            persistence="none",
            memory=MemoryPolicy(read_scope="none", write_mode="none"),
        ),
    )
    entities, relations, telemetry, meta, attempts = execute_discovery(request)
    output = {
        "condition": "salva",
        "round": args.rounds,
        "request": request.model_dump(mode="json"),
        "meta": meta,
        "entities": [item.model_dump(mode="json") for item in entities],
        "relations": [item.model_dump(mode="json") for item in relations],
        "telemetry": [item.model_dump(mode="json") for item in telemetry],
        "source_attempts": [item.model_dump(mode="json") for item in attempts],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output),
        "rounds": args.rounds,
        "raw_count": meta.get("raw_count", 0),
        "qualified_count": meta.get("qualified_count", 0),
        "entity_count": len(entities),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
