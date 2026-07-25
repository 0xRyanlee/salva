import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, GitCompare, Plus, Minus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge, pillTintClass } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { getRunSnapshot, type RunSnapshot } from "@/lib/api";
import { computeRunDiff, type EntityDiffRow, type HyperedgeDiffRow } from "@/lib/runDiff";

interface RunDiffViewProps {
  runIdBefore: string;
  runIdAfter: string;
  onBack: () => void;
}

const rowTone: Record<EntityDiffRow["kind"] | HyperedgeDiffRow["kind"], string> = {
  added: "border-l-4 border-l-success bg-success/5",
  removed: "border-l-4 border-l-destructive bg-destructive/5",
  changed: "border-l-4 border-l-warn bg-warn/5",
};

const rowLabel: Record<EntityDiffRow["kind"] | HyperedgeDiffRow["kind"], string> = {
  added: "新增",
  removed: "移除",
  changed: "變更",
};

const rowIcon: Record<EntityDiffRow["kind"] | HyperedgeDiffRow["kind"], typeof Plus> = {
  added: Plus,
  removed: Minus,
  changed: RefreshCw,
};

function EntityDiffRowView({ row }: { row: EntityDiffRow }) {
  const Icon = rowIcon[row.kind];
  return (
    <li className={`rounded-lg p-3 space-y-1.5 ${rowTone[row.kind]}`}>
      <div className="flex items-center gap-2 flex-wrap">
        <Icon size={12} />
        <span className="type-caption font-medium">{rowLabel[row.kind]}</span>
        <span className="type-body font-medium truncate">{row.title}</span>
        {row.kind === "changed" && row.confidenceDelta != null && (
          <Badge className={row.confidenceDelta > 0 ? pillTintClass.success : pillTintClass.destructive}>
            信心 {row.confidenceDelta > 0 ? "+" : ""}
            {row.confidenceDelta.toFixed(2)}
          </Badge>
        )}
      </div>
      {row.kind === "changed" && row.before && row.after && (
        <div className="grid grid-cols-2 gap-3 text-xs-minus pt-1">
          <div>
            <p className="text-muted-foreground mb-0.5">舊版（{row.before.confidence.toFixed(2)}）</p>
            <p className="text-foreground/70">{row.before.summary || "（無摘要）"}</p>
          </div>
          <div>
            <p className="text-muted-foreground mb-0.5">新版（{row.after.confidence.toFixed(2)}）</p>
            <p className="text-foreground">{row.after.summary || "（無摘要）"}</p>
          </div>
        </div>
      )}
      {row.kind !== "changed" && (row.before ?? row.after)?.summary && (
        <p className="type-caption text-muted-foreground">{(row.before ?? row.after)?.summary}</p>
      )}
    </li>
  );
}

function HyperedgeDiffRowView({ row }: { row: HyperedgeDiffRow }) {
  const Icon = rowIcon[row.kind];
  return (
    <li className={`rounded-lg p-3 space-y-1 ${rowTone[row.kind]}`}>
      <div className="flex items-center gap-2 flex-wrap">
        <Icon size={12} />
        <span className="type-caption font-medium">{rowLabel[row.kind]}</span>
        <Badge variant="outline">{row.edge.hyperedge_type}</Badge>
        <span className="type-caption text-muted-foreground">信心 {row.edge.confidence.toFixed(2)}</span>
      </div>
      {row.edge.summary && <p className="type-caption text-muted-foreground">{row.edge.summary}</p>}
      {row.edge.members.length > 0 && (
        <p className="text-xs-minus text-muted-foreground">
          {row.edge.members.length} 個成員：
          {row.edge.members.map((m) => m.role).join("、")}
        </p>
      )}
    </li>
  );
}

export function RunDiffView({ runIdBefore, runIdAfter, onBack }: RunDiffViewProps) {
  const [before, setBefore] = useState<RunSnapshot | null>(null);
  const [after, setAfter] = useState<RunSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setBefore(null);
      setAfter(null);
      try {
        const [a, b] = await Promise.all([getRunSnapshot(runIdBefore), getRunSnapshot(runIdAfter)]);
        if (cancelled) return;
        setBefore(a);
        setAfter(b);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runIdBefore, runIdAfter]);

  const diff = useMemo(() => (before && after ? computeRunDiff(before, after) : null), [before, after]);

  return (
    <div className="flex-1 flex flex-col gap-3 p-4 overflow-y-auto">
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onBack}>
          <ArrowLeft size={14} className="mr-1.5" />
          返回
        </Button>
        <GitCompare size={14} className="text-muted-foreground" />
        <span className="type-caption text-muted-foreground">
          {runIdBefore} → {runIdAfter}
        </span>
      </div>

      {loading && <LoadingState />}
      {error && <ErrorBanner message={error} />}

      {diff && (
        <>
          <div className="glass-1 border border-border/30 rounded-lg p-3 flex items-center gap-2 flex-wrap">
            {diff.summary.entitiesAdded > 0 && (
              <Badge className={pillTintClass.success}>+{diff.summary.entitiesAdded} 實體</Badge>
            )}
            {diff.summary.entitiesRemoved > 0 && (
              <Badge className={pillTintClass.destructive}>-{diff.summary.entitiesRemoved} 實體</Badge>
            )}
            {diff.summary.entitiesChanged > 0 && (
              <Badge className={pillTintClass.warn}>{diff.summary.entitiesChanged} 項變更</Badge>
            )}
            <Badge variant="secondary">{diff.summary.entitiesUnchanged} 個不變</Badge>
            {diff.summary.hyperedgesAdded > 0 && (
              <Badge className={pillTintClass.success}>+{diff.summary.hyperedgesAdded} hyperedge</Badge>
            )}
            {diff.summary.hyperedgesRemoved > 0 && (
              <Badge className={pillTintClass.destructive}>-{diff.summary.hyperedgesRemoved} hyperedge</Badge>
            )}
            {diff.entityRows.length === 0 && diff.hyperedgeRows.length === 0 && (
              <span className="type-caption text-muted-foreground">兩個 run 之間沒有差異</span>
            )}
          </div>

          {diff.entityRows.length > 0 && (
            <div className="space-y-1.5">
              <span className="type-label text-muted-foreground">實體差異</span>
              <ul className="space-y-1.5">
                {diff.entityRows.map((row) => (
                  <EntityDiffRowView key={`${row.kind}-${row.entityId}`} row={row} />
                ))}
              </ul>
            </div>
          )}

          {diff.hyperedgeRows.length > 0 && (
            <div className="space-y-1.5">
              <span className="type-label text-muted-foreground">Hyperedge 差異</span>
              <ul className="space-y-1.5">
                {diff.hyperedgeRows.map((row) => (
                  <HyperedgeDiffRowView key={`${row.kind}-${row.hyperedgeId}`} row={row} />
                ))}
              </ul>
            </div>
          )}

          {diff.entityRows.length === 0 && diff.hyperedgeRows.length === 0 && (
            <EmptyState icon={GitCompare} label="這兩個 run 的實體與 hyperedge 完全相同" />
          )}
        </>
      )}
    </div>
  );
}
