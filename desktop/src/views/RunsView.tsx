import { useEffect, useState } from "react";
import { History } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingState } from "@/components/ui/LoadingState";
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
    return <LoadingState />;
  }

  if (error) {
    return (
      <div className="flex-1 p-4">
        <ErrorBanner message={error} />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <EmptyState icon={History} label="還沒有 run" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col gap-2 p-4 overflow-y-auto">
      {total > 50 && (
        <span className="type-caption text-muted-foreground">顯示最新 50 筆</span>
      )}
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left type-caption text-muted-foreground border-b border-border/40">
            <th className="py-1.5 pr-3 font-medium">建立時間</th>
            <th className="py-1.5 pr-3 font-medium">目標</th>
            <th className="py-1.5 pr-3 font-medium">市場・產業</th>
            <th className="py-1.5 pr-3 font-medium text-right">實體</th>
            <th className="py-1.5 pr-3 font-medium text-right">關係</th>
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
