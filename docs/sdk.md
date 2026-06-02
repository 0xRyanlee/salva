# Salva Python SDK

Thin Python wrappers for the REST API.

## Install

Use the project package directly:

```bash
pip install -e .
```

If you only need the SDK in an external environment, install the runtime package
and point it at a running Salva API server.

## Sync client

```python
from salva_sdk import SalvaClient

with SalvaClient(base_url="http://localhost:8000", api_key="...") as client:
    result = client.discover(
        market="Germany",
        industry="legal tech",
        objective="find_companies",
        tenant_id="tenant-acme",
        domain_hints={"signal_terms": ["compliance", "e-signature"]},
    )
```

`tenant_id` is optional and is forwarded to both discovery and job creation
payloads when provided.

## Async client

```python
from salva_sdk import AsyncSalvaClient

async with AsyncSalvaClient(base_url="http://localhost:8000") as client:
    routes = await client.routes()
```

## Available methods

- `discover`
- `create_job`
- `job_status`
- `run_result`
- `pilot`
- `experience_plan`
- `routes`
- `route`
- `providers`
- `provider_catalog`

## Contract rule

The SDK does not call internal service functions. It only wraps REST endpoints,
so it stays aligned with the public contract layer.

For MCP HTTP deployments, `SALVA_MCP_API_KEY` must match `SALVA_API_KEY`
when the API key is enabled. The env check happens at process start.
