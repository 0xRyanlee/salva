from __future__ import annotations

import json

import salva_core.pricing as pricing


def test_normalize_pricing_entry_and_catalog_payload() -> None:
    entry = pricing.normalize_pricing_entry(
        {
            "provider": "demo",
            "model": "alpha",
            "input_usd_per_1m": 12.5,
        }
    )
    assert entry["provider_name"] == "demo"
    assert entry["model_name"] == "alpha"
    assert entry["usd_per_1k_tokens"] == 0.0125
    assert entry["currency"] == "USD"

    payload = pricing.normalize_pricing_catalog_payload(
        [
            {"provider": "demo", "input_usd_per_1m": 10},
            {"provider_name": "other", "usd_per_1k_tokens": 0.2},
        ],
        source_name="demo-catalog",
        source_url="https://example.com/pricing",
    )

    assert payload["source_name"] == "demo-catalog"
    assert payload["source_url"] == "https://example.com/pricing"
    assert len(payload["entries"]) == 2


def test_resolve_and_build_pricing_catalog_from_file(tmp_path) -> None:
    catalog_path = tmp_path / "pricing.json"
    catalog_path.write_text(
        json.dumps(
            {
                "generated_at": "2025-01-01T12:00:00Z",
                "source_name": "demo-catalog",
                "source_url": "https://example.com/pricing",
                "entries": [
                    {
                        "provider_name": "demo",
                        "model_name": "alpha",
                        "usd_per_1k_tokens": 0.02,
                        "currency": "USD",
                        "notes": ["primary"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    quote = pricing.resolve_pricing_quote(
        provider_name="demo",
        model_name="alpha",
        catalog_path=str(catalog_path),
    )
    assert quote is not None
    assert quote.usd_per_1k_tokens == 0.02
    assert quote.source_name == "demo-catalog"
    assert quote.fetched_at is not None

    response = pricing.build_pricing_catalog_response(
        provider_name="demo",
        model_name="alpha",
        catalog_path=str(catalog_path),
    )
    assert response["resolved"] is True
    assert response["resolved_quote"]["provider_name"] == "demo"
    assert response["entries"][0]["provider_name"] == "demo"


def test_resolve_pricing_quote_and_catalog_fallback(monkeypatch) -> None:
    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "generated_at": "2025-01-01T12:00:00Z",
                    "source_name": "remote-catalog",
                    "entries": [
                        {"provider_name": "remote", "model_name": "beta", "usd_per_1k_tokens": 0.05}
                    ],
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout=20):  # noqa: ANN001
        return DummyResponse()

    monkeypatch.setattr(pricing, "urlopen", fake_urlopen)

    quote = pricing.resolve_pricing_quote(provider_name="missing", catalog_url="https://example.com/pricing")
    assert quote is not None
    assert quote.usd_per_1k_tokens is None
    assert "pricing_quote_not_found" in quote.notes

    remote_quote = pricing.resolve_pricing_quote(provider_name="remote", model_name="beta", catalog_url="https://example.com/pricing")
    assert remote_quote is not None
    assert remote_quote.usd_per_1k_tokens == 0.05

    response = pricing.build_pricing_catalog_response(catalog_url="https://example.com/pricing")
    assert response["source_name"] == "remote-catalog"
    assert response["resolved"] is True


def test_pricing_no_source_and_dict_payload_paths(tmp_path) -> None:
    assert pricing.resolve_pricing_quote() is None

    response = pricing.build_pricing_catalog_response()
    assert response["resolved"] is False
    assert response["entries"] == []

    payload = pricing.normalize_pricing_catalog_payload(
        {
            "pricing": [
                {"provider": "alpha", "model": "beta", "output_usd_per_1m": 22},
            ],
        },
        source_name="override-name",
        source_url="https://example.com/override",
    )
    assert payload["source_name"] == "override-name"
    assert payload["source_url"] == "https://example.com/override"
    assert payload["entries"][0]["provider_name"] == "alpha"
    assert payload["entries"][0]["model_name"] == "beta"
    assert payload["entries"][0]["usd_per_1k_tokens"] == 0.022

    output_path = pricing.save_pricing_catalog(payload, output_path=str(tmp_path / "catalog.json"))
    assert output_path.exists()
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["source_name"] == "override-name"
