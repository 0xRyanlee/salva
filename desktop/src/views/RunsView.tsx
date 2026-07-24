import { useEffect, useState } from "react";
import { History } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { listRuns, type RunRecord } from "@/lib/api";

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (diffSec < 60) return `${diffSec} 秒前`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} 分鐘前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} 小時前`;
  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay} 天前`;
}

function marketIndustry(request: Record<string, unknown>): string {
  const intent = request.intent as Record<string, unknown> | undefined;
  const market = intent?.market;
  const industry = intent?.industry;
  if (!market && !industry) return "—";
  return [market, industry].filter(Boolean).join(" / ");
}

interface RunsViewProps {
  onSelectRun: (runId: string) => void;
}

export function RunsView({ onSelectRun }: RunsViewProps) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await listRuns(50);
        if (cancelled) return;
        setRuns(result.items);
        setTotal(result.total);
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
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="type-caption text-muted-foreground">loading…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-4">
        <div className="rounded-md border border-destructive bg-destructive/10 text-destructive text-sm px-3 py-2">
          {error}
        </div>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <EmptyState icon={History} label="no runs yet" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col gap-2 p-4 overflow-y-auto">
      {total > 50 && (
        <span className="type-caption text-muted-foreground">showing latest 50</span>
      )}
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left type-caption text-muted-foreground border-b border-border/40">
            <th className="py-1.5 pr-3 font-medium">created</th>
            <th className="py-1.5 pr-3 font-medium">objective</th>
            <th className="py-1.5 pr-3 font-medium">market / industry</th>
            <th className="py-1.5 pr-3 font-medium text-right">entities</th>
            <th className="py-1.5 pr-3 font-medium text-right">relations</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr
              key={run.run_id}
              onClick={() => onSelectRun(run.run_id)}
              className="border-b border-border/20 cursor-pointer hover:bg-secondary/40"
            >
              <td className="py-1.5 pr-3 whitespace-nowrap">{relativeTime(run.created_at)}</td>
              <td className="py-1.5 pr-3">{run.objective}</td>
              <td className="py-1.5 pr-3">{marketIndustry(run.request)}</td>
              <td className="py-1.5 pr-3 text-right">{run.entity_count}</td>
              <td className="py-1.5 pr-3 text-right">{run.relation_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
