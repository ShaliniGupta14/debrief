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

export interface EvalResultOut {
  id: string;
  eval_definition_id: string;
  score: string;
  passed: boolean | null;
  judge_rationale: string | null;
  created_at: string;
}

export interface CallDetail {
  id: string;
  project_id: string;
  trace_id: string | null;
  client_call_id: string | null;
  model: string;
  prompt: string;
  response: string;
  prompt_version: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: string | null;
  latency_ms: number;
  status: "ok" | "error";
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  eval_results: EvalResultOut[];
}

export interface EvalDefinitionOut {
  id: string;
  name: string;
  type: string;
  config: Record<string, unknown>;
  enabled: boolean;
  calibration_report: Record<string, unknown> | null;
  created_at: string;
}

export interface EvalDefinitionListResponse {
  items: EvalDefinitionOut[];
}

export interface EvalComparison {
  eval_definition_id: string;
  eval_name: string;
  mean_score_a: number | null;
  mean_score_b: number | null;
  delta: number | null;
  ci_low: number | null;
  ci_high: number | null;
  n_calls_a: number;
  n_calls_b: number;
  regressed: boolean;
}

export interface WorstRegressionOut {
  eval_definition_id: string;
  eval_name: string;
  prompt: string;
  mean_score_a: number;
  mean_score_b: number;
  delta: number;
  n_calls_a: number;
  n_calls_b: number;
}

export interface CompareResponse {
  version_a: string;
  version_b: string;
  evals: EvalComparison[];
  worst_regressions: WorstRegressionOut[];
  any_regression: boolean;
}
