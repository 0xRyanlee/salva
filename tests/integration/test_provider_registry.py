from fastapi.testclient import TestClient

from apps.api import main
from retrieval.router import RoutedRetriever
from salva_core.schemas import RetrievalPolicy, RetrievalProviderConfig


def test_provider_registry_allows_custom_provider_endpoints() -> None:
    policy = RetrievalPolicy(
        providers=[
            RetrievalProviderConfig(
                kind="whoogle",
                base_url="https://whoogle.example",
            )
        ]
    )

    routed = RoutedRetriever(policy=policy, strategy="dive")

    assert len(routed.providers) == 1
    assert getattr(routed.providers[0], "base_url", None) == "https://whoogle.example"
    assert getattr(routed.providers[0], "strategy", None) == "dive"


def test_provider_catalog_endpoint_lists_builtins() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/providers")

    assert response.status_code == 200
    body = response.json()
    kinds = {item["kind"] for item in body["items"]}
    assert {"searxng", "whoogle", "ddg_html", "site_html"}.issubset(kinds)


def test_provider_interface_catalog_exposes_all_planes() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/providers/catalog")

    assert response.status_code == 200
    body = response.json()
    families = {item["family"] for item in body["items"]}
    kinds = {item["kind"] for item in body["items"]}
    assert {"search", "llm", "vector_store", "relational_store", "osint"}.issubset(families)
    assert {"searxng", "whoogle", "ddg_html", "site_html", "omlx", "semantic_plane", "sqlite_hold_store"}.issubset(kinds)
