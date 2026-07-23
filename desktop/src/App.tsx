import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { Search, AlertTriangle, Sparkles, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import {
  checkHealth,
  checkLlmStatus,
  discover,
  type CanonicalEntity,
  type DiscoverMeta,
  type LlmSidecarStatus,
} from "@/lib/api";

const OBJECTIVES = [
  { value: "find_companies", label: "Companies" },
  { value: "find_leads", label: "Leads" },
  { value: "find_events", label: "Events" },
  { value: "find_market_activity", label: "Market Activity" },
];

interface CoreStatusEvent {
  online: boolean;
  error: string | null;
}

function App() {
  const [coreOnline, setCoreOnline] = useState<boolean | null>(null);
  const [coreError, setCoreError] = useState<string | null>(null);
  const [showCoreError, setShowCoreError] = useState(false);
  const [llmStatus, setLlmStatus] = useState<LlmSidecarStatus | null>(null);
  const [market, setMarket] = useState("Germany");
  const [industry, setIndustry] = useState("software");
  const [objective, setObjective] = useState("find_companies");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [entities, setEntities] = useState<CanonicalEntity[]>([]);
  const [meta, setMeta] = useState<DiscoverMeta | null>(null);

  // Rust 端 spawn core 後會 emit 一次立即結果（含失敗原因）；health-check
  // 輪詢是補強訊號（例如 core 起來後又中途掛掉），兩者互補而非取代彼此。
  useEffect(() => {
    const unlisten = listen<CoreStatusEvent>("core-status", (event) => {
      setCoreOnline(event.payload.online);
      setCoreError(event.payload.error);
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const online = await checkHealth();
      if (cancelled) return;
      setCoreOnline(online);
      if (online) setCoreError(null);
      setLlmStatus(await checkLlmStatus());
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  async function runSearch() {
    setLoading(true);
    setError(null);
    try {
      const result = await discover({ market, industry, objective, maxResults: 15 });
      setEntities(result.entities);
      setMeta(result.meta);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const llmUnavailable = llmStatus && !llmStatus.sidecar_reachable && !llmStatus.byok_configured;

  return (
    <main className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="glass-1 border-b border-border/40 px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-primary" />
          <span className="type-title">Salva</span>
        </div>
        <div className="flex items-center gap-3">
          {llmStatus && (
            <span
              className="type-caption text-muted-foreground"
              title={
                llmStatus.sidecar_reachable
                  ? "LLM enrichment: sidecar 已連線"
                  : llmStatus.byok_configured
                    ? "LLM enrichment: 使用 BYOK 端點"
                    : "LLM enrichment 未啟用——結果不含 rerank/query-proposal 加值，搜尋本身仍會正常運作"
              }
            >
              LLM: {llmStatus.sidecar_reachable ? "sidecar" : llmStatus.byok_configured ? "BYOK" : "off"}
            </span>
          )}
          <button
            type="button"
            onClick={() => coreError && setShowCoreError((v) => !v)}
            className="flex items-center gap-1.5"
          >
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full",
                coreOnline === null ? "bg-muted-foreground" : coreOnline ? "bg-success" : "bg-destructive",
              )}
            />
            <span className="type-caption text-muted-foreground">
              {coreOnline === null ? "connecting…" : coreOnline ? "core online" : "core offline"}
            </span>
            {coreError && <ChevronDown size={12} className="text-muted-foreground" />}
          </button>
        </div>
      </header>

      {coreError && showCoreError && (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 type-caption text-destructive whitespace-pre-wrap">
          {coreError}
        </div>
      )}
      {llmUnavailable && (
        <div className="border-b border-warn/40 bg-warn/10 px-4 py-2 type-caption text-warn">
          LLM enrichment 未啟用——搜尋結果不含 rerank/追加查詢加值。要啟用：另開一個
          terminal 執行 <code className="font-mono">python -m salva_core.llm_sidecar_run</code>
          （需先 <code className="font-mono">claude login</code> 或{" "}
          <code className="font-mono">codex login</code>），或設定 BYOK 環境變數。
        </div>
      )}

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
            disabled={loading || !market || !industry || !coreOnline}
            className="w-full"
          >
            <Search size={14} className="mr-1.5" />
            {loading ? "Searching…" : coreOnline ? "Search" : "等待 core 連線…"}
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
              {entities.map((entity) => (
                <li
                  key={entity.entity_id}
                  className="glass-1 border border-border/30 rounded-lg p-3 space-y-1 overflow-hidden"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="type-body font-medium">{entity.title}</span>
                    <Badge variant="outline">{entity.confidence.toFixed(2)}</Badge>
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
                </li>
              ))}
            </ul>
          )}
        </ScrollArea>
      </div>
    </main>
  );
}

export default App;
