# Campaigns: registration, retention, and cache-clear

Status: design finalized 2026-07-25, owner-approved, not yet implemented.
Supersedes the frontend-only campaign store proposed in the original desktop
GUI v2 plan (that plan text was never committed to the repo). This is the spec
an implementer should execute against directly.

## Why

`campaign_id` is already the isolation key for cross-run memory
(`execution-context.md`). Today the desktop app hardcodes a single constant
`CAMPAIGN_ID = "desktop-default"` — there is no real campaign entity: no way
to create, list, switch, archive, or delete one. The owner decided (OQ-4,
2026-07-25) that campaigns must be a real backend-managed entity with full
CRUD, not a frontend-only store, because campaign-scoped data destruction
(archive/retention/delete) has to be enforced server-side to be trustworthy.

## 1. Schema — `campaigns` table

```sql
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,              -- "campaign:" + uuid4().hex[:12]
    name TEXT NOT NULL COLLATE NOCASE,         -- 1..120 chars after strip
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    retention_days INTEGER,                    -- NULL = indefinite archive (no auto-purge)
    purge_at TEXT,                              -- archived_at + retention_days; NULL if indefinite
    cache_cleared_at TEXT,                      -- last time clear-cache ran for this campaign, NULL if never
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_campaigns_name ON campaigns(name);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_purge_at ON campaigns(purge_at) WHERE purge_at IS NOT NULL;
```

`discovery_runs` gains one column (migration, `ALTER TABLE ... ADD COLUMN`):

```sql
ALTER TABLE discovery_runs ADD COLUMN cache_cleared_at TEXT;
```

Add both blocks to `SCHEMA_SQL` and to the idempotent `_migrate_schema(conn)`
guard in `salva_core/persistence/db.py`, following the existing
`PRAGMA table_info` column-guard pattern used for prior migrations. Also add
a backfill in the same migration pass:

```sql
INSERT OR IGNORE INTO campaigns (campaign_id, name, status, created_at, updated_at)
SELECT DISTINCT campaign_id, campaign_id, 'active', :now, :now
FROM (
    SELECT campaign_id FROM discovery_runs WHERE campaign_id IS NOT NULL
    UNION
    SELECT campaign_id FROM query_family_memory WHERE campaign_id IS NOT NULL
)
WHERE campaign_id NOT LIKE 'campaign:auto:%'
```
(`INSERT OR IGNORE` + `DISTINCT` makes this idempotent across restarts. Excludes
one-shot auto campaigns so they don't spam the registered list. This registers
the desktop's existing `desktop-default` id so historical data surfaces once
the frontend switches off the hardcoded constant.)

No FK enforcement exists in this DB (`PRAGMA foreign_keys` is never set ON in
`get_conn()`), so all cascade/cleanup below is explicit multi-statement SQL,
not `ON DELETE CASCADE`.

## 2. Persistence module — `salva_core/persistence/campaigns.py`

All functions take `path: str = DEFAULT_DB_PATH` last, re-exported from
`salva_core/persistence/__init__.py`, following the plain-SQL-function
convention used by every other persistence module in this package (no ORM).

```python
def create_campaign(name: str, description: str | None = None, *, path=...) -> CampaignRecord
    # strips name; raises ValueError if empty/>120 chars or on sqlite3.IntegrityError (dup name)
def get_campaign(campaign_id: str, *, path=...) -> CampaignRecord | None
def list_campaigns(status: str | None = None, limit: int = 100, offset: int = 0, *, path=...) -> tuple[list[CampaignRecord], int]
    # ORDER BY created_at DESC; calls sweep_expired_campaigns(path=path) first (see §4)
def update_campaign(campaign_id: str, name: str | None = None, description: str | None = None, *, path=...) -> CampaignRecord
def archive_campaign(campaign_id: str, retention_days: int | None, *, path=...) -> CampaignRecord
    # sets status='archived', archived_at=now, retention_days=retention_days,
    # purge_at = now + retention_days days if retention_days is not None else NULL.
    # Idempotent: re-calling on an already-archived campaign updates retention_days/purge_at
    # (this is how a user changes or cancels a pending timer without unarchiving first).
def unarchive_campaign(campaign_id: str, *, path=...) -> CampaignRecord
    # status='active', archived_at=NULL, retention_days=NULL, purge_at=NULL (cancels any pending timer)
def delete_campaign(campaign_id: str, *, path=...) -> dict[str, int]
    # full cascade per §3; raises ValueError if status != 'archived' (must archive first);
    # raises KeyError if missing
def clear_campaign_cache(campaign_id: str, *, path=...) -> dict[str, int]
    # partial prune per §5; works on active OR archived campaigns
def sweep_expired_campaigns(*, path=...) -> list[str]
    # SELECT campaign_id FROM campaigns WHERE status='archived' AND purge_at IS NOT NULL AND purge_at <= now
    # calls delete_campaign() on each; returns the list of purged campaign_ids for logging
```

Counts on `CampaignRecord` (`run_count`, `memory_quarantine_count`,
`memory_promoted_count`) are computed via indexed `COUNT(*)` queries against
`discovery_runs`/`query_family_memory` at read time — cheap at desktop-local
data volumes, no denormalized counters needed.

## 3. Full delete cascade (used by `delete_campaign` and by the retention sweep)

One transaction, children first (order matters because some tables are only
reachable via `run_id IN (...)`, computed once at the top):

```python
run_ids = [r[0] for r in conn.execute(
    "SELECT run_id FROM discovery_runs WHERE campaign_id = ?", (campaign_id,)
)]
job_ids = [r[0] for r in conn.execute(
    "SELECT job_id FROM jobs WHERE run_id IN ({})".format(...), run_ids
)]
hyperedge_ids = [r[0] for r in conn.execute(
    "SELECT hyperedge_id FROM hyperedges WHERE run_id IN ({})".format(...), run_ids
)]

DELETE FROM semantic_vectors WHERE run_id IN (run_ids)
DELETE FROM query_family_memory WHERE campaign_id = ? OR run_id IN (run_ids)
DELETE FROM hyperedge_incidences WHERE hyperedge_id IN (hyperedge_ids)
DELETE FROM hyperedges WHERE run_id IN (run_ids)
DELETE FROM relation_records WHERE run_id IN (run_ids)
DELETE FROM evidence_chain_records WHERE run_id IN (run_ids)
DELETE FROM evidence_records WHERE run_id IN (run_ids)
DELETE FROM plugin_reports WHERE run_id IN (run_ids)
DELETE FROM source_attempts WHERE run_id IN (run_ids)
DELETE FROM telemetry_records WHERE run_id IN (run_ids)
DELETE FROM stream_events WHERE job_id IN (job_ids)
DELETE FROM jobs WHERE run_id IN (run_ids)
DELETE FROM discovery_runs WHERE campaign_id = ?
DELETE FROM campaigns WHERE campaign_id = ?
```

Not touched (global, non-campaign-scoped by design):
`canonical_entities`, `entity_aliases`, `routing_memory`, `hold_schema_registry`.

Return per-table row counts actually removed (`{"query_family_memory": N,
"discovery_runs": M, ...}`) so callers (API response, retention-sweep log
line) can show a receipt.

## 4. Retention timer (archive → auto full-delete)

No cron/always-on process exists (or should exist) for a local desktop app.
The sweep is opportunistic, not wall-clock-precise:

- Call `sweep_expired_campaigns()` once at core process startup (wherever
  `ensure_db()` is first called in `apps/api/main.py`'s startup path).
- Call it again at the top of `list_campaigns()` (i.e. every `GET
  /v1/campaigns`), before building the response — cheap indexed query, and
  guarantees the list the user is looking at never shows an already-expired
  campaign as if it still existed.
- Practical effect: a campaign set to auto-delete in 7 days purges the next
  time the app is opened on or after that date, not at the literal moment
  the timer elapses while the app is closed. Document this as expected
  behavior in the UI copy ("will be deleted after 7 days, next time you open
  Salva" — not a promise of exact-time deletion).
- Log every sweep-triggered delete (`logger.info("campaign %s auto-deleted:
  retention timer expired", campaign_id)`) distinctly from a manual
  user-triggered delete, so audit trails can tell the two apart.

## 5. Cache-clear (independent of archive/delete — works on active campaigns)

Purpose: let a user keep researching within a campaign (reusing promoted
query-family memory, keeping extracted entities/relations/hyperedges) without
the SQLite file growing unboundedly from raw evidence text that gets
duplicated three times over in the current schema (`evidence_records.snippet`,
`evidence_chain_records.links_json`, and `discovery_runs.entities_json`'s
inlined `CanonicalEntity.evidence` list — confirmed by reading
`salva_core/persistence/runs.py` and `salva_core/schemas/entity.py`).

**Deleted (bulky, regenerable, or purely diagnostic — not "key results"):**
- `evidence_records` — raw snippet/title text (search-result descriptions).
- `evidence_chain_records` — denormalized copy of the same snippet text
  (`links_json` inlines full `EvidenceChainLink` objects, not just ids).
- `semantic_vectors` — full embedding arrays; safe to drop because they are
  fully reconstructable from `query_family_memory` alone via
  `build_query_family_semantic_text()` (confirmed: `semantic_vectors.source_id`
  FKs *to* `query_family_memory`, not the reverse — deleting vectors cannot
  orphan a memory record). Rebuilt lazily next time semantic search needs them.
- `source_attempts`, `telemetry_records`, `plugin_reports` — per-run
  execution diagnostics, not distilled findings.
- `stream_events` — transient SSE progress log, scoped via `jobs.run_id`.

**Kept unmodified (compact, distilled "key results" — the whole point of the
compounding model):**
- `query_family_memory` (all statuses — this is the "複利內容", both
  quarantine and promoted; bulk-clearing quarantine specifically is a
  separate, already-decided OQ-3 mechanism, not part of cache-clear).
- `relation_records`, `hyperedges`, `hyperedge_incidences` — already
  pointer-only (`evidence_ids_json` stores ids, not text) and represent paid-for
  analysis work, not re-fetchable by re-crawling.
- `canonical_entities`, `entity_aliases` — global, untouched regardless.

**Rewritten in place (contains both bulky and compact data mixed in one
column — needs a JSON transform, not a blanket delete):**
- `discovery_runs.entities_json` / `.relations_json` — for each entity/relation
  dict, strip the nested `evidence` list down to bare `evidence_id` references
  (drop `snippet`/`title`/`source_name`/`metadata`), keep every other field
  (`entity_id`, `entity_type`, `primary_label`, `confidence`, etc.) intact.
  This is a Python-level `json.loads` → transform → `json.dumps` →
  `UPDATE discovery_runs SET entities_json = ?, relations_json = ?, cache_cleared_at = ? WHERE run_id = ?`,
  not raw SQL. The row itself is kept (so `listRuns`/`getRunSnapshot` still
  show the run existed, its objective, and its entity/relation counts) —
  only the bulky nested evidence is stripped.
- Also stamp `campaigns.cache_cleared_at = now`.

```python
def clear_campaign_cache(campaign_id: str, *, path=...) -> dict[str, int]:
    run_ids = ...  # same lookup as §3
    for run_id in run_ids:
        row = conn.execute("SELECT entities_json, relations_json FROM discovery_runs WHERE run_id = ?", (run_id,)).fetchone()
        entities = [strip_evidence_text(e) for e in json.loads(row["entities_json"])]
        relations = [strip_evidence_text(r) for r in json.loads(row["relations_json"])]
        conn.execute(
            "UPDATE discovery_runs SET entities_json = ?, relations_json = ?, cache_cleared_at = ? WHERE run_id = ?",
            (json.dumps(entities, ensure_ascii=False), json.dumps(relations, ensure_ascii=False), now, run_id),
        )
    DELETE FROM evidence_records WHERE run_id IN (run_ids)
    DELETE FROM evidence_chain_records WHERE run_id IN (run_ids)
    DELETE FROM semantic_vectors WHERE run_id IN (run_ids)
    DELETE FROM source_attempts WHERE run_id IN (run_ids)
    DELETE FROM telemetry_records WHERE run_id IN (run_ids)
    DELETE FROM plugin_reports WHERE run_id IN (run_ids)
    DELETE FROM stream_events WHERE job_id IN (job_ids)
    UPDATE campaigns SET cache_cleared_at = ? WHERE campaign_id = ?
    return {"evidence_records": n1, "evidence_chain_records": n2, ...}
```

`strip_evidence_text(item: dict) -> dict` is a small pure function (new,
co-located in the same module or `salva_core/schemas/entity.py`): copies the
dict, replaces `item["evidence"]` with `[{"evidence_id": e["evidence_id"]} for
e in item.get("evidence", [])]` if the key exists, leaves everything else
untouched. Apply the same helper to both entity and relation dicts if
relations also inline evidence (verify against the actual `CanonicalRelation`
schema at implementation time — `relation_records` itself is already
pointer-only, so this only matters for whatever gets serialized into
`discovery_runs.relations_json`).

## 6. REST endpoints (`apps/api/main.py`, following its existing direct
`@app.get/post` style — there is no `include_router` wiring in this repo, the
`apps/api/routes/` package is dead code; do not use it)

```
GET    /v1/campaigns?status=&limit=&offset=        -> CampaignsResponse
POST   /v1/campaigns                                -> CampaignRecord (201)
GET    /v1/campaigns/{campaign_id}                  -> CampaignRecord (404 if missing)
PATCH  /v1/campaigns/{campaign_id}                  -> CampaignRecord  (rename/description only)
POST   /v1/campaigns/{campaign_id}/archive          -> CampaignRecord  (body: {retention_days: int|null})
POST   /v1/campaigns/{campaign_id}/unarchive        -> CampaignRecord
POST   /v1/campaigns/{campaign_id}/clear-cache      -> CampaignCacheClearResponse
DELETE /v1/campaigns/{campaign_id}?confirm_name=... -> CampaignDeleteResponse
```

Guardrails on `DELETE`:
- `409` if `status != 'archived'` (must archive first — the retention-timer
  path and the manual-delete path both require this; there is no
  archive-skipping fast path even for immediate deletion, so a mis-click
  always has one confirmation step in front of it).
- `409` if `confirm_name` (case-insensitive) doesn't match `name`.
- `404` if missing.

Guardrail on writes into an archived campaign: in `discover()` /
`create_discovery_job()` / `promote_query_family()` handlers, if
`execution.campaign_id` resolves to a **registered** campaign with
`status='archived'`, return `409` ("campaign is archived; unarchive it to run
new research"). Unregistered campaign_id strings (headless SDK/agent callers,
`campaign:auto:*`) pass through untouched — `execution-context.md`'s existing
contract is unchanged, registration is additive not required.

## 7. Schemas — `salva_core/schemas/campaign.py`

```python
class CampaignRecord(BaseModel):
    campaign_id: str
    name: str
    description: str | None = None
    status: Literal["active", "archived"] = "active"
    retention_days: int | None = None
    purge_at: datetime | None = None
    cache_cleared_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    run_count: int = 0
    memory_quarantine_count: int = 0
    memory_promoted_count: int = 0

class CampaignsResponse(BaseModel):
    items: list[CampaignRecord]
    total: int

class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None

class CampaignUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None

class CampaignArchiveRequest(BaseModel):
    retention_days: int | None = None   # None = indefinite; else must be >= 1

class CampaignDeleteResponse(BaseModel):
    campaign_id: str
    deleted: dict[str, int]

class CampaignCacheClearResponse(BaseModel):
    campaign_id: str
    cleared: dict[str, int]
    cache_cleared_at: datetime
```

Export all from `salva_core/schemas/__init__.py` alongside the existing
alphabetical import/`__all__` blocks.

## 8. Desktop integration

### `desktop/src/lib/api.ts`
- Delete `export const CAMPAIGN_ID = "desktop-default"`.
- Add `CampaignRecord`/`CampaignsResponse` types and: `listCampaigns`,
  `createCampaign`, `updateCampaign`, `archiveCampaign(id, retentionDays)`,
  `unarchiveCampaign`, `clearCampaignCache`, `deleteCampaign(id, confirmName)`.
- `DiscoverParams` gains a required `campaignId: string`; `discover()` sends
  `params.campaignId` instead of the removed constant.

### `App.tsx` — campaign switcher (prop-drilled state, matches existing style)
- `const [activeCampaign, setActiveCampaign] = useState<CampaignRecord | null>(null)`.
- Bootstrap once core is online: `listCampaigns("active")` → resolve
  `localStorage.getItem("salva.activeCampaignId")` against the list → if
  missing/archived, pick first active → if list empty, `createCampaign("Default")`
  → persist id to localStorage on every switch.
- Header gains a campaign switcher dropdown next to the core/LLM status
  cluster: shows `activeCampaign.name`, lists active campaigns, last item
  "Manage campaigns…" navigates to the new view.
- `View` union gains `| { name: "campaigns" }`; nav gets a `FolderKanban`
  (lucide-react, already a dependency) entry.
- `SearchView` gets `campaignId={activeCampaign.campaign_id}` (threads into
  `discover`); `MemoryView`'s three existing `CAMPAIGN_ID` usages are replaced
  with the same prop. Both render a disabled/empty state while
  `activeCampaign` is null.

### New `desktop/src/views/CampaignsView.tsx`
- Table: name, status badge, run/promoted/quarantine counts, `purge_at`
  countdown if set ("清除於 3 天後" style), `cache_cleared_at` indicator,
  created_at. Toggle to show archived.
- Create form (name + optional description).
- Inline rename.
- Archive action opens a small dialog: retention choice — preset chips
  (7/30/90 days) + custom number input + "無限期（僅封存）" option — calls
  `archiveCampaign(id, retentionDays)`. Re-archiving an already-archived
  campaign reuses the same dialog to change/cancel the timer.
- "清除快取" button (any status) → confirm dialog explaining what's kept vs
  cleared (mirror §5's two lists in plain language) → calls
  `clearCampaignCache` → shows the returned row-count receipt.
- Delete: only enabled on archived rows, opens a confirm dialog requiring the
  user to type the campaign name, shows the deletion-count receipt on success.
- If the deleted/archived-and-purged campaign was the active one, invalidate
  via a callback prop so `App.tsx` re-runs the bootstrap fallback.

### New `desktop/src/views/SettingsView.tsx` (new — no settings surface exists
today; this decision is what first requires one)
- Global default retention (used to prefill the archive dialog's preset,
  stored in localStorage client-side — not a backend concept, campaigns keep
  their own `retention_days` once set).
- Bulk "清除所有已封存 campaign 的快取" action — loops `clearCampaignCache`
  over every archived campaign, shows aggregate receipt.
- This view is new scope beyond the original OQ-4/OQ-6 rounds; keep it
  minimal (these two controls only) rather than building a general settings
  framework speculatively.

## 9. Tests

`tests/integration/test_campaigns_api.py` (mirror `test_query_families_api.py`'s
`main.<handler>` + `asyncio.run` pattern, inject tmp DB via `path=`):
- CRUD roundtrip; duplicate-name 409.
- Archive with `retention_days=7` sets `purge_at`; archive with `null` leaves
  it unset; re-archiving updates the timer.
- `sweep_expired_campaigns` deletes a campaign whose `purge_at` is in the
  past and leaves one whose `purge_at` is in the future or `NULL`.
- Delete-while-active 409; wrong `confirm_name` 409; delete cascade row
  counts match seeded fixture data.
- `clear_campaign_cache`: seed a run with evidence + memory, call it, assert
  `evidence_records`/`evidence_chain_records`/`semantic_vectors` rows are
  gone, `query_family_memory`/`hyperedges`/`relation_records` rows are
  untouched, and `discovery_runs.entities_json` no longer contains snippet
  text but still has entity ids/labels.
- Discover-into-archived-campaign 409.
- Migration backfill test (pre-seed `campaign_id="desktop-default"` data,
  call `ensure_db`, assert the campaigns row exists; assert `campaign:auto:*`
  ids are excluded).

## 10. Open items for the implementer to flag back if wrong

1. Whether `relations_json` on `discovery_runs` actually inlines evidence
   text the same way `entities_json` does — verify against the live
   `CanonicalRelation`/serialization code before assuming `strip_evidence_text`
   needs to touch it too; if relations never inlined evidence, skip that half
   of §5's rewrite step.
2. `SettingsView` is new scope this doc introduces to give the cache-clear
   bulk action and default-retention preference somewhere to live — if a
   settings surface is being designed for other reasons in parallel, don't
   duplicate, consolidate.
3. The retention-timer sweep is best-effort (checked on app open only, not
   wall-clock precise) — flagged here again because it's a real product
   behavior difference from "the file is gone at exactly hour 168," and the
   UI copy must not overpromise precision.
