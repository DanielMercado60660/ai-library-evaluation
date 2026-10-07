export interface ScenarioStepDefinition {
  step_id: string;
  order: number;
  title: string;
  description: string;
  phase: string;
  expected_signal: string;
}

export interface ScenarioManifestEntry {
  id: string;
  nodeid_pattern: string;
  tier: number;
  expected_steps: number;
  policy_checks: number;
  tool_calls_total: number;
  taxonomy_hint: string;
  steps: ScenarioStepDefinition[];
}

export interface ScenarioCatalogResponse {
  manifest_version: string;
  suite: string;
  generated_at: string;
  scenarios: ScenarioManifestEntry[];
  scripts: Record<string, string[]>;
}

export interface BenchmarkSummary {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  completion: number;
  step_accuracy: number;
  policy_compliance: number;
  hallucinations: number;
  tool_calls_total: number;
  tool_calls_correct: number;
  tool_precision: number;
  completion_rate_percent: number;
  step_accuracy_percent: number;
  policy_compliance_percent: number;
  tool_precision_percent: number;
}

export interface ScenarioResult {
  scenario_id: string;
  nodeid: string;
  status: 'passed' | 'failed' | 'skipped';
  tier: number;
  duration_seconds: number;
  completion: number;
  step_accuracy: number;
  policy_compliance: number;
  hallucinations: number;
  tool_calls_total: number;
  tool_calls_correct: number;
  taxonomy: string;
  detail: string;
  tool_trace?: string[];
}

export interface ForensicAssertion {
  assertion_id: string;
  status: 'pass' | 'fail';
  severity: 'critical' | 'warning' | 'info';
  sql?: string;
  result?: { rows: Record<string, unknown>[] };
  evidence: string;
}

export interface TraceSummary {
  trace_id: string;
  run_id: string;
  total_events: number;
  event_type_counts: Record<string, number>;
  first_event_at: string;
  last_event_at: string;
  trace_file: string;
}

export interface BenchmarkReport {
  schema_version: string;
  suite: string;
  run_mode?: 'pytest' | 'eval' | 'benchmark';
  generated_at: string;
  pytest_exit_code?: number;
  manifest_path?: string;
  summary: BenchmarkSummary;
  taxonomy_counts?: Record<string, number>;
  scenarios: ScenarioResult[];
  forensic_assertions: ForensicAssertion[];
  trace_summary?: TraceSummary;
  eval_details?: Record<string, EvalScenarioDetail>;
  benchmark_details?: BenchmarkDetails;
  adk_summary?: {
    total: number;
    completion: number;
    step_accuracy: number;
    policy_compliance: number;
    hallucinations: number;
    tool_calls_total: number;
    tool_calls_correct: number;
    results: ScenarioResult[];
  };
}

// --- Eval-specific detail models ---

export interface EvalStepAssertion {
  type: string;
  passed: boolean;
  details: string;
}

export interface EvalStepDetail {
  step_id: string;
  order: number;
  patron_message: string;
  agent_response: string;
  tool_calls_observed: string[];
  passed: boolean;
  duration_ms: number;
  error: string | null;
  assertions: EvalStepAssertion[];
}

export interface EvalScenarioDetail {
  scenario_id: string;
  passed: boolean;
  total_assertions: number;
  passed_assertions: number;
  duration_ms: number;
  steps: EvalStepDetail[];
}

export interface TraceItem {
  type: 'tool' | 'state' | 'assertion' | 'network';
  label: string;
  status: 'pass' | 'danger' | 'warning' | 'info' | 'success';
  time: string;
  details: string;
}

// --- V1.5 Run Control Plane Models ---

export type RunStatus = 'queued' | 'running' | 'passed' | 'failed';

export interface RunMetadata {
  run_id: string;
  suite: string;
  status: RunStatus;
  run_mode?: 'pytest' | 'eval' | 'benchmark';
  model_name: string;
  model_family: string;
  started_at: string;
  completed_at: string | null;
  artifact_dir: string;
  report_path: string | null;
  trace_path: string | null;
  artifact_paths: string[];
  error_message: string | null;
  scenario_ids?: string[];
  trigger_source?: string;
  actor_patron_id?: string | null;
}

export interface RunCreateRequest {
  suite: string;
  run_mode?: 'pytest' | 'eval' | 'benchmark';
  include_adk?: boolean;
  no_forensic?: boolean;
  chaos_profile?: string;
  model_name?: string;
  scenario_ids?: string[];
  trigger_source?: string;
  actor_patron_id?: string | null;
  benchmark_config?: BenchmarkConfigRequest;
}

export interface RunCreateResponse {
  run_id: string;
  status: RunStatus;
  run_mode?: 'pytest' | 'eval' | 'benchmark';
  artifact_dir: string;
  model_name: string;
  model_family: string;
  scenario_ids?: string[];
  trigger_source?: string;
  actor_patron_id?: string | null;
}

export interface RunListResponse {
  runs: RunMetadata[];
  total: number;
}

export interface TraceEvent {
  trace_id: string;
  run_id: string;
  scenario_id: string | null;
  event_type: string;
  source: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface BenchmarkModelOption {
  model_name: string;
  model_family: string;
  is_default: boolean;
}

export interface ModelCatalogResponse {
  default_model: string;
  models: BenchmarkModelOption[];
}

export interface RunComparisonRequest {
  run_ids: string[];
  suite?: string;
}

export interface RunScoreSnapshot {
  run_id: string;
  suite: string;
  status: RunStatus;
  model_name: string;
  model_family: string;
  total_scenarios: number;
  completion_rate_percent: number;
  policy_compliance_percent: number;
  tool_precision_percent: number;
  hallucinations: number;
  composite_score: number;
}

export interface RunMetricDelta {
  run_id: string;
  baseline_run_id: string;
  composite_score_delta: number;
  completion_rate_delta: number;
  policy_compliance_delta: number;
  tool_precision_delta: number;
  hallucinations_delta: number;
}

export interface TierDelta {
  run_id: string;
  baseline_run_id: string;
  tier: number;
  completion_rate_delta: number;
  policy_compliance_delta: number;
  tool_precision_delta: number;
  hallucinations_delta: number;
}

export interface ScenarioDelta {
  run_id: string;
  baseline_run_id: string;
  scenario_id: string;
  completion_delta: number;
  policy_compliance_delta: number;
  tool_precision_delta: number;
  hallucinations_delta: number;
}

export interface RunComparisonResponse {
  baseline_run_id: string;
  ranked_run_ids: string[];
  runs: RunScoreSnapshot[];
  run_deltas: RunMetricDelta[];
  tier_deltas: TierDelta[];
  scenario_deltas: ScenarioDelta[];
}

export interface LeaderboardRow {
  rank: number;
  model_name: string;
  model_family: string;
  run_count: number;
  avg_composite_score: number;
  avg_completion_rate: number;
  avg_policy_compliance: number;
  avg_tool_precision: number;
  avg_hallucinations: number;
}

export interface LeaderboardResponse {
  suite?: string;
  min_runs: number;
  total_models: number;
  rows: LeaderboardRow[];
}

// --- v2.4 Benchmark Config & Detail Models ---

export interface BenchmarkDomainWeights {
  catalog: number;
  circulation: number;
  ill: number;
}

export interface BenchmarkComplexityDistribution {
  simple: number;
  medium: number;
  complex: number;
}

export interface BenchmarkConfigRequest {
  patron_pool?: string[];
  patron_category_filter?: string[];
  interaction_count?: number;
  time_budget_seconds?: number;
  domain_weights?: BenchmarkDomainWeights;
  complexity_distribution?: BenchmarkComplexityDistribution;
  seed_before_run?: boolean;
  stateful_sequences?: boolean;
  random_seed?: number;
}

export interface BenchmarkInteractionDetail {
  interaction_id: string;
  sequence_id: string | null;
  patron_id: string;
  interaction_type: string;
  expected_domain: string;
  complexity_tier: string;
  message_sent: string;
  agent_response: string;
  tool_engaged: boolean;
  tool_calls_observed: string[];
  coherence_score: number;
  hallucination_detected: boolean;
  appropriate_refusal: boolean;
  is_edge_case: boolean;
  duration_ms: number;
  error: string | null;
  status: string;
}

export interface BenchmarkDetails {
  config: BenchmarkConfigRequest;
  total_interactions: number;
  completed: number;
  errored: number;
  timed_out: number;
  avg_response_time_ms: number;
  tool_engagement_rate: number;
  error_rate: number;
  domain_breakdown: Record<string, { total: number; completed: number; errored: number }>;
  wall_clock_seconds: number;
  interactions: BenchmarkInteractionDetail[];
}
