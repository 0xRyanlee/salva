import { useCallback, useEffect, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import {
  Sparkles,
  ChevronDown,
  Search,
  History,
  Brain,
  FolderKanban,
  Settings as SettingsIcon,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  checkHealth,
  checkLlmStatus,
  listCampaigns,
  createCampaign,
  type LlmSidecarStatus,
  type SidecarManagedStatus,
  type CampaignRecord,
} from "@/lib/api";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { LlmStatusPopover } from "@/components/LlmStatusPopover";
import { SearchView } from "@/views/SearchView";
import { RunsView } from "@/views/RunsView";
import { RunDetailView } from "@/views/RunDetailView";
import { MemoryView } from "@/views/MemoryView";
import { CampaignsView } from "@/views/CampaignsView";
import { SettingsView } from "@/views/SettingsView";

type View =
  | { name: "search" }
  | { name: "runs" }
  | { name: "run-detail"; runId: string; from: "search" | "runs" }
  | { name: "memory" }
  | { name: "campaigns" }
  | { name: "settings" };

const NAV_ITEMS: { name: View["name"]; icon: typeof Search; label: string }[] = [
  { name: "search", icon: Search, label: "搜尋" },
  { name: "runs", icon: History, label: "執行紀錄" },
  { name: "memory", icon: Brain, label: "記憶" },
  { name: "campaigns", icon: FolderKanban, label: "活動管理" },
  { name: "settings", icon: SettingsIcon, label: "設定" },
];

const ACTIVE_CAMPAIGN_KEY = "salva.activeCampaignId";
const LLM_CONSENT_KEY = "salva.llmEnabled";

interface CoreStatusEvent {
  online: boolean;
  error: string | null;
}

function App() {
  const [coreOnline, setCoreOnline] = useState<boolean | null>(null);
  const [coreError, setCoreError] = useState<string | null>(null);
  const [showCoreError, setShowCoreError] = useState(false);
  const [llmStatus, setLlmStatus] = useState<LlmSidecarStatus | null>(null);
  const [sidecarManaged, setSidecarManaged] = useState<SidecarManagedStatus | null>(null);
  const [llmMismatch, setLlmMismatch] = useState(false);
  const [showConsentDialog, setShowConsentDialog] = useState(false);
  const [view, setView] = useState<View>({ name: "search" });

  const [campaigns, setCampaigns] = useState<CampaignRecord[]>([]);
  const [activeCampaign, setActiveCampaign] = useState<CampaignRecord | null>(null);
  const [campaignsError, setCampaignsError] = useState<string | null>(null);

  const sidecarManagedRef = useRef<SidecarManagedStatus | null>(null);
  const mismatchCountRef = useRef(0);
  const consentDecidedRef = useRef(false);

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

  // sidecar-managed-process.md §5：Rust 端狀態機轉換時 emit，鏡像 core-status
  // 的做法；同一份 state 也用來判斷 badge 顏色/文字與 popover 內容。
  useEffect(() => {
    const unlisten = listen<SidecarManagedStatus>("sidecar-managed-status", (event) => {
      setSidecarManaged(event.payload);
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  useEffect(() => {
    sidecarManagedRef.current = sidecarManaged;
  }, [sidecarManaged]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      const online = await checkHealth();
      if (cancelled) return;
      setCoreOnline(online);
      if (online) setCoreError(null);
      const status = await checkLlmStatus();
      if (cancelled) return;
      setLlmStatus(status);
      // running 但 API 輪詢連不到——單一 poll 的落差可能只是race，連續超過
      // 2 次才判定為真的不一致，避免狀態轉換瞬間的假警報。
      const managed = sidecarManagedRef.current;
      if (managed?.state === "running" && status && !status.sidecar_reachable) {
        mismatchCountRef.current += 1;
      } else {
        mismatchCountRef.current = 0;
      }
      setLlmMismatch(mismatchCountRef.current > 2);
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  // sidecar-managed-process.md §1：consent 只問一次（per machine，存
  // localStorage）。等第一次 llmStatus 輪詢回來才判斷，避免在還不知道
  // byok_configured 之前就誤跳出同意框。
  useEffect(() => {
    if (llmStatus === null || consentDecidedRef.current) return;
    consentDecidedRef.current = true;
    if (llmStatus.byok_configured) return;
    const stored = localStorage.getItem(LLM_CONSENT_KEY);
    if (stored === "true" || stored === "false") {
      invoke("sidecar_consent", { enabled: stored === "true" }).catch(() => {});
    } else {
      setShowConsentDialog(true);
    }
  }, [llmStatus]);

  function handleConsent(enabled: boolean) {
    localStorage.setItem(LLM_CONSENT_KEY, String(enabled));
    setShowConsentDialog(false);
    invoke("sidecar_consent", { enabled }).catch(() => {});
  }

  // campaigns-lifecycle.md §8：core 上線後才 bootstrap；已有 activeCampaign
  // 就不重跑，core 重新上線（例如重啟後 coreOnline 由 false 變 true）才重試。
  useEffect(() => {
    if (!coreOnline || activeCampaign) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await listCampaigns("active");
        let list = res.items;
        const storedId = localStorage.getItem(ACTIVE_CAMPAIGN_KEY);
        let next = list.find((c) => c.campaign_id === storedId) ?? null;
        if (!next && list.length > 0) next = list[0];
        if (!next) {
          next = await createCampaign("Default");
          list = [next, ...list];
        }
        if (cancelled) return;
        setCampaigns(list);
        setActiveCampaign(next);
        localStorage.setItem(ACTIVE_CAMPAIGN_KEY, next.campaign_id);
        setCampaignsError(null);
      } catch (err) {
        if (!cancelled) setCampaignsError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [coreOnline, activeCampaign]);

  function switchCampaign(campaign: CampaignRecord) {
    setActiveCampaign(campaign);
    localStorage.setItem(ACTIVE_CAMPAIGN_KEY, campaign.campaign_id);
  }

  // CampaignsView 的任何異動（改名/封存/刪除/清快取）都呼叫這個，讓 header
  // 的清單跟 activeCampaign 保持一致；如果目前使用中的 campaign 被封存或刪除
  // 而不再出現在 active 清單裡，就清掉 activeCampaign 讓上面的 bootstrap effect
  // 重新挑一個。
  const refreshCampaigns = useCallback(async () => {
    try {
      const res = await listCampaigns("active");
      setCampaigns(res.items);
      setActiveCampaign((prev) => {
        if (!prev) return prev;
        const stillActive = res.items.find((c) => c.campaign_id === prev.campaign_id);
        if (stillActive) return stillActive;
        localStorage.removeItem(ACTIVE_CAMPAIGN_KEY);
        return null;
      });
    } catch {
      // 忽略——下一次使用者操作觸發的 refresh 會再試一次
    }
  }, []);

  const llmUnavailable = llmStatus && !llmStatus.sidecar_reachable && !llmStatus.byok_configured;
  const llmBadge = llmBadgeInfo(sidecarManaged, llmStatus, llmMismatch);

  return (
    <main className="min-h-screen bg-background text-foreground flex flex-col">
      <header className="glass-1 border-b border-border/40 px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-primary" />
          <span className="type-title">Salva</span>
        </div>
        <div className="flex items-center gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-1 type-caption text-muted-foreground hover:text-foreground"
              >
                <FolderKanban size={12} />
                <span className="max-w-32 truncate">
                  {activeCampaign ? activeCampaign.name : "選擇 campaign"}
                </span>
                <ChevronDown size={12} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              {campaigns.length === 0 && <DropdownMenuLabel>沒有可用的 campaign</DropdownMenuLabel>}
              {campaigns.map((c) => (
                <DropdownMenuItem key={c.campaign_id} onSelect={() => switchCampaign(c)}>
                  <span className="flex-1 truncate">{c.name}</span>
                  {c.campaign_id === activeCampaign?.campaign_id && <Check size={12} />}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => setView({ name: "campaigns" })}>
                管理 campaigns…
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {(llmStatus || sidecarManaged) && (
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className={cn("type-caption", llmToneClass[llmBadge.tone])}
                >
                  LLM: {llmBadge.text}
                </button>
              </PopoverTrigger>
              <PopoverContent>
                <LlmStatusPopover
                  managedStatus={sidecarManaged}
                  llmStatus={llmStatus}
                  mismatch={llmMismatch}
                  onEnable={() => handleConsent(true)}
                />
              </PopoverContent>
            </Popover>
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
              {coreOnline === null ? "連線中…" : coreOnline ? "core 已連線" : "core 已離線"}
            </span>
            {coreError && <ChevronDown size={12} className="text-muted-foreground" />}
          </button>
        </div>
      </header>

      {coreError && showCoreError && (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 type-caption text-destructive whitespace-pre-wrap break-words">
          {coreError}
        </div>
      )}
      {campaignsError && (
        <div className="border-b border-destructive/40 bg-destructive/10 px-4 py-2 type-caption text-destructive">
          campaign 清單載入失敗：{campaignsError}
        </div>
      )}
      {llmUnavailable && (
        <div className="border-b border-warn/40 bg-warn/10 px-4 py-2 type-caption text-warn">
          LLM 增強功能未啟用——搜尋結果不含 rerank/追加查詢加值，搜尋本身仍會正常運作。點右上角
          「LLM」標籤啟用（背景會啟動一個本機行程，呼叫你已登入的 claude/codex CLI）。
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
              campaignId={activeCampaign?.campaign_id ?? null}
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
          {view.name === "memory" && <MemoryView campaignId={activeCampaign?.campaign_id ?? null} />}
          {view.name === "campaigns" && (
            <CampaignsView
              activeCampaignId={activeCampaign?.campaign_id ?? null}
              onChanged={refreshCampaigns}
            />
          )}
          {view.name === "settings" && <SettingsView />}
        </div>
      </div>

      <Dialog
        open={showConsentDialog}
        onOpenChange={(open) => {
          if (!open) handleConsent(false);
        }}
      >
        <DialogContent>
          <DialogTitle>啟用 LLM 增強功能？</DialogTitle>
          <DialogDescription>
            Salva 會在背景啟動一個本機行程，呼叫你已登入的 claude/codex CLI 來做實體解析與摘要。
          </DialogDescription>
          <DialogFooter>
            <Button variant="outline" onClick={() => handleConsent(false)}>
              不用，稍後再說
            </Button>
            <Button onClick={() => handleConsent(true)}>啟用</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}

const llmToneClass = {
  muted: "text-muted-foreground",
  warn: "text-warn",
  destructive: "text-destructive",
} as const;

// sidecar-managed-process.md §5 的狀態對照表：結合 Rust 端狀態機事件
// （sidecarManaged）與既有的 API 輪詢結果（llmStatus）決定 badge 文字。
function llmBadgeInfo(
  managed: SidecarManagedStatus | null,
  status: LlmSidecarStatus | null,
  mismatch: boolean,
): { text: string; tone: keyof typeof llmToneClass } {
  const state = managed?.state ?? (status?.byok_configured ? "byok" : "disabled");

  if (state === "running" && status?.sidecar_reachable) {
    return mismatch ? { text: "錯誤（狀態不一致）", tone: "destructive" } : { text: "sidecar", tone: "muted" };
  }
  if (state === "external" && status?.sidecar_reachable) {
    return { text: "sidecar（外部）", tone: "muted" };
  }
  switch (state) {
    case "disabled":
      return { text: "未啟用", tone: "muted" };
    case "probing":
      return { text: "檢查中…", tone: "muted" };
    case "awaiting_login":
      return { text: "需要登入", tone: "warn" };
    case "starting":
      return { text: "啟動中…", tone: "muted" };
    case "byok":
      return { text: "BYOK", tone: "muted" };
    case "failed":
      return { text: "錯誤", tone: "destructive" };
    default:
      return { text: "未啟用", tone: "muted" };
  }
}

export default App;
