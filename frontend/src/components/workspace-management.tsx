import { useCallback, useEffect, useState } from "react";
import type { Catalog, Experiment, JsonObject } from "../types";
import type { Conversation } from "../workspace-types";
import { api, downloadEvaluation, errorMessage, post } from "../lib/api";
import { Badge, Button, EmptyState, Notice, PageHeader } from "./ui";
import { LocalHistory, LocalSetup } from "./local-product";
import { SuiteBatches } from "./suite-batches";

interface Suite {
  cases?: unknown[];
  id: string;
  name: string;
  version: string;
  repetitions: number;
  snapshot_id: string;
  checks?: { name: string }[];
}
interface RegressionDelta {
  agent_id: string;
  baseline_check_score: number | null;
  candidate_check_score: number | null;
  check_score_delta: number | null;
  newly_failed_checks: string[];
  now_passing_checks: string[];
}
interface Report {
  id: string;
  experiment_id: string;
  created_at: string;
  data: { format: "pdf" | "md" | "json" | "csv"; size: number };
}
interface DashboardData {
  evaluations: number;
  conversations?: number;
  attempts: number;
  successful_executions: number;
  failed_executions: number;
  average_latency_ms: number | null;
  observed_input_tokens: number | null;
  observed_output_tokens: number | null;
  token_observed_runs: number;
  agents: {
    name: string;
    attempts: number;
    completed: number;
    latency_ms: number | null;
  }[];
  regressions: {
    id: string;
    data: { baseline_id: string; candidate_id: string; gate: string };
  }[];
}

export function WorkspaceManagement({
  view,
  catalog,
}: {
  view: "dashboard" | "benchmarks" | "regression" | "reports";
  catalog: Catalog;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [suites, setSuites] = useState<Suite[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [source, setSource] = useState("");
  const [candidate, setCandidate] = useState("");
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1.0");
  const [repetitions, setRepetitions] = useState(3);
  const [result, setResult] = useState<JsonObject | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [truth, setTruth] = useState("");
  const [additional, setAdditional] = useState<string[]>([]);
  const [allowAgentChanges, setAllowAgentChanges] = useState(false);
  const [allowInputChanges, setAllowInputChanges] = useState(false);
  const [evaluations, setEvaluations] = useState<Experiment[]>(
    catalog.experiments,
  );
  const refresh = useCallback(async () => {
    const calls: Promise<unknown>[] = [
      api<Experiment[]>("/experiments").then(setEvaluations),
    ];
    if (view === "dashboard")
      calls.push(
        api<Conversation[]>("/workspace/conversations").then(setConversations),
        api<DashboardData>("/workspace/dashboard").then(setDashboard),
      );
    if (view === "benchmarks")
      calls.push(api<Suite[]>("/workspace/suites").then(setSuites));
    if (view === "reports")
      calls.push(api<Report[]>("/workspace/reports").then(setReports));
    const results = await Promise.allSettled(calls);
    const failure = results.find((item) => item.status === "rejected");
    if (failure?.status === "rejected") setError(errorMessage(failure.reason));
  }, [view]);
  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    const poll = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 10000);
    return () => {
      clearTimeout(timer);
      clearInterval(poll);
    };
  }, [refresh]);
  const action = async (callback: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await callback();
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const labels = {
    dashboard: "Dashboard",
    benchmarks: "Benchmarks",
    regression: "Regression Lab",
    reports: "Reports",
  };
  return (
    <>
      <PageHeader
        title={labels[view]}
        description={
          view === "dashboard"
            ? "Your recorded evaluations, conversations and evidence reports."
            : view === "benchmarks"
              ? "Save captured conditions and repeat the same task across both agents."
              : view === "regression"
                ? "Inspect changed findings and execution metrics under recorded conditions."
                : "Download reports generated from actual persisted evaluations."
        }
      />
      {error && <Notice kind="error">{error}</Notice>}
      {view === "dashboard" && <LocalSetup settings={catalog.settings} />}
      {view === "reports" && <LocalHistory />}
      {view === "dashboard" && (
        <>
          <div className="workspace-stat-grid">
            {[
              ["Total evaluations", dashboard?.evaluations ?? "—"],
              ["Recorded attempts", dashboard?.attempts ?? "—"],
              [
                "Successful executions",
                dashboard?.successful_executions ?? "—",
              ],
              ["Failed executions", dashboard?.failed_executions ?? "—"],
              [
                "Average latency",
                dashboard?.average_latency_ms == null
                  ? "—"
                  : `${(dashboard.average_latency_ms / 1000).toFixed(1)} s`,
              ],
              [
                "Conversations",
                dashboard?.conversations ?? conversations.length,
              ],
            ].map(([label, value]) => (
              <section className="panel" key={label}>
                <small>{label}</small>
                <strong>{value}</strong>
              </section>
            ))}
          </div>
          <section className="panel padded-panel">
            <h2>Recent evaluations</h2>
            {evaluations.slice(0, 8).map((exp) => (
              <a
                className="workspace-record-row"
                key={exp.id}
                href={`#/experiments/${exp.id}`}
              >
                <span>
                  <strong>{exp.name}</strong>
                  <small>
                    {exp.spec.model} · {exp.progress.completed}/
                    {exp.progress.total} attempts
                  </small>
                  {exp.preparation_error && (
                    <small>Input not ready: {exp.preparation_error}</small>
                  )}
                </span>
                <Badge status={exp.state} />
              </a>
            ))}
            {!evaluations.length && (
              <EmptyState
                title="Start with one useful task"
                description="Open Chat or analyze a repository. Your real results will appear here."
              />
            )}
          </section>
          <section className="panel padded-panel">
            <h2>Model usage</h2>
            <p>
              {dashboard?.observed_input_tokens == null
                ? "No observed token usage yet."
                : `${dashboard.observed_input_tokens.toLocaleString()} input tokens · ${(dashboard.observed_output_tokens ?? 0).toLocaleString()} output tokens across ${dashboard.token_observed_runs} runs with reported usage.`}
            </p>
            <p className="muted">
              {[
                ...new Set(catalog.experiments.map((exp) => exp.spec.model)),
              ].join(" · ") || "No model usage recorded."}
            </p>
            <p className="muted">
              Totals cover all stored executions, including labeled fixture
              benchmarks. Recent history shows the latest{" "}
              {catalog.experiments.length} loaded evaluations. Completion and
              verified accuracy are separate.
            </p>
          </section>
          <section className="panel padded-panel">
            <h2>Agent execution performance</h2>
            {dashboard?.agents.map((agent) => (
              <div className="workspace-record-row" key={agent.name}>
                <strong>{agent.name}</strong>
                <span>
                  {agent.completed}/{agent.attempts} completed ·{" "}
                  {agent.latency_ms == null
                    ? "Latency unknown"
                    : `${(agent.latency_ms / 1000).toFixed(1)} s average`}
                </span>
              </div>
            ))}
            <small className="muted">
              Completion counts reflect execution, not answer correctness. This
              is not a ranking across different tasks.
            </small>
          </section>
          <section className="panel padded-panel">
            <h2>Recent regression comparisons</h2>
            {dashboard?.regressions.map((item) => (
              <a
                className="workspace-record-row"
                key={item.id}
                href={`#/experiments/${item.data.candidate_id}`}
              >
                <span>{item.data.candidate_id}</span>
                <span>{item.data.gate.replaceAll("_", " ")}</span>
              </a>
            ))}
            {!dashboard?.regressions.length && (
              <p className="muted">
                Retest a saved evaluation, then compare it in Regression Lab.
              </p>
            )}
          </section>
        </>
      )}
      {(view === "benchmarks" || view === "regression") && (
        <section className="panel padded-panel">
          <form
            className="workspace-composer management-form"
            onSubmit={(event) => {
              event.preventDefault();
              void action(async () => {
                if (view === "benchmarks")
                  await post("/workspace/suites", {
                    name,
                    version,
                    repetitions,
                    source_experiment_id: source,
                    additional_experiment_ids: additional,
                    labels: truth.trim() ? JSON.parse(truth) : [],
                  });
                else
                  setResult(
                    await post<JsonObject>("/workspace/regressions", {
                      baseline_id: source,
                      candidate_id: candidate,
                      allow_agent_changes: allowAgentChanges,
                      allow_input_changes: allowInputChanges,
                    }),
                  );
              });
            }}
          >
            <label className="field">
              {view === "benchmarks"
                ? "Source evaluation"
                : "Baseline evaluation"}
              <select
                required
                value={source}
                onChange={(event) => setSource(event.target.value)}
              >
                <option value="">Select an evaluation</option>
                {evaluations
                  .filter(
                    (exp) =>
                      exp.spec.engine === "bifrost" &&
                      exp.state === "completed",
                  )
                  .map((exp) => (
                    <option key={exp.id} value={exp.id}>
                      {exp.name}
                    </option>
                  ))}
              </select>
            </label>
            {view === "regression" && (
              <div className="product-toolbar">
                <label>
                  <input
                    type="checkbox"
                    checked={allowAgentChanges}
                    onChange={(e) => setAllowAgentChanges(e.target.checked)}
                  />{" "}
                  Declare candidate agent/model/prompt changes
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={allowInputChanges}
                    onChange={(e) => setAllowInputChanges(e.target.checked)}
                  />{" "}
                  Declare source snapshot changes
                </label>
                <small>
                  Changed conditions remain recorded. Other incompatible
                  settings still prevent a like-for-like result.
                </small>
              </div>
            )}
            {view === "benchmarks" ? (
              <div className="workspace-controls">
                <label className="field">
                  Suite name
                  <input
                    required
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    maxLength={120}
                  />
                </label>
                <label className="field">
                  Dataset version
                  <input
                    required
                    value={version}
                    onChange={(event) => setVersion(event.target.value)}
                    maxLength={40}
                  />
                </label>
                <label className="field">
                  Repeated trials
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={repetitions}
                    onChange={(event) =>
                      setRepetitions(Number(event.target.value))
                    }
                  />
                </label>
              </div>
            ) : (
              <label className="field">
                Candidate evaluation
                <select
                  required
                  value={candidate}
                  onChange={(event) => setCandidate(event.target.value)}
                >
                  <option value="">Select a candidate</option>
                  {evaluations
                    .filter(
                      (exp) =>
                        exp.spec.engine === "bifrost" &&
                        exp.state === "completed",
                    )
                    .map((exp) => (
                      <option key={exp.id} value={exp.id}>
                        {exp.name}
                      </option>
                    ))}
                </select>
              </label>
            )}
            {view === "benchmarks" && (
              <label className="field">
                Additional test cases (up to 9)
                <select
                  multiple
                  value={additional}
                  onChange={(e) =>
                    setAdditional(
                      Array.from(
                        e.target.selectedOptions,
                        (option) => option.value,
                      ).slice(0, 9),
                    )
                  }
                >
                  {evaluations
                    .filter(
                      (exp) =>
                        exp.id !== source &&
                        exp.state === "completed" &&
                        exp.spec.engine === "bifrost",
                    )
                    .map((exp) => (
                      <option key={exp.id} value={exp.id}>
                        {exp.name}
                      </option>
                    ))}
                </select>
                <small>
                  Each case retains its own task, captured sources and checks.
                </small>
              </label>
            )}
            {view === "benchmarks" && (
              <details>
                <summary>Optional ground-truth quotation labels</summary>
                <label className="field">
                  Labels as JSON
                  <textarea
                    rows={4}
                    value={truth}
                    onChange={(event) => setTruth(event.target.value)}
                    placeholder={
                      '[{"label_id":"storage","reference":"src/store.py","expected_quote":"exact captured passage"}]'
                    }
                  />
                </label>
                <small>
                  Exact source quotations only. Labels must match captured
                  content. These metrics do not measure vulnerability accuracy.
                </small>
              </details>
            )}
            <Button variant="violet" type="submit" busy={busy}>
              {view === "benchmarks"
                ? "Save versioned suite"
                : "Compare recorded results"}
            </Button>
            <small className="muted">
              Requires a workspace evaluation with a captured snapshot. Existing
              research benchmarks remain available under Experiments.
            </small>
          </form>
        </section>
      )}
      {view === "benchmarks" && (
        <section className="panel padded-panel">
          <h2>Saved suites</h2>
          {suites.map((suite) => (
            <div className="workspace-record-row" key={suite.id}>
              <span>
                <strong>
                  {suite.name} · {suite.version}
                </strong>
                <small>
                  {suite.repetitions} repetitions · {suite.checks?.length ?? 0}{" "}
                  task checks · {suite.snapshot_id}
                </small>
              </span>
              <Button
                disabled={busy}
                onClick={() =>
                  void action(async () => {
                    const batch = await post<{
                      cases: { id: string; name: string }[];
                      admission_error?: string;
                    }>(`/workspace/suites/${suite.id}/batches`, {});
                    setResult({ queued_cases: batch.cases });
                    if (batch.admission_error)
                      throw new Error(
                        batch.admission_error +
                          " The saved batch can resume its remaining cases.",
                      );
                  })
                }
              >
                Run suite
              </Button>
            </div>
          ))}
          {!suites.length && (
            <EmptyState
              title="Capture a benchmark"
              description="Save a completed evaluation to repeat its prompt, model, limits and source snapshot."
            />
          )}
        </section>
      )}
      {result && (
        <section className="panel padded-panel">
          <h2>
            {Array.isArray(result.queued_cases)
              ? "Queued suite cases"
              : "Comparison result"}
          </h2>
          {!Array.isArray(result.queued_cases) && (
            <Badge status="inconclusive">
              {result.compatible
                ? "Compatible recorded conditions"
                : "Conditions differ"}
            </Badge>
          )}
          {Array.isArray(result.queued_cases) &&
            (result.queued_cases as { id: string; name: string }[]).map(
              (value) => (
                <p key={value.id}>
                  <a href={`#/experiments/${value.id}`}>{value.name}</a>
                </p>
              ),
            )}
          {typeof result.gate === "string" && (
            <p>
              <strong>{result.gate.replaceAll("_", " ")}</strong> · Declared
              task checks and source quotation labels only.
            </p>
          )}
          {Array.isArray(result.agent_deltas) && (
            <div className="check-table-scroll">
              <table className="check-table">
                <caption>Task-check changes by agent</caption>
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>Before → after</th>
                    <th>Changed checks</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.agent_deltas as unknown as RegressionDelta[]).map(
                    (delta) => (
                      <tr key={delta.agent_id}>
                        <th scope="row">{delta.agent_id}</th>
                        <td>
                          {delta.baseline_check_score == null
                            ? "Ungraded"
                            : `${Math.round(delta.baseline_check_score * 100)}%`}{" "}
                          →{" "}
                          {delta.candidate_check_score == null
                            ? "Ungraded"
                            : `${Math.round(delta.candidate_check_score * 100)}%`}
                        </td>
                        <td>
                          {delta.newly_failed_checks?.length
                            ? `New failures: ${delta.newly_failed_checks.join(", ")}`
                            : "No newly failed checks recorded."}
                          {!!delta.now_passing_checks?.length && (
                            <p>
                              Now passing: {delta.now_passing_checks.join(", ")}
                            </p>
                          )}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          )}
          <details>
            <summary>All comparison details and conditions</summary>
            <pre className="management-result">
              {JSON.stringify(result, null, 2)}
            </pre>
          </details>
        </section>
      )}
      {view === "benchmarks" && <SuiteBatches />}
      {view === "reports" && (
        <section className="panel padded-panel">
          {reports.map((report) => (
            <div className="workspace-record-row" key={report.id}>
              <span>
                <strong>{report.experiment_id}</strong>
                <small>
                  {new Date(report.created_at).toLocaleString()} ·{" "}
                  {report.data.format.toUpperCase()} ·{" "}
                  {report.data.size.toLocaleString()} bytes
                </small>
              </span>
              <Button
                onClick={() =>
                  void action(() =>
                    downloadEvaluation(
                      report.experiment_id,
                      report.data.format,
                    ),
                  )
                }
              >
                Download
              </Button>
            </div>
          ))}
          {!reports.length && (
            <EmptyState
              title="Export your first evidence report"
              description="Open a completed conversation and choose PDF, Markdown, JSON or CSV. Reports use the persisted findings and verification results."
            />
          )}
        </section>
      )}
    </>
  );
}
