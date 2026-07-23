// 直接呼叫本機 Python core（apps/api/main.py，Rust 側在 app 啟動時 spawn 為
// sidecar）。開發模式下 SALVA_API_KEY 未設定，auth 是關閉的，先不處理金鑰。
const API_BASE = "http://127.0.0.1:8765";

export interface CanonicalEntity {
  entity_id: string;
  entity_type: string;
  title: string;
  summary?: string | null;
  confidence: number;
  score: number;
  tags: string[];
  source_urls: string[];
}

export interface DiscoverMeta {
  run_id?: string | null;
  domain?: string;
  qualified_count?: number;
  raw_count?: number;
  rounds?: number;
  providers_exhausted?: boolean;
  entities_merged_count?: number;
  [key: string]: unknown;
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

export async function discover(params: DiscoverParams): Promise<DiscoverResponse> {
  const response = await fetch(`${API_BASE}/v1/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      objective: params.objective || "find_companies",
      output_profile: "company_profile",
      max_results: params.maxResults ?? 10,
      execution: { persistence: "audit" },
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
