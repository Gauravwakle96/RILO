export type Json =
  string | number | boolean | null | Json[] | { [key: string]: Json };
export type JsonObject = { [key: string]: Json };
export type View =
  | "dashboard"
  | "benchmarks"
  | "regression"
  | "reports"
  | "chat"
  | "repository"
  | "documents"
  | "website"
  | "search"
  | "experiments"
  | "agents"
  | "tasks"
  | "scenarios"
  | "evidence"
  | "compare"
  | "settings"
  | "guide";
export type Engine = "fixture" | "bifrost";
export type Mode = "controlled" | "live";
export type AssessmentStatus = "pass" | "fail" | "inconclusive";

export interface Session {
  csrf_token: string;
  app_version: string;
  workspace_name: string;
  hosted: boolean;
  user: { id: string; name: string; email?: string; role: "admin" | "member" };
}
export interface Agent {
  id: string;
  name: string;
  description: string;
  framework: string;
  kind: "plain" | "graph" | "http";
  version: string;
  capabilities: string[];
  config: JsonObject;
}
export interface Task {
  id: string;
  title: string;
  description: string;
  prompt: string;
  company: string;
  reference_time: string;
  required_facts: string[];
  source_ids: string[];
}
export interface Scenario {
  id: string;
  name: string;
  description: string;
  type: string;
}
export interface Source {
  id: string;
  title: string;
  url: string;
  published_at: string;
  content: string;
  entity_id: string;
  license: string;
}
export interface Integration {
  status: string;
  detail: string;
  configured: boolean;
  credential_configured?: boolean;
  models?: string[];
}
export interface Settings {
  config: {
    bifrost_url: string;
    model: string;
    offline?: boolean;
    agentrouter_configured?: boolean;
    bynara_configured?: boolean;
  };
  integrations: {
    bifrost: Integration;
    ollama: Integration;
    tavily: Integration;
    agentrouter?: Integration;
    bynara?: Integration;
  };
}
export interface Limits {
  max_model_calls: number;
  max_tool_calls: number;
  timeout_seconds: number;
}
export interface ExperimentSpec {
  name: string;
  agent_ids: string[];
  task_ids: string[];
  scenario_ids: string[];
  repetitions: number;
  engine: Engine;
  mode: Mode;
  model: string;
  limits: Limits;
}
export type ExperimentPreset = Pick<
  Partial<ExperimentSpec>,
  | "name"
  | "agent_ids"
  | "task_ids"
  | "scenario_ids"
  | "engine"
  | "mode"
  | "repetitions"
  | "model"
  | "limits"
>;
export interface AgentMetric {
  agent_id: string;
  agent_name: string;
  total: number;
  passed: number;
  failed: number;
  inconclusive: number;
  infrastructure_errors: number;
  success_rate: number | null;
  avg_duration_ms: number | null;
  total_tool_calls: number | null;
  total_model_calls: number | null;
  total_steps?: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  api_cost_usd: number | null;
  tokens_provenance: string;
  cost_provenance: string;
}
export interface RunSummary {
  id: string;
  experiment_id: string;
  agent_id: string;
  agent_name: string;
  task_id: string;
  task_name: string;
  scenario_id: string;
  scenario_name: string;
  scenario_activated: boolean;
  repetition: number;
  outcome: string;
  assessment_status: AssessmentStatus;
  duration_ms: number | null;
  tool_calls: number | null;
  model_calls: number | null;
  steps?: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  api_cost_usd: number | null;
}
export interface TraceEvent {
  sequence: number;
  type: string;
  timestamp: string;
  title: string;
  data: JsonObject;
  duration_ms: number | null;
}
export interface Check {
  name: string;
  passed: boolean | null;
  evidence: string;
}
export interface RunDetail extends RunSummary {
  output: {
    summary: string;
    facts: { text: string; source_ids: string[] }[];
  } | null;
  assessment: {
    status: AssessmentStatus;
    checks: Check[];
    coverage?: JsonObject;
    limitations?: string[];
  } | null;
  events: TraceEvent[];
}
export interface Experiment {
  preparation_error?: string;
  id: string;
  name: string;
  state: string;
  created_at: string;
  updated_at: string;
  spec: ExperimentSpec;
  progress: { completed: number; total: number };
  summary: {
    passes: number;
    failures: number;
    inconclusive: number;
    infrastructure_errors: number;
  };
  agent_metrics: AgentMetric[];
  runs?: RunSummary[];
  manifest?: JsonObject;
}
export interface Baseline {
  id: string;
  name: string;
  experiment_id: string;
  created_at: string;
}
export interface Comparison {
  declared_changes?: { field: string; baseline: Json; candidate: Json }[];
  allow_agent_changes?: boolean;
  agent_versions?: { baseline: Agent[]; candidate: Agent[] };
  compatible: boolean;
  mismatches: string[];
  baseline: Experiment;
  candidate: Experiment;
  agent_deltas: JsonObject[];
  gate: { status: AssessmentStatus; reasons: string[] };
}
export interface Catalog {
  agents: Agent[];
  tasks: Task[];
  scenarios: Scenario[];
  sources: Source[];
  experiments: Experiment[];
  baselines: Baseline[];
  settings: Settings | null;
}
