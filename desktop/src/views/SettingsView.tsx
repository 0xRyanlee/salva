import { useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { SuccessBanner } from "@/components/ui/SuccessBanner";
import { RetentionPicker } from "@/components/ui/RetentionPicker";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { listCampaigns, clearCampaignCache } from "@/lib/api";

const DEFAULT_RETENTION_KEY = "salva.defaultRetentionDays";

export function readDefaultRetention(): number | null {
  const raw = localStorage.getItem(DEFAULT_RETENTION_KEY);
  if (raw == null || raw === "indefinite") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function SettingsView() {
  const [defaultRetention, setDefaultRetention] = useState<number | null>(readDefaultRetention);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [bulkRunning, setBulkRunning] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);
  const [bulkReceipt, setBulkReceipt] = useState<{ campaigns: number; counts: Record<string, number> } | null>(
    null,
  );

  function persistRetention(value: number | null) {
    setDefaultRetention(value);
    localStorage.setItem(DEFAULT_RETENTION_KEY, value == null ? "indefinite" : String(value));
  }

  async function confirmBulkClearCache() {
    setBulkRunning(true);
    setBulkError(null);
    setBulkReceipt(null);
    try {
      const { items } = await listCampaigns("archived", 200);
      const aggregate: Record<string, number> = {};
      for (const campaign of items) {
        const res = await clearCampaignCache(campaign.campaign_id);
        for (const [table, n] of Object.entries(res.cleared)) {
          aggregate[table] = (aggregate[table] ?? 0) + n;
        }
      }
      setBulkReceipt({ campaigns: items.length, counts: aggregate });
      setBulkConfirmOpen(false);
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : String(err));
    } finally {
      setBulkRunning(false);
    }
  }

  return (
    <div className="flex-1 flex flex-col gap-4 p-4 max-w-2xl w-full mx-auto">
      <div className="flex items-center gap-2">
        <SettingsIcon size={16} className="text-primary" />
        <span className="type-title">設定</span>
      </div>

      <section className="glass-1 border border-border/30 rounded-lg p-3 space-y-2">
        <span className="type-label text-muted-foreground">預設封存清除時限</span>
        <p className="type-caption text-muted-foreground">
          之後封存 campaign 時，「封存」對話框的預設選項會套用這個值；每個 campaign 仍可個別調整。
        </p>
        <RetentionPicker value={defaultRetention} onChange={persistRetention} />
      </section>

      <section className="glass-1 border border-border/30 rounded-lg p-3 space-y-2">
        <span className="type-label text-muted-foreground">批次清除快取</span>
        <p className="type-caption text-muted-foreground">
          對所有已封存的 campaign 逐一執行清除快取，保留 query family 記憶與已萃取的實體/關係，只清可再生的原始資料。
        </p>
        <Button size="sm" variant="outline" disabled={bulkRunning} onClick={() => setBulkConfirmOpen(true)}>
          清除所有已封存 campaign 的快取
        </Button>
        {bulkError && <ErrorBanner message={bulkError} />}
        {bulkReceipt && (
          <SuccessBanner>
            已處理 {bulkReceipt.campaigns} 個已封存 campaign：
            {Object.entries(bulkReceipt.counts)
              .map(([table, n]) => `${table} ${n}`)
              .join("、") || "沒有可清除的資料"}
          </SuccessBanner>
        )}
      </section>

      <Dialog open={bulkConfirmOpen} onOpenChange={(open) => !bulkRunning && setBulkConfirmOpen(open)}>
        <DialogContent>
          <DialogTitle>清除所有已封存 campaign 的快取</DialogTitle>
          <DialogDescription>
            這會對每一個已封存的 campaign 執行清除快取，只清掉可再生的原始資料（原始搜尋片段/標題文字、embedding
            向量、per-run 診斷紀錄），不會動到已萃取出的實體/關係/hyperedge 與 query family 記憶。此動作會套用到所有已封存
            campaign，無法個別排除。
          </DialogDescription>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkConfirmOpen(false)}>
              取消
            </Button>
            <Button disabled={bulkRunning} onClick={confirmBulkClearCache}>
              {bulkRunning ? "清除中…" : "確認清除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
