// 直接呼叫本機 Python core（apps/api/main.py，Rust 側在 app 啟動時 spawn 為
// 子進程）。開發模式下 SALVA_API_KEY 未設定，auth 是關閉的，先不處理金鑰。
const API_BASE = "http://127.0.0.1:8765";

// 桌面端目前只有單一 campaign，先固定值讓 memory 迴路（campaign_promoted 讀取 /
// quarantine 寫入）有 campaign_id 可用；之後有多 campaign 需求時再改成可選。
export const CAMPAIGN_ID = "desktop-default";

export interface EvidenceItem {
  source_url: string;
  source_name?: string | null;
  title?: string | null;
  snippet?: string | null;
}

export interface CanonicalEntity {
  entity_id: string;
  entity_type: string;
  title: string;
  summary?: string | null;
  confidence: number;
  score: number;
  tags: string[];
  source_urls: string[];
  evidence?: EvidenceItem[];
}

export interface DiscoverMeta {
  run_id?: string | null;
  domain?: string;
  qualified_count?: number;
  raw_count?: number;
  rounds?: number;
  providers_exhausted?: boolean;
  entities_merged_count?: number;
  memory_seeds_used?: number;
  [key: string]: unknown;
}

export interface RunRecord {
  run_id: string;
  objective: string;
  output_profile: string;
  created_at: string;
  request: Record<string, unknown>;
  meta: Record<string, unknown>;
  project_id?: string | null;
  campaign_id?: string | null;
  continuation_id?: string | null;
  entity_count: number;
  relation_count: number;
}

export interface RunsResponse {
  items: RunRecord[];
  total: number;
}

export interface EvidenceChainLink {
  evidence_id: string;
  source_url: string;
  source_name?: string | null;
  title?: string | null;
  snippet?: string | null;
  captured_at?: string | null;
  relation_ids: string[];
  hyperedge_ids: string[];
  metadata: Record<string, unknown>;
}

export interface EvidenceChainRecord {
  entity_id: string;
  entity_title?: string | null;
  run_id?: string | null;
  evidence_ids: string[];
  relation_ids: string[];
  hyperedge_ids: string[];
  links: EvidenceChainLink[];
  first_captured_at?: string | null;
  last_captured_at?: string | null;
  evidence_count: number;
  relation_count: number;
  hyperedge_count: number;
  notes: string[];
}

export interface HoldHyperedgeMember {
  member_id: string;
  member_kind: string;
  role: string;
  weight: number;
  evidence_ids: string[];
}

export interface HoldHyperedgeRecord {
  hyperedge_id: string;
  run_id: string;
  hyperedge_type: string;
  summary?: string | null;
  confidence: number;
  members: HoldHyperedgeMember[];
  evidence_ids: string[];
  source_ids: string[];
  properties: Record<string, unknown>;
  created_at?: string | null;
}

export type MemoryStatus = "legacy" | "quarantine" | "promoted";

export interface QueryFamilyMemoryRecord {
  memory_id: string;
  run_id: string;
  campaign_id?: string | null;
  continuation_id?: string | null;
  memory_status: MemoryStatus;
  promoted_at?: string | null;
  domain?: string | null;
  objective: string;
  output_profile: string;
  round_num: number;
  strategy: string;
  query: string;
  query_signature: string;
  source_nodes: string[];
  content_nodes: string[];
  content_weights: Record<string, number>;
  source_hints: string[];
  notes: string[];
  raw_total: number;
  qualified_total: number;
  avg_score: number;
  success_score: number;
  created_at?: string | null;
}

export interface QueryFamilyMemoryResponse {
  items: QueryFamilyMemoryRecord[];
  total: number;
}

export interface RunSnapshot {
  run_id: string;
  objective: string;
  output_profile: string;
  created_at?: string | null;
  generated_at: string;
  request: Record<string, unknown>;
  meta: Record<string, unknown>;
  entities: CanonicalEntity[];
  relations: unknown[];
  evidence_records: unknown[];
  evidence_chains: EvidenceChainRecord[];
  hyperedges: HoldHyperedgeRecord[];
  query_family_memory: QueryFamilyMemoryRecord[];
  telemetry: unknown[];
  source_attempts: unknown[];
  plugin_reports: unknown[];
  audit: unknown | null;
  entity_count: number;
  relation_count: number;
  evidence_count: number;
  evidence_chain_count: number;
  hyperedge_count: number;
  query_family_count: number;
  telemetry_count: number;
  source_attempt_count: number;
  plugin_report_count: number;
}

export interface SemanticQueryFamilyHit {
  score: number;
  vector_id: string;
  query_family: QueryFamilyMemoryRecord;
  matched_text?: string | null;
  backend_used: string;
}

export interface SemanticQueryFamilySearchResponse {
  query: string;
  objective?: string | null;
  strategy?: string | null;
  dimensions: number;
  total: number;
  items: SemanticQueryFamilyHit[];
}

export interface DiscoverResponse {
  entities: CanonicalEntity[];
  relations: unknown[];
  telemetry: unknown[];
  meta: DiscoverMeta;
}

export interface DiscoverParams {
  market: string;
  industry: string;
  objective?: string;
  product?: string;
  role?: string;
  maxResults?: number;
}

export interface LlmSidecarStatus {
  sidecar_reachable: boolean;
  byok_configured: boolean;
}

// fetch() 本身在連線層失敗時(core離線/尚未啟動)拋出的是瀏覽器原生
// TypeError("Failed to fetch")，對使用者來說是一句沒有意義的英文技術訊息。
// 統一在這裡轉成看得懂、能行動的中文說明，而不是讓 caller 各自處理一次。
async function fetchCore(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error("無法連線到 salva core——請確認 core 已啟動（看畫面上方的連線燈號）");
  }
}

export async function discover(params: DiscoverParams): Promise<DiscoverResponse> {
  const response = await fetchCore("/v1/discover", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      objective: params.objective || "find_companies",
      output_profile: "company_profile",
      max_results: params.maxResults ?? 10,
      execution: {
        persistence: "audit",
        campaign_id: CAMPAIGN_ID,
        memory: { read_scope: "campaign_promoted", write_mode: "quarantine" },
      },
      intent: {
        market: params.market,
        industry: params.industry,
        product: params.product || undefined,
        role: params.role || undefined,
      },
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`discover 失敗（${response.status}）：${detail}`);
  }
  return response.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

export async function checkLlmStatus(): Promise<LlmSidecarStatus | null> {
  try {
    const response = await fetch(`${API_BASE}/v1/llm/sidecar-status`);
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function listRuns(limit = 20, offset = 0): Promise<RunsResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await fetchCore(`/v1/runs?${params}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`listRuns 失敗（${response.status}）：${detail}`);
  }
  return response.json();
}

export async function getRunSnapshot(runId: string): Promise<RunSnapshot> {
  const response = await fetchCore(`/v1/snapshots/${runId}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`getRunSnapshot 失敗（${response.status}）：${detail}`);
  }
  return response.json();
}

export interface QueryFamilyFilters {
  campaignId?: string;
  memoryStatus?: string;
  limit?: number;
}

export async function listQueryFamilies(
  filters: QueryFamilyFilters = {},
): Promise<QueryFamilyMemoryResponse> {
  const params = new URLSearchParams();
  if (filters.campaignId) params.set("campaign_id", filters.campaignId);
  if (filters.memoryStatus) params.set("memory_status", filters.memoryStatus);
  if (filters.limit != null) params.set("limit", String(filters.limit));
  const response = await fetchCore(`/v1/query-families?${params}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`listQueryFamilies 失敗（${response.status}）：${detail}`);
  }
  return response.json();
}

export async function promoteQueryFamily(
  memoryId: string,
  campaignId: string,
): Promise<QueryFamilyMemoryRecord> {
  const params = new URLSearchParams({ campaign_id: campaignId });
  const response = await fetchCore(`/v1/query-families/${memoryId}/promote?${params}`, {
    method: "POST",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`promoteQueryFamily 失敗（${response.status}）：${detail}`);
  }
  return response.json();
}

export async function searchQueryFamilies(
  query: string,
  limit = 5,
): Promise<SemanticQueryFamilySearchResponse> {
  const params = new URLSearchParams({ query, limit: String(limit) });
  const response = await fetchCore(`/v1/semantic/query-families?${params}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`searchQueryFamilies 失敗（${response.status}）：${detail}`);
  }
  return response.json();
}
