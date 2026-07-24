import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Button } from "@/components/ui/button";
import type { LlmSidecarStatus, SidecarManagedStatus } from "@/lib/api";

interface LlmStatusPopoverProps {
  managedStatus: SidecarManagedStatus | null;
  llmStatus: LlmSidecarStatus | null;
  mismatch: boolean;
  onEnable: () => void;
}

export function LlmStatusPopover({ managedStatus, llmStatus, mismatch, onEnable }: LlmStatusPopoverProps) {
  const [busy, setBusy] = useState(false);

  async function openLogin(cli: "claude" | "codex") {
    setBusy(true);
    try {
      await invoke("sidecar_open_login", { cli });
    } finally {
      setBusy(false);
    }
  }

  async function restart() {
    setBusy(true);
    try {
      await invoke("sidecar_restart");
    } finally {
      setBusy(false);
    }
  }

  const state = managedStatus?.state ?? (llmStatus?.byok_configured ? "byok" : "disabled");

  return (
    <div className="space-y-2">
      <span className="type-label">LLM enrichment</span>

      {state === "disabled" && (
        <div className="space-y-2">
          <p className="type-caption text-muted-foreground">
            啟用 LLM 增強功能？Salva 會在背景啟動一個本機行程，呼叫你已登入的 claude/codex CLI
            來做實體解析與摘要。
          </p>
          <Button size="sm" onClick={onEnable}>
            啟用
          </Button>
        </div>
      )}

      {state === "probing" && (
        <p className="type-caption text-muted-foreground">正在檢查本機 claude/codex CLI…</p>
      )}

      {state === "starting" && (
        <p className="type-caption text-muted-foreground">sidecar 啟動中…</p>
      )}

      {state === "awaiting_login" && (
        <div className="space-y-2">
          <p className="type-caption text-warn">需要先登入 claude 或 codex CLI 才能啟動 sidecar。</p>
          <p className="type-caption text-muted-foreground">
            點下方按鈕會另外開一個終端機視窗完成登入，登入完成後這裡會自動偵測並繼續。
          </p>
          <div className="flex gap-1.5">
            <Button size="sm" variant="outline" disabled={busy} onClick={() => openLogin("claude")}>
              用 Claude 登入
            </Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => openLogin("codex")}>
              用 Codex 登入
            </Button>
          </div>
        </div>
      )}

      {state === "running" && mismatch && (
        <div className="space-y-2">
          <p className="type-caption text-destructive">
            Rust 端顯示 sidecar 已啟動，但 API 輪詢連不到它——狀態不一致，可能已卡住。
          </p>
          <Button size="sm" variant="outline" disabled={busy} onClick={restart}>
            重試
          </Button>
        </div>
      )}
      {state === "running" && !mismatch && (
        <p className="type-caption text-success">sidecar 已連線，enrichment 正常運作。</p>
      )}

      {state === "external" && (
        <div className="space-y-1">
          <p className="type-caption text-muted-foreground">
            偵測到一個外部（手動啟動的）sidecar 正在使用——app 不會管理它的生命週期。
          </p>
          <p className="text-xs-minus font-mono text-muted-foreground/70">
            python -m salva_core.llm_sidecar_run
          </p>
        </div>
      )}

      {state === "byok" && (
        <p className="type-caption text-muted-foreground">使用 BYOK 端點，不需要本機 sidecar。</p>
      )}

      {state === "failed" && (
        <div className="space-y-2">
          <p className="type-caption text-destructive">
            {managedStatus?.detail || "sidecar 發生錯誤"}
          </p>
          <Button size="sm" variant="outline" disabled={busy} onClick={restart}>
            重試
          </Button>
        </div>
      )}
    </div>
  );
}
