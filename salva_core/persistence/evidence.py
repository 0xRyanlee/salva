"""Evidence records, evidence chains, relations, hyperedges, and hold schema migrations."""
from __future__ import annotations

import json
from datetime import datetime

from salva_core.schemas import (
    EvidenceChainLink,
    EvidenceChainRecord,
    EvidenceRecord,
    HoldHyperedgeMember,
    HoldHyperedgeRecord,
    HoldMigrationRecord,
    RelationRecord,
)

from .db import DEFAULT_DB_PATH, get_conn


def list_evidence_records(
    run_id: str | None = None,
    entity_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[EvidenceRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if entity_id:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM evidence_records {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT evidence_id, run_id, entity_id, source_url, source_name, title, snippet, captured_at, metadata_json
            FROM evidence_records
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        EvidenceRecord(
            evidence_id=row[0],
            run_id=row[1],
            entity_id=row[2],
            source_url=row[3],
            source_name=row[4],
            title=row[5],
            snippet=row[6],
            captured_at=datetime.fromisoformat(row[7]) if row[7] else None,
            metadata=json.loads(row[8]),
        )
        for row in rows
    ]
    return items, int(total)


def list_evidence_chains(
    run_id: str | None = None,
    entity_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[EvidenceChainRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if entity_id:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM evidence_chain_records {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT chain_id, run_id, entity_id, entity_title, evidence_ids_json,
                   relation_ids_json, hyperedge_ids_json, links_json,
                   first_captured_at, last_captured_at, evidence_count,
                   relation_count, hyperedge_count, notes_json, created_at
            FROM evidence_chain_records
            {where}
            ORDER BY evidence_count DESC, created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        EvidenceChainRecord(
            entity_id=row[2],
            entity_title=row[3],
            run_id=row[1],
            evidence_ids=json.loads(row[4]),
            relation_ids=json.loads(row[5]),
            hyperedge_ids=json.loads(row[6]),
            links=[
                EvidenceChainLink.model_validate(link)
                for link in json.loads(row[7])
            ],
            first_captured_at=datetime.fromisoformat(row[8]) if row[8] else None,
            last_captured_at=datetime.fromisoformat(row[9]) if row[9] else None,
            evidence_count=row[10],
            relation_count=row[11],
            hyperedge_count=row[12],
            notes=json.loads(row[13]),
        )
        for row in rows
    ]
    return items, int(total)


def list_relations(
    run_id: str | None = None,
    relation_type: str | None = None,
    from_entity_id: str | None = None,
    to_entity_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[RelationRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if relation_type:
        clauses.append("relation_type = ?")
        params.append(relation_type)
    if from_entity_id:
        clauses.append("from_entity_id = ?")
        params.append(from_entity_id)
    if to_entity_id:
        clauses.append("to_entity_id = ?")
        params.append(to_entity_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM relation_records {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT relation_id, run_id, relation_type, from_entity_id, to_entity_id,
                   schema_name, schema_version, storage_version, migration_version,
                   confidence, evidence_ids_json, attributes_json, created_at
            FROM relation_records
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        RelationRecord(
            relation_id=row[0],
            run_id=row[1],
            relation_type=row[2],
            from_entity_id=row[3],
            to_entity_id=row[4],
            schema_name=row[5],
            schema_version=row[6],
            storage_version=row[7],
            migration_version=row[8],
            confidence=row[9],
            evidence_ids=json.loads(row[10]),
            attributes=json.loads(row[11]),
            created_at=datetime.fromisoformat(row[12]),
        )
        for row in rows
    ]
    return items, int(total)


def list_hyperedges(
    run_id: str | None = None,
    hyperedge_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[HoldHyperedgeRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if hyperedge_type:
        clauses.append("hyperedge_type = ?")
        params.append(hyperedge_type)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM hyperedges {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT hyperedge_id, run_id, hyperedge_type, summary, confidence,
                   evidence_ids_json, source_ids_json, members_json, properties_json, created_at
            FROM hyperedges
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        HoldHyperedgeRecord(
            hyperedge_id=row[0],
            run_id=row[1],
            hyperedge_type=row[2],
            summary=row[3],
            confidence=row[4],
            evidence_ids=json.loads(row[5]),
            source_ids=json.loads(row[6]),
            members=[HoldHyperedgeMember.model_validate(member) for member in json.loads(row[7])],
            properties=json.loads(row[8]),
            created_at=datetime.fromisoformat(row[9]),
        )
        for row in rows
    ]
    return items, int(total)


def list_hold_schema_migrations(
    limit: int = 50,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[HoldMigrationRecord], int]:
    with get_conn(path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM hold_schema_registry").fetchone()[0]
        rows = conn.execute(
            """
            SELECT registry_id, schema_name, hold_version, storage_version, migration_version,
                   migration_strategy, status, details_json, created_at
            FROM hold_schema_registry
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    items = [
        HoldMigrationRecord(
            registry_id=row[0],
            schema_name=row[1],
            hold_version=row[2],
            storage_version=row[3],
            migration_version=row[4],
            migration_strategy=row[5],
            status=row[6],
            details=json.loads(row[7]),
            created_at=datetime.fromisoformat(row[8]),
        )
        for row in rows
    ]
    return items, int(total)
