# Frozen-Corpus Replay Harness

Board card: `salva-methodology-frozen-corpus-harness`.

## Why this exists

Every prior `experiments/salva_v2/*` pipeline experiment hit live network on
every run. Retrieval variance (which pages DDGS/SearXNG happen to return
*this second*) was mixed in with whatever gate/scorer/rerank/confidence
change was actually under test, so results weren't reproducible and at least
one experiment (memory compounding) needed 3 reruns to isolate its variable.

This harness freezes the retrieval layer: record raw provider results once,
replay them offline for as many downstream (scorer/gate/confidence) experiment
iterations as needed. **Only `record_fixtures.py` is allowed to touch the
network.** Everything else in this directory — and every future experiment
built on top of it — runs offline.

## What was reused vs. what had to be recorded

`experiments/salva_v2/raw_results/` (36 files) and `raw_results_rerun/`
(26 files) were checked first. They only contain the **final agent-reported
entities** from earlier Arm A (bare WebSearch)/Arm B (Salva MCP tool) runs —
no provider-level raw search responses. Neither the retrieval layer's exact
input/output nor the queries issued survive in that data, so they could not
be turned into fixtures. New fixtures had to be recorded from the live
pipeline; recording is disciplined to exactly what's needed (see below).

## Fixture format

The replay target is `retrieval.router.RoutedRetriever.search(query, n)` —
same granularity `core.controller.Retriever` (the Protocol production code
depends on) calls at, i.e. one already-deduped list of raw result dicts per
`(strategy, query)`. Not per-provider (ddgs/searxng/marginalia/...) — the
router's own provider fallback logic is part of what gets frozen, which is
fine because nothing downstream of `RoutedRetriever.search()` cares which
provider produced a result.

```
experiments/salva_v2/fixtures/
  <task_id>/
    _recorded_run_summary.json      # entities from the recording run, for compare
    dive/<query_hash>.json
    anchor/<query_hash>.json
    radar/<query_hash>.json
    pirate/<query_hash>.json        # only if that strategy was actually used
```

Each `<query_hash>.json`:

```json
{
  "task_id": "single-01-tsmc",
  "strategy": "dive",
  "query": "\"TSMC\" TW -blog -museum -review -job -news -report",
  "n": 10,
  "recorded_at": "2026-07-21T12:10:00+00:00",
  "results": [ {"title": "...", "url": "...", "snippet": "...", "engine": "...", "retrieval_instance": "..."} ]
}
```

The filename is a hash of the query (filesystem-safe key); lookups match on
the `query` field's exact string content, not the filename.

## How it plugs into the pipeline

`core/controller.py`'s `Retriever` Protocol is `search(query, n) -> list[dict]`
plus a `strategy` attribute. `salva_core/service.py` constructs 4
`RoutedRetriever`s (`dive`/`anchor`/`radar`/`pirate`) and passes them to
`SalvaController`. Neither file was modified. Instead:

- `recording_retriever.py::RecordingRetriever` wraps a real `RoutedRetriever`,
  passes every call through unchanged, and writes a fixture file per call.
- `replay_retriever.py::ReplayRetriever` implements the same shape
  (`strategy`, `last_attempts`, `search()`) and loads fixtures instead of
  hitting any provider.

Both are swapped in via `unittest.mock.patch("salva_core.service.RoutedRetriever", ...)`
around a plain `salva_core.service.execute_discovery(request)` call — no
production code path changes.

## Recording (touches the network — run sparingly, once per new task)

```bash
.venv/bin/python3 -m experiments.salva_v2.harness.record_fixtures --task-id single-01-tsmc
```

Notes:
- Multiple `--task-id` flags record several tasks in one process.
- `task_request.py` pins `retrieval.providers` to `ddgs` + `searxng`
  explicitly. Several experience profiles' `PROFILE_ROUTE_HINTS`
  (`salva_core/routes.py`) restrict the chain to `searxng`/`ddg_html`/
  `obscura_browser`, none of which are reliably reachable without a fully
  provisioned deployment (local SearXNG, working Obscura binary). `ddgs` is
  the provider `DDGS_BACKEND_DIAGNOSTIC.md` and the Arm D design already
  found reliable in this kind of environment. This override lives only in
  the harness's request builder — it does not change production defaults or
  profile routing.
- Writes fixture files for every `(strategy, query)` the run actually issued,
  plus `_recorded_run_summary.json` (entities from that run) for later diff.
- Re-run only for tasks that don't have fixtures yet, or whose downstream
  config change would generate genuinely new queries (see Known limitation
  below) — don't re-record everything just to be safe.

## Replay (never touches the network)

```bash
.venv/bin/python3 -m experiments.salva_v2.harness.run_replay --task-id single-01-tsmc --compare
```

`--compare` diffs the replayed entity titles against `_recorded_run_summary.json`.

### Proof it stays offline

`replay_retriever.py::no_network_guard()` is applied around every replay run:

1. Monkeypatches `socket.socket.connect` to raise `NetworkCallBlocked` for
   the duration of the call. Any code path that still tries to reach the
   network — a bug, or new code added outside the retriever layer — fails
   loudly instead of silently succeeding. That failure *is* the proof.
2. Sets `SEARXNG_ENABLED=false` for the duration, so `salva_core/topology.py`'s
   live environment probe (`salva_core/live_probe.py`) short-circuits to
   `None` instead of attempting a probe request that would otherwise hit the
   guard and abort the run.

Verified manually: with the guard active, `socket.socket().connect(...)`
raises `NetworkCallBlocked`; outside the guard, the same call proceeds
normally. `ReplayRetriever.search()` on a query with no matching fixture
raises `FixtureMissingError` (never falls back to empty/wrong data silently).

## End-to-end validation performed

Two tasks recorded and replayed:

| task_id | recorded (raw/qualified) | replayed (raw/qualified) | entity titles |
|---|---|---|---|
| `single-01-tsmc` | 4 / 3 | 4 / 3 | identical (MATCH) |
| `crosslang-01-tsmc` | 18 / 1 | 18 / 1 | identical (MATCH) |

Scores drift by a few thousandths between record and replay runs (e.g.
`0.465` → `0.435`) — expected, not a bug: `processing/scorer.py`'s recency
component (`w_recency`) is computed from wall-clock time at scoring time, so
a run replayed minutes after recording gets a slightly different recency
score for the same result. Entity identity/count/qualification is the
determinism contract this harness guarantees, not bit-identical floats.

## Known limitation

Round 2+ queries depend on `KeywordGraph.apply_telemetry()`, which is fed by
`result.qualified`/`relevance_score` — i.e. by the scorer. Query *generation*
itself (`keyword_graph.py`) has no randomness, so replay is exactly
deterministic as long as the downstream scorer/gate config matches what was
used during recording. If a future experiment changes scorer/gate behavior
in a way that alters which content_terms get fed back after round 1, round 2+
might request a query that was never recorded. `ReplayRetriever` surfaces
this as a loud `FixtureMissingError` listing what *was* recorded for that
`(task_id, strategy)`, rather than silently returning empty results — so a
missing fixture is visible and fixable (top up with one more
`record_fixtures.py` run), never a silent corruption of results.

## Files

- `fixture_store.py` — fixture read/write, keyed by `(task_id, strategy, query)`.
- `recording_retriever.py` — `RecordingRetriever`, live-network recording wrapper.
- `replay_retriever.py` — `ReplayRetriever`, `FixtureMissingError`, `no_network_guard()`.
- `task_request.py` — builds a `DiscoveryRequest` from a `task_set_v1`/`v2` task dict.
- `record_fixtures.py` — CLI: record fixtures for one or more task_ids.
- `run_replay.py` — CLI: replay one or more task_ids offline, optional `--compare`.
- `build_task_set_v2.py` — one-off script that derived `../task_set_v2.json`.
