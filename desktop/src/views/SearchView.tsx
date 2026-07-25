import { useEffect, useState } from "react";
import { Search, AlertTriangle, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ChipToggle } from "@/components/ui/ChipToggle";
import { ScrollArea } from "@/components/ui/scroll-area";
import { discover, type CanonicalEntity, type DiscoverMeta } from "@/lib/api";

const OBJECTIVES = [
  { value: "find_companies", label: "公司" },
  { value: "find_leads", label: "名單" },
  { value: "find_events", label: "活動" },
  { value: "find_market_activity", label: "市場動態" },
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
            <span className="type-label text-muted-foreground">市場</span>
            <Input value={market} onChange={(e) => setMarket(e.target.value)} placeholder="Germany" />
          </label>
          <label className="space-y-1">
            <span className="type-label text-muted-foreground">產業</span>
            <Input value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="software" />
          </label>
        </div>

        <label className="space-y-1 block">
          <span className="type-label text-muted-foreground">目標</span>
          <div className="flex gap-1.5 flex-wrap">
            {OBJECTIVES.map((opt) => (
              <ChipToggle
                key={opt.value}
                selected={objective === opt.value}
                onClick={() => setObjective(opt.value)}
              >
                {opt.label}
              </ChipToggle>
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
            ? `搜尋中…(${elapsedSeconds}秒)`
            : !coreOnline
              ? "等待 core 連線…"
              : !campaignId
                ? "尚未選擇 campaign"
                : "搜尋"}
        </Button>
      </section>

      {error && <ErrorBanner message={error} />}

      {meta && (
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="secondary">
            {meta.qualified_count ?? 0} / {meta.raw_count ?? 0} 合格
          </Badge>
          {meta.rounds != null && <Badge variant="outline">{meta.rounds} 輪</Badge>}
          {!!meta.entities_merged_count && (
            <Badge variant="default">{meta.entities_merged_count} 合併</Badge>
          )}
          {meta.providers_exhausted && (
            <span className="inline-flex items-center gap-1 text-warn text-xs-minus">
              <AlertTriangle size={12} />
              provider 已耗盡——結果可能不完整
            </span>
          )}
          {meta.memory_seeds_used ? (
            <Badge variant="default">
              <Zap size={10} className="mr-0.5" />
              復用了 {meta.memory_seeds_used} 筆 memory seeds
            </Badge>
          ) : (
            <span className="type-caption text-muted-foreground">沒有復用 memory</span>
          )}
          {meta.run_id && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => meta.run_id && onViewRun(meta.run_id)}
            >
              查看 run →
            </Button>
          )}
        </div>
      )}

      <ScrollArea className="flex-1 min-h-0">
        {loading && entities.length === 0 ? (
          <LoadingState />
        ) : entities.length === 0 ? (
          <EmptyState
            icon={Search}
            label={
              !meta
                ? "執行搜尋以查看結果"
                : meta.providers_exhausted
                  ? "資料來源用盡導致 0 筆結果，建議稍後重試"
                  : "沒有合格結果"
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
                    <div className="flex-1 min-w-0">
                      <span className="type-body font-medium truncate block">{entity.title}</span>
                    </div>
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
                        <p className="type-caption text-muted-foreground">沒有擷取到佐證</p>
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
