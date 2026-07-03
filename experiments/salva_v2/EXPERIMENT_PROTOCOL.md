# Experiment Protocol — Claude Code + Haiku, bare search vs +Salva MCP

**Status:** Protocol design only. No arm has been executed under this
protocol yet — execution is `salva-p3-execute-arms`.

## 0. What this experiment is actually trying to answer

Not "Salva vs an unspecified agent" (that was E10's framing, and it never
named which agent/model ran the agent-only side). The actual milestone,
stated directly by the project owner: **does Claude Code, invoking Haiku,
using Salva as an MCP tool, achieve real/effective business outcomes across
multiple target scenarios** — compared to the same Claude Code + Haiku combo
working without Salva. Every metric and judgment call below is designed to
answer that specific question, not a generic retrieval-quality benchmark.

Hard constraint carried through every arm: **no paid tools, ever.** No paid
search APIs, no paid MCP services, no paid LLM calls beyond what Claude
Code's own Haiku access already provides. This is why the "swap in a paid
provider to isolate provider quality" arm that appears in earlier analysis
of this project does NOT appear here — see Arm D below, which answers the
same underlying question using the free-provider isolation data from
`salva-p2-diagnostic-isolation` instead.

## 1. Primary arms (required — this is the hard deliverable of Phase 3)

### Arm A — Claude Code + Haiku, bare web search

A Haiku-model agent (spawned via the `Agent` tool with `model: "haiku"`, or
an equivalent Haiku-backed Claude Code session) is given each task's query
in natural language, with **no Salva MCP tool available** — only its
built-in `WebSearch`/`WebFetch` capability. Prompt template:

```
You are researching a business question. Use web search to find the answer.
Question: [derived from the task's intent — see Section 3 "Query phrasing"]
Report: what you found, with source URLs for each claim.
```

Isolation note: subagents spawned via the `Agent` tool inherit a tool set
determined by their agent-type definition, which can include MCP tools if
any are connected to the session. To keep Arm A genuinely bare, either (a)
run it in a session/agent-type with no Salva MCP server registered at all,
or (b) explicitly instruct the agent not to use any `salva_*` tool if one
happens to be available, and verify in the transcript that it didn't. Prefer
(a) — structural isolation over instruction-following — whenever practical.

### Arm B — Claude Code + Haiku, with Salva MCP tool available

Same Haiku-model agent setup, but with Salva's MCP server registered for
the session and available as a tool. **Prerequisite the executor must do
first** (not yet done as of this protocol being written — verify before
assuming it's ready):

1. Confirm the venv has the `mcp` extra installed: `.venv/bin/python -c "import mcp"` should succeed (it does, per `salva-p1-ddgs-install-verify`'s `dev` extra fix pulling in `mcp>=1.0.0`).
2. Register the server. Project-scoped `.mcp.json` at the salva repo root (create if it doesn't exist):
   ```json
   {
     "mcpServers": {
       "salva": {
         "command": "/Volumes/Astoria/Projects/salva/.venv/bin/python",
         "args": ["-m", "apps.mcp"]
       }
     }
   }
   ```
   Use the venv's absolute python path, not a bare `python3` — a bare
   `python3` on `PATH` will not have `salva_core`/`mcp` installed and the
   server will fail to start.
3. Restart/reconnect the Claude Code session (or the tool-search mechanism)
   so the new MCP server's tools become available before spawning Arm B's
   agent.
4. Verify at least one tool call succeeds (e.g. `salva_providers`, which
   needs no arguments and does no live retrieval) before trusting Arm B's
   results — a silently-disconnected MCP server would make Arm B
   indistinguishable from Arm A, which would invalidate the comparison.

Prompt template mirrors Arm A but tells the agent the tool exists:

```
You are researching a business question. You have access to Salva MCP
tools (salva_discover, salva_topology, etc.) as well as your built-in web
search. Use whichever you judge best, including Salva if it helps.
Question: [same phrasing as Arm A]
Report: what you found, with source URLs / run_id for each claim.
```

Deliberately does NOT force the agent to use Salva — an agent that tries
Salva and abandons it for bare search when it's not helping is realistic
production behavior worth observing, not a protocol violation.

## 2. Secondary arms (optional — only run if Arm A/B is done and there's time; do not let this block Phase 3)

### Arm C — memory write_mode ablation

Re-run Arm B with `stability`/memory settings changed: `execution.memory.write_mode="none"` vs the current default `"quarantine"`. Isolates
whether memory compounding itself (VP9) contributes anything on top of the
base Salva pipeline, independent of the Arm A/B question. Same task set,
same metrics.

### Arm D — free-provider-combination ablation (replaces a paid-provider isolation arm)

`salva-p2-diagnostic-isolation` already found, on this exact task set's
themes, that `ddgs` outperforms the default chain's other free providers
head-to-head, and that `ddg_html`/`searxng_pool` are frequently non-
functional. Arm D re-runs a handful of Arm B tasks with `retrieval.providers`
explicitly pinned to just the empirically-best free combination (`searxng`
local + `ddgs`, skipping `ddg_html`/`marginalia`/`searxng_pool`) versus the
unpinned default chain, to quantify how much of Arm B's outcome is
attributable to provider selection versus the rest of the pipeline
(structuring, dedup, scoring). This is the free-only substitute for what
would otherwise require a paid provider swap to isolate — same underlying
question (how much does provider quality gate the ceiling), answered without
spending money.

## 3. Fixed variables (apply to every arm)

- **Same task set**: `experiments/salva_v2/task_set_v1.json`, all 18 tasks,
  every arm. Do not cherry-pick a subset per arm.
- **Same time window**: run all arms for a given task back-to-back (not
  Arm A for all 18 tasks on Monday and Arm B on Wednesday) — network/provider
  conditions drift, and E10 already got flagged for not being an equal-
  budget comparison; don't repeat that mistake here.
- **Same query budget per arm**: cap at a fixed number of tool calls/search
  queries per task (suggest 5 for Arm A's WebSearch calls; Salva's own
  internal round budget for Arm B is whatever `salva_discover`'s defaults
  are — record it, don't silently let Arm B use an unbounded budget while
  Arm A is capped).
- **Query phrasing**: derive the natural-language question fed to both arms
  directly and mechanically from each task's `intent` fields (market/
  industry/product/role/extra_keywords) in `task_set_v1.json` — do not hand-
  craft a differently-worded question per arm. The exact phrasing template:
  `"Find {extra_keywords joined}: {intent purpose implied by objective}."`
  e.g. for `single-01-tsmc`: *"Find TSMC 台積電: official website and
  contact information."* For `multihop-01-cncf-founders`: *"Find CNCF
  founding members Cloud Native Computing Foundation 2015: which companies
  were founding members?"*

## 4. Metrics to record per (task, arm) run

Not just P/R/F1 — the milestone is about real usefulness, not academic recall:

| Metric | How to compute | Why it matters here |
|---|---|---|
| `precision` | matched ground-truth entities / total entities reported | standard |
| `recall` | matched ground-truth entities / total ground-truth entities | standard |
| `f1` | harmonic mean of the above | standard |
| `requests_used` | count of search/tool calls the agent made | cost proxy — E21c's "19 requests, zero true positives" showed raw counts matter as their own signal, not just derived P/R/F1 |
| `latency_seconds` | wall-clock time from prompt to final answer | |
| `retrieval_health_distribution` | for Arm B only: tally of `ok`/`degraded`/`probe_failed` across any `salva_discover`/`salva_topology` calls made (the field added in `salva-p1-degraded-mode-signal`) | tells you whether a bad Arm B result was the pipeline's fault or an unlucky provider moment |
| `business_outcome_judgment` | **one human sentence per (task, arm)**: did this result actually achieve something a real user could act on? (e.g. "yes — got a real, currently-live contact page" / "no — found the right company but no usable contact info" / "no — result was thin/uncertain but honestly reported as such") | this is the metric that actually answers the milestone question; P/R/F1 alone can't distinguish "confidently wrong" from "honestly uncertain," which matters a lot given `multihop-03-naturehike-dach`'s deliberately-thin ground truth |

`business_outcome_judgment` is explicitly qualitative and human-authored, not
automated — do not try to derive it purely from the P/R/F1 numbers. This
is a deliberate design choice: a task like `multihop-03-naturehike-dach`
could score low P/R/F1 in both arms while one arm's answer ("coverage is
genuinely thin, here's what little I found") is a much better real business
outcome than the other's confident-sounding wrong answer.

## 5. Data recording format

Per `(task_id, arm)`, record a JSON object appended to
`experiments/salva_v2/raw_results/<task_id>_<arm>.json` (created by the
execution card, not this one) with at minimum:

```json
{
  "task_id": "single-01-tsmc",
  "arm": "A",
  "timestamp": "...",
  "reported_entities": [{"name": "...", "url": "...", "claim": "..."}],
  "requests_used": 3,
  "latency_seconds": 12.4,
  "retrieval_health_distribution": {"ok": 1, "degraded": 0, "probe_failed": 0},
  "precision": 1.0,
  "recall": 1.0,
  "f1": 1.0,
  "business_outcome_judgment": "yes -- found the real official contact page"
}
```

## 6. Questions each arm needs to answer (keep these explicit, don't let the raw numbers speak for themselves without addressing them directly in Phase 3's analysis)

1. Across all 18 tasks, does Arm B win, lose, or tie against Arm A more
   often, and is there a pattern by `difficulty_tier` (e.g. does Salva help
   more on `multi_hop` where its structured/hypergraph representation should
   matter more, or is it uniform)?
2. On tasks Arm B loses, is it because Salva returned nothing useful, or
   because it returned something actively worse than what bare search found?
3. Does `retrieval_health` correlate with Arm B's losses — i.e. are Arm B's
   worst results concentrated in runs where the pipeline itself flagged
   `degraded`/`probe_failed`, or does it lose even on `ok`-health runs (which
   would point at a scoring/structuring problem rather than a retrieval
   problem)?
4. What does `requests_used` say about efficiency, independent of whether
   the final answer was right — is Arm B using its budget more efficiently
   even when it doesn't outright win?
5. (If Arm C run) Does disabling memory write actually change anything on
   this task set, or is memory compounding a no-op here (task set is single-
   shot per task, not repeated queries on the same domain, so this may
   legitimately show no effect — that's a valid finding, not a failure of
   the protocol).
6. (If Arm D run) How much of Arm B's outcome is attributable to provider
   selection alone versus the rest of the pipeline?

## 7. Non-goals

- Not a formal statistical significance test — 18 tasks is enough to move
  past "one anecdote," per `salva-p2-task-set-design`'s own reasoning, not
  enough for p-values. Report win/loss/tie counts and patterns, not
  confidence intervals.
- Not re-litigating whether the free providers themselves are good enough
  in general — that's what `salva-p2-diagnostic-isolation` already covered;
  this protocol is about the Arm A vs Arm B question specifically.
- Arm C/D are explicitly optional; do not delay delivering Arm A/B results
  in order to also complete them.
