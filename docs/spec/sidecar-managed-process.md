# App-managed LLM sidecar process

Status: design finalized 2026-07-25, owner-approved, not yet implemented.
Supersedes the terminal-guidance onboarding assumption in the original
desktop GUI v2 Phase 3 plan (never committed to the repo as a file — this doc
is now the source of truth for that scope).

## Why

Salva's LLM "sidecar" (`salva_core/llm_sidecar_run.py` → `SidecarServer` in
`salva_core/llm_sidecar.py`) wraps `claude`/`codex` CLI calls behind a local
Unix-socket server, one instance per app instance (2026-07-23 decision, see
`~/.claude/projects/-Volumes-Astoria-Projects-salva/memory/decisions-20260723-llm-backend-kyc-commit.md`).
Today the user must open their own terminal and run
`python -m salva_core.llm_sidecar_run` manually; the desktop app only polls
`/v1/llm/sidecar-status` and shows an off/sidecar/BYOK badge.

The owner decided (OQ-6, 2026-07-25, against fable's own recommendation to
keep the manual-terminal flow) that the app should spawn and manage this
process itself. fable flagged this trades a visible failure mode (user
watching their own terminal) for a more hidden one (a managed background
process failing silently) — this design's job is to make every failure loud
again despite the process no longer being visible by default. A follow-up
owner decision (same day) requires a one-time "啟用 LLM 功能？" consent
prompt before the app ever spawns anything — auto-spawn is not silent-by-default.

## 1. Consent gate (owner decision, 2026-07-25 follow-up to OQ-6)

Before any spawn/probe logic runs, the app must get one-time consent:

- First launch after this feature ships: show a small dialog — "啟用 LLM
  增強功能？Salva 會在背景啟動一個本機行程，呼叫你已登入的 claude/codex CLI
  來做實體解析與摘要。" with **啟用** / **不用，稍後再說** actions.
- Persist the choice (`localStorage.setItem("salva.llmEnabled", "true"|"false")`
  — client-side is sufficient, this is a UX preference not a security
  boundary). "不用，稍後再說" leaves the badge in a distinct `disabled` state
  with a small "啟用" affordance in its popover, so the user can flip it on
  later without hunting for a settings screen.
- Only after consent is `true` does the app run preflight/spawn (§2–3). BYOK
  configured (`SALVA_BYOK_BASE_URL`/`SALVA_BYOK_API_KEY` both set) skips the
  consent prompt entirely and goes straight to `byok` state — BYOK is an
  explicit env-var opt-in already, asking again would be redundant.
- Consent is asked once per machine/profile, not once per campaign or per
  session — store it at the app level (`localStorage`, not tied to any
  campaign).

## 2. Spawn mechanism

Rust side, `desktop/src-tauri/src/lib.rs` (or a new sibling `sidecar.rs` —
the file is ~190 lines today and this roughly doubles it; splitting is
recommended but not required).

```rust
fn spawn_sidecar(repo_root: &PathBuf) -> std::io::Result<Child> {
    Command::new(resolve_uv_binary())          // reuse existing helper, do not call bare "uv"
        .args(["run", "python", "-m", "salva_core.llm_sidecar_run"])
        .current_dir(repo_root)
        .env("PATH", augmented_path())          // new — see below
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
}
```

- **`uv run python -m ...`, never a bare `python`/`uv` name.** `resolve_uv_binary()`
  already exists for the core spawn's GUI-launch-trimmed-PATH problem; reuse
  it, don't reimplement.
- **`augmented_path()` is a new fix, not just reuse.** The sidecar's
  `default_cli_runner()` shells out to `claude`/`codex` by bare name
  (`subprocess.run(["claude", ...])`). Those inherit the sidecar's env, which
  inherits the GUI app's trimmed PATH — a Dock-launched app would spawn a
  sidecar where both CLIs are `FileNotFoundError`, i.e. the badge goes green
  (`sidecar_reachable() == true`) while every completion silently fails. Fix
  in Rust: build `PATH` = existing PATH + `~/.local/bin`, `/opt/homebrew/bin`,
  `/usr/local/bin`, `~/.cargo/bin`, `~/.npm-global/bin` (or wherever `claude`/
  `codex` actually install to — verify at implementation time with `which
  claude codex` in a fresh, non-terminal-sourced shell). Apply the same
  augmented PATH to the **core** spawn too, at no extra cost.
- **Working directory**: `repo_root` (same as core spawn), so `uv` finds
  `pyproject.toml` and `SALVA_SQLITE_PATH`-relative defaults resolve
  identically for core and sidecar — their computed `instance_id`/socket path
  then match automatically without Rust ever computing the socket path itself.
- **Stdio**: piped, reuse the existing `forward_and_capture()` helper for both
  streams (prefix `sidecar:stdout`/`sidecar:stderr`, keep the 50-line stderr
  tail for error surfacing).

Python-side additions (`salva_core/llm_sidecar.py` / `llm_sidecar_run.py`):

1. **Already-running guard.** `SidecarServer.serve_forever()` currently
   unlinks any existing socket file unconditionally before binding. Under
   app-managed spawn this is a live hazard: a leftover manual-terminal
   sidecar, or a second app instance, would have its socket silently stolen.
   Before unlink, attempt a short-timeout `connect()`; on success, print a
   marker line and exit with **exit code 3** ("already running"). Rust maps
   exit 3 to state `external` and does not treat it as a failure.
2. **`--preflight` mode** (new argparse flag on `llm_sidecar_run.py`): checks
   each CLI in `_CLI_ORDER` for (a) resolvable on PATH (`shutil.which`), (b)
   authenticated. Prints one JSON line, e.g.
   `{"claude": "ok", "codex": "not_logged_in"}`, exits 0. See §7 open item 1
   for the exact auth-check mechanism per CLI — verify against the real CLIs
   before implementing, don't guess the flag name.

Rust state machine (new, alongside the existing core-process management):

```rust
enum SidecarState {
    Disabled,                       // consent not yet given, or declined
    Probing,
    AwaitingLogin { detail: String },
    Starting,
    Running,
    External,                       // exit code 3 — a foreign sidecar owns the socket
    Failed { detail: String },
    Byok,
}
struct SidecarManager { state: Mutex<SidecarState>, child: Mutex<Option<Child>> }
```

Startup sequence (after consent — the frontend calls a new Tauri command once
consent is granted, or on every launch if consent was already persisted):
BYOK env vars set → `Byok`, don't spawn. Else run `--preflight` (async, off
the main thread) → if at least one CLI is `ok`, spawn → `Starting` → after the
same 1.5s `try_wait()` liveness pattern the core spawn uses → `Running` (exit
3 → `External`). If **no** CLI is authenticated → `AwaitingLogin`, **do not
spawn** — spawning an unauthenticated sidecar would make the badge go green
while every completion fails, exactly the hidden-failure-mode risk fable
flagged. This ordering (probe before spawn) is the core of this whole design.

New Tauri commands (there is no `invoke_handler` registered today — this is
net-new; app-defined commands need no capability-file changes,
`core:default` already covers them):

```rust
#[tauri::command] fn sidecar_consent(app: AppHandle, enabled: bool) -> Result<(), String>;  // triggers first probe+spawn if true
#[tauri::command] fn sidecar_status(state: State<SidecarManager>) -> SidecarStatusDto;
#[tauri::command] fn sidecar_restart(app: AppHandle) -> Result<(), String>;   // re-run preflight + spawn
#[tauri::command] fn sidecar_open_login(cli: String) -> Result<(), String>;   // "claude" | "codex"
```

Event `sidecar-managed-status`, emitted on every state transition:
`{ state: "disabled"|"probing"|"awaiting_login"|"starting"|"running"|"external"|"failed"|"byok", detail: string|null }`.

## 3. The login problem

`claude login`/`codex login` are interactive: typically an OAuth URL opens in
a browser, then the CLI itself wants terminal interaction (paste a code,
confirm an account). Recommendation: **open a real, visible native terminal
window that the app launches but does not otherwise manage** — the login
interaction happens exactly where the CLI vendors designed it to work, and
it's the one part of this flow the app genuinely cannot supervise, so put it
in front of the user's eyes rather than trying to parse it.

Rejected alternatives: a pty-backed in-app terminal (`portable-pty`) parsing
CLI output — highest fidelity but the most fragile (breaks on any CLI output
format change) and the least visible failure mode if the parser is wrong,
which is the opposite of this design's goal. Token/device-code flows — no
stable equivalent across both `claude` and `codex`.

macOS mechanism for `sidecar_open_login(cli)`:

```rust
Command::new("/usr/bin/osascript")
    .args(["-e", r#"tell application "Terminal" to activate"#,
           "-e", &format!(r#"tell application "Terminal" to do script "{} login""#,
                          resolved_cli_path.display())])
    .spawn()
```

Use the **absolute** CLI path returned by the preflight JSON (not a bare
name — Terminal.app's login-shell PATH usually has it, but absolute is the
audit-compliant choice given the PATH-fragility already found once in this
codebase's history). After launching, Rust enters `AwaitingLogin` and polls
`--preflight` every 5s for up to 10 minutes; on success → `Starting` → spawn.
Poll timeout → `Failed { detail: "login not completed within 10 min" }` with
a retry action, not a dead end. The login process is not a child of the app
(it belongs to Terminal.app) — never killed by the app, its window closing
means nothing to the state machine; only the next preflight result matters.

Windows/Linux equivalents are out of scope for this round (current dogfood
target is macOS arm64 only) — leave a `#[cfg(target_os = "macos")]` seam.

## 4. Lifecycle management

- **App quit → kill the managed sidecar.** Extend the existing
  `on_window_event` `CloseRequested` handler to `take()`-and-`kill()` both
  the core child and the sidecar child, same ordering discipline already
  used for the core spawn (manage the child handle immediately after spawn,
  before the liveness check, to avoid the documented orphan-window race).
  Rationale: the app now owns the process; leaving it running leaks one
  sidecar per launch, and the exit-3 socket-steal guard would then make the
  *next* launch attach to a stale process nobody can see or restart.
- **Exception — `External` state**: if exit-3 detection found a foreign
  (manual-terminal) sidecar, the app kills nothing on quit — old semantics
  preserved for that path.
- **Login child (Terminal.app window)**: never killed — see §3.
- **Unexpected sidecar death** (crash, external kill): a monitor thread calls
  `child.wait()`; on exit, emit `Failed` with the stderr tail, then attempt
  at most 2 automatic restarts with 5s backoff (each re-running preflight
  first). After that, stay in `Failed` with a manual restart action — capped
  to avoid a silent crash-loop burning CPU.
- **TESTPLAN impact**: the existing manual test step ("另開終端機跑 sidecar…
  關掉該終端機視窗後應變回未連線") becomes the `External`-state test only
  (start a manual sidecar *before* launching the app). The primary flow to
  test becomes: fresh launch + consent + already-logged-in CLI → badge
  reaches `Running` with zero manual steps; `kill <sidecar-pid>` from a
  terminal mid-session → badge shows `Failed` then auto-recovers.

## 5. UI/status surface

Badge (top-right, `App.tsx`), combining the existing `/v1/llm/sidecar-status`
API poll with the new `sidecar-managed-status` Rust event:

| State | Badge text | Source |
|---|---|---|
| `disabled` | `LLM: 未啟用`（可點擊「啟用」） | Rust event / consent not given |
| `probing` | `LLM: 檢查中…` | Rust event |
| `awaiting_login` | `LLM: 需要登入`（警示色，可點擊） | Rust event |
| `starting` | `LLM: 啟動中…` | Rust event |
| `running` + API poll reachable | `LLM: sidecar` | agree |
| `external` + API poll reachable | `LLM: sidecar（外部）` | agree |
| `byok` | `LLM: BYOK` | existing logic, unchanged |
| `failed` | `LLM: 錯誤`（可點擊重試） | Rust event |
| `running` but API poll unreachable for >2 polls | `LLM: 錯誤`（狀態不一致） | cross-check — treat disagreement as a real problem, not a race |

Badge + popover, not a dedicated onboarding wizard — new
`desktop/src/components/LlmStatusPopover.tsx` shows current state + detail
text and contextual actions: `disabled` → "啟用" button (re-shows the consent
dialog copy inline); `awaiting_login` → "用 Claude 登入" / "用 Codex 登入"
buttons (`invoke("sidecar_open_login", { cli })`) plus one line explaining a
terminal window will open; `failed` → error detail + "重試"
(`invoke("sidecar_restart")`). The existing full-width warning banner in
`App.tsx` is retained but its copy changes from "另開 terminal 執行 python -m
…" to "點右上角 LLM 標籤啟用" — the manual command survives only as
fine-print in the popover for the `External`/power-user path.

Frontend plumbing: `lib/api.ts` gains a `SidecarManagedStatus` type;
`App.tsx` gains a `listen<...>("sidecar-managed-status")` effect mirroring
the existing `core-status` one; `@tauri-apps/api/core`'s `invoke` is imported
for the first time in this codebase.

## 6. Failure visibility — what must stop being silent

| Failure | Old (manual terminal) | New (app-managed) must surface as |
|---|---|---|
| `uv`/venv broken | visible in the user's terminal | spawn error → `Failed` + detail |
| sidecar exits immediately | visible traceback | 1.5s liveness check → `Failed` + stderr tail |
| CLI not installed | user saw "not found" per-request | preflight `missing` → popover says "未安裝", no login button offered |
| not logged in | per-request auth errors in terminal | preflight → `AwaitingLogin` **before** spawning, never green-but-broken |
| login abandoned / OAuth network failure | stuck terminal, visible | 10-min poll timeout → `Failed` "登入未完成" + retry |
| stale socket from a crashed instance | rebound silently on next manual start | unchanged — `serve_forever` only unlinks a genuinely dead socket |
| socket owned by a live process (2nd instance / manual sidecar) | impossible to hit silently before | exit 3 → `External`, visible in badge, no steal |
| sidecar dies mid-session | badge went to off with stale "go run it" advice | monitor thread → `Failed` + up to 2 auto-restarts, badge narrates recovery |
| CLI invisible on PATH inside sidecar (GUI-trimmed PATH) | n/a — new-model-only bug class | prevented by `augmented_path()`; residual cases caught by preflight `missing` |
| sidecar reachable but every completion failing (auth revoked mid-session) | invisible in both models | flagged as a stretch goal — extend `/v1/llm/sidecar-status` with a `last_completion_error` field if this becomes a real issue in dogfooding |

## 7. Open items for the implementer to verify before/while implementing

1. **Exact auth-check per CLI for `--preflight`.** `codex login status` is
   confirmed to exist as a real subcommand. Claude's CLI has no equally
   clean non-interactive check found in this repo's research pass — options
   are a credentials-file-presence heuristic (fast, but version/keychain
   fragile) or a real 1-token `claude -p ok --model haiku` call (definitive
   but costs a real API call and 2–10s, too slow for a 5s poll loop).
   Suggested: file-heuristic for the repeated `AwaitingLogin` poll, one real
   probe only on the transition into `Running` as final confirmation.
   **Verify actual current CLI behavior before implementing** — do not guess
   flag/file names, run the CLIs and check.
2. **Preflight cost**: each call is a cold `uv run python` start (~0.5–2s).
   Fine at the 5s `AwaitingLogin` poll interval; do not run it on the
   existing 3s `/v1/llm/sidecar-status` poll.
3. **Two children, no shared abstraction.** Core and sidecar now share a
   spawn/kill/liveness shape; resist genericizing into a process-supervisor
   abstraction this round — this codebase's audit history (2026-07-24
   self-audit) favors explicit duplicated failure paths over a shared
   abstraction that hides which process failed which way.
4. **Release-build dependency on `SALVA_REPO_ROOT`/a working `uv` checkout
   is unchanged and now double-visible** — a tester without the repo gets
   both a dead core *and* a dead sidecar badge. Not a regression, but the
   TESTPLAN's known-limitations section must say so plainly.
