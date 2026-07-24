import { useEffect, useState } from "react";
import { Brain, Search as SearchIcon, X } from "lucide-react";
import { Badge, pillTintClass } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/EmptyState";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import {
  CAMPAIGN_ID,
  listQueryFamilies,
  promoteQueryFamily,
  searchQueryFamilies,
  type MemoryStatus,
  type QueryFamilyMemoryRecord,
} from "@/lib/api";

const FILTERS: { value: MemoryStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "quarantine", label: "Quarantine" },
  { value: "promoted", label: "Promoted" },
  { value: "legacy", label: "Legacy" },
];

// Badge 元件沒有 warn/success variant，借用 pillTintClass（badge.tsx 的
// accent-tint recipe）疊在 outline 底色上，twMerge 會用同一 group 的後者覆蓋前者。
function statusBadgeClassName(status: MemoryStatus) {
  if (status === "quarantine") return pillTintClass.warn;
  if (status === "promoted") return pillTintClass.success;
  return undefined; // legacy 用 Badge 預設的 secondary 灰階即可
}

export function MemoryView() {
  const [filter, setFilter] = useState<MemoryStatus | "all">("all");
  const [records, setRecords] = useState<QueryFamilyMemoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [promotingIds, setPromotingIds] = useState<Set<string>>(new Set());

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<
    { record: QueryFamilyMemoryRecord; score: number }[] | null
  >(null);
  const [searching, setSearching] = useState(false);

  const inSearchMode = searchResults !== null;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listQueryFamilies({
      campaignId: CAMPAIGN_ID,
      memoryStatus: filter === "all" ? undefined : filter,
      limit: 100,
    })
      .then((res) => {
        if (!cancelled) setRecords(res.items);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filter]);

  function selectFilter(value: MemoryStatus | "all") {
    setFilter(value);
    setSearchResults(null);
    setSearchQuery("");
  }

  async function handleSearchSubmit() {
    const query = searchQuery.trim();
    if (!query) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const res = await searchQueryFamilies(query, 10);
      setSearchResults(
        res.items.map((hit) => ({ record: hit.query_family, score: hit.score })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSearching(false);
    }
  }

  function clearSearch() {
    setSearchQuery("");
    setSearchResults(null);
  }

  function applyPromoted(memoryId: string, updated: QueryFamilyMemoryRecord) {
    setRecords((prev) => prev.map((r) => (r.memory_id === memoryId ? updated : r)));
    setSearchResults((prev) =>
      prev ? prev.map((h) => (h.record.memory_id === memoryId ? { ...h, record: updated } : h)) : prev,
    );
  }

  async function handlePromote(memoryId: string) {
    setPromotingIds((prev) => new Set(prev).add(memoryId));
    setError(null);
    try {
      const updated = await promoteQueryFamily(memoryId, CAMPAIGN_ID);
      applyPromoted(memoryId, updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPromotingIds((prev) => {
        const next = new Set(prev);
        next.delete(memoryId);
        return next;
      });
    }
  }

  const items = inSearchMode ? searchResults! : records.map((record) => ({ record, score: undefined as number | undefined }));
  const busy = inSearchMode ? searching : loading;

  return (
    <div className="flex-1 flex flex-col gap-4 p-4 max-w-3xl w-full mx-auto">
      <section className="glass-1 border border-border/30 rounded-lg p-3 space-y-3 overflow-hidden">
        <div className="flex gap-1.5 flex-wrap">
          {FILTERS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => selectFilter(opt.value)}
              className={cn(
                "rounded-full px-2.5 py-1 text-xs-minus border transition-colors",
                !inSearchMode && filter === opt.value
                  ? "border-primary bg-primary/30 text-primary"
                  : "border-border/40 text-muted-foreground hover:bg-secondary/60",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearchSubmit();
            }}
            placeholder="語意搜尋 query family…"
            className="flex-1"
          />
          {inSearchMode && (
            <Button variant="outline" size="sm" onClick={clearSearch}>
              <X size={12} className="mr-1" />
              清除
            </Button>
          )}
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-destructive bg-destructive/10 text-destructive text-sm px-3 py-2">
          {error}
        </div>
      )}

      <ScrollArea className="flex-1 min-h-0">
        {items.length === 0 && !busy ? (
          <EmptyState
            icon={inSearchMode ? SearchIcon : Brain}
            label={inSearchMode ? "沒有符合的搜尋結果" : "沒有符合篩選條件的記錄"}
          />
        ) : (
          <ul className="space-y-2">
            {items.map(({ record, score }) => (
              <li
                key={record.memory_id}
                className="glass-1 border border-border/30 rounded-lg p-3 space-y-1 overflow-hidden"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="type-body font-mono truncate">{record.query}</span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {score != null && <Badge variant="outline">{score.toFixed(2)}</Badge>}
                    <Badge
                      variant={record.memory_status === "legacy" ? "secondary" : "outline"}
                      className={statusBadgeClassName(record.memory_status)}
                    >
                      {record.memory_status}
                    </Badge>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap type-caption text-muted-foreground">
                  <span>{record.strategy}</span>
                  <span>·</span>
                  <span>
                    {record.qualified_total} / {record.raw_total} qualified
                  </span>
                  <span>·</span>
                  <span>success {record.success_score.toFixed(2)}</span>
                  {record.domain && (
                    <>
                      <span>·</span>
                      <span>{record.domain}</span>
                    </>
                  )}
                  {record.created_at && (
                    <>
                      <span>·</span>
                      <span>{new Date(record.created_at).toLocaleString()}</span>
                    </>
                  )}
                </div>
                {record.memory_status === "quarantine" && (
                  <Button
                    size="sm"
                    variant="soft"
                    disabled={promotingIds.has(record.memory_id)}
                    onClick={() => handlePromote(record.memory_id)}
                  >
                    {promotingIds.has(record.memory_id) ? "Promoting…" : "Promote"}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </ScrollArea>
    </div>
  );
}
