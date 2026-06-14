"""Environment-level SearXNG live probe with in-process TTL cache.

Probes once per TTL per SEARXNG_URL endpoint (stable per deployment/network).
All exceptions are caught — callers must degrade gracefully when None is returned.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger("salva.live_probe")

# Default 5-minute TTL: provider health changes on the order of minutes, not seconds.
# Error signals are not cached so they get retried on the next request.
_PROBE_TTL: float = float(os.getenv("SALVA_PROBE_TTL", "300"))

# env_key -> (signal, monotonic_cached_at)
_cache: dict[str, tuple["LiveProbeSignal", float]] = {}


@dataclass
class LiveProbeSignal:
    result_count: int
    avg_score: float
    has_error: bool
    latency_ms: float
    searxng_url: str
    provider_names: list[str] = field(default_factory=list)
    probed_at: float = field(default_factory=time.time)


def _env_key() -> str:
    return os.getenv("SEARXNG_URL", "http://localhost:8080").rstrip("/")


def get_probe_signal() -> LiveProbeSignal | None:
    """Return cached signal if within TTL, else None."""
    key = _env_key()
    entry = _cache.get(key)
    if entry is None:
        return None
    signal, cached_at = entry
    if time.monotonic() - cached_at > _PROBE_TTL:
        del _cache[key]
        return None
    return signal


def _set_probe_cache(signal: LiveProbeSignal) -> None:
    _cache[_env_key()] = (signal, time.monotonic())


def invalidate_probe_cache() -> None:
    _cache.clear()


def run_live_probe(query: str, timeout: float = 3.0) -> LiveProbeSignal | None:
    """
    Fire one SearXNG search against the local instance (no public fallback).
    Caches healthy signals; error signals are not cached so they retry next request.
    Returns None when SearXNG is disabled or on unexpected import error.
    """
    if os.getenv("SEARXNG_ENABLED", "true").lower() in ("0", "false", "no"):
        return None

    key = _env_key()
    t0 = time.monotonic()
    has_error = False
    result_count = 0
    avg_score = 0.0
    provider_names: list[str] = []

    try:
        from retrieval.sources.searxng import SearXNGRetriever
        from salva_core.schemas import RetrievalPolicy

        policy = RetrievalPolicy(
            local_first=True,
            allow_public_fallback=False,
            html_fallback=False,
            max_instances_per_query=1,
        )
        retriever = SearXNGRetriever(policy=policy)
        results = retriever.search(query, n=5)

        result_count = len(results)
        raw_scores = [
            float(r["score"]) for r in results
            if isinstance(r, dict) and "score" in r and r["score"] is not None
        ]
        avg_score = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
        provider_names = list({a.base_url for a in retriever.last_attempts if a.succeeded})

    except Exception as exc:
        logger.debug("live probe error for %s: %s", key, exc)
        has_error = True

    latency_ms = (time.monotonic() - t0) * 1000
    signal = LiveProbeSignal(
        result_count=result_count,
        avg_score=avg_score,
        has_error=has_error,
        latency_ms=latency_ms,
        searxng_url=key,
        provider_names=provider_names,
    )

    if not has_error:
        _set_probe_cache(signal)

    return signal


def get_or_run_probe(query: str, timeout: float = 3.0) -> LiveProbeSignal | None:
    """Return cached signal or run a fresh probe. Entry point for topology.py."""
    cached = get_probe_signal()
    if cached is not None:
        return cached
    return run_live_probe(query, timeout=timeout)
