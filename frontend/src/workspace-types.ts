import type { Experiment, RunDetail } from "./types";

export interface TaskCheck {
  id: string;
  name: string;
  type:
    | "equals"
    | "contains"
    | "icontains"
    | "not-contains"
    | "not-icontains"
    | "is-json";
  value: string | null;
  target: "summary" | "response";
}
export interface TaskCheckResult {
  engine: string;
  version: string;
  status: "pass" | "fail" | "ungraded" | "error";
  score: number | null;
  passed?: number;
  total?: number;
  scope: string;
  reason?: string;
  checks: (TaskCheck & { passed: boolean; score: number; reason: string })[];
}
export interface Readiness {
  ready: boolean;
  checks: { name: string; ready: boolean | null; detail: string }[];
  scope: string;
}

export type Category =
  "chat" | "repository" | "documents" | "website" | "search";
export interface VerifiedFinding {
  id: string;
  title: string;
  claim: string;
  severity: string;
  explanation: string;
  verification: {
    state: string;
    scope: string;
    method: string;
    claim_correctness: string;
    citations: {
      source_id: string;
      source_reference: string;
      quote: string;
      captured_content?: string | null;
      matching_method?: string;
      start_line: number | null;
      end_line: number | null;
      page: number | null;
      valid: boolean;
      reasons: string[];
    }[];
  };
}
export type WorkspaceRun = RunDetail & {
  assessment: RunDetail["assessment"] & {
    task_checks?: TaskCheckResult;
    findings?: VerifiedFinding[];
    observations?: { title: string; claim: string }[];
    metrics?: {
      citation_validity: number | null;
      evidence_coverage: number | null;
    };
  };
};
export interface Conversation {
  id: string;
  title: string;
  category: Category;
  model: string;
  agent_ids: string[];
  search_provider: "off" | "tavily";
  created_at: string;
  turns?: {
    id: string;
    message: string;
    created_at: string;
    experiment: Experiment;
    runs: WorkspaceRun[];
    retry_experiments?: Experiment[];
    artifacts?: { id: string; kind: string; data: unknown }[];
  }[];
}
