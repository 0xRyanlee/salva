from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from salva_core.evaluation import build_audit_report
from salva_core.persistence import (
    get_run,
    list_evidence_chains,
    list_evidence_records,
    list_hyperedges,
    list_plugin_reports,
    list_query_family_memory,
    list_source_attempts,
    list_telemetry,
)
from salva_core.schemas import (
    CanonicalEntity,
    CanonicalRelation,
    EvidenceRecord,
    EvidenceChainRecord,
    HoldHyperedgeRecord,
    PluginReportRecord,
    QueryFamilyMemoryRecord,
    RunSnapshot,
    SnapshotExportResult,
    SourceAttemptRecord,
    TelemetryRecord,
)


def build_run_snapshot(run_id: str, path: str | None = None) -> RunSnapshot:
    detail = get_run(run_id, path=path) if path is not None else get_run(run_id)
    if detail is None:
        raise KeyError(f"run not found: {run_id}")

    telemetry, telemetry_total = _list_telemetry(run_id=run_id, path=path)
    source_attempts, source_total = _list_source_attempts(run_id=run_id, path=path)
    evidence_records, evidence_total = _list_evidence_records(run_id=run_id, path=path)
    evidence_chains, evidence_chain_total = _list_evidence_chains(run_id=run_id, path=path)
    hyperedges, hyperedge_total = _list_hyperedges(run_id=run_id, path=path)
    query_family_memory, query_family_total = _list_query_family_memory(run_id=run_id, path=path)
    plugin_reports, plugin_total = _list_plugin_reports(run_id=run_id, path=path)
    audit = build_audit_report(run_id, path=path)
    generated_at = datetime.now(UTC)

    entities = [CanonicalEntity.model_validate(entity) for entity in detail["entities"]]
    relations = [CanonicalRelation.model_validate(relation) for relation in detail["relations"]]

    return RunSnapshot(
        run_id=run_id,
        objective=detail["objective"],
        output_profile=detail["output_profile"],
        created_at=_coerce_created_at(detail.get("created_at")),
        generated_at=generated_at,
        request=detail["request"],
        meta=detail["meta"],
        entities=entities,
        relations=relations,
        evidence_records=evidence_records,
        evidence_chains=evidence_chains,
        hyperedges=hyperedges,
        query_family_memory=query_family_memory,
        telemetry=telemetry,
        source_attempts=source_attempts,
        plugin_reports=plugin_reports,
        audit=audit,
        entity_count=len(entities),
        relation_count=len(relations),
        evidence_count=evidence_total,
        evidence_chain_count=evidence_chain_total,
        hyperedge_count=hyperedge_total,
        query_family_count=query_family_total,
        telemetry_count=telemetry_total,
        source_attempt_count=source_total,
        plugin_report_count=plugin_total,
    )


def write_run_snapshot(
    run_id: str,
    output_path: str | None = None,
    path: str | None = None,
) -> SnapshotExportResult:
    snapshot = build_run_snapshot(run_id, path=path)
    export_path = _resolve_export_path(run_id, output_path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2)
    export_path.write_text(payload, encoding="utf-8")
    data = payload.encode("utf-8")
    sha256 = hashlib.sha256(data).hexdigest()
    return SnapshotExportResult(
        snapshot=snapshot,
        export_path=str(export_path),
        bytes_written=len(data),
        sha256=sha256,
    )


def _resolve_export_path(run_id: str, output_path: str | None) -> Path:
    if output_path:
        return Path(output_path).expanduser()
    return Path(tempfile.gettempdir()) / "salva-exports" / f"{run_id}.json"


def _list_telemetry(run_id: str, path: str | None):
    records, total = list_telemetry(run_id=run_id, path=path) if path is not None else list_telemetry(run_id=run_id)
    return [
        record if isinstance(record, TelemetryRecord) else TelemetryRecord.model_validate(record)
        for record in records
    ], total


def _list_source_attempts(run_id: str, path: str | None):
    records, total = list_source_attempts(run_id=run_id, path=path) if path is not None else list_source_attempts(run_id=run_id)
    return [
        record if isinstance(record, SourceAttemptRecord) else SourceAttemptRecord.model_validate(record)
        for record in records
    ], total


def _list_plugin_reports(run_id: str, path: str | None):
    records, total = list_plugin_reports(run_id=run_id, path=path) if path is not None else list_plugin_reports(run_id=run_id)
    return [
        record if isinstance(record, PluginReportRecord) else PluginReportRecord.model_validate(record)
        for record in records
    ], total


def _list_evidence_records(run_id: str, path: str | None):
    records, total = list_evidence_records(run_id=run_id, path=path) if path is not None else list_evidence_records(run_id=run_id)
    return [
        record if isinstance(record, EvidenceRecord) else EvidenceRecord.model_validate(record)
        for record in records
    ], total


def _list_evidence_chains(run_id: str, path: str | None):
    records, total = list_evidence_chains(run_id=run_id, path=path) if path is not None else list_evidence_chains(run_id=run_id)
    return [
        record if isinstance(record, EvidenceChainRecord) else EvidenceChainRecord.model_validate(record)
        for record in records
    ], total


def _list_hyperedges(run_id: str, path: str | None):
    records, total = list_hyperedges(run_id=run_id, path=path) if path is not None else list_hyperedges(run_id=run_id)
    return [
        record if isinstance(record, HoldHyperedgeRecord) else HoldHyperedgeRecord.model_validate(record)
        for record in records
    ], total


def _list_query_family_memory(run_id: str, path: str | None):
    records, total = list_query_family_memory(run_id=run_id, path=path) if path is not None else list_query_family_memory(run_id=run_id)
    return [
        record if isinstance(record, QueryFamilyMemoryRecord) else QueryFamilyMemoryRecord.model_validate(record)
        for record in records
    ], total


def _coerce_created_at(value):
    return value
