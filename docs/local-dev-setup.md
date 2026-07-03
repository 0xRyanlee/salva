# Local Dev Setup — Self-Hosted SearXNG

`SEARXNG_URL` (`.env`, default `http://localhost:8080`) needs a real SearXNG
instance listening on it for live retrieval to work. This is **not** bundled
into this repo's `docker-compose.yml` — see "Why not in docker-compose.yml"
below for why, and run it standalone instead.

Free, self-hosted, official image only — no paid SearXNG hosting/proxy.

## Quick start

```bash
docker run -d \
  --name searxng \
  --restart unless-stopped \
  -p 8080:8080 \
  -v "$(pwd)/searxng:/etc/searxng:rw" \
  -e SEARXNG_BASE_URL=http://localhost:8080/ \
  searxng/searxng:latest
```

On first run this generates a default `searxng/settings.yml` in the mounted
volume. `--restart unless-stopped` means it survives `docker` daemon restarts
without needing to be manually started again each time you resume work.

## Verify it's actually working

Don't just check the container is "Up" — confirm it returns real results:

```bash
curl -s 'http://localhost:8080/search?q=test&format=json' | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(len(d.get('results', [])), 'results')"
```

Should print a number > 0. If it's 0 or the curl fails, check `docker logs searxng`.

Then confirm the Python layer sees it too:

```bash
cd /path/to/salva && source .venv/bin/activate
python3 -c "
from retrieval.sources.searxng import SearXNGRetriever
from salva_core.schemas import RetrievalPolicy
r = SearXNGRetriever(policy=RetrievalPolicy())
results = r.search('test', n=5)
print(len(results), 'results, probe_inconclusive=', r.probe_inconclusive)
"
```

`probe_inconclusive` should be `False` when SearXNG is reachable and
returning results (see `salva_core/topology.py::_apply_live_probe` for how
this signal feeds into topology classification and `retrieval_health`).

## Why not in docker-compose.yml

Two reasons, both discovered hands-on rather than assumed:

1. **Port ownership conflict.** Adding a `searxng` service to this repo's
   `docker-compose.yml` collides with any standalone SearXNG instance you
   (or another project) already have running on port 8080 —
   `docker compose up` fails with `port is already allocated` rather than
   reusing it. SearXNG is host-level shared infrastructure, not something
   scoped to one project's compose lifecycle.
2. **It's meant to outlive any single project.** A standalone container with
   `restart: unless-stopped` keeps running across reboots/Docker restarts
   independent of whether this specific repo's other services are up —
   matches how `salva`/`salva-mcp`/`salva-worker` already reference
   `SEARXNG_URL: http://host.docker.internal:8080` as an *external* dependency,
   not something they expect to own the lifecycle of.

If you don't already have a SearXNG instance running anywhere on your
machine, use the Quick start command above once, then leave it running.

## Fallback behavior if SearXNG is down

The retrieval pipeline degrades gracefully, not silently: `allow_public_fallback=True`
(default, `salva_core/schemas.py::RetrievalPolicy`) falls back to public
SearXNG mirrors (`retrieval/sources/searxng.py::PUBLIC_INSTANCE_POOLS`), and
`retrieval_health` on discovery responses will report `"probe_failed"` rather
than a confident-looking low score — see `salva_core/topology.py`. Public
mirrors are frequently rate-limited/blocked (`retrieval/registry.py`'s
`searxng_pool` provider description says so explicitly), so a working local
instance is still the fastest, most reliable first tier.
