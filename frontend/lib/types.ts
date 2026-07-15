export interface CallSummary {
  id: string;
  model: string;
  prompt_preview: string;
  prompt_version: string | null;
  status: "ok" | "error";
  error_message: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: string | null;
  latency_ms: number;
  trace_id: string | null;
  created_at: string;
}

export interface CallListResponse {
  items: CallSummary[];
  next_cursor: string | null;
}

export interface StatsBucket {
  bucket: string;
  group_key: string | null;
  volume: number;
  spend_usd: string;
  latency_p50_ms: number;
  latency_p95_ms: number;
  latency_p99_ms: number;
}

export interface StatsResponse {
  buckets: StatsBucket[];
}
