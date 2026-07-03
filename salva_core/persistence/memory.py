"""Query family memory: list, semantic search, and bootstrap seeding."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from salva_core.schemas import QueryFamilyMemoryRecord
from salva_core.vector_backends import ScalarHashVectorBackend, resolve_semantic_vector_backend

from .db import DEFAULT_DB_PATH, get_conn

logger = logging.getLogger(__name__)

_MEMORY_SELECT_COLUMNS = """
    memory_id, run_id, campaign_id, continuation_id, memory_status,
    promoted_at, domain, objective, output_profile, round_num, strategy,
    query, query_signature, source_nodes_json, content_nodes_json,
    content_weights_json, source_hints_json, notes_json, raw_total,
    qualified_total, avg_score, success_score, created_at
"""


def _record_from_row(row: tuple[object, ...]) -> QueryFamilyMemoryRecord:
    return QueryFamilyMemoryRecord(
        memory_id=str(row[0]),
        run_id=str(row[1]),
        campaign_id=str(row[2]) if row[2] is not None else None,
        continuation_id=str(row[3]) if row[3] is not None else None,
        memory_status=str(row[4]),
        promoted_at=datetime.fromisoformat(str(row[5])) if row[5] else None,
        domain=str(row[6]) if row[6] is not None else None,
        objective=str(row[7]),
        output_profile=str(row[8]),
        round_num=int(row[9]),
        strategy=str(row[10]),
        query=str(row[11]),
        query_signature=str(row[12]),
        source_nodes=json.loads(str(row[13])),
        content_nodes=json.loads(str(row[14])) if row[14] else [],
        content_weights=json.loads(str(row[15])),
        source_hints=json.loads(str(row[16])),
        notes=json.loads(str(row[17])),
        raw_total=int(row[18]),
        qualified_total=int(row[19]),
        avg_score=float(row[20]),
        success_score=float(row[21]),
        created_at=datetime.fromisoformat(str(row[22])),
    )


def list_query_family_memory(
    run_id: str | None = None,
    objective: str | None = None,
    strategy: str | None = None,
    campaign_id: str | None = None,
    continuation_id: str | None = None,
    memory_status: str | None = None,
    limit: int = 200,
    offset: int = 0,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[QueryFamilyMemoryRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if objective:
        clauses.append("objective = ?")
        params.append(objective)
    if strategy:
        clauses.append("strategy = ?")
        params.append(strategy)
    if campaign_id:
        clauses.append("campaign_id = ?")
        params.append(campaign_id)
    if continuation_id:
        clauses.append("continuation_id = ?")
        params.append(continuation_id)
    if memory_status:
        clauses.append("memory_status = ?")
        params.append(memory_status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM query_family_memory {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT {_MEMORY_SELECT_COLUMNS}
            FROM query_family_memory
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [_record_from_row(row) for row in rows]
    return items, int(total)


def search_query_family_memory(
    query: str,
    objective: str | None = None,
    strategy: str | None = None,
    campaign_id: str | None = None,
    memory_status: str | None = None,
    limit: int = 10,
    offset: int = 0,
    path: str | None = DEFAULT_DB_PATH,
) -> tuple[list[tuple[QueryFamilyMemoryRecord, float, str, str]], int]:
    """Returns (rows, total) where each row is (record, score, vector_id, backend_used).

    backend_used names whichever backend's score actually won for that row --
    the primary semantic backend (resolve_semantic_vector_backend(), e.g.
    "hybrid_hash"/"jina_omlx"/"sqlite_vec") or the ScalarHashVectorBackend
    compatibility fallback ("scalar_hash") when its score was higher. Both are
    non-semantic hash backends when omlx is unreachable -- callers should not
    treat a returned score as a trustworthy semantic similarity without
    checking this label."""
    if path is None:
        path = DEFAULT_DB_PATH

    backend = resolve_semantic_vector_backend()
    query_embedding = backend.embed(query)
    compatibility_backend = ScalarHashVectorBackend(dimensions=len(query_embedding))
    compatibility_query_embedding = compatibility_backend.embed(query)
    clauses: list[str] = ["sv.vector_kind = 'query_family'", "sv.dimensions = ?"]
    params: list[object] = [len(query_embedding)]
    if objective:
        clauses.append("qf.objective = ?")
        params.append(objective)
    if strategy:
        clauses.append("qf.strategy = ?")
        params.append(strategy)
    if campaign_id:
        clauses.append("qf.campaign_id = ?")
        params.append(campaign_id)
    if memory_status:
        clauses.append("qf.memory_status = ?")
        params.append(memory_status)
    where = f"WHERE {' AND '.join(clauses)}"

    with get_conn(path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                   qf.memory_id, qf.run_id, qf.campaign_id, qf.continuation_id,
                   qf.memory_status, qf.promoted_at, qf.domain, qf.objective,
                   qf.output_profile, qf.round_num, qf.strategy, qf.query,
                   qf.query_signature, qf.source_nodes_json, qf.content_nodes_json,
                   qf.content_weights_json, qf.source_hints_json, qf.notes_json,
                   qf.raw_total, qf.qualified_total, qf.avg_score, qf.success_score,
                   qf.created_at, sv.embedding_json, sv.vector_id, sv.dimensions
            FROM query_family_memory qf
            JOIN semantic_vectors sv ON qf.memory_id = sv.source_id
            {where}
            ORDER BY qf.created_at DESC
            """,
            params,
        ).fetchall()

    scored: list[tuple[QueryFamilyMemoryRecord, float, str, str]] = []
    for row in rows:
        embedding = [float(value) for value in json.loads(row[23])]
        score = backend.score(query_embedding, embedding)
        backend_used = backend.name
        if compatibility_query_embedding and row[25] == len(compatibility_query_embedding):
            compatibility_score = compatibility_backend.score(compatibility_query_embedding, embedding)
            if compatibility_score > score:
                score = compatibility_score
                backend_used = compatibility_backend.name
        scored.append(
            (
                _record_from_row(row[:23]),
                round(score, 4),
                row[24],
                backend_used,
            )
        )

    scored.sort(key=lambda item: item[1], reverse=True)
    total = len(scored)
    return scored[offset : offset + limit], total


def read_top_query_families_for_seeding(
    domain: str,
    objective: str | None = None,
    campaign_id: str | None = None,
    memory_status: str | None = None,
    top_k: int = 5,
    min_success_score: float = 0.3,
    path: str = DEFAULT_DB_PATH,
) -> list[dict]:
    clauses: list[str] = ["success_score >= ?", "domain = ?"]
    params: list[object] = [min_success_score, _normalize_domain(domain)]

    if objective:
        clauses.append("objective = ?")
        params.append(objective)
    if campaign_id:
        clauses.append("campaign_id = ?")
        params.append(campaign_id)
    if memory_status:
        clauses.append("memory_status = ?")
        params.append(memory_status)

    where = f"WHERE {' AND '.join(clauses)}"

    try:
        with get_conn(path) as conn:
            rows = conn.execute(
                f"""
                SELECT memory_id, source_nodes_json, success_score, strategy, content_nodes_json
                FROM query_family_memory
                {where}
                ORDER BY success_score DESC
                LIMIT ?
                """,
                [*params, top_k],
            ).fetchall()
    except Exception:
        return []

    return [
        {
            "memory_id": row[0],
            "source_nodes": json.loads(row[1]),
            "success_score": row[2],
            "strategy": row[3],
            "content_nodes": json.loads(row[4]) if row[4] else [],
        }
        for row in rows
    ]


def promote_query_family_memory(
    memory_id: str,
    campaign_id: str,
    path: str = DEFAULT_DB_PATH,
) -> QueryFamilyMemoryRecord:
    campaign_id = campaign_id.strip()
    if not campaign_id:
        raise ValueError("campaign_id is required for memory promotion")

    now = datetime.now(UTC).isoformat()

    with get_conn(path) as conn:
        cursor = conn.execute(
            """
            UPDATE query_family_memory
            SET memory_status = 'promoted', promoted_at = ?
            WHERE memory_id = ? AND campaign_id = ?
            """,
            (now, memory_id, campaign_id),
        )
        if cursor.rowcount != 1:
            raise KeyError(f"query family memory not found: {memory_id}")
        row = conn.execute(
            f"""
            SELECT {_MEMORY_SELECT_COLUMNS}
            FROM query_family_memory
            WHERE memory_id = ? AND campaign_id = ?
            """,
            (memory_id, campaign_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"query family memory not found after promotion: {memory_id}")
        return _record_from_row(row)


def _normalize_domain(domain: str) -> str:
    cleaned = domain.strip().lower()
    return cleaned or "general"
