# Salva Specs

Canonical contract docs for callers, agents, and maintainers.

Use these first when debugging or changing behavior:

| Spec | What it covers |
|------|----------------|
| [route-catalog.md](route-catalog.md) | objective → experience profile → strategy rotation → call surfaces |
| [topology-probe.md](topology-probe.md) | probe-driven topology classification and route planning |
| [planner.md](planner.md) | round budgets, clarification policy, and research planning |
| [preprompt.md](preprompt.md) | ambiguity scoring, question shaping, and goal normalization |
| [retrieval-contract.md](retrieval-contract.md) | retrieval modes, quality gating, fallback, parallel expansion |
| [provider-contract.md](provider-contract.md) | provider kinds, config fields, health, pacing, locality |
| [testing-matrix.md](testing-matrix.md) | how to choose the minimum regression scope |
| [hold-walk.md](hold-walk.md) | relation-aware graph walk over a run snapshot |
| [hold-backends.md](hold-backends.md) | Hold backend evaluation catalog |
| [semantic-memory.md](semantic-memory.md) | query-family semantic search and backend catalog |
| [execution-context.md](execution-context.md) | campaign isolation, persistence, memory quarantine/promotion, cache intent |
| [semantic-memory.md](semantic-memory.md#benchmark) | semantic backend benchmark and comparison surface |
| [usage-telemetry.md](usage-telemetry.md) | tenant-aware usage aggregation over runs and jobs |
| [job-storage.md](job-storage.md) | tenant-aware job record contract |
| [quota-rate-limit.md](quota-rate-limit.md) | tenant quota evaluation and enforcement |
| [error-contract.md](error-contract.md) | HTTP/MCP/job error mapping and persisted failure data |
| [debug-playbook.md](debug-playbook.md) | how to trace failures and decide the next fix |

Rules:
- Specs define behavior, not history.
- Docs may explain why; specs define what must be true.
- If a change alters observable behavior, update a spec first.
