# Topology Probe Spec

This spec defines the probe layer that sits between user intent and route selection.

## Purpose

Salva should not assume the caller already knows the best retrieval shape.
Before committing to a route, the runtime should probe the target space and
infer the most likely retrieval topology, then choose a plan that fits that shape.

## Source of truth

- Probe output API: `POST /v1/topology/probe`
- Planner API: `POST /v1/planner`
- Route planning API: `salva_core/topology.py`
- Implementation: `salva_core/topology.py`, `salva_core/planner.py`, `salva_core/mode_resolver.py`, `apps/api/main.py`

## Probe lifecycle

1. Accept the user's goal and minimal context.
2. Generate a low-cost probe query family.
3. Classify the response shape.
4. Emit a route plan with topology, source bias, and strategy guidance.
5. Execute the route and re-plan if feedback diverges from the probe.

## Topology classes

The probe stage should classify the target into one or more of:

- `vertical`
- `broad`
- `concentrated`
- `distributed`
- `semantic_union`
- `structured`
- `unstructured`
- `mixed`

These classes describe the retrieval shape, not the business domain.

## Probe outputs

The probe layer should emit a structured plan that includes:

- `topology`
- `confidence`
- `recommended_route`
- `recommended_objective`
- `source_pack`
- `strategy_bias`
- `fanout_policy`
- `merge_policy`
- `error_surface`

## Planning rules

- `structured` and `vertical` shapes should bias toward source packs with explicit schema.
- `broad` and `distributed` shapes should bias toward wider fanout and looser merge.
- `concentrated` shapes should bias toward strict dedupe and higher precision.
- `semantic_union` shapes should preserve multiple evidence trails and compare them jointly.
- `mixed` shapes may require multi-tool parallelism and re-planning.

## Error shape

The probe and planning layers should not collapse all failures into generic `500`s.
They should surface:

- `stage`
- `code`
- `route`
- `provider`
- `topology`
- `query`
- `message`
- `actionable_hint`

## Debug checks

- If a caller keeps choosing the wrong route, inspect the probe classification first.
- If a result set is too noisy, verify whether the topology was misclassified as `broad` or `mixed`.
- If a structured target returns unstructured results, the source pack or merge policy is wrong.
- If repeated runs never improve, inspect whether the probe stage is feeding back into route planning.

Related specs:

- [planner.md](planner.md)
- [preprompt.md](preprompt.md)
- [retrieval-contract.md](retrieval-contract.md)
- [route-catalog.md](route-catalog.md)
- [provider-contract.md](provider-contract.md)
- [error-contract.md](error-contract.md)
