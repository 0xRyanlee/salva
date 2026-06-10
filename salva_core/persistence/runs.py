"""
Discovery run persistence: write, read, and update runs.

persist_discovery_run is a single atomic transaction that stores the run record,
telemetry, source attempts, plugin reports, evidence, relations, hyperedges,
evidence chains, query family memory, and semantic vectors.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from salva_core.schemas import (
    CanonicalEntity,
    CanonicalRelation,
    DiscoveryRequest,
    EvidenceChainLink,
    HoldHyperedgeMember,
    HoldHyperedgeRecord,
    QueryFamilyMemoryRecord,
    RunRecord,
    SourceAttemptRecord,
    TelemetryRecord,
)
from salva_core.semantic import (
    build_query_family_semantic_text,
    build_semantic_embedding,
    build_semantic_vector_id,
    vector_norm,
)

from .db import DEFAULT_DB_PATH, get_conn


def persist_discovery_run(
    request: DiscoveryRequest,
    entities: list[CanonicalEntity],
    relations: list[CanonicalRelation],
    telemetry: list[TelemetryRecord],
    meta: dict[str, Any],
    source_attempts: list[SourceAttemptRecord] | None = None,
    hyperedges: list[HoldHyperedgeRecord] | None = None,
    path: str = DEFAULT_DB_PATH,
) -> str:
    run_id = f"run:{uuid.uuid4()}"
    now = datetime.now(UTC).isoformat()
    plugin_reports = meta.get("plugin_reports", [])

    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO discovery_runs (
                run_id, objective, output_profile, project_id, campaign_id, continuation_id,
                persistence_mode, request_json, entities_json, relations_json,
                meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                request.objective,
                request.output_profile,
                request.execution.project_id,
                request.execution.campaign_id,
                request.execution.continuation_id,
                request.execution.persistence,
                request.model_dump_json(),
                json.dumps([entity.model_dump(mode="json") for entity in entities], ensure_ascii=False),
                json.dumps([relation.model_dump(mode="json") for relation in relations], ensure_ascii=False),
                json.dumps(meta, ensure_ascii=False),
                now,
            ),
        )

        conn.executemany(
            """
            INSERT INTO telemetry_records (
                telemetry_id, run_id, query, round_num, strategy, results_total,
                results_qualified, avg_score, reject_reasons_json, noise_domains_json,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"telemetry:{uuid.uuid4()}",
                    run_id,
                    record.query,
                    record.round_num,
                    record.strategy,
                    record.results_total,
                    record.results_qualified,
                    record.avg_score,
                    json.dumps(record.reject_reasons, ensure_ascii=False),
                    json.dumps(record.noise_domains, ensure_ascii=False),
                    json.dumps(record.metadata, ensure_ascii=False),
                    now,
                )
                for record in telemetry
            ],
        )

        if source_attempts:
            conn.executemany(
                """
                INSERT INTO source_attempts (
                    attempt_id, run_id, strategy, base_url, mode, source_class, trust_level,
                    risk_level, recommended_crawl_mode, result_count,
                    succeeded, error, format_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        f"attempt:{uuid.uuid4()}",
                        run_id,
                        attempt.strategy,
                        attempt.base_url,
                        attempt.mode,
                        attempt.source_class,
                        attempt.trust_level,
                        attempt.risk_level,
                        attempt.recommended_crawl_mode,
                        attempt.result_count,
                        1 if attempt.succeeded else 0,
                        attempt.error,
                        attempt.format_used,
                        now,
                    )
                    for attempt in source_attempts
                ],
            )

        if plugin_reports:
            conn.executemany(
                """
                INSERT INTO plugin_reports (
                    report_id, run_id, plugin, target_entity_id, status,
                    applied, message, data_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        f"plugin_report:{uuid.uuid4()}",
                        run_id,
                        report["plugin"],
                        report["target_entity_id"],
                        report["status"],
                        1 if report.get("applied") else 0,
                        report.get("message"),
                        json.dumps(report.get("data", {}), ensure_ascii=False),
                        now,
                    )
                    for report in plugin_reports
                ],
            )

        evidence_rows: list[tuple[object, ...]] = []
        for entity in entities:
            for evidence in entity.evidence:
                evidence_rows.append(
                    (
                        f"evidence:{uuid.uuid4()}",
                        run_id,
                        entity.entity_id,
                        evidence.source_url,
                        evidence.source_name,
                        evidence.title,
                        evidence.snippet,
                        evidence.captured_at.isoformat() if evidence.captured_at else None,
                        json.dumps(evidence.metadata, ensure_ascii=False),
                        now,
                    )
                )
        if evidence_rows:
            conn.executemany(
                """
                INSERT INTO evidence_records (
                    evidence_id, run_id, entity_id, source_url, source_name,
                    title, snippet, captured_at, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                evidence_rows,
            )

        relation_rows = [
            (
                uuid.uuid4().hex,
                relation.relation_id,
                run_id,
                relation.schema_name,
                relation.schema_version,
                relation.storage_version,
                relation.migration_version,
                relation.relation_type,
                relation.from_entity_id,
                relation.to_entity_id,
                relation.confidence,
                json.dumps(relation.evidence_ids, ensure_ascii=False),
                json.dumps(relation.attributes, ensure_ascii=False),
                now,
            )
            for relation in relations
        ]
        if relation_rows:
            conn.executemany(
                """
                INSERT INTO relation_records (
                    record_id, relation_id, run_id, schema_name, schema_version,
                    storage_version, migration_version, relation_type, from_entity_id,
                    to_entity_id, confidence, evidence_ids_json, attributes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                relation_rows,
            )

        persisted_hyperedges = hyperedges or _derive_default_hyperedges(
            run_id=run_id,
            entities=entities,
            telemetry=telemetry,
        )
        if persisted_hyperedges:
            conn.executemany(
                """
                INSERT OR IGNORE INTO hyperedges (
                    hyperedge_id, run_id, hyperedge_type, summary, confidence,
                    evidence_ids_json, source_ids_json, members_json, properties_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        hyperedge.hyperedge_id,
                        run_id,
                        hyperedge.hyperedge_type,
                        hyperedge.summary,
                        hyperedge.confidence,
                        json.dumps(hyperedge.evidence_ids, ensure_ascii=False),
                        json.dumps(hyperedge.source_ids, ensure_ascii=False),
                        json.dumps([member.model_dump(mode="json") for member in hyperedge.members], ensure_ascii=False),
                        json.dumps(hyperedge.properties, ensure_ascii=False),
                        hyperedge.created_at.isoformat() if hyperedge.created_at else now,
                    )
                    for hyperedge in persisted_hyperedges
                ],
            )

        evidence_chain_rows = _build_evidence_chain_rows(
            run_id=run_id,
            entities=entities,
            evidence_rows=evidence_rows,
            relation_rows=relation_rows,
            hyperedges=persisted_hyperedges,
            created_at=now,
        )
        # Deduplicate by chain_id to handle duplicate entity_ids in a single request
        seen_chain_ids: set[str] = set()
        deduped_chain_rows: list[tuple[object, ...]] = []
        for row in evidence_chain_rows:
            chain_id = str(row[0])
            if chain_id not in seen_chain_ids:
                seen_chain_ids.add(chain_id)
                deduped_chain_rows.append(row)
        if deduped_chain_rows:
            conn.executemany(
                """
                INSERT OR IGNORE INTO evidence_chain_records (
                    chain_id, run_id, entity_id, entity_title, evidence_ids_json,
                    relation_ids_json, hyperedge_ids_json, links_json,
                    first_captured_at, last_captured_at, evidence_count,
                    relation_count, hyperedge_count, notes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                deduped_chain_rows,
            )

        query_family_rows: list[tuple[object, ...]] = []
        semantic_vector_rows: list[tuple[object, ...]] = []
        memory_write_mode = request.execution.memory.write_mode
        memory_status = "promoted" if memory_write_mode == "promote" else "quarantine"
        promoted_at = now if memory_status == "promoted" else None
        for record in telemetry if memory_write_mode != "none" else []:
            metadata = record.metadata or {}
            source_nodes = list(metadata.get("source_nodes", []))
            content_nodes = list(metadata.get("content_terms", []))
            content_weights = dict(metadata.get("content_weights", {}))
            source_hints = list(metadata.get("source_hints", []))
            notes = list(metadata.get("notes", []))
            memory_id = f"query_family:{uuid.uuid4()}"
            strategy = metadata.get("round_strategy") or record.strategy
            query_signature = _query_signature(record.query, strategy, content_weights)
            domain = str(meta.get("domain") or _resolve_domain_for_request(request))
            temporary_query_family = QueryFamilyMemoryRecord(
                memory_id=memory_id,
                run_id=run_id,
                campaign_id=request.execution.campaign_id,
                continuation_id=request.execution.continuation_id,
                memory_status=memory_status,
                promoted_at=datetime.fromisoformat(promoted_at) if promoted_at else None,
                domain=domain,
                objective=request.objective,
                output_profile=request.output_profile,
                round_num=record.round_num,
                strategy=strategy,
                query=record.query,
                query_signature=query_signature,
                source_nodes=source_nodes,
                content_weights=content_weights,
                source_hints=source_hints,
                notes=notes,
                raw_total=record.results_total,
                qualified_total=record.results_qualified,
                avg_score=record.avg_score,
                success_score=round(record.results_qualified / max(record.results_total, 1), 4),
                created_at=datetime.fromisoformat(now),
            )
            semantic_text = build_query_family_semantic_text(temporary_query_family)
            embedding = build_semantic_embedding(semantic_text)
            vector_id = build_semantic_vector_id("query_family", memory_id)
            query_family_rows.append(
                (
                    memory_id,
                    run_id,
                    request.execution.campaign_id,
                    request.execution.continuation_id,
                    memory_status,
                    promoted_at,
                    domain,
                    request.objective,
                    request.output_profile,
                    record.round_num,
                    strategy,
                    record.query,
                    query_signature,
                    json.dumps(source_nodes, ensure_ascii=False),
                    json.dumps(content_weights, ensure_ascii=False),
                    json.dumps(source_hints, ensure_ascii=False),
                    json.dumps(notes, ensure_ascii=False),
                    record.results_total,
                    record.results_qualified,
                    record.avg_score,
                    temporary_query_family.success_score,
                    now,
                    json.dumps(content_nodes, ensure_ascii=False),
                )
            )
            semantic_vector_rows.append(
                (
                    vector_id,
                    "query_family",
                    memory_id,
                    run_id,
                    request.objective,
                    request.output_profile,
                    strategy,
                    semantic_text,
                    json.dumps(embedding, ensure_ascii=False),
                    len(embedding),
                    vector_norm(embedding),
                    now,
                )
            )
        if query_family_rows:
            conn.executemany(
                """
                INSERT INTO query_family_memory (
                    memory_id, run_id, campaign_id, continuation_id, memory_status,
                    promoted_at, domain, objective, output_profile, round_num, strategy,
                    query, query_signature, source_nodes_json, content_weights_json,
                    source_hints_json, notes_json, raw_total, qualified_total,
                    avg_score, success_score, created_at, content_nodes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                query_family_rows,
            )
        if semantic_vector_rows:
            conn.executemany(
                """
                INSERT INTO semantic_vectors (
                    vector_id, vector_kind, source_id, run_id, objective, output_profile,
                    strategy, text, embedding_json, dimensions, norm, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                semantic_vector_rows,
            )

    return run_id


def list_runs(
    limit: int = 20,
    offset: int = 0,
    project_id: str | None = None,
    campaign_id: str | None = None,
    continuation_id: str | None = None,
    path: str = DEFAULT_DB_PATH,
) -> tuple[list[RunRecord], int]:
    clauses: list[str] = []
    params: list[object] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if campaign_id:
        clauses.append("campaign_id = ?")
        params.append(campaign_id)
    if continuation_id:
        clauses.append("continuation_id = ?")
        params.append(continuation_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn(path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM discovery_runs {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT run_id, objective, output_profile, project_id, campaign_id, continuation_id,
                   request_json, entities_json, relations_json, meta_json, created_at
            FROM discovery_runs
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    items: list[RunRecord] = []
    for row in rows:
        entities = json.loads(row[7])
        relations = json.loads(row[8])
        meta = json.loads(row[9])
        items.append(
            RunRecord(
                run_id=row[0],
                objective=row[1],
                output_profile=row[2],
                project_id=row[3],
                campaign_id=row[4],
                continuation_id=row[5],
                request=json.loads(row[6]),
                meta=meta,
                created_at=datetime.fromisoformat(row[10]),
                entity_count=len(entities),
                relation_count=len(relations),
            )
        )
    return items, int(total)


def get_run(run_id: str, path: str = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    with get_conn(path) as conn:
        row = conn.execute(
            """
            SELECT run_id, objective, output_profile, campaign_id, continuation_id,
                   persistence_mode, request_json, entities_json, relations_json,
                   meta_json, created_at
            FROM discovery_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "run_id": row[0],
        "objective": row[1],
        "output_profile": row[2],
        "campaign_id": row[3],
        "continuation_id": row[4],
        "persistence_mode": row[5],
        "request": json.loads(row[6]),
        "entities": json.loads(row[7]),
        "relations": json.loads(row[8]),
        "meta": json.loads(row[9]),
        "created_at": row[10],
    }


def update_run_meta(run_id: str, meta: dict[str, Any], path: str = DEFAULT_DB_PATH) -> None:
    with get_conn(path) as conn:
        existing = conn.execute(
            "SELECT meta_json FROM discovery_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if existing is None:
            raise KeyError(f"run not found: {run_id}")

        existing_meta = json.loads(existing[0]) if existing[0] else {}
        existing_meta.update(meta)
        conn.execute(
            """
            UPDATE discovery_runs
            SET meta_json = ?
            WHERE run_id = ?
            """,
            (
                json.dumps(existing_meta, ensure_ascii=False),
                run_id,
            ),
        )


# ---------------------------------------------------------------------------
# Private helpers (used only by persist_discovery_run)
# ---------------------------------------------------------------------------

def _derive_default_hyperedges(
    run_id: str,
    entities: list[CanonicalEntity],
    telemetry: list[TelemetryRecord],
) -> list[HoldHyperedgeRecord]:
    hyperedges: list[HoldHyperedgeRecord] = []
    now = datetime.now(UTC)

    if entities:
        members = [
            HoldHyperedgeMember(
                member_id=entity.entity_id,
                member_kind="entity",
                role=entity.entity_type,
                evidence_ids=[f"evidence:{entity.entity_id}"] if entity.evidence else [],
            )
            for entity in entities
        ]
        hyperedges.append(
            HoldHyperedgeRecord(
                hyperedge_id=f"hyperedge:{run_id}:entity_bundle",
                run_id=run_id,
                hyperedge_type="entity_bundle",
                summary="Bundle of canonical entities discovered in a single voyage.",
                confidence=max((entity.confidence for entity in entities), default=0.0),
                members=members,
                evidence_ids=[],
                source_ids=_collect_source_ids(entities),
                properties={"entity_count": len(entities)},
                created_at=now,
            )
        )

    for record in telemetry:
        metadata = record.metadata or {}
        query_signature = _query_signature(
            record.query,
            metadata.get("round_strategy") or record.strategy,
            metadata.get("content_weights", {}),
        )
        hyperedges.append(
            HoldHyperedgeRecord(
                hyperedge_id=f"hyperedge:{run_id}:query:{record.round_num}",
                run_id=run_id,
                hyperedge_type="query_family",
                summary=record.query,
                confidence=record.avg_score,
                members=[
                    HoldHyperedgeMember(
                        member_id=f"query:{query_signature}",
                        member_kind="query",
                        role="query_family",
                        weight=1.0,
                    ),
                    HoldHyperedgeMember(
                        member_id=f"run:{run_id}",
                        member_kind="run",
                        role="voyage",
                        weight=1.0,
                    ),
                    HoldHyperedgeMember(
                        member_id=f"strategy:{metadata.get('round_strategy') or record.strategy}",
                        member_kind="strategy",
                        role="routing",
                        weight=0.8,
                    ),
                ],
                evidence_ids=[],
                source_ids=list(metadata.get("source_hints", [])),
                properties={
                    "round_num": record.round_num,
                    "raw_total": record.results_total,
                    "qualified_total": record.results_qualified,
                    "success_score": round(record.results_qualified / max(record.results_total, 1), 4),
                },
                created_at=now,
            )
        )

    return hyperedges


def _collect_source_ids(entities: list[CanonicalEntity]) -> list[str]:
    source_ids: list[str] = []
    seen: set[str] = set()
    for entity in entities:
        for source_url in entity.source_urls:
            if source_url not in seen:
                seen.add(source_url)
                source_ids.append(source_url)
    return source_ids


def _build_evidence_chain_rows(
    run_id: str,
    entities: list[CanonicalEntity],
    evidence_rows: Sequence[tuple[object, ...]],
    relation_rows: Sequence[tuple[object, ...]],
    hyperedges: list[HoldHyperedgeRecord],
    created_at: str,
) -> list[tuple[object, ...]]:
    evidence_by_entity: dict[str, list[dict[str, object]]] = {}
    for row in evidence_rows:
        evidence_by_entity.setdefault(str(row[2]), []).append(
            {
                "evidence_id": row[0],
                "entity_id": row[2],
                "source_url": row[3],
                "source_name": row[4],
                "title": row[5],
                "snippet": row[6],
                "captured_at": row[7],
                "metadata": json.loads(str(row[8])),
            }
        )

    relation_ids_by_entity: dict[str, list[str]] = {}
    for row in relation_rows:
        relation_id = str(row[0])
        from_entity_id = str(row[3])
        to_entity_id = str(row[4])
        relation_ids_by_entity.setdefault(from_entity_id, []).append(relation_id)
        relation_ids_by_entity.setdefault(to_entity_id, []).append(relation_id)

    hyperedge_ids_by_entity: dict[str, list[str]] = {}
    for hyperedge in hyperedges:
        for member in hyperedge.members:
            hyperedge_ids_by_entity.setdefault(member.member_id, []).append(hyperedge.hyperedge_id)

    rows: list[tuple[object, ...]] = []
    for entity in entities:
        entity_evidence = evidence_by_entity.get(entity.entity_id, [])
        evidence_ids = [item["evidence_id"] for item in entity_evidence]
        relation_ids = _dedupe_preserve_order(relation_ids_by_entity.get(entity.entity_id, []))
        hyperedge_ids = _dedupe_preserve_order(hyperedge_ids_by_entity.get(entity.entity_id, []))

        links = [
            EvidenceChainLink(
                evidence_id=str(item["evidence_id"]),
                source_url=str(item["source_url"]),
                source_name=item["source_name"] if isinstance(item["source_name"], str) else None,
                title=item["title"] if isinstance(item["title"], str) else None,
                snippet=item["snippet"] if isinstance(item["snippet"], str) else None,
                captured_at=datetime.fromisoformat(str(item["captured_at"])) if item["captured_at"] else None,
                relation_ids=relation_ids,
                hyperedge_ids=hyperedge_ids,
                metadata=item["metadata"] if isinstance(item["metadata"], dict) else {},
            )
            for item in entity_evidence
        ]
        first_captured_at = links[0].captured_at.isoformat() if links and links[0].captured_at else None
        last_captured_at = links[-1].captured_at.isoformat() if links and links[-1].captured_at else None

        rows.append(
            (
                f"evidence_chain:{run_id}:{entity.entity_id}",
                run_id,
                entity.entity_id,
                entity.title,
                json.dumps(evidence_ids, ensure_ascii=False),
                json.dumps(relation_ids, ensure_ascii=False),
                json.dumps(hyperedge_ids, ensure_ascii=False),
                json.dumps([link.model_dump(mode="json") for link in links], ensure_ascii=False),
                first_captured_at,
                last_captured_at,
                len(evidence_ids),
                len(relation_ids),
                len(hyperedge_ids),
                json.dumps(
                    [
                        f"entity_type={entity.entity_type}",
                        f"evidence_count={len(evidence_ids)}",
                        f"relation_count={len(relation_ids)}",
                        f"hyperedge_count={len(hyperedge_ids)}",
                    ],
                    ensure_ascii=False,
                ),
                created_at,
            )
        )

    return rows


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            items.append(value)
    return items


def _query_signature(query: str, strategy: str, content_weights: dict[str, object]) -> str:
    payload = json.dumps(
        {
            "query": query,
            "strategy": strategy,
            "content_weights": content_weights,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"qf:{uuid.uuid5(uuid.NAMESPACE_URL, payload)}"


def _resolve_domain_for_request(request: DiscoveryRequest) -> str:
    objective_to_domain = {
        "find_events": "events",
        "find_exhibitors": "events",
        "find_leads": "bd_leads",
        "find_companies": "companies",
        "find_market_activity": "market_intel",
        "find_partnership_signals": "partnerships",
    }
    return objective_to_domain.get(request.objective, "general")
