import type { CanonicalEntity, HoldHyperedgeRecord, RunSnapshot } from "@/lib/api";

export type EntityChangeKind = "added" | "removed" | "changed";

export interface EntityDiffRow {
  entityId: string;
  title: string;
  kind: EntityChangeKind;
  before?: CanonicalEntity;
  after?: CanonicalEntity;
  confidenceDelta?: number;
}

export type HyperedgeChangeKind = "added" | "removed";

export interface HyperedgeDiffRow {
  hyperedgeId: string;
  kind: HyperedgeChangeKind;
  edge: HoldHyperedgeRecord;
}

export interface RunDiffSummary {
  entitiesAdded: number;
  entitiesRemoved: number;
  entitiesChanged: number;
  entitiesUnchanged: number;
  hyperedgesAdded: number;
  hyperedgesRemoved: number;
}

export interface RunDiffResult {
  entityRows: EntityDiffRow[];
  hyperedgeRows: HyperedgeDiffRow[];
  summary: RunDiffSummary;
}

// 信心分數的浮動雜訊(重跑同一輪 pipeline 可能有極小數值誤差)不算變更，
// 超過這個門檻才視為實質變化——跟 Paperclip DiffView 的 CONFIDENCE_THRESHOLD
// 是不同概念(那是「低信心需複核」，這裡是「差異多大才算差異」)，故獨立命名。
const CONFIDENCE_DELTA_THRESHOLD = 0.01;

function entitySummary(entity: CanonicalEntity): string {
  return entity.summary ?? "";
}

// 比較同一個 campaign 內兩個 run(通常是 continuation 關係)的實體與
// hyperedge 差異，讓使用者看得懂「這次追加檢索多找到 / 少掉 / 信心變化
// 了什麼」——純函式，資料完全來自既有的 getRunSnapshot()，不需要新後端端點。
export function computeRunDiff(before: RunSnapshot, after: RunSnapshot): RunDiffResult {
  const beforeById = new Map(before.entities.map((e) => [e.entity_id, e]));
  const afterById = new Map(after.entities.map((e) => [e.entity_id, e]));

  const entityRows: EntityDiffRow[] = [];
  let unchanged = 0;

  for (const entity of after.entities) {
    const prior = beforeById.get(entity.entity_id);
    if (!prior) {
      entityRows.push({ entityId: entity.entity_id, title: entity.title, kind: "added", after: entity });
      continue;
    }
    const confidenceDelta = entity.confidence - prior.confidence;
    const changed =
      Math.abs(confidenceDelta) > CONFIDENCE_DELTA_THRESHOLD || entitySummary(entity) !== entitySummary(prior);
    if (changed) {
      entityRows.push({
        entityId: entity.entity_id,
        title: entity.title,
        kind: "changed",
        before: prior,
        after: entity,
        confidenceDelta,
      });
    } else {
      unchanged += 1;
    }
  }

  for (const entity of before.entities) {
    if (!afterById.has(entity.entity_id)) {
      entityRows.push({ entityId: entity.entity_id, title: entity.title, kind: "removed", before: entity });
    }
  }

  const beforeEdgeIds = new Set(before.hyperedges.map((h) => h.hyperedge_id));
  const afterEdgeIds = new Set(after.hyperedges.map((h) => h.hyperedge_id));

  const hyperedgeRows: HyperedgeDiffRow[] = [
    ...after.hyperedges
      .filter((h) => !beforeEdgeIds.has(h.hyperedge_id))
      .map((edge): HyperedgeDiffRow => ({ hyperedgeId: edge.hyperedge_id, kind: "added", edge })),
    ...before.hyperedges
      .filter((h) => !afterEdgeIds.has(h.hyperedge_id))
      .map((edge): HyperedgeDiffRow => ({ hyperedgeId: edge.hyperedge_id, kind: "removed", edge })),
  ];

  const summary: RunDiffSummary = {
    entitiesAdded: entityRows.filter((r) => r.kind === "added").length,
    entitiesRemoved: entityRows.filter((r) => r.kind === "removed").length,
    entitiesChanged: entityRows.filter((r) => r.kind === "changed").length,
    entitiesUnchanged: unchanged,
    hyperedgesAdded: hyperedgeRows.filter((r) => r.kind === "added").length,
    hyperedgesRemoved: hyperedgeRows.filter((r) => r.kind === "removed").length,
  };

  return { entityRows, hyperedgeRows, summary };
}
