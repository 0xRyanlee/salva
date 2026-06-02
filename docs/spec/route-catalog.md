# Route Catalog Spec

This spec defines the public decision surface for choosing a Salva pipeline.

## Purpose

The route catalog exists so a caller can resolve:

`objective -> experience_profile -> strategy_rotation -> recommended_call_surfaces`

before calling `discover`, `jobs`, or `pilot`.

In the topology-probe flow, the route catalog is selected after the probe stage
classifies the target shape.

## Source of truth

- API: `GET /v1/routes`
- API: `GET /v1/routes/{route_name}`
- Implementation: `salva_core/routes.py`
- Manifest exposure: `bay/manifest.py`

## Canonical route entries

- `quick_scan`
- `lead_focus`
- `event_discovery`
- `company_research`
- `deep_investigation`
- `platform_integrator`

## Required fields

Every route entry must include:

- `name`
- `title`
- `description`
- `experience_profile`
- `objective`
- `output_profile`
- `retrieval_mode`
- `enrichment_mode`
- `strategy_rotation`
- `recommended_call_surfaces`
- `usage_notes`
- `notes`
- `source_path`

## Strategy rotations

- `quick_scan` -> `dive`
- `lead_focus` -> `dive`, `anchor`
- `event_discovery` -> `radar`, `anchor`
- `company_research` -> `dive`, `anchor`, `radar`
- `deep_investigation` -> `anchor`, `radar`, `pirate`
- `platform_integrator` -> `dive`, `anchor`

## Debug checks

- If the caller has a good objective but the wrong route, inspect topology probe output first.
- If a caller cannot decide which pipeline to use, route catalog resolution should be the first lookup.
- If an objective resolves to the wrong profile, fix the mapping in `salva_core/routes.py` and the preset metadata together.
- If a route entry is missing a call surface, the API contract is incomplete and must be updated before release.
