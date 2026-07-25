import { useEffect, useState } from "react";
import { FolderKanban, Pencil, Check, X, Archive, ArchiveRestore, Trash2, Eraser } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { SuccessBanner } from "@/components/ui/SuccessBanner";
import { LoadingState } from "@/components/ui/LoadingState";
import { ChipToggle } from "@/components/ui/ChipToggle";
import { RetentionPicker } from "@/components/ui/RetentionPicker";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  listCampaigns,
  createCampaign,
  updateCampaign,
  archiveCampaign,
  unarchiveCampaign,
  clearCampaignCache,
  deleteCampaign,
  type CampaignRecord,
} from "@/lib/api";
import { readDefaultRetention } from "@/views/SettingsView";

interface CampaignsViewProps {
  activeCampaignId: string | null;
  onChanged: () => void;
}

function purgeCountdown(campaign: CampaignRecord): string | null {
  if (campaign.status !== "archived") return null;
  if (!campaign.purge_at) return "無限期（僅封存）";
  const days = Math.ceil((new Date(campaign.purge_at).getTime() - Date.now()) / (24 * 60 * 60 * 1000));
  if (days <= 0) return "即將於下次開啟 app 時清除";
  return `清除於 ${days} 天後（下次開啟 app 時執行，非精確整點）`;
}

export function CampaignsView({ activeCampaignId, onChanged }: CampaignsViewProps) {
  const [campaigns, setCampaigns] = useState<CampaignRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const [archiveTarget, setArchiveTarget] = useState<CampaignRecord | null>(null);
  const [archiveRetention, setArchiveRetention] = useState<number | null>(30);

  const [clearTarget, setClearTarget] = useState<CampaignRecord | null>(null);
  const [clearing, setClearing] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<CampaignRecord | null>(null);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");
  const [deleting, setDeleting] = useState(false);

  const [receipt, setReceipt] = useState<{ label: string; counts: Record<string, number> } | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const res = await listCampaigns(undefined, 200);
      setCampaigns(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function afterMutation() {
    await refresh();
    onChanged();
  }

  async function handleCreate() {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      await createCampaign(name, newDescription.trim() || undefined);
      setNewName("");
      setNewDescription("");
      await afterMutation();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  function startRename(campaign: CampaignRecord) {
    setRenamingId(campaign.campaign_id);
    setRenameValue(campaign.name);
  }

  async function commitRename(campaignId: string) {
    const name = renameValue.trim();
    setRenamingId(null);
    if (!name) return;
    setError(null);
    try {
      await updateCampaign(campaignId, { name });
      await afterMutation();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function openArchiveDialog(campaign: CampaignRecord) {
    setArchiveTarget(campaign);
    setArchiveRetention(
      campaign.status === "archived" ? (campaign.retention_days ?? null) : readDefaultRetention(),
    );
  }

  async function confirmArchive() {
    if (!archiveTarget) return;
    setError(null);
    try {
      await archiveCampaign(archiveTarget.campaign_id, archiveRetention);
      setArchiveTarget(null);
      await afterMutation();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleUnarchive(campaign: CampaignRecord) {
    setError(null);
    try {
      await unarchiveCampaign(campaign.campaign_id);
      await afterMutation();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function confirmClearCache() {
    if (!clearTarget) return;
    setClearing(true);
    setError(null);
    try {
      const res = await clearCampaignCache(clearTarget.campaign_id);
      setReceipt({ label: `已清除「${clearTarget.name}」的快取`, counts: res.cleared });
      setClearTarget(null);
      await afterMutation();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setClearing(false);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    setError(null);
    try {
      const res = await deleteCampaign(deleteTarget.campaign_id, deleteConfirmName);
      setReceipt({ label: `已刪除「${deleteTarget.name}」`, counts: res.deleted });
      setDeleteTarget(null);
      setDeleteConfirmName("");
      await afterMutation();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleting(false);
    }
  }

  const visible = campaigns.filter((c) => c.status === (showArchived ? "archived" : "active"));

  return (
    <div className="flex-1 flex flex-col gap-4 p-4 max-w-4xl w-full mx-auto">
      <section className="glass-1 border border-border/30 rounded-lg p-3 space-y-2 overflow-hidden">
        <span className="type-label text-muted-foreground">建立 campaign</span>
        <div className="flex gap-2">
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="名稱"
            className="flex-1"
          />
          <Input
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            placeholder="描述（選填）"
            className="flex-1"
          />
          <Button size="sm" disabled={creating || !newName.trim()} onClick={handleCreate}>
            建立
          </Button>
        </div>
      </section>

      {error && <ErrorBanner message={error} />}

      {receipt && (
        <SuccessBanner onDismiss={() => setReceipt(null)}>
          {receipt.label}：
          {Object.entries(receipt.counts)
            .map(([table, n]) => `${table} ${n}`)
            .join("、")}
        </SuccessBanner>
      )}

      <div className="flex gap-1.5">
        <ChipToggle selected={!showArchived} onClick={() => setShowArchived(false)}>
          進行中
        </ChipToggle>
        <ChipToggle selected={showArchived} onClick={() => setShowArchived(true)}>
          已封存
        </ChipToggle>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {loading && visible.length === 0 ? (
          <LoadingState />
        ) : visible.length === 0 ? (
          <EmptyState icon={FolderKanban} label={showArchived ? "沒有已封存的 campaign" : "還沒有 campaign"} />
        ) : (
          <ul className="space-y-2">
            {visible.map((campaign) => {
              const countdown = purgeCountdown(campaign);
              return (
                <li
                  key={campaign.campaign_id}
                  className="glass-1 border border-border/30 rounded-lg p-3 space-y-1.5 overflow-hidden"
                >
                  <div className="flex items-center justify-between gap-2">
                    {renamingId === campaign.campaign_id ? (
                      <div className="flex items-center gap-1.5 flex-1">
                        <Input
                          autoFocus
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") commitRename(campaign.campaign_id);
                            if (e.key === "Escape") setRenamingId(null);
                          }}
                          className="flex-1"
                        />
                        <Button size="icon-sm" variant="ghost" onClick={() => commitRename(campaign.campaign_id)}>
                          <Check size={12} />
                        </Button>
                        <Button size="icon-sm" variant="ghost" onClick={() => setRenamingId(null)}>
                          <X size={12} />
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5 flex-1 min-w-0">
                        <span className="type-body font-medium truncate">{campaign.name}</span>
                        {campaign.campaign_id === activeCampaignId && (
                          <Badge variant="active">使用中</Badge>
                        )}
                        <button
                          type="button"
                          onClick={() => startRename(campaign)}
                          className="text-muted-foreground hover:text-foreground shrink-0"
                        >
                          <Pencil size={11} />
                        </button>
                      </div>
                    )}
                    <Badge variant={campaign.status === "archived" ? "secondary" : "outline"}>
                      {campaign.status === "archived" ? "已封存" : "進行中"}
                    </Badge>
                  </div>

                  {campaign.description && (
                    <p className="type-caption text-muted-foreground">{campaign.description}</p>
                  )}

                  <div className="flex items-center gap-2 flex-wrap type-caption text-muted-foreground">
                    <span>{campaign.run_count} 個 run</span>
                    <span>·</span>
                    <span>{campaign.memory_promoted_count} 筆 promoted</span>
                    <span>·</span>
                    <span>{campaign.memory_quarantine_count} 筆 quarantine</span>
                    <span>·</span>
                    <span>建立於 {new Date(campaign.created_at).toLocaleDateString()}</span>
                    <span>·</span>
                    <span>
                      {campaign.cache_cleared_at
                        ? `快取已於 ${new Date(campaign.cache_cleared_at).toLocaleDateString()} 清除過`
                        : "從未清除快取"}
                    </span>
                    {countdown && (
                      <>
                        <span>·</span>
                        <span className="text-warn">{countdown}</span>
                      </>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 pt-1">
                    {campaign.status === "active" ? (
                      <Button size="sm" variant="outline" onClick={() => openArchiveDialog(campaign)}>
                        <Archive size={12} className="mr-1" />
                        封存
                      </Button>
                    ) : (
                      <>
                        <Button size="sm" variant="outline" onClick={() => openArchiveDialog(campaign)}>
                          <Archive size={12} className="mr-1" />
                          變更清除時限
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => handleUnarchive(campaign)}>
                          <ArchiveRestore size={12} className="mr-1" />
                          取消封存
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => {
                            setDeleteTarget(campaign);
                            setDeleteConfirmName("");
                          }}
                        >
                          <Trash2 size={12} className="mr-1" />
                          刪除
                        </Button>
                      </>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => setClearTarget(campaign)}>
                      <Eraser size={12} className="mr-1" />
                      清除快取
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </ScrollArea>

      <Dialog open={!!archiveTarget} onOpenChange={(open) => !open && setArchiveTarget(null)}>
        <DialogContent>
          <DialogTitle>封存「{archiveTarget?.name}」</DialogTitle>
          <DialogDescription>
            封存後，campaign 進入唯讀狀態，之後可設定自動清除時限，或選擇無限期僅封存。
          </DialogDescription>
          <RetentionPicker
            value={archiveRetention}
            onChange={setArchiveRetention}
            presetLabel={(days) => `${days} 天後清除`}
            indefiniteLabel="無限期（僅封存）"
            hint="清除時限是機會性檢查（下次開啟 app 時才會實際執行），不是精確整點刪除。"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setArchiveTarget(null)}>
              取消
            </Button>
            <Button onClick={confirmArchive}>確認封存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!clearTarget} onOpenChange={(open) => !open && setClearTarget(null)}>
        <DialogContent>
          <DialogTitle>清除「{clearTarget?.name}」的快取</DialogTitle>
          <DialogDescription>
            這個動作只清掉可再生的原始資料，不會動到已萃取出的重點內容。
          </DialogDescription>
          <div className="space-y-2 type-caption">
            <div>
              <span className="text-destructive font-medium">會清除：</span>
              <span className="text-muted-foreground">
                原始搜尋片段/標題文字、embedding 向量、per-run 診斷紀錄（可視需要重新產生）。
              </span>
            </div>
            <div>
              <span className="text-success font-medium">會保留：</span>
              <span className="text-muted-foreground">
                query family 記憶（quarantine + promoted）、已萃取的實體/關係/hyperedge——這些是複利內容本身，不會被清掉。
              </span>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClearTarget(null)}>
              取消
            </Button>
            <Button disabled={clearing} onClick={confirmClearCache}>
              {clearing ? "清除中…" : "確認清除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setDeleteConfirmName("");
          }
        }}
      >
        <DialogContent>
          <DialogTitle>刪除「{deleteTarget?.name}」</DialogTitle>
          <DialogDescription>
            這會永久刪除這個 campaign 及其所有 run、實體、關係、hyperedge、query family 記憶。此動作無法復原。
            請輸入完整的 campaign 名稱以確認。
          </DialogDescription>
          <Input
            value={deleteConfirmName}
            onChange={(e) => setDeleteConfirmName(e.target.value)}
            placeholder={deleteTarget?.name}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={
                deleting ||
                deleteConfirmName.trim().toLowerCase() !== (deleteTarget?.name.trim().toLowerCase() ?? "")
              }
              onClick={confirmDelete}
            >
              {deleting ? "刪除中…" : "永久刪除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
