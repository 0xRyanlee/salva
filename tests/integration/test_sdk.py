from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from salva_sdk import AsyncSalvaClient, SalvaClient


def _handler(request: httpx.Request) -> httpx.Response:
    if request.method == "POST" and request.url.path == "/v1/discover":
        body = json.loads(request.content.decode() or "{}")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "path": request.url.path,
                "objective": body["objective"],
                "tenant_id": body.get("tenant_id"),
                "intent": body["intent"],
                "headers": dict(request.headers),
            },
        )
    if request.method == "POST" and request.url.path == "/v1/jobs":
        return httpx.Response(200, json={"ok": True, "job_id": "job:123", "status": "queued"})
    if request.method == "GET" and request.url.path == "/v1/jobs/job:123":
        return httpx.Response(200, json={"ok": True, "job_id": "job:123", "status": "completed"})
    if request.method == "GET" and request.url.path == "/v1/routes":
        return httpx.Response(200, json={"items": [{"name": "quick_scan"}], "total": 1})
    if request.method == "GET" and request.url.path == "/v1/routes/quick_scan":
        return httpx.Response(200, json={"name": "quick_scan", "experience_profile": "quick_scan"})
    if request.method == "POST" and request.url.path == "/v1/pilot":
        body = json.loads(request.content.decode() or "{}")
        return httpx.Response(200, json={"ok": True, "run_id": body.get("run_id"), "pilot": {}})
    if request.method == "POST" and request.url.path == "/v1/experience-plan":
        return httpx.Response(200, json={"plan": {"profile": "lead_focus"}})
    if request.method == "GET" and request.url.path == "/v1/providers":
        return httpx.Response(200, json={"items": [], "total": 0})
    if request.method == "GET" and request.url.path == "/v1/providers/catalog":
        return httpx.Response(200, json={"items": [], "total": 0})
    return httpx.Response(404, json={"error": "not found", "path": request.url.path})


def test_sync_sdk_wraps_rest_endpoints() -> None:
    transport = httpx.MockTransport(_handler)
    with SalvaClient(base_url="https://salva.test", api_key="secret", transport=transport) as client:
        discover = client.discover(
            market="Germany",
            industry="legal tech",
            objective="find_companies",
            tenant_id="tenant-sdk",
            domain_hints={"signal_terms": ["compliance"]},
        )
        job = client.create_job(
            market="Germany",
            industry="legal tech",
            tenant_id="tenant-sdk",
            wait_for_completion=False,
        )
        status = client.job_status("job:123")
        routes = client.routes()
        route = client.route("quick_scan")
        pilot = client.pilot(run_id="run:1", market="Germany", industry="legal tech")
        plan = client.experience_plan({"objective": "find_leads"})
        providers = client.providers()
        provider_catalog = client.provider_catalog()

    assert discover["ok"] is True
    assert discover["tenant_id"] == "tenant-sdk"
    assert discover["intent"]["domain_hints"]["signal_terms"] == ["compliance"]
    assert discover["headers"]["x-salva-key"] == "secret"
    assert job["job_id"] == "job:123"
    assert status["status"] == "completed"
    assert routes["total"] == 1
    assert route["name"] == "quick_scan"
    assert pilot["ok"] is True
    assert plan["plan"]["profile"] == "lead_focus"
    assert providers["total"] == 0
    assert provider_catalog["total"] == 0


def test_async_sdk_wraps_rest_endpoints() -> None:
    async def run() -> dict[str, Any]:
        transport = httpx.MockTransport(_handler)
        async with AsyncSalvaClient(base_url="https://salva.test", transport=transport) as client:
            return {
                "discover": await client.discover(market="US", industry="software", tenant_id="tenant-sdk"),
                "job": await client.create_job(
                    market="US",
                    industry="software",
                    tenant_id="tenant-sdk",
                    wait_for_completion=False,
                ),
                "status": await client.job_status("job:123"),
                "routes": await client.routes(),
            }

    result = asyncio.run(run())

    assert result["discover"]["objective"] == "find_companies"
    assert result["job"]["job_id"] == "job:123"
    assert result["status"]["status"] == "completed"
    assert result["routes"]["total"] == 1
