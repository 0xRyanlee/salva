from __future__ import annotations

import os
from typing import Any

from retrieval.sources.ddg_html import DDGHTMLRetriever
from retrieval.sources.ddgs_retriever import DDGSRetriever, _is_ddgs_available
from retrieval.sources.marginalia import MarginaliaRetriever, _marginalia_enabled
from retrieval.sources.obscura import ObscuraBrowserRetriever, _find_obscura_binary
from retrieval.sources.rss import RSSRetriever
from retrieval.sources.searxng import DEFAULT_LOCAL_INSTANCE, SearXNGRetriever
from retrieval.sources.searxng_pool import PublicSearXNGPool
from retrieval.sources.site_html import SiteHTMLRetriever
from retrieval.sources.sitemap import SitemapRetriever
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
    if _is_ddgs_available():
        kinds.add("ddgs")
    if _searxng_enabled():
        kinds.add("searxng")
    if os.getenv("WHOOGLE_URL", "").strip():
        kinds.add("whoogle")
    if _marginalia_enabled():
        kinds.add("marginalia")
    if _find_obscura_binary():
        kinds.add("obscura_browser")
    kinds.add("searxng_pool")  # always available; public instances may be in cooldown
    kinds.add("sitemap")       # source-direct; use via policy.providers with site_domains
    kinds.add("rss")           # source-direct; use via policy.providers with site_domains
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
            kind="ddgs",
            name="DDGS (primp TLS)",
            description=(
                "Multi-engine search via the `ddgs` library with Rust/primp TLS impersonation. "
                "Bypasses bot detection using JA3 fingerprint spoofing. "
                "Supports google, bing, brave, duckduckgo, yandex backends."
            ),
            supports_custom_endpoint=False,
            enabled_by_default=_is_ddgs_available(),
            env_vars=["DDGS_PROXY", "DDGS_BACKEND"],
        ),
        ProviderDescriptor(
            kind="marginalia",
            name="Marginalia Search",
            description=(
                "Marginalia runs its own crawler index, biased toward smaller and technical "
                "sites under-represented in mainstream indexes. Free public API, no key required."
            ),
            supports_custom_endpoint=True,
            enabled_by_default=True,
            env_vars=["MARGINALIA_BASE_URL", "MARGINALIA_ENABLED"],
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
        ProviderDescriptor(
            kind="searxng_pool",
            name="Public SearXNG Pool",
            description=(
                "Last-resort fallback pool of public SearXNG instances. "
                "Per-instance circuit breaker; max 2 tries per query. "
                "Instances are frequently rate-limited or blocked — long cooldown on failure."
            ),
            supports_custom_endpoint=False,
            enabled_by_default=True,
            env_vars=["SEARXNG_POOL_CONFIG"],
        ),
        ProviderDescriptor(
            kind="sitemap",
            name="Sitemap Source-Direct",
            description=(
                "Discovers entity-directory URLs from a domain's robots.txt → sitemap.xml. "
                "Source-direct: does not accept a query string. "
                "Use via policy.providers with site_domains to target specific domains."
            ),
            supports_custom_endpoint=False,
            supports_site_domains=True,
            enabled_by_default=False,
        ),
        ProviderDescriptor(
            kind="rss",
            name="RSS/Atom Source-Direct",
            description=(
                "Fetches RSS or Atom feed entries from a domain's auto-detected feed URL. "
                "Source-direct: does not accept a query string. "
                "Use via policy.providers with site_domains to target specific domains."
            ),
            supports_custom_endpoint=False,
            supports_site_domains=True,
            enabled_by_default=False,
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
    # ddgs (primp TLS) preferred over ddg_html when the package is installed.
    content_fetch_kind = "obscura_browser" if _find_obscura_binary() else "site_html"
    defaults = []
    if _searxng_enabled():
        defaults.append(RetrievalProviderConfig(kind="searxng"))
    defaults.append(RetrievalProviderConfig(kind="whoogle"))
    if _is_ddgs_available():
        defaults.append(RetrievalProviderConfig(kind="ddgs"))
    else:
        defaults.append(RetrievalProviderConfig(kind="ddg_html"))
    defaults.append(RetrievalProviderConfig(kind="marginalia"))
    defaults.append(RetrievalProviderConfig(kind="searxng_pool"))
    defaults.append(RetrievalProviderConfig(kind=content_fetch_kind))
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
    elif config.kind == "ddgs":
        provider = DDGSRetriever(policy=merged_policy)
    elif config.kind == "marginalia":
        provider = MarginaliaRetriever(policy=merged_policy)
    elif config.kind == "ddg_html":
        provider = DDGHTMLRetriever(policy=merged_policy, base_url=config.base_url or None)
    elif config.kind == "site_html":
        provider = SiteHTMLRetriever(policy=merged_policy)
    elif config.kind == "obscura_browser":
        provider = ObscuraBrowserRetriever(policy=merged_policy)
    elif config.kind == "searxng_pool":
        provider = PublicSearXNGPool(policy=merged_policy)
    elif config.kind == "sitemap":
        provider = SitemapRetriever(policy=merged_policy)
    elif config.kind == "rss":
        provider = RSSRetriever(policy=merged_policy)
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
