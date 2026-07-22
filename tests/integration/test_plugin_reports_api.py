import asyncio

from apps.api.main import discover, plugin_reports
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest


def test_plugin_reports_api_roundtrip() -> None:
    payload = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software", product="crm"),
        enrichment={
            "mode": "selected",
            "enabled_plugins": ["site_html"],
            "max_targets": 3,
            "parallelism": 2,
            "auto_merge": True,
        },
        max_results=5,
    )
    response = asyncio.run(discover(payload))
    run_id = response.meta.get("run_id")
    assert run_id is not None

    reports = asyncio.run(plugin_reports(run_id=run_id))
    assert reports.total >= 0
    assert isinstance(reports.items, list)
