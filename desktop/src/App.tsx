import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { Sparkles, ChevronDown, Search, History, Brain } from "lucide-react";
import { cn } from "@/lib/utils";
import { checkHealth, checkLlmStatus, type LlmSidecarStatus } from "@/lib/api";
import { SearchView } from "@/views/SearchView";
import { RunsView } from "@/views/RunsView";
import { RunDetailView } from "@/views/RunDetailView";
import { MemoryView } from "@/views/MemoryView";

type View =
  | { name: "search" }
  | { name: "runs" }
  | { name: "run-detail"; runId: string; from: "search" | "runs" }
  | { name: "memory" };

const NAV_ITEMS: { name: View["name"]; icon: typeof Search; label: string }[] = [
  { name: "search", icon: Search, label: "Search" },
  { name: "runs", icon: History, label: "Runs" },
  { name: "memory", icon: Brain, label: "Memory" },
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
  const [view, setView] = useState<View>({ name: "search" });

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

      <div className="flex-1 flex min-h-0">
        <nav className="glass-1 border-r border-border/40 w-16 flex flex-col items-center gap-1 py-3">
          {NAV_ITEMS.map((item) => {
            const active = view.name === item.name || (view.name === "run-detail" && item.name === "runs");
            const Icon = item.icon;
            return (
              <button
                key={item.name}
                type="button"
                onClick={() => setView({ name: item.name } as View)}
                className={cn(
                  "flex flex-col items-center gap-0.5 w-12 py-2 rounded-md transition-colors",
                  active
                    ? "bg-primary/20 text-primary"
                    : "text-muted-foreground hover:bg-secondary/60",
                )}
              >
                <Icon size={16} />
                <span className="text-xs-minus">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
          {view.name === "search" && (
            <SearchView
              coreOnline={coreOnline}
              onViewRun={(runId) => setView({ name: "run-detail", runId, from: "search" })}
            />
          )}
          {view.name === "runs" && (
            <RunsView
              onSelectRun={(runId) => setView({ name: "run-detail", runId, from: "runs" })}
            />
          )}
          {view.name === "run-detail" && (
            <RunDetailView
              runId={view.runId}
              onBack={() => setView(view.from === "search" ? { name: "search" } : { name: "runs" })}
            />
          )}
          {view.name === "memory" && <MemoryView />}
        </div>
      </div>
    </main>
  );
}

export default App;
