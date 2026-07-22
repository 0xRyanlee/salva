import asyncio

from apps.api import main
from apps.api.main import query_families
from salva_core.persistence import persist_discovery_run
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest, TelemetryRecord


def test_query_families_api_roundtrip(tmp_path) -> None:
    db_path = str(tmp_path / "salva_test.db")
    main.list_query_family_memory = lambda run_id=None, objective=None, strategy=None, limit=200, offset=0: __import__(
        "salva_core.persistence",
        fromlist=["list_query_family_memory"],
    ).list_query_family_memory(
        run_id=run_id,
        objective=objective,
        strategy=strategy,
        limit=limit,
        offset=offset,
        path=db_path,
    )
    run_id = persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software", product="crm", role="reseller"),
        ),
        entities=[],
        relations=[],
        telemetry=[
            TelemetryRecord(
                query="software reseller germany",
                round_num=1,
                strategy="dive",
                results_total=10,
                results_qualified=3,
                avg_score=0.7,
                metadata={
                    "round_strategy": "dive",
                    "content_weights": {"title": 0.45, "platform": 0.1},
                    "source_hints": ["example.com"],
                    "notes": ["precision_first"],
                    "source_nodes": ["software", "reseller"],
                },
            )
        ],
        meta={"qualified_count": 3, "raw_count": 10, "provider_kinds": []},
        source_attempts=[],
        path=db_path,
    )

    response = asyncio.run(query_families(run_id=run_id, limit=10, offset=0))

    assert response.total == 1
    assert response.items[0].query == "software reseller germany"
    assert response.items[0].success_score == 0.3
