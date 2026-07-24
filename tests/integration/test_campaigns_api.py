import asyncio
from datetime import UTC, datetime, timedelta

import pytest

import salva_core.persistence as persistence
from apps.api import main
from apps.api.main import (
    campaign_archive,
    campaign_clear_cache,
    campaign_create,
    campaign_delete,
    campaign_detail,
    campaign_unarchive,
    campaign_update,
    campaigns,
    discover,
)
from salva_core.persistence import persist_discovery_run
from salva_core.persistence.db import ensure_db, get_conn
from salva_core.schemas import (
    CampaignArchiveRequest,
    CampaignCreateRequest,
    CampaignUpdateRequest,
    CanonicalEntity,
    CanonicalRelation,
    DiscoveryIntent,
    DiscoveryRequest,
    EvidenceItem,
    TelemetryRecord,
)


def _isolate_campaigns_runtime(db_path: str) -> None:
    main.create_campaign = lambda name, description=None: persistence.create_campaign(
        name, description, path=db_path
    )
    main.get_campaign = lambda campaign_id: persistence.get_campaign(campaign_id, path=db_path)
    main.list_campaigns = lambda status=None, limit=100, offset=0: persistence.list_campaigns(
        status=status, limit=limit, offset=offset, path=db_path
    )
    main.update_campaign = (
        lambda campaign_id, name=None, description=None: persistence.update_campaign(
            campaign_id, name=name, description=description, path=db_path
        )
    )
    main.archive_campaign = lambda campaign_id, retention_days: persistence.archive_campaign(
        campaign_id, retention_days, path=db_path
    )
    main.unarchive_campaign = lambda campaign_id: persistence.unarchive_campaign(
        campaign_id, path=db_path
    )
    main.delete_campaign = lambda campaign_id: persistence.delete_campaign(
        campaign_id, path=db_path
    )
    main.clear_campaign_cache = lambda campaign_id: persistence.clear_campaign_cache(
        campaign_id, path=db_path
    )
    main.sweep_expired_campaigns = lambda: persistence.sweep_expired_campaigns(path=db_path)


def _seed_run(db_path: str, campaign_id: str) -> str:
    return persist_discovery_run(
        request=DiscoveryRequest(
            objective="find_leads",
            intent=DiscoveryIntent(
                market="Germany", industry="software", product="crm", role="reseller"
            ),
            execution={"campaign_id": campaign_id},
        ),
        entities=[
            CanonicalEntity(
                entity_id="lead:1",
                entity_type="lead",
                title="Example Lead",
                source_urls=["https://example.com"],
                evidence=[
                    EvidenceItem(
                        source_url="https://example.com",
                        source_name="example",
                        title="Example Lead",
                        snippet="Confidential lead evidence snippet",
                    )
                ],
            )
        ],
        relations=[
            CanonicalRelation(
                relation_id="relation:1",
                relation_type="related_to",
                from_entity_id="lead:1",
                to_entity_id="lead:1",
            )
        ],
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
                    "content_weights": {"title": 0.45},
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


def test_campaign_crud_roundtrip(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    created = asyncio.run(
        campaign_create(CampaignCreateRequest(name="Q1 Outreach", description="initial"))
    )
    assert created.status == "active"
    assert created.run_count == 0

    fetched = asyncio.run(campaign_detail(created.campaign_id))
    assert fetched.campaign_id == created.campaign_id

    listed = asyncio.run(campaigns())
    assert listed.total == 1
    assert listed.items[0].campaign_id == created.campaign_id

    updated = asyncio.run(
        campaign_update(created.campaign_id, CampaignUpdateRequest(name="Q1 Outreach Renamed"))
    )
    assert updated.name == "Q1 Outreach Renamed"


def test_campaign_duplicate_name_conflict(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    asyncio.run(campaign_create(CampaignCreateRequest(name="Dup Name")))
    with pytest.raises(Exception) as excinfo:
        asyncio.run(campaign_create(CampaignCreateRequest(name="dup name")))
    assert getattr(excinfo.value, "status_code", None) == 409


def test_campaign_archive_sets_purge_at_and_rearchive_updates_timer(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    created = asyncio.run(campaign_create(CampaignCreateRequest(name="Archive Me")))

    archived = asyncio.run(
        campaign_archive(created.campaign_id, CampaignArchiveRequest(retention_days=7))
    )
    assert archived.status == "archived"
    assert archived.retention_days == 7
    assert archived.purge_at is not None
    first_purge_at = archived.purge_at

    rearchived = asyncio.run(
        campaign_archive(created.campaign_id, CampaignArchiveRequest(retention_days=30))
    )
    assert rearchived.retention_days == 30
    assert rearchived.purge_at is not None
    assert rearchived.purge_at != first_purge_at


def test_campaign_archive_indefinite_leaves_purge_at_unset(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    created = asyncio.run(campaign_create(CampaignCreateRequest(name="Indefinite Archive")))
    archived = asyncio.run(
        campaign_archive(created.campaign_id, CampaignArchiveRequest(retention_days=None))
    )

    assert archived.status == "archived"
    assert archived.retention_days is None
    assert archived.purge_at is None

    unarchived = asyncio.run(campaign_unarchive(created.campaign_id))
    assert unarchived.status == "active"
    assert unarchived.archived_at is None


def test_sweep_expired_campaigns_deletes_expired_only(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")

    expired = persistence.create_campaign("Expired Campaign", path=db_path)
    future = persistence.create_campaign("Future Campaign", path=db_path)
    indefinite = persistence.create_campaign("Indefinite Campaign", path=db_path)

    persistence.archive_campaign(expired.campaign_id, 1, path=db_path)
    persistence.archive_campaign(future.campaign_id, 30, path=db_path)
    persistence.archive_campaign(indefinite.campaign_id, None, path=db_path)

    # Force the expired campaign's purge_at into the past.
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE campaigns SET purge_at = ? WHERE campaign_id = ?",
            (past, expired.campaign_id),
        )

    purged = persistence.sweep_expired_campaigns(path=db_path)

    assert purged == [expired.campaign_id]
    assert persistence.get_campaign(expired.campaign_id, path=db_path) is None
    assert persistence.get_campaign(future.campaign_id, path=db_path) is not None
    assert persistence.get_campaign(indefinite.campaign_id, path=db_path) is not None


def test_campaign_delete_while_active_conflict(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    created = asyncio.run(campaign_create(CampaignCreateRequest(name="Still Active")))
    with pytest.raises(Exception) as excinfo:
        asyncio.run(campaign_delete(created.campaign_id, confirm_name=created.name))
    assert getattr(excinfo.value, "status_code", None) == 409


def test_campaign_delete_wrong_confirm_name_conflict(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    created = asyncio.run(campaign_create(CampaignCreateRequest(name="Confirm Name Test")))
    asyncio.run(campaign_archive(created.campaign_id, CampaignArchiveRequest(retention_days=None)))

    with pytest.raises(Exception) as excinfo:
        asyncio.run(campaign_delete(created.campaign_id, confirm_name="wrong name"))
    assert getattr(excinfo.value, "status_code", None) == 409


def test_campaign_delete_cascade_row_counts(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    created = asyncio.run(campaign_create(CampaignCreateRequest(name="Cascade Delete")))
    _seed_run(db_path, created.campaign_id)

    asyncio.run(campaign_archive(created.campaign_id, CampaignArchiveRequest(retention_days=None)))
    response = asyncio.run(campaign_delete(created.campaign_id, confirm_name=created.name))

    assert response.deleted["discovery_runs"] == 1
    assert response.deleted["evidence_records"] == 1
    assert response.deleted["evidence_chain_records"] == 1
    assert response.deleted["relation_records"] == 1
    assert response.deleted["telemetry_records"] == 1
    assert response.deleted["query_family_memory"] == 1
    assert response.deleted["campaigns"] == 1
    assert persistence.get_campaign(created.campaign_id, path=db_path) is None

    with get_conn(db_path) as conn:
        remaining_runs = conn.execute("SELECT COUNT(*) FROM discovery_runs").fetchone()[0]
        remaining_memory = conn.execute("SELECT COUNT(*) FROM query_family_memory").fetchone()[0]
    assert remaining_runs == 0
    assert remaining_memory == 0


def test_campaign_clear_cache(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    created = asyncio.run(campaign_create(CampaignCreateRequest(name="Clear Cache")))
    run_id = _seed_run(db_path, created.campaign_id)

    response = asyncio.run(campaign_clear_cache(created.campaign_id))

    assert response.cleared["evidence_records"] == 1
    assert response.cleared["evidence_chain_records"] == 1
    assert response.cache_cleared_at is not None

    with get_conn(db_path) as conn:
        evidence_count = conn.execute("SELECT COUNT(*) FROM evidence_records").fetchone()[0]
        memory_count = conn.execute("SELECT COUNT(*) FROM query_family_memory").fetchone()[0]
        hyperedge_count = conn.execute("SELECT COUNT(*) FROM hyperedges").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM relation_records").fetchone()[0]
        entities_json = conn.execute(
            "SELECT entities_json FROM discovery_runs WHERE run_id = ?", (run_id,)
        ).fetchone()[0]

    assert evidence_count == 0
    assert memory_count == 1
    assert hyperedge_count >= 1
    assert relation_count == 1
    assert "Confidential lead evidence snippet" not in entities_json
    assert "lead:1" in entities_json


def test_discover_into_archived_campaign_conflict(tmp_path) -> None:
    db_path = str(tmp_path / "salva_campaigns.db")
    _isolate_campaigns_runtime(db_path)

    created = asyncio.run(campaign_create(CampaignCreateRequest(name="Archived For Discover")))
    asyncio.run(campaign_archive(created.campaign_id, CampaignArchiveRequest(retention_days=None)))

    payload = DiscoveryRequest(
        objective="find_leads",
        intent=DiscoveryIntent(market="Germany", industry="software"),
        execution={"campaign_id": created.campaign_id},
    )
    with pytest.raises(Exception) as excinfo:
        asyncio.run(discover(payload))
    assert getattr(excinfo.value, "status_code", None) == 409


def test_campaign_migration_backfill_registers_historical_campaign_ids(tmp_path) -> None:
    db_path = str(tmp_path / "salva_backfill.db")
    ensure_db(db_path)

    now = datetime.now(UTC).isoformat()
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO discovery_runs (
                run_id, objective, output_profile, campaign_id, request_json,
                entities_json, relations_json, meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run:backfill-1", "find_leads", "lead", "desktop-default",
                "{}", "[]", "[]", "{}", now,
            ),
        )
        conn.execute(
            """
            INSERT INTO discovery_runs (
                run_id, objective, output_profile, campaign_id, request_json,
                entities_json, relations_json, meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run:backfill-2", "find_leads", "lead", "campaign:auto:xyz123",
                "{}", "[]", "[]", "{}", now,
            ),
        )

    # Simulate the next app start: ensure_db() re-runs the idempotent migration/backfill pass.
    ensure_db(db_path)

    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT campaign_id FROM campaigns").fetchall()
        registered = {row[0] for row in rows}

    assert "desktop-default" in registered
    assert "campaign:auto:xyz123" not in registered
