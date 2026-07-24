"""Campaign lifecycle persistence: CRUD, archive/retention, cascade delete, cache-clear.

campaign_id is the isolation key for cross-run memory (execution-context.md). This
module makes campaigns a real backend-managed entity so archive/retention/delete can
be enforced server-side rather than trusted to a frontend-only store.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from salva_core.schemas import CampaignRecord

from .db import DEFAULT_DB_PATH, get_conn

logger = logging.getLogger(__name__)

_CAMPAIGN_COLUMNS = (
    "campaign_id, name, description, status, retention_days, purge_at, "
    "cache_cleared_at, created_at, updated_at, archived_at"
)


def create_campaign(
    name: str,
    description: str | None = None,
    *,
    path: str = DEFAULT_DB_PATH,
) -> CampaignRecord:
    cleaned = _validate_name(name)
    campaign_id = f"campaign:{uuid.uuid4().hex[:12]}"
    now = datetime.now(UTC).isoformat()

    with get_conn(path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO campaigns
                    (campaign_id, name, description, status, created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?)
                """,
                (campaign_id, cleaned, description, now, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"campaign name already exists: {cleaned}") from exc

    return _require_campaign(campaign_id, path=path)


def get_campaign(campaign_id: str, *, path: str = DEFAULT_DB_PATH) -> CampaignRecord | None:
    with get_conn(path) as conn:
        row = conn.execute(
            f"SELECT {_CAMPAIGN_COLUMNS} FROM campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if row is None:
            return None
        return _record_from_row(conn, row)


def list_campaigns(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    *,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[CampaignRecord], int]:
    sweep_expired_campaigns(path=path)

    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM campaigns {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT {_CAMPAIGN_COLUMNS}
            FROM campaigns
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        items = [_record_from_row(conn, row) for row in rows]

    return items, int(total)


def update_campaign(
    campaign_id: str,
    name: str | None = None,
    description: str | None = None,
    *,
    path: str = DEFAULT_DB_PATH,
) -> CampaignRecord:
    now = datetime.now(UTC).isoformat()
    sets = ["updated_at = ?"]
    params: list[object] = [now]
    if name is not None:
        sets.append("name = ?")
        params.append(_validate_name(name))
    if description is not None:
        sets.append("description = ?")
        params.append(description)
    params.append(campaign_id)

    with get_conn(path) as conn:
        try:
            cursor = conn.execute(
                f"UPDATE campaigns SET {', '.join(sets)} WHERE campaign_id = ?",
                params,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"campaign name already exists: {name}") from exc
        if cursor.rowcount == 0:
            raise KeyError(f"campaign not found: {campaign_id}")

    return _require_campaign(campaign_id, path=path)


def archive_campaign(
    campaign_id: str,
    retention_days: int | None,
    *,
    path: str = DEFAULT_DB_PATH,
) -> CampaignRecord:
    if retention_days is not None and retention_days < 1:
        raise ValueError("retention_days must be >= 1 when set")

    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    purge_at = (
        (now_dt + timedelta(days=retention_days)).isoformat()
        if retention_days is not None
        else None
    )

    with get_conn(path) as conn:
        cursor = conn.execute(
            """
            UPDATE campaigns
            SET status = 'archived', archived_at = ?, retention_days = ?,
                purge_at = ?, updated_at = ?
            WHERE campaign_id = ?
            """,
            (now, retention_days, purge_at, now, campaign_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"campaign not found: {campaign_id}")

    return _require_campaign(campaign_id, path=path)


def unarchive_campaign(campaign_id: str, *, path: str = DEFAULT_DB_PATH) -> CampaignRecord:
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        cursor = conn.execute(
            """
            UPDATE campaigns
            SET status = 'active', archived_at = NULL, retention_days = NULL,
                purge_at = NULL, updated_at = ?
            WHERE campaign_id = ?
            """,
            (now, campaign_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"campaign not found: {campaign_id}")

    return _require_campaign(campaign_id, path=path)


def delete_campaign(campaign_id: str, *, path: str = DEFAULT_DB_PATH) -> dict[str, int]:
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT status FROM campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"campaign not found: {campaign_id}")
        if row[0] != "archived":
            raise ValueError("campaign must be archived before it can be deleted")
        return _delete_campaign_cascade(conn, campaign_id)


def clear_campaign_cache(campaign_id: str, *, path: str = DEFAULT_DB_PATH) -> dict[str, int]:
    now = datetime.now(UTC).isoformat()

    with get_conn(path) as conn:
        exists = conn.execute(
            "SELECT 1 FROM campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if exists is None:
            raise KeyError(f"campaign not found: {campaign_id}")

        run_ids = _ids_where(conn, "discovery_runs", "run_id", "campaign_id", [campaign_id])
        job_ids = _ids_where(conn, "jobs", "job_id", "run_id", run_ids)

        for run_id in run_ids:
            row = conn.execute(
                "SELECT entities_json, relations_json FROM discovery_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            entities = [strip_evidence_text(item) for item in json.loads(row[0])]
            relations = [strip_evidence_text(item) for item in json.loads(row[1])]
            conn.execute(
                """
                UPDATE discovery_runs
                SET entities_json = ?, relations_json = ?, cache_cleared_at = ?
                WHERE run_id = ?
                """,
                (
                    json.dumps(entities, ensure_ascii=False),
                    json.dumps(relations, ensure_ascii=False),
                    now,
                    run_id,
                ),
            )

        counts: dict[str, int] = {
            "evidence_records": _delete_where_in(conn, "evidence_records", "run_id", run_ids),
            "evidence_chain_records": _delete_where_in(
                conn, "evidence_chain_records", "run_id", run_ids
            ),
            "semantic_vectors": _delete_where_in(conn, "semantic_vectors", "run_id", run_ids),
            "source_attempts": _delete_where_in(conn, "source_attempts", "run_id", run_ids),
            "telemetry_records": _delete_where_in(conn, "telemetry_records", "run_id", run_ids),
            "plugin_reports": _delete_where_in(conn, "plugin_reports", "run_id", run_ids),
            "stream_events": _delete_where_in(conn, "stream_events", "job_id", job_ids),
        }

        conn.execute(
            "UPDATE campaigns SET cache_cleared_at = ?, updated_at = ? WHERE campaign_id = ?",
            (now, now, campaign_id),
        )

    return counts


def sweep_expired_campaigns(*, path: str = DEFAULT_DB_PATH) -> list[str]:
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        expired = [
            row[0]
            for row in conn.execute(
                "SELECT campaign_id FROM campaigns "
                "WHERE status = 'archived' AND purge_at IS NOT NULL AND purge_at <= ?",
                (now,),
            ).fetchall()
        ]

    purged: list[str] = []
    for campaign_id in expired:
        try:
            delete_campaign(campaign_id, path=path)
        except (KeyError, ValueError):
            # 另一個 sweep（startup 與 list_campaigns 各觸發一次）已經先刪掉，
            # 或該 campaign 在這之間被 unarchive 了——不是錯誤，跳過即可。
            continue
        logger.info("campaign %s auto-deleted: retention timer expired", campaign_id)
        purged.append(campaign_id)

    return purged


def strip_evidence_text(item: dict[str, Any]) -> dict[str, Any]:
    """裁掉 dict 內 `evidence` list 中的大段文字欄位，只留可回溯來源的最小資訊。

    entities_json 內的 CanonicalEntity.evidence（EvidenceItem）沒有 evidence_id
    欄位（那個 id 只在寫入 evidence_records 資料表時才生成，不會回填進實體本
    身），所以這裡改用 source_url + captured_at 當保留欄位，而非規格原文假設的
    {"evidence_id": ...}——同樣達成「丟棄 snippet/title/source_name/metadata
    等大段重複文字、保留可追溯來源」的目的。relations_json（CanonicalRelation）
    本身就只有 evidence_ids（pointer-only），沒有 "evidence" key，所以這個函式
    對它是 no-op，符合規格 §10 open item 1 的預期。
    """
    if "evidence" not in item:
        return item
    cleaned = dict(item)
    cleaned["evidence"] = [
        {"source_url": entry.get("source_url"), "captured_at": entry.get("captured_at")}
        for entry in item.get("evidence", [])
    ]
    return cleaned


def _validate_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 120:
        raise ValueError("campaign name must be 1..120 characters after strip")
    return cleaned


def _require_campaign(campaign_id: str, *, path: str) -> CampaignRecord:
    record = get_campaign(campaign_id, path=path)
    if record is None:
        raise KeyError(f"campaign not found: {campaign_id}")
    return record


def _record_from_row(conn: sqlite3.Connection, row: tuple[object, ...]) -> CampaignRecord:
    campaign_id = str(row[0])
    run_count = conn.execute(
        "SELECT COUNT(*) FROM discovery_runs WHERE campaign_id = ?",
        (campaign_id,),
    ).fetchone()[0]
    quarantine_count = conn.execute(
        "SELECT COUNT(*) FROM query_family_memory "
        "WHERE campaign_id = ? AND memory_status = 'quarantine'",
        (campaign_id,),
    ).fetchone()[0]
    promoted_count = conn.execute(
        "SELECT COUNT(*) FROM query_family_memory "
        "WHERE campaign_id = ? AND memory_status = 'promoted'",
        (campaign_id,),
    ).fetchone()[0]

    return CampaignRecord(
        campaign_id=campaign_id,
        name=str(row[1]),
        description=row[2] if row[2] is not None else None,
        status=str(row[3]),
        retention_days=int(row[4]) if row[4] is not None else None,
        purge_at=datetime.fromisoformat(str(row[5])) if row[5] else None,
        cache_cleared_at=datetime.fromisoformat(str(row[6])) if row[6] else None,
        created_at=datetime.fromisoformat(str(row[7])),
        updated_at=datetime.fromisoformat(str(row[8])),
        archived_at=datetime.fromisoformat(str(row[9])) if row[9] else None,
        run_count=int(run_count),
        memory_quarantine_count=int(quarantine_count),
        memory_promoted_count=int(promoted_count),
    )


def _delete_campaign_cascade(conn: sqlite3.Connection, campaign_id: str) -> dict[str, int]:
    run_ids = _ids_where(conn, "discovery_runs", "run_id", "campaign_id", [campaign_id])
    job_ids = _ids_where(conn, "jobs", "job_id", "run_id", run_ids)
    hyperedge_ids = _ids_where(conn, "hyperedges", "hyperedge_id", "run_id", run_ids)

    counts: dict[str, int] = {
        "semantic_vectors": _delete_where_in(conn, "semantic_vectors", "run_id", run_ids),
        "query_family_memory": _delete_query_family_memory(conn, campaign_id, run_ids),
        "hyperedge_incidences": _delete_where_in(
            conn, "hyperedge_incidences", "hyperedge_id", hyperedge_ids
        ),
        "hyperedges": _delete_where_in(conn, "hyperedges", "run_id", run_ids),
        "relation_records": _delete_where_in(conn, "relation_records", "run_id", run_ids),
        "evidence_chain_records": _delete_where_in(
            conn, "evidence_chain_records", "run_id", run_ids
        ),
        "evidence_records": _delete_where_in(conn, "evidence_records", "run_id", run_ids),
        "plugin_reports": _delete_where_in(conn, "plugin_reports", "run_id", run_ids),
        "source_attempts": _delete_where_in(conn, "source_attempts", "run_id", run_ids),
        "telemetry_records": _delete_where_in(conn, "telemetry_records", "run_id", run_ids),
        "stream_events": _delete_where_in(conn, "stream_events", "job_id", job_ids),
        "jobs": _delete_where_in(conn, "jobs", "run_id", run_ids),
    }
    counts["discovery_runs"] = conn.execute(
        "DELETE FROM discovery_runs WHERE campaign_id = ?",
        (campaign_id,),
    ).rowcount
    conn.execute("DELETE FROM campaigns WHERE campaign_id = ?", (campaign_id,))
    counts["campaigns"] = 1

    return counts


def _delete_query_family_memory(
    conn: sqlite3.Connection, campaign_id: str, run_ids: list[str]
) -> int:
    if run_ids:
        placeholders = ",".join("?" for _ in run_ids)
        cursor = conn.execute(
            f"DELETE FROM query_family_memory WHERE campaign_id = ? OR run_id IN ({placeholders})",
            [campaign_id, *run_ids],
        )
    else:
        cursor = conn.execute(
            "DELETE FROM query_family_memory WHERE campaign_id = ?",
            (campaign_id,),
        )
    return cursor.rowcount


def _ids_where(
    conn: sqlite3.Connection,
    table: str,
    id_col: str,
    filter_col: str,
    filter_values: list[str],
) -> list[str]:
    if not filter_values:
        return []
    placeholders = ",".join("?" for _ in filter_values)
    rows = conn.execute(
        f"SELECT {id_col} FROM {table} WHERE {filter_col} IN ({placeholders})",
        filter_values,
    ).fetchall()
    return [row[0] for row in rows]


def _delete_where_in(conn: sqlite3.Connection, table: str, col: str, values: list[str]) -> int:
    if not values:
        return 0
    placeholders = ",".join("?" for _ in values)
    cursor = conn.execute(f"DELETE FROM {table} WHERE {col} IN ({placeholders})", values)
    return cursor.rowcount
