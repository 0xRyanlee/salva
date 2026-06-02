# Planner Spec

This spec defines the planning layer between topology probe and execution.

## Purpose

The planner converts a goal into an executable research plan.
It decides:

- how many rounds to run
- what each round should try to learn
- when to stop
- when to replan
- when to ask the caller for clarification

## Source of truth

- Planner API: `POST /v1/planner`
- Implementation: `salva_core/planner.py`

## Inputs

The planner receives:

- the discovery request
- or a minimal `objective + intent` input that is normalized into a discovery
  request
- the topology probe result
- the route plan
- clarification policy output

## Outputs

The planner should emit:

- `probe`
- `route_plan`
- `preprompt`
- `plan`
- `experience_plan`

The plan should also be explicit about:

- `clarification_mode`
- `round_budget`
- `needs_clarification`
- `clarifying_questions`
- `replan_triggers`
- `stop_conditions`

## Planning rules

- `structured` and `vertical` searches should use smaller round budgets and
  tighter stop conditions.
- `broad` and `distributed` searches should use larger budgets and wider fanout.
- `semantic_union` searches should preserve multiple evidence trails.
- `mixed` searches may require clarification before execution.

## Round planning

The plan should include:

- `round_budget`
- `round_goals`
- `completeness_target`
- `confidence_target`
- `source_pack`
- `strategy_bias`
- `fanout_policy`
- `merge_policy`
- `replan_triggers`
- `stop_conditions`

## Clarification integration

If the preprompt layer marks the request as ambiguous:

- the planner should include the clarification questions in its output
- the plan should still include fallback assumptions
- the planner should not dead-end if the caller skips clarification
- the planner should prefer agent-mediated clarification over local LLM calls

## Optional LLM preprompt

- When `SALVA_PLANNER_USE_LLM` is enabled and an LLM backend is reachable,
  the preprompt layer may ask the model to shape the clarification questions.
- If the LLM is unavailable or returns invalid JSON, fall back to the rule-based
  preprompt output.

## Debug checks

- If the runtime keeps over-searching, round budget is too high.
- If the runtime keeps under-searching, completeness or confidence targets are too low.
- If the runtime asks too many questions, clarification thresholds are too aggressive.
- If the runtime never replans, replan triggers are too weak.

Related specs:

- [preprompt.md](preprompt.md)
- [topology-probe.md](topology-probe.md)
- [retrieval-contract.md](retrieval-contract.md)
- [route-catalog.md](route-catalog.md)
