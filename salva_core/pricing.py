from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

_PRICING_PATH_ENV = os.environ.get("SALVA_PRICING_CATALOG_PATH")
DEFAULT_PRICING_PATH = Path(_PRICING_PATH_ENV).expanduser() if _PRICING_PATH_ENV else None
_PRICING_URL_ENV = os.environ.get("SALVA_PRICING_CATALOG_URL")
DEFAULT_PRICING_URL = _PRICING_URL_ENV if _PRICING_URL_ENV else None


@dataclass(slots=True)
class PricingQuote:
    provider_name: str | None = None
    model_name: str | None = None
    usd_per_1k_tokens: float | None = None
    currency: str = "USD"
    source_name: str | None = None
    source_url: str | None = None
    source_latency_ms: float | None = None
    fetched_at: datetime | None = None
    notes: list[str] = field(default_factory=list)


def resolve_pricing_quote(
    provider_name: str | None = None,
    model_name: str | None = None,
    catalog_url: str | None = None,
    catalog_path: str | None = None,
) -> PricingQuote | None:
    source_path = _resolve_catalog_path(catalog_path)
    catalog_url = catalog_url or DEFAULT_PRICING_URL

    if source_path is None and catalog_url is None:
        return None

    started = time.perf_counter()
    catalog = load_pricing_catalog(catalog_path=source_path, catalog_url=catalog_url)
    source_latency_ms = round((time.perf_counter() - started) * 1000.0, 2)

    match = _match_quote(catalog, provider_name=provider_name, model_name=model_name)
    if match is None:
        return PricingQuote(
            provider_name=provider_name,
            model_name=model_name,
            source_name=catalog.get("source_name"),
            source_url=catalog.get("source_url"),
            source_latency_ms=source_latency_ms,
            fetched_at=_coerce_datetime(catalog.get("generated_at")),
            notes=["pricing_quote_not_found"],
        )

    return PricingQuote(
        provider_name=provider_name or match.get("provider_name"),
        model_name=model_name or match.get("model_name"),
        usd_per_1k_tokens=_coerce_float(match.get("usd_per_1k_tokens")),
        currency=str(match.get("currency") or "USD"),
        source_name=catalog.get("source_name") or match.get("source_name"),
        source_url=catalog.get("source_url") or match.get("source_url"),
        source_latency_ms=source_latency_ms,
        fetched_at=_coerce_datetime(catalog.get("generated_at")),
        notes=list(match.get("notes", [])),
    )


def build_pricing_catalog_response(
    provider_name: str | None = None,
    model_name: str | None = None,
    catalog_url: str | None = None,
    catalog_path: str | None = None,
) -> dict[str, Any]:
    source_path = _resolve_catalog_path(catalog_path)
    catalog_url = catalog_url or DEFAULT_PRICING_URL

    if source_path is None and catalog_url is None:
        return {
            "generated_at": None,
            "source_name": None,
            "source_url": None,
            "source_latency_ms": None,
            "entries": [],
            "resolved_quote": None,
            "resolved": False,
        }

    started = time.perf_counter()
    catalog = load_pricing_catalog(catalog_path=source_path, catalog_url=catalog_url)
    source_latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
    resolved = resolve_pricing_quote(
        provider_name=provider_name,
        model_name=model_name,
        catalog_url=catalog_url,
        catalog_path=str(source_path) if source_path is not None else None,
    )

    return {
        "generated_at": _coerce_datetime(catalog.get("generated_at")),
        "source_name": catalog.get("source_name"),
        "source_url": catalog.get("source_url"),
        "source_latency_ms": source_latency_ms,
        "entries": [normalize_pricing_entry(entry) for entry in catalog.get("entries", []) if isinstance(entry, dict)],
        "resolved_quote": None if resolved is None else {
            "provider_name": resolved.provider_name,
            "model_name": resolved.model_name,
            "usd_per_1k_tokens": resolved.usd_per_1k_tokens,
            "currency": resolved.currency,
            "notes": resolved.notes,
        },
        "resolved": resolved is not None and resolved.usd_per_1k_tokens is not None,
    }


def load_pricing_catalog(
    catalog_path: Path | None = None,
    catalog_url: str | None = None,
) -> dict[str, Any]:
    if catalog_path and catalog_path.exists():
        return json.loads(catalog_path.read_text(encoding="utf-8"))

    if catalog_url:
        request = Request(catalog_url, headers={"User-Agent": "SalvaRuntime/1.0"})
        with urlopen(request, timeout=20) as response:  # nosec: runtime-controlled URL
            payload = response.read().decode("utf-8")
        return json.loads(payload)

    return {"generated_at": datetime.now(UTC).isoformat(), "entries": []}


def save_pricing_catalog(payload: dict[str, Any], output_path: str | None = None) -> Path:
    target = Path(output_path).expanduser() if output_path else _default_catalog_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_default_catalog_payload(entries: list[dict[str, Any]], source_name: str | None = None, source_url: str | None = None) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_name": source_name,
        "source_url": source_url,
        "entries": entries,
    }


def normalize_pricing_catalog_payload(
    payload: Any,
    source_name: str | None = None,
    source_url: str | None = None,
) -> dict[str, Any]:
    if isinstance(payload, dict) and "entries" in payload:
        normalized = dict(payload)
        normalized.setdefault("generated_at", datetime.now(UTC).isoformat())
        if source_name is not None:
            normalized["source_name"] = source_name
        if source_url is not None:
            normalized["source_url"] = source_url
        normalized["entries"] = [normalize_pricing_entry(entry) for entry in normalized.get("entries", []) if isinstance(entry, dict)]
        return normalized

    if isinstance(payload, list):
        return build_default_catalog_payload(
            [normalize_pricing_entry(entry) for entry in payload if isinstance(entry, dict)],
            source_name=source_name,
            source_url=source_url,
        )

    if isinstance(payload, dict):
        candidate_entries = payload.get("pricing") or payload.get("models") or payload.get("data") or []
        if isinstance(candidate_entries, list):
            return build_default_catalog_payload(
                [normalize_pricing_entry(entry) for entry in candidate_entries if isinstance(entry, dict)],
                source_name=source_name,
                source_url=source_url,
            )

    return build_default_catalog_payload([], source_name=source_name, source_url=source_url)


def _default_catalog_path() -> Path:
    if DEFAULT_PRICING_PATH:
        return DEFAULT_PRICING_PATH
    return Path(tempfile.gettempdir()) / "salva-pricing-catalog.json"


def _resolve_catalog_path(catalog_path: str | Path | None) -> Path | None:
    if catalog_path:
        return Path(catalog_path).expanduser()
    if DEFAULT_PRICING_PATH:
        return DEFAULT_PRICING_PATH
    return None


def _match_quote(catalog: dict[str, Any], provider_name: str | None, model_name: str | None) -> dict[str, Any] | None:
    entries = catalog.get("entries", [])
    if not isinstance(entries, list):
        return None

    normalized_provider = (provider_name or "").strip().lower()
    normalized_model = (model_name or "").strip().lower()

    best_match: dict[str, Any] | None = None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_provider = str(entry.get("provider_name") or "").strip().lower()
        entry_model = str(entry.get("model_name") or "").strip().lower()
        if normalized_provider and entry_provider != normalized_provider:
            continue
        if normalized_model and entry_model and entry_model != normalized_model:
            continue
        best_match = entry
        if normalized_provider and normalized_model:
            break
    return best_match


def normalize_pricing_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    if "usd_per_1k_tokens" not in normalized:
        input_price = normalized.get("input_usd_per_1m")
        output_price = normalized.get("output_usd_per_1m")
        if input_price is not None:
            normalized["usd_per_1k_tokens"] = float(input_price) / 1000.0
        elif output_price is not None:
            normalized["usd_per_1k_tokens"] = float(output_price) / 1000.0
    if "provider_name" not in normalized and "provider" in normalized:
        normalized["provider_name"] = normalized["provider"]
    if "model_name" not in normalized and "model" in normalized:
        normalized["model_name"] = normalized["model"]
    if "currency" not in normalized:
        normalized["currency"] = "USD"
    return normalized


def _coerce_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _coerce_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
