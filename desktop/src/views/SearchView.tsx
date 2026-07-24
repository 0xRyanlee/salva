import { useEffect, useState } from "react";
import { Search, AlertTriangle, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { discover, type CanonicalEntity, type DiscoverMeta } from "@/lib/api";

const OBJECTIVES = [
  { value: "find_companies", label: "Companies" },
  { value: "find_leads", label: "Leads" },
  { value: "find_events", label: "Events" },
  { value: "find_market_activity", label: "Market Activity" },
];

interface SearchViewProps {
  coreOnline: boolean | null;
  campaignId: string | null;
  onViewRun: (runId: string) => void;
}

export function SearchView({ coreOnline, campaignId, onViewRun }: SearchViewProps) {
  const [market, setMarket] = useState("Germany");
  const [industry, setIndustry] = useState("software");
  const [objective, setObjective] = useState("find_companies");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [entities, setEntities] = useState<CanonicalEntity[]>([]);
  const [meta, setMeta] = useState<DiscoverMeta | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!loading) return;
    setElapsedSeconds(0);
    const start = Date.now();
    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [loading]);

  function toggleExpanded(entityId: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(entityId)) {
        next.delete(entityId);
      } else {
        next.add(entityId);
      }
      return next;
    });
  }

  async function runSearch() {
    if (!campaignId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await discover({ market, industry, objective, campaignId, maxResults: 15 });
      setEntities(result.entities);
      setMeta(result.meta);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 flex flex-col gap-4 p-4 max-w-3xl w-full mx-auto">
      <section className="glass-1 border border-border/30 rounded-lg p-3 space-y-3 overflow-hidden">
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1">
            <span className="type-label text-muted-foreground">Market</span>
            <Input value={market} onChange={(e) => setMarket(e.target.value)} placeholder="Germany" />
          </label>
          <label className="space-y-1">
            <span className="type-label text-muted-foreground">Industry</span>
            <Input value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="software" />
          </label>
        </div>

        <label className="space-y-1 block">
          <span className="type-label text-muted-foreground">Objective</span>
          <div className="flex gap-1.5 flex-wrap">
            {OBJECTIVES.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setObjective(opt.value)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-xs-minus border transition-colors",
                  objective === opt.value
                    ? "border-primary bg-primary/30 text-primary"
                    : "border-border/40 text-muted-foreground hover:bg-secondary/60",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </label>

        <Button
          onClick={runSearch}
          disabled={loading || !market || !industry || !coreOnline || !campaignId}
          className="w-full"
        >
          <Search size={14} className="mr-1.5" />
          {loading
            ? `Searching… (${elapsedSeconds}s)`
            : !coreOnline
              ? "等待 core 連線…"
              : !campaignId
                ? "尚未選擇 campaign"
                : "Search"}
        </Button>
      </section>

      {error && (
        <div className="rounded-md border border-destructive bg-destructive/10 text-destructive text-sm px-3 py-2">
          {error}
        </div>
      )}

      {meta && (
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="secondary">
            {meta.qualified_count ?? 0} / {meta.raw_count ?? 0} qualified
          </Badge>
          {meta.rounds != null && <Badge variant="outline">{meta.rounds} rounds</Badge>}
          {!!meta.entities_merged_count && (
            <Badge variant="default">{meta.entities_merged_count} merged</Badge>
          )}
          {meta.providers_exhausted && (
            <span className="inline-flex items-center gap-1 text-warn text-xs-minus">
              <AlertTriangle size={12} />
              providers exhausted — results may be incomplete
            </span>
          )}
          {meta.memory_seeds_used ? (
            <Badge variant="default">
              <Zap size={10} className="mr-0.5" />
              {meta.memory_seeds_used} memory seeds reused
            </Badge>
          ) : (
            <span className="type-caption text-muted-foreground">no memory reused</span>
          )}
          {meta.run_id && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => meta.run_id && onViewRun(meta.run_id)}
            >
              View run →
            </Button>
          )}
        </div>
      )}

      <ScrollArea className="flex-1 min-h-0">
        {entities.length === 0 && !loading ? (
          <EmptyState
            icon={Search}
            label={
              !meta
                ? "run a search to see results"
                : meta.providers_exhausted
                  ? "資料來源用盡導致 0 筆結果，建議稍後重試"
                  : "no qualified results"
            }
          />
        ) : (
          <ul className="space-y-2">
            {entities.map((entity) => {
              const evidence = entity.evidence ?? [];
              const isExpanded = expandedIds.has(entity.entity_id);
              return (
                <li
                  key={entity.entity_id}
                  className="glass-1 border border-border/30 rounded-lg p-3 space-y-1 overflow-hidden"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="type-body font-medium">{entity.title}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Badge variant="outline">{entity.entity_type}</Badge>
                      <Badge variant="outline">{entity.confidence.toFixed(2)}</Badge>
                    </div>
                  </div>
                  {entity.summary && (
                    <p className="type-caption text-muted-foreground">{entity.summary}</p>
                  )}
                  {entity.source_urls[0] && (
                    <a
                      href={entity.source_urls[0]}
                      target="_blank"
                      rel="noreferrer"
                      className="type-caption text-primary hover:underline block truncate"
                    >
                      {entity.source_urls[0]}
                    </a>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="px-0 h-auto py-1"
                    onClick={() => toggleExpanded(entity.entity_id)}
                  >
                    {isExpanded ? "收合 evidence ▲" : `展開 evidence（${evidence.length}）▼`}
                  </Button>
                  {isExpanded && (
                    <div className="space-y-1.5 pt-1 border-t border-border/20">
                      {evidence.length === 0 ? (
                        <p className="type-caption text-muted-foreground">no evidence captured</p>
                      ) : (
                        evidence.map((item, idx) => (
                          <div key={idx} className="type-caption space-y-0.5">
                            {item.source_name && (
                              <span className="text-muted-foreground">{item.source_name}</span>
                            )}
                            {item.title && <p className="font-medium">{item.title}</p>}
                            {item.snippet && (
                              <p className="text-muted-foreground">{item.snippet}</p>
                            )}
                            <a
                              href={item.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary hover:underline block truncate"
                            >
                              {item.source_url}
                            </a>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </ScrollArea>
    </div>
  );
}
