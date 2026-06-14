# Salva Execution Isolation and Adversarial Audit

Date: 2026-06-08

## Decision

Salva remains a tool called by an agent. Isolation is not exclusively an agent
problem: the agent selects scope, while the tool must enforce scope at the
persistence and memory boundary. Relying on prompt discipline alone cannot stop
cross-run leakage or memory poisoning.

One Salva call can perform multiple retrieval rounds without filesystem cache.
The previous contamination surface was the shared SQLite query-family memory,
which was read globally by objective/domain and written after every run.

## Implemented Architecture

The implemented native contract is `DiscoveryRequest.execution`:

- cross-run read defaults to `none`;
- writes default to `quarantine`;
- only `campaign_promoted` can reuse reviewed memory in the same campaign;
- `persistence=none` performs no database or memory write;
- campaign and continuation IDs are stored and filterable;
- caller `source_hints` no longer become trusted-source whitelist entries;
- API, CLI, MCP, SDK, worker, migration, and tests use the same contract.

Alternative architecture options remain available:

1. **Per-campaign database**: strongest physical isolation, simple deletion and
   export, but higher operational overhead and poor cross-campaign analytics.
2. **Central database with enforced scope**: implemented option; easier
   operations and audit, but requires strict query filters and authorization.
3. **External orchestrator workspace**: agent platform owns isolated stores and
   invokes Salva statelessly; useful for enterprise deployments, but pushes more
   integration work onto every caller.

## Risks and Countermeasures

| Risk | Attack or failure | Mitigation A | Mitigation B |
|---|---|---|---|
| Cross-campaign leakage | campaign B reads campaign A query terms | campaign-filtered reads | separate DB/store per campaign |
| Memory poisoning | malicious page becomes a future seed | quarantine then explicit promotion | signed provenance plus reviewer/quality gate |
| Source trust spoofing | caller adds its domain to `source_hints` | hints never alter trusted sources | server-side trust registry with admin-only updates |
| Indirect prompt injection | retrieved page contains instructions | treat retrieved text as data, never tool authority | isolate extraction model/tool permissions and scan outputs |
| Cache contamination | stale artifacts reused under a new target | ephemeral default | content-addressed cache keyed by request, provider, parser, and policy version |
| Tenant/session bleed | tenant ID used only for accounting | authorize campaign/tenant on every read/write | physical tenant database or row-level security |
| Provider drift | repeated run returns different SERP or zero results | frozen-corpus replay benchmark | multi-provider quorum and raw response snapshots |
| False qualification | keyword-heavy retail page scores as a distributor | channel-type classifier and minimum evidence schema | human review queue before promotion/export |
| Path injection | agent supplies arbitrary cache/database path | expose IDs, not paths | deployment-controlled MCP roots and allowlists |
| Irreproducible claims | curated results omit raw noise | raw SERP/result capture | experiment manifest with budgets, versions, timestamps, and hashes |

The OWASP prompt-injection guidance recommends layered controls rather than
treating prompt text as a security boundary. OWASP Agent Memory Guard explicitly
targets persistent memory poisoning. MCP roots provide a standard mechanism for
declaring filesystem boundaries, while LangGraph's `thread_id` demonstrates the
value of explicit state identifiers. MLflow and DVC show the complementary
pattern for run metadata, metrics, and versioned artifacts.

References:

- [OWASP LLM Prompt Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
- [OWASP Agent Memory Guard](https://owasp.org/www-project-agent-memory-guard/)
- [MCP Roots specification](https://modelcontextprotocol.io/specification/2025-06-18/client)
- [LangGraph persistence and threads](https://langchain-ai.github.io/langgraph/cloud/concepts/threads/)
- [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)
- [DVC experiment management](https://dvc.org/doc/user-guide/experiment-management)

## Historical Baseline Audit

The old `scripts/compare_agent_mode.py` and its test appeared only in commit
`5073ff1` on 2026-06-03. It created an empty synthetic run when no run ID was
provided, then called `build_pilot_advice()` twice against the same run. The test
mocked advice, route, and experience planning and asserted only output shape.
It did not execute Agent-only research or Salva retrieval.

No prior comparison JSON, Markdown, or chart artifact existed. The replacement
reports pooled recall against a declared reference set and warns when that set
is a post-hoc verified union rather than predeclared external ground truth.

Historical databases are retained as operational context, not A/B evidence:

| Database | Runs | Query memory | Non-empty content nodes | Avg success | Naturehike hits |
|---|---:|---:|---:|---:|---:|
| `data/salva_runtime.db` | 331 | 618 | 0 | 0.0593 | 0 |
| `data/salva.db` | 84 | not used for comparison | not used | not used | 0 |

The 331 runtime runs break down into 162 `find_companies`, 123 `find_leads`,
37 `find_events`, 6 `find_partnership_signals`, and 3
`find_market_activity`. They cannot be compared to the Naturehike task because
there is no matching target, budget, ground truth, or raw-result capture.

## Adversarial Test Result

`experiments/agent_vs_salva/isolation-report.json` passed all six checks:

- poisoned promoted memory did not cross campaign boundaries;
- clean promoted memory remained reusable;
- quarantined memory was blocked from `campaign_promoted`;
- `campaign_all` could explicitly read quarantine;
- `read_scope=none` read nothing;
- caller source hints could not self-declare trust.

## Remaining Work

Two viable next implementations:

1. **Review workflow first**: add reviewer identity, promotion reason, provenance
   hash, rejection state, and promotion audit log.
2. **Artifact isolation first**: implement content-addressed raw response storage,
   TTL cleanup, immutable manifests, and frozen-corpus replay.

For production multi-tenancy, choose one of:

1. central PostgreSQL with tenant/campaign authorization and row-level security;
2. tenant-specific database and artifact bucket with no global legacy read mode.
