from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx


def _listify(values: Sequence[str] | None) -> list[str]:
    return [value for value in (values or []) if value]


def _intent_payload(
    *,
    market: str,
    industry: str,
    product: str | None = None,
    role: str | None = None,
    extra_keywords: Sequence[str] | None = None,
    negative_keywords: Sequence[str] | None = None,
    constraints: Mapping[str, Any] | None = None,
    domain_hints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "market": market,
        "industry": industry,
        "extra_keywords": _listify(extra_keywords),
        "negative_keywords": _listify(negative_keywords),
        "constraints": dict(constraints or {}),
    }
    if product:
        payload["product"] = product
    if role:
        payload["role"] = role
    if domain_hints:
        payload["domain_hints"] = dict(domain_hints)
    return payload


def _discovery_payload(
    *,
    objective: str,
    market: str,
    industry: str,
    tenant_id: str | None = None,
    product: str | None = None,
    role: str | None = None,
    output_profile: str = "lead",
    max_results: int = 50,
    transform: Mapping[str, Any] | None = None,
    retrieval: Mapping[str, Any] | None = None,
    enrichment: Mapping[str, Any] | None = None,
    extra_keywords: Sequence[str] | None = None,
    negative_keywords: Sequence[str] | None = None,
    constraints: Mapping[str, Any] | None = None,
    domain_hints: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "objective": objective,
        "output_profile": output_profile,
        "max_results": max_results,
        "intent": _intent_payload(
            market=market,
            industry=industry,
            product=product,
            role=role,
            extra_keywords=extra_keywords,
            negative_keywords=negative_keywords,
            constraints=constraints,
            domain_hints=domain_hints,
        ),
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    if transform is not None:
        payload["transform"] = dict(transform)
    if retrieval is not None:
        payload["retrieval"] = dict(retrieval)
    if enrichment is not None:
        payload["enrichment"] = dict(enrichment)
    return payload


def _headers(api_key: str | None, headers: Mapping[str, str] | None) -> dict[str, str]:
    merged = dict(headers or {})
    if api_key:
        merged.setdefault("X-Salva-Key", api_key)
    return merged


class _BaseClient:
    def __init__(self, base_url: str, api_key: str | None = None, headers: Mapping[str, str] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = _headers(api_key, headers)

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        response.raise_for_status()


class SalvaClient(_BaseClient):
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        headers: Mapping[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(base_url, api_key=api_key, headers=headers)
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self.headers,
            transport=transport,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "SalvaClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._client.request(method, path, params=params, json=json_payload)
        self._raise(response)
        return response.json()

    def discover(
        self,
        *,
        market: str,
        industry: str,
        objective: str = "find_companies",
        tenant_id: str | None = None,
        product: str | None = None,
        role: str | None = None,
        output_profile: str = "lead",
        max_results: int = 50,
        extra_keywords: Sequence[str] | None = None,
        negative_keywords: Sequence[str] | None = None,
        constraints: Mapping[str, Any] | None = None,
        domain_hints: Mapping[str, Any] | None = None,
        transform: Mapping[str, Any] | None = None,
        retrieval: Mapping[str, Any] | None = None,
        enrichment: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/v1/discover",
            json_payload=_discovery_payload(
                objective=objective,
                market=market,
                industry=industry,
                tenant_id=tenant_id,
                product=product,
                role=role,
                output_profile=output_profile,
                max_results=max_results,
                extra_keywords=extra_keywords,
                negative_keywords=negative_keywords,
                constraints=constraints,
                domain_hints=domain_hints,
                transform=transform,
                retrieval=retrieval,
                enrichment=enrichment,
            ),
        )

    def create_job(
        self,
        *,
        market: str,
        industry: str,
        objective: str = "find_companies",
        tenant_id: str | None = None,
        product: str | None = None,
        role: str | None = None,
        output_profile: str = "lead",
        max_results: int = 50,
        extra_keywords: Sequence[str] | None = None,
        negative_keywords: Sequence[str] | None = None,
        constraints: Mapping[str, Any] | None = None,
        domain_hints: Mapping[str, Any] | None = None,
        transform: Mapping[str, Any] | None = None,
        retrieval: Mapping[str, Any] | None = None,
        enrichment: Mapping[str, Any] | None = None,
        wait_for_completion: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "discovery": _discovery_payload(
                objective=objective,
                market=market,
                industry=industry,
                tenant_id=tenant_id,
                product=product,
                role=role,
                output_profile=output_profile,
                max_results=max_results,
                extra_keywords=extra_keywords,
                negative_keywords=negative_keywords,
                constraints=constraints,
                domain_hints=domain_hints,
                transform=transform,
                retrieval=retrieval,
                enrichment=enrichment,
            ),
            "wait_for_completion": wait_for_completion,
        }
        return self._request_json("POST", "/v1/jobs", json_payload=payload)

    def job_status(self, job_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/v1/jobs/{job_id}")

    def run_result(self, run_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/v1/runs/{run_id}")

    def pilot(
        self,
        *,
        run_id: str | None = None,
        market: str = "",
        industry: str = "",
        objective: str = "find_companies",
        max_suggestions: int = 5,
        discovery: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": run_id,
            "max_suggestions": max_suggestions,
        }
        if discovery is not None:
            payload["discovery"] = dict(discovery)
        else:
            payload["discovery"] = _discovery_payload(
                objective=objective,
                market=market,
                industry=industry,
                max_results=50,
            )
        return self._request_json("POST", "/v1/pilot", json_payload=payload)

    def experience_plan(self, discovery: Mapping[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", "/v1/experience-plan", json_payload={"discovery": dict(discovery)})

    def routes(self) -> dict[str, Any]:
        return self._request_json("GET", "/v1/routes")

    def route(self, route_name: str) -> dict[str, Any]:
        return self._request_json("GET", f"/v1/routes/{route_name}")

    def providers(self) -> dict[str, Any]:
        return self._request_json("GET", "/v1/providers")

    def provider_catalog(self) -> dict[str, Any]:
        return self._request_json("GET", "/v1/providers/catalog")


class AsyncSalvaClient(_BaseClient):
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        headers: Mapping[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(base_url, api_key=api_key, headers=headers)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=self.headers,
            transport=transport,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncSalvaClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self._client.request(method, path, params=params, json=json_payload)
        self._raise(response)
        return response.json()

    async def discover(
        self,
        *,
        market: str,
        industry: str,
        objective: str = "find_companies",
        tenant_id: str | None = None,
        product: str | None = None,
        role: str | None = None,
        output_profile: str = "lead",
        max_results: int = 50,
        extra_keywords: Sequence[str] | None = None,
        negative_keywords: Sequence[str] | None = None,
        constraints: Mapping[str, Any] | None = None,
        domain_hints: Mapping[str, Any] | None = None,
        transform: Mapping[str, Any] | None = None,
        retrieval: Mapping[str, Any] | None = None,
        enrichment: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/v1/discover",
            json_payload=_discovery_payload(
                objective=objective,
                market=market,
                industry=industry,
                tenant_id=tenant_id,
                product=product,
                role=role,
                output_profile=output_profile,
                max_results=max_results,
                extra_keywords=extra_keywords,
                negative_keywords=negative_keywords,
                constraints=constraints,
                domain_hints=domain_hints,
                transform=transform,
                retrieval=retrieval,
                enrichment=enrichment,
            ),
        )

    async def create_job(
        self,
        *,
        market: str,
        industry: str,
        objective: str = "find_companies",
        tenant_id: str | None = None,
        product: str | None = None,
        role: str | None = None,
        output_profile: str = "lead",
        max_results: int = 50,
        extra_keywords: Sequence[str] | None = None,
        negative_keywords: Sequence[str] | None = None,
        constraints: Mapping[str, Any] | None = None,
        domain_hints: Mapping[str, Any] | None = None,
        transform: Mapping[str, Any] | None = None,
        retrieval: Mapping[str, Any] | None = None,
        enrichment: Mapping[str, Any] | None = None,
        wait_for_completion: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "discovery": _discovery_payload(
                objective=objective,
                market=market,
                industry=industry,
                tenant_id=tenant_id,
                product=product,
                role=role,
                output_profile=output_profile,
                max_results=max_results,
                extra_keywords=extra_keywords,
                negative_keywords=negative_keywords,
                constraints=constraints,
                domain_hints=domain_hints,
                transform=transform,
                retrieval=retrieval,
                enrichment=enrichment,
            ),
            "wait_for_completion": wait_for_completion,
        }
        return await self._request_json("POST", "/v1/jobs", json_payload=payload)

    async def job_status(self, job_id: str) -> dict[str, Any]:
        return await self._request_json("GET", f"/v1/jobs/{job_id}")

    async def run_result(self, run_id: str) -> dict[str, Any]:
        return await self._request_json("GET", f"/v1/runs/{run_id}")

    async def pilot(
        self,
        *,
        run_id: str | None = None,
        market: str = "",
        industry: str = "",
        objective: str = "find_companies",
        max_suggestions: int = 5,
        discovery: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": run_id,
            "max_suggestions": max_suggestions,
        }
        if discovery is not None:
            payload["discovery"] = dict(discovery)
        else:
            payload["discovery"] = _discovery_payload(
                objective=objective,
                market=market,
                industry=industry,
                max_results=50,
            )
        return await self._request_json("POST", "/v1/pilot", json_payload=payload)

    async def experience_plan(self, discovery: Mapping[str, Any]) -> dict[str, Any]:
        return await self._request_json("POST", "/v1/experience-plan", json_payload={"discovery": dict(discovery)})

    async def routes(self) -> dict[str, Any]:
        return await self._request_json("GET", "/v1/routes")

    async def route(self, route_name: str) -> dict[str, Any]:
        return await self._request_json("GET", f"/v1/routes/{route_name}")

    async def providers(self) -> dict[str, Any]:
        return await self._request_json("GET", "/v1/providers")

    async def provider_catalog(self) -> dict[str, Any]:
        return await self._request_json("GET", "/v1/providers/catalog")
