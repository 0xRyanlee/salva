from __future__ import annotations

from urllib.parse import urlparse


def classify_source_attempt(
    base_url: str,
    succeeded: bool,
    error: str | None,
) -> dict[str, str]:
    hostname = urlparse(base_url).hostname or ""
    source_class = _source_class(hostname)
    trust_level = _trust_level(source_class)
    risk_level = _risk_level(source_class, succeeded, error)
    crawl_mode = _recommended_crawl_mode(source_class, risk_level)

    return {
        "source_class": source_class,
        "trust_level": trust_level,
        "risk_level": risk_level,
        "recommended_crawl_mode": crawl_mode,
    }


def _source_class(hostname: str) -> str:
    if hostname in {"localhost", "127.0.0.1"}:
        return "local"
    if any(token in hostname for token in ["searx", "search.", "priv.", "northboot", "paulgo"]):
        return "public_mirror"
    if hostname:
        return "custom_remote"
    return "unknown"


def _trust_level(source_class: str) -> str:
    if source_class == "local":
        return "high"
    if source_class == "custom_remote":
        return "medium"
    if source_class == "public_mirror":
        return "medium"
    return "low"


def _risk_level(source_class: str, succeeded: bool, error: str | None) -> str:
    if source_class == "local":
        return "low" if succeeded else "medium"
    if error:
        lowered = error.lower()
        if any(token in lowered for token in ["timeout", "forbidden", "ssl", "refused", "blocked"]):
            return "high"
    if source_class == "public_mirror":
        return "medium" if succeeded else "high"
    if source_class == "custom_remote":
        return "medium"
    return "high"


def _recommended_crawl_mode(source_class: str, risk_level: str) -> str:
    if source_class == "local":
        return "normal"
    if risk_level == "high":
        return "wall_guarded"
    if risk_level == "medium":
        return "cautious"
    return "resilient"
