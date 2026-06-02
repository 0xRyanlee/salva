from __future__ import annotations

import os
from typing import Any

from retrieval.sources.ddg_html import DDGHTMLRetriever
from retrieval.sources.obscura import ObscuraBrowserRetriever, _find_obscura_binary
from retrieval.sources.searxng import DEFAULT_LOCAL_INSTANCE, SearXNGRetriever
from retrieval.sources.site_html import SiteHTMLRetriever
from retrieval.sources.whoogle import WhoogleRetriever
from salva_core.schemas import (
    ProviderDescriptor,
    RetrievalPolicy,
    RetrievalProviderConfig,
)


def _searxng_enabled() -> bool:
    """False when SEARXNG_ENABLED=false — skips SearXNG entirely, no Docker needed."""
    return os.getenv("SEARXNG_ENABLED", "true").lower() not in ("0", "false", "no")


def available_provider_kinds() -> set[str]:
    """
    Return the set of provider kinds that are usable in the current environment.
    Called at policy-build time so availability is checked once per request.
    """
    kinds: set[str] = {"ddg_html", "site_html"}  # always available
    if _searxng_enabled():
        kinds.add("searxng")
    if os.getenv("WHOOGLE_URL", "").strip():
        kinds.add("whoogle")
    if _find_obscura_binary():
        kinds.add("obscura_browser")
    return kinds


def list_provider_descriptors() -> list[ProviderDescriptor]:
    return [
        ProviderDescriptor(
            kind="searxng",
            name="SearXNG",
            description="SearXNG search provider with JSON-first and HTML fallback behavior.",
            supports_custom_endpoint=True,
            enabled_by_default=True,
            env_vars=["SEARXNG_URL", "SEARXNG_FALLBACK_URLS"],
        ),
        ProviderDescriptor(
            kind="whoogle",
            name="Whoogle",
            description="Self-hosted Whoogle search endpoint.",
            supports_custom_endpoint=True,
            enabled_by_default=True,
            env_vars=["WHOOGLE_URL"],
        ),
        ProviderDescriptor(
            kind="ddg_html",
            name="DuckDuckGo HTML",
            description="DuckDuckGo HTML fallback provider without external API keys.",
            supports_custom_endpoint=True,
            enabled_by_default=True,
        ),
        ProviderDescriptor(
            kind="site_html",
            name="Site HTML",
            description="Site-specific HTML fetch and parse provider for domain-aware retrieval.",
            supports_custom_endpoint=False,
            supports_site_domains=True,
            enabled_by_default=True,
            env_vars=["SITE_HTML_DOMAINS"],
        ),
        ProviderDescriptor(
            kind="obscura_browser",
            name="Obscura Browser",
            description=(
                "Headless browser provider using Obscura (Rust/V8). Executes JavaScript, "
                "bypasses basic bot protection, and supports parallel scraping. "
                "Auto-detected from PATH or OBSCURA_BIN env. Falls back to static HTML if absent."
            ),
            supports_custom_endpoint=False,
            supports_site_domains=True,
            enabled_by_default=bool(_find_obscura_binary()),
            env_vars=["OBSCURA_BIN", "OBSCURA_STEALTH", "OBSCURA_PROXY", "SITE_HTML_DOMAINS"],
        ),
    ]


def build_provider_chain(
    policy: RetrievalPolicy,
    strategy: str,
) -> list[object]:
    configs = [config for config in policy.providers if config.enabled]
    if not configs:
        return _build_default_chain(policy, strategy)

    providers: list[object] = []
    for config in configs:
        provider = _build_provider(policy, config, strategy)
        if provider is not None:
            providers.append(provider)
    return providers


def _build_default_chain(policy: RetrievalPolicy, strategy: str) -> list[object]:
    # obscura_browser replaces site_html when the binary is available.
    # SearXNG is skipped entirely when SEARXNG_ENABLED=false (no Docker needed).
    content_fetch_kind = "obscura_browser" if _find_obscura_binary() else "site_html"
    defaults = []
    if _searxng_enabled():
        defaults.append(RetrievalProviderConfig(kind="searxng"))
    defaults += [
        RetrievalProviderConfig(kind="whoogle"),
        RetrievalProviderConfig(kind="ddg_html"),
        RetrievalProviderConfig(kind=content_fetch_kind),
    ]
    providers: list[object] = []
    for config in defaults:
        provider = _build_provider(policy, config, strategy)
        if provider is not None:
            providers.append(provider)
    return providers


def _build_provider(
    policy: RetrievalPolicy,
    config: RetrievalProviderConfig,
    strategy: str,
) -> object | None:
    merged_policy = policy.model_copy(
        update=_apply_provider_overrides(policy, config),
    )

    provider: object | None
    if config.kind == "searxng":
        provider = SearXNGRetriever(policy=merged_policy, base_url=config.base_url or DEFAULT_LOCAL_INSTANCE)
    elif config.kind == "whoogle":
        provider = WhoogleRetriever(policy=merged_policy, base_url=config.base_url)
    elif config.kind == "ddg_html":
        provider = DDGHTMLRetriever(policy=merged_policy, base_url=config.base_url or None)
    elif config.kind == "site_html":
        provider = SiteHTMLRetriever(policy=merged_policy)
    elif config.kind == "obscura_browser":
        provider = ObscuraBrowserRetriever(policy=merged_policy)
    else:  # pragma: no cover - guard for future extension
        return None

    provider.strategy = strategy
    return provider


def _apply_provider_overrides(
    policy: RetrievalPolicy,
    config: RetrievalProviderConfig,
) -> dict[str, Any]:
    update: dict[str, Any] = {}
    if config.request_timeout is not None:
        update["request_timeout"] = config.request_timeout
    if config.request_delay is not None:
        update["request_delay"] = config.request_delay
    if config.cooldown_seconds is not None:
        update["cooldown_seconds"] = config.cooldown_seconds
    if config.max_instances_per_query is not None:
        update["max_instances_per_query"] = config.max_instances_per_query
    if config.allow_public_fallback is not None:
        update["allow_public_fallback"] = config.allow_public_fallback
    if config.prefer_builtin_instances is not None:
        update["prefer_builtin_instances"] = config.prefer_builtin_instances
    if config.html_fallback is not None:
        update["html_fallback"] = config.html_fallback
    if config.engine_rotation is not None:
        update["engine_rotation"] = config.engine_rotation

    if config.site_domains:
        update["site_domains"] = _merge_unique(policy.site_domains, config.site_domains)
    if config.extra_instances:
        update["extra_instances"] = _merge_unique(policy.extra_instances, config.extra_instances)
    return update


def _merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in [*primary, *secondary]:
        normalized = value.strip().lower().removeprefix("www.")
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(normalized)
    return merged
