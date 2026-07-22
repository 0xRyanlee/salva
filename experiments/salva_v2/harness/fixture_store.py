"""Read/write helpers for frozen retrieval fixtures.

One fixture file = one (task_id, strategy, query) -> raw provider results
capture, at the same granularity as retrieval.router.RoutedRetriever.search()
(post-dedup, pre-extraction). This is the exact call the controller's
Retriever protocol issues, so a fixture is a drop-in substitute for a live
call without needing per-provider (ddgs/searxng/marginalia/...) recording.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


def _slug(query: str) -> str:
    return hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]


def fixture_dir(task_id: str, strategy: str, *, root: Path = FIXTURES_ROOT) -> Path:
    return root / task_id / strategy


def fixture_path(task_id: str, strategy: str, query: str, *, root: Path = FIXTURES_ROOT) -> Path:
    return fixture_dir(task_id, strategy, root=root) / f"{_slug(query)}.json"


def write_fixture(
    task_id: str,
    strategy: str,
    query: str,
    n: int,
    results: list[dict[str, Any]],
    *,
    recorded_at: str,
    root: Path = FIXTURES_ROOT,
) -> Path:
    path = fixture_path(task_id, strategy, query, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": task_id,
        "strategy": strategy,
        "query": query,
        "n": n,
        "recorded_at": recorded_at,
        "results": results,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_fixtures(
    task_id: str, strategy: str, *, root: Path = FIXTURES_ROOT
) -> dict[str, dict[str, Any]]:
    """Return {query: fixture_payload} for every recorded fixture under this
    (task_id, strategy). Keyed by the exact query string, not the filename
    hash -- lookups must match on content, the hash is just a filesystem key.
    """
    directory = fixture_dir(task_id, strategy, root=root)
    out: dict[str, dict[str, Any]] = {}
    if not directory.exists():
        return out
    for file in sorted(directory.glob("*.json")):
        payload = json.loads(file.read_text(encoding="utf-8"))
        out[payload["query"]] = payload
    return out
