# Preprompt Spec

This spec defines the clarification layer that runs before planner execution
when the user's goal is ambiguous or high-risk.

## Purpose

Preprompt is not retrieval. It exists to normalize the user's request and to
ask only the minimum number of clarifying questions needed to make the plan
reliable.

## Source of truth

- Preprompt behavior: `salva_core/planner.py`
- Planner API: `POST /v1/planner`

## Responsibilities

- Detect ambiguity and missing decision inputs.
- Normalize the goal into a canonical brief.
- Ask at most 3 concrete clarification questions.
- Provide safe fallback assumptions if the caller skips clarification.
- Optionally use an LLM for question shaping when enabled and available.
- The optional LLM preprompt is gated by `SALVA_PLANNER_USE_LLM`.

## Clarification signals

The clarification layer should look for:

- missing output shape
- missing precision vs. coverage preference
- missing time window
- missing source preferences
- high topology uncertainty

## Output fields

The preprompt result should include:

- `clarification_needed`
- `clarification_mode`
- `ambiguity_score`
- `risk_level`
- `normalized_goal`
- `clarifying_questions`
- `assumptions_if_skip`
- `llm_used`
- `llm_model`
- `llm_message`

## Policy

- Ask only when the decision materially changes planning.
- Prefer 1-3 concrete questions over broad interviews.
- If the caller does not answer, continue with explicit assumptions.
- Keep the output stable enough to inspect in logs and tests.
- Prefer agent-mediated clarification when the caller can ask the user directly.
- Reserve LLM-assisted shaping for the optional `SALVA_PLANNER_USE_LLM` path.

## Related specs

- [planner.md](planner.md)
- [topology-probe.md](topology-probe.md)
- [error-contract.md](error-contract.md)
