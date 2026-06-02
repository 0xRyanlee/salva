"""Query family memory: list, semantic search, and bootstrap seeding."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from salva_core.schemas import QueryFamilyMemoryRecord
from salva_core.vector_backends import ScalarHashVectorBackend, resolve_semantic_vector_backend

from .db import DEFAULT_DB_PATH, get_conn

logger = logging.getLogger(__name__)


def list_query_family_memory(
    run_id: str | None = None,
    objective: str | None = None,
    strategy: str | None = None,
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
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM query_family_memory {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT memory_id, run_id, objective, output_profile, round_num, strategy, query,
                   query_signature, source_nodes_json, content_weights_json, source_hints_json,
                   notes_json, raw_total, qualified_total, avg_score, success_score, created_at,
                   domain
            FROM query_family_memory
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items = [
        QueryFamilyMemoryRecord(
            memory_id=row[0],
            run_id=row[1],
            objective=row[2],
            output_profile=row[3],
            round_num=row[4],
            strategy=row[5],
            query=row[6],
            query_signature=row[7],
            source_nodes=json.loads(row[8]),
            content_weights=json.loads(row[9]),
            source_hints=json.loads(row[10]),
            notes=json.loads(row[11]),
            raw_total=row[12],
            qualified_total=row[13],
            avg_score=row[14],
            success_score=row[15],
            created_at=datetime.fromisoformat(row[16]),
            domain=row[17],
        )
        for row in rows
    ]
    return items, int(total)


def search_query_family_memory(
    query: str,
    objective: str | None = None,
    strategy: str | None = None,
    limit: int = 10,
    offset: int = 0,
    path: str | None = DEFAULT_DB_PATH,
) -> tuple[list[tuple[QueryFamilyMemoryRecord, float, str]], int]:
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
    where = f"WHERE {' AND '.join(clauses)}"

    with get_conn(path) as conn:
        rows = conn.execute(
            f"""
            SELECT qf.memory_id, qf.run_id, qf.objective, qf.output_profile, qf.round_num,
                   qf.strategy, qf.query, qf.query_signature, qf.source_nodes_json,
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

    scored: list[tuple[QueryFamilyMemoryRecord, float, str]] = []
    for row in rows:
        embedding = [float(value) for value in json.loads(row[17])]
        score = backend.score(query_embedding, embedding)
        if compatibility_query_embedding and row[19] == len(compatibility_query_embedding):
            compatibility_score = compatibility_backend.score(compatibility_query_embedding, embedding)
            score = max(score, compatibility_score)
        scored.append(
            (
                QueryFamilyMemoryRecord(
                    memory_id=row[0],
                    run_id=row[1],
                    objective=row[2],
                    output_profile=row[3],
                    round_num=row[4],
                    strategy=row[5],
                    query=row[6],
                    query_signature=row[7],
                    source_nodes=json.loads(row[8]),
                    content_weights=json.loads(row[9]),
                    source_hints=json.loads(row[10]),
                    notes=json.loads(row[11]),
                    raw_total=row[12],
                    qualified_total=row[13],
                    avg_score=row[14],
                    success_score=row[15],
                    created_at=datetime.fromisoformat(row[16]),
                ),
                round(score, 4),
                row[18],
            )
        )

    scored.sort(key=lambda item: item[1], reverse=True)
    total = len(scored)
    return scored[offset : offset + limit], total


def read_top_query_families_for_seeding(
    domain: str,
    objective: str | None = None,
    top_k: int = 5,
    min_success_score: float = 0.3,
    path: str = DEFAULT_DB_PATH,
) -> list[dict]:
    clauses: list[str] = ["success_score >= ?", "domain = ?"]
    params: list[object] = [min_success_score, _normalize_domain(domain)]

    if objective:
        clauses.append("objective = ?")
        params.append(objective)

    where = f"WHERE {' AND '.join(clauses)}"

    try:
        with get_conn(path) as conn:
            rows = conn.execute(
                f"""
                SELECT source_nodes_json, success_score, strategy
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
            "source_nodes": json.loads(row[0]),
            "success_score": row[1],
            "strategy": row[2],
        }
        for row in rows
    ]


def _normalize_domain(domain: str) -> str:
    cleaned = domain.strip().lower()
    return cleaned or "general"
