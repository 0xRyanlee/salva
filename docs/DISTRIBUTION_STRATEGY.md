# Distribution Strategy — free channels only

**Date:** 2026-07-03
**Status:** Research only. Nothing in this document has been published —
no `pip publish`, `docker push`, or registry submission was executed.

Per the project's hard constraint (no paid tools, ever), this document
covers **free-tier distribution channels only**. Where a channel turned out
to have a paid component, it's flagged explicitly and NOT recommended —
that decision is left to the owner, not decided here.

## 1. PyPI (Python package)

**Free.** PyPI has no listing fee; publishing requires only a PyPI account
and an API token.

**Current state, verified by actually building the package (not just
reading pyproject.toml):**

```
uv build --wheel -o /tmp/salva_dist
# -> Successfully built salva_runtime-0.1.0-py3-none-any.whl
```

The wheel builds cleanly today — 105 files, valid `METADATA`/`WHEEL`/
`entry_points.txt`/`RECORD`, correct dependency declarations including
optional-extras groups (`retrieval`, `vector`, `mcp`, `cli`, `dev`), and the
`salva = "apps.cli.main:main"` console-script entry point. **`pip install
salva-runtime` would technically work today if published.**

Gaps found (none blocking, all cosmetic/best-practice):
- No `[project.urls]` section in `pyproject.toml` — PyPI project pages
  normally show Homepage/Repository/Issues links; currently absent.
- No `.github/workflows/` directory at all — no CI, and specifically no
  automated publish-on-tag workflow (the standard pattern is a GitHub
  Action triggered on a version tag that runs `uv build` + `uv publish` or
  `pypa/gh-action-pypi-publish` using PyPI's trusted-publisher OIDC flow,
  which needs no stored API token).
- Version is `0.1.0` — fine for an initial publish, but versioning/release
  process itself is out of this card's scope (release actions are owner-lane
  per this project's board conventions).

**Recommended priority: high.** Lowest-effort channel — the package
already builds correctly; the only real work is adding `[project.urls]`
and a CI publish workflow, both non-destructive additions.

## 2. Docker image (GHCR)

**Free.** GitHub Container Registry (GHCR) has no cost for public images;
publishing requires only `docker login ghcr.io` with a GitHub PAT and
`docker push`.

**Current state:** `Dockerfile` and `docker-compose.yml` already exist.
Attempted a local build to verify (`docker build -t salva-test:local .`) —
hit a local environment issue unrelated to the Dockerfile itself
(`docker-credential-desktop` executable missing from this machine's PATH,
blocking the base-image pull step before the Dockerfile's own instructions
even run). Could not complete a full build verification in this
environment; the Dockerfile's instructions read correctly on inspection
(installs Obscura browser, copies source, `pip install -e ".[dev]"`,
exposes port 8765, runs uvicorn) but this is not the same as a verified
clean build.

One real finding from inspection, not from the failed build attempt: the
Dockerfile installs the **`.[dev]`** extras group (pytest, ruff, mypy,
coverage) into the shipped image. That's appropriate for local development
via `docker-compose.yml` but heavier than necessary for a published release
image — a released image should probably install a leaner extras
combination (e.g. `.[retrieval,vector,mcp]`) with a separate dev-only
Dockerfile or build stage for local development. Not fixed here (out of
this card's research-only scope) — flagged as a finding for a future card.

**Recommended priority: medium.** Needs the credential-helper issue
resolved locally (or verified in CI, where GHCR auth doesn't hit this
problem) before a real build can be confirmed, plus the dev-extras
image-weight issue addressed before a release-quality image is ready.

## 3. MCP directory listings

Researched via live web search (2026-07-03), not assumed from prior
knowledge — the MCP ecosystem has grown and consolidated significantly
since Salva's `apps/mcp/server.py` was originally built.

| Directory | Free? | Notes |
|---|---|---|
| **Official MCP Registry** (`registry.modelcontextprotocol.io`) | **Free** | Anthropic-backed canonical metadata feed (GitHub/PulseMCP/Microsoft also contribute). Launched preview Sept 2025. Listing means publishing a `server.json` record under a name you prove ownership of (typically via a GitHub-linked namespace). Metadata only — doesn't host code/binaries, just points to where they live (e.g. PyPI, GHCR, GitHub). |
| **Smithery** | **Free to list** | ~7,000+ servers, app-store-style UI with install commands; also offers optional hosted remote-server execution (that hosting tier may have its own pricing — the *listing* itself is free, hosting is a separate consideration not needed for a self-hosted MCP server like Salva). |
| **PulseMCP** | **Free** | ~11,840+ servers, hand-reviewed. |
| **Glama.ai/mcp** | **Free** | ~21,000+ servers, largest by volume, daily crawl-based updates. |
| **mcp.so** | **Free** | ~20,222 servers indexed as of April 2026 (third-party marketplace, not Anthropic-affiliated). |

**No paid submission found across any of these** — general pattern
confirmed by research: MCP directory listings are free with no formal
review process; servers appear via direct submission (a `server.json` /
metadata file) or automatic crawling of public repos. If a future,
different directory is found to charge a listing fee, it should be flagged
the same way this document flags other paid options — not used without
owner sign-off.

**Recommended priority: high, once PyPI/GHCR publishing exists.** These
registries mostly point at where the actual package lives (PyPI, GHCR,
GitHub) rather than hosting it themselves — so channels 1-2 are the actual
prerequisite work; listing here afterward is comparatively cheap (write one
`server.json`, submit to 3-4 directories).

## 4. Claude Desktop Extension (`.mcpb`, formerly `.dxt`)

**Free** — this is a packaging format, not a paid distribution channel.
Researched via live web search: Anthropic renamed the original `.dxt`
("Desktop Extensions") format to `.mcpb` ("MCP Bundle") during 2026;
existing `.dxt` files still work, but new work should target `.mcpb`
naming. Structurally, both are a zip archive containing the full MCP
server (bundled dependencies) plus a `manifest.json` describing what
Claude Desktop needs to know — enabling one-click local install with no
separate `pip`/`npm`/Docker step from the end user, automatic OS-keychain
secret storage, and auto-updates.

**Relevance to Salva:** this targets *individual end users* running Claude
Desktop locally, a different audience than the current MCP config snippet
in `README.md` (which already documents a `.mcp.json` `mcpServers` entry
pointing at a venv Python path — that's the "I have a dev environment"
path, not the "I clicked a file and it worked" path `.mcpb` provides).
Building one would mean bundling Salva's Python runtime + dependencies
into a self-contained archive, which is nontrivial packaging work distinct
from the PyPI/Docker channels above (Python-based MCP servers bundling
into `.mcpb` is less mature/well-documented than the Node.js case, per the
research above — "no developer tools required (Node.js is built into
Claude Desktop)" implies first-class support skews toward Node servers).

**Recommended priority: low, defer.** Real channel, but meaningfully more
packaging effort than PyPI/GHCR for a payoff (single-user Desktop install)
that matters less than the MCP-directory discoverability channels above,
given Salva's actual primary consumption pattern this session validated is
"Claude Code invoking it as an MCP tool," not "an individual double-clicks
an install file."

## 5. Gap vs. current install flow

`README.md`'s "快速啟動" section currently documents:
```bash
pip install -e ".[dev]"   # editable install from a cloned repo
```
This is a **developer-clone workflow**, not any of the four channels
above — there is currently no path to `pip install salva-runtime` (no
PyPI release), `docker run ghcr.io/.../salva` (no GHCR image), or an MCP
directory listing (nothing published to list). All four researched
channels are additive work on top of the current git-clone-and-editable-
install flow, not a replacement for it — the editable-install path remains
correct for local development regardless of what gets published.

## Priority summary

| Channel | Free? | Priority | Blocking issue found |
|---|---|---|---|
| PyPI | Yes | High | None — wheel builds clean today; needs `[project.urls]` + CI publish workflow |
| GHCR (Docker) | Yes | Medium | Dev-extras image weight; local build verification blocked by an unrelated environment credential-helper issue |
| MCP directories | Yes (all 4 researched) | High, after PyPI/GHCR | None — mostly point at PyPI/GHCR, so sequenced after those |
| Claude Desktop `.mcpb` | Yes | Low, defer | Nontrivial Python-bundling packaging effort; targets a less-relevant audience than Salva's actual MCP-as-a-tool usage pattern |

No paid channel was found in this research pass. If the owner later
discovers a directory or service that does charge, it should be flagged
the same way this document handles it — listed with the cost noted, not
used without explicit sign-off, per the project's non-negotiable
no-paid-tools constraint.
