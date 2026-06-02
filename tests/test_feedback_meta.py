from salva_core import service
from salva_core.schemas import DiscoveryIntent, DiscoveryRequest


def test_run_discovery_attaches_feedback(monkeypatch) -> None:
    def fake_execute_discovery(payload: DiscoveryRequest):
        return [], [], [], {"qualified_count": 0, "raw_count": 0}, []

    monkeypatch.setattr(service, "execute_discovery", fake_execute_discovery)
    monkeypatch.setattr(service, "persist_discovery_run", lambda *args, **kwargs: "run:demo")
    monkeypatch.setattr(
        service,
        "build_request_feedback",
        lambda run_id, payload: {
            "mate": {"run_id": run_id, "estimated_tokens_saved": 0},
            "pilot": {"run_id": run_id, "recommended_retrieval_mode": "resilient"},
        },
    )
    monkeypatch.setattr(service, "update_run_meta", lambda *args, **kwargs: None)

    entities, relations, telemetry, meta = service.run_discovery(
        DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(market="Germany", industry="software"),
        )
    )

    assert entities == []
    assert relations == []
    assert telemetry == []
    assert meta["run_id"] == "run:demo"
    assert meta["feedback"]["mate"]["run_id"] == "run:demo"
    assert meta["feedback"]["pilot"]["recommended_retrieval_mode"] == "resilient"
