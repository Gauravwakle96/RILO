import { useEffect, useRef, useState } from "react";
import { EvaluationCheckComparison } from "./task-checks";
import {
  Activity,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Braces,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FlaskConical,
  GitCompareArrows,
  ListFilter,
  Play,
  RotateCcw,
  Search,
  ShieldAlert,
  Square,
  Target,
} from "lucide-react";
import { api, downloadReport, errorMessage, post } from "../lib/api";
import { containDialogFocus } from "../lib/dialog";
import {
  active,
  date,
  duration,
  human,
  money,
  number,
  rate,
} from "../lib/format";
import type {
  AgentMetric,
  Catalog,
  Experiment,
  ExperimentPreset,
  RunDetail,
  RunSummary,
} from "../types";
import {
  Badge,
  Button,
  EmptyState,
  JsonBlock,
  LinkAction,
  Metric,
  Notice,
  PageHeader,
  SectionTitle,
  Skeleton,
} from "./ui";

export function ExperimentList({
  catalog,
  loading,
  onNew,
  onOpen,
  onExample,
  onGuide,
}: {
  catalog: Catalog;
  loading: boolean;
  onNew: () => void;
  onOpen: (id: string) => void;
  onExample: () => void;
  onGuide: () => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const experiments = catalog.experiments.filter(
    (experiment) =>
      experiment.name.toLowerCase().includes(query.toLowerCase()) &&
      (filter === "all" ||
        (filter === "active"
          ? active(experiment.state)
          : experiment.state === filter)),
  );
  const attempts = catalog.experiments.reduce(
    (sum, experiment) => sum + experiment.progress.completed,
    0,
  );
  const passes = catalog.experiments.reduce(
    (sum, experiment) => sum + experiment.summary.passes,
    0,
  );
  const assessed = catalog.experiments.reduce(
    (sum, experiment) =>
      sum + experiment.summary.passes + experiment.summary.failures,
    0,
  );
  const faults = catalog.experiments.reduce(
    (sum, experiment) =>
      sum +
      experiment.summary.failures +
      experiment.summary.infrastructure_errors,
    0,
  );
  const latestModel = [...catalog.experiments]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .find(
      (experiment) =>
        experiment.state === "completed" &&
        experiment.spec.engine === "bifrost" &&
        experiment.spec.mode === "controlled" &&
        experiment.spec.scenario_ids.length > 1 &&
        experiment.agent_metrics.length > 1 &&
        experiment.spec.agent_ids.every((id) =>
          catalog.agents.some(
            (agent) => agent.id === id && agent.kind !== "http",
          ),
        ),
    );
  const demoReady =
    ["scout", "relay"].every((id) =>
      catalog.agents.some((agent) => agent.id === id),
    ) && catalog.tasks.length > 0;
  return (
    <>
      <PageHeader
        title="Experiments"
        description="Test the task. Expose the failure. Check the next revision."
        actions={
          <Button variant="primary" onClick={onNew}>
            <Play size={16} />
            New experiment
          </Button>
        }
      />
      <section
        className="recovery-workspace"
        aria-labelledby="recovery-workspace-title"
      >
        <div className="recovery-intro">
          <h2 id="recovery-workspace-title">
            Find the failures
            <br />
            your demo missed.
          </h2>
          <p>
            One task. Different agents. A search tool stops responding. See who
            recovers—and inspect the evidence behind the answer.
          </p>
          <div className="recovery-actions">
            <Button variant="primary" disabled={!demoReady} onClick={onExample}>
              <Play size={15} /> Try recovery example
            </Button>
            <Button variant="ghost" onClick={onGuide}>
              How Rilo works <ArrowRight size={15} />
            </Button>
          </div>
          <span className="recovery-note">
            12 attempts · deterministic demo · no API key
          </span>
        </div>
        <div className="recovery-proof">
          {latestModel ? (
            <>
              <div className="recovery-proof-heading">
                <span className="small-status-dot" />
                <strong>Recorded real-model experiment</strong>
              </div>
              <p>
                {latestModel.spec.task_ids.length} tasks ·{" "}
                {latestModel.spec.scenario_ids.length} conditions ·{" "}
                {latestModel.spec.repetitions} trials
              </p>
              <div className="recovery-agent-results">
                {latestModel.agent_metrics.slice(0, 2).map((metric) => (
                  <div key={metric.agent_id}>
                    <div>
                      <strong>{metric.agent_name}</strong>
                      <span>
                        {metric.passed} / {metric.total} passed
                      </span>
                    </div>
                    <b>{rate(metric.success_rate)}</b>
                  </div>
                ))}
              </div>
              <button
                className="recovery-evidence-link"
                onClick={() => onOpen(latestModel.id)}
              >
                Inspect this experiment <ArrowRight size={15} />
              </button>
              <small>
                Results apply to these recorded tasks and conditions.
              </small>
            </>
          ) : (
            <>
              <h3>A failure becomes a repeatable test.</h3>
              <ol className="recovery-flow">
                <li>Compare the same task</li>
                <li>Inspect the fault and recovery</li>
                <li>Retest after your change</li>
              </ol>
              <p>
                Start with the demo. Switch to your real model when you are
                ready.
              </p>
            </>
          )}
        </div>
      </section>
      <div className="metrics-strip">
        <Metric
          label="Experiments"
          value={catalog.experiments.length}
          detail={`${catalog.experiments.filter((experiment) => active(experiment.state)).length} currently running`}
          icon={<FlaskConical size={17} />}
        />
        <Metric
          label="Recorded attempts"
          value={number(attempts)}
          detail="Across all engines · fixture and real model"
          icon={<Activity size={17} />}
        />
        <Metric
          label="Task success"
          value={assessed ? rate(passes / assessed) : "—"}
          detail={
            assessed
              ? `${passes} / ${assessed} assessable attempts · all engines`
              : "Run a test to establish a baseline"
          }
          icon={<Target size={17} />}
        />
        <Metric
          label="Issues to inspect"
          value={number(faults)}
          detail="Task failures + infrastructure errors"
          icon={<ShieldAlert size={17} />}
        />
      </div>
      <section className="panel experiment-panel">
        <div className="panel-toolbar">
          <div
            className="toolbar-tabs"
            role="group"
            aria-label="Experiment status filter"
          >
            <button
              className={filter === "all" ? "selected" : ""}
              onClick={() => setFilter("all")}
            >
              All experiments<span>{catalog.experiments.length}</span>
            </button>
            <button
              className={filter === "active" ? "selected" : ""}
              onClick={() => setFilter("active")}
            >
              Running
            </button>
            <button
              className={filter === "completed" ? "selected" : ""}
              onClick={() => setFilter("completed")}
            >
              Completed
            </button>
          </div>
          <label className="search-field">
            <Search size={15} aria-hidden="true" />
            <input
              aria-label="Search experiments"
              placeholder="Search experiments…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <kbd>/</kbd>
          </label>
        </div>
        {loading ? (
          <Skeleton />
        ) : catalog.experiments.length === 0 ? (
          <EmptyState
            title="Your first experiment starts here"
            description="Connect your agents, choose a referenced task, and compare how they handle normal and difficult conditions."
            icon={<FlaskConical size={29} />}
            action={
              <Button variant="primary" onClick={onNew}>
                <Play size={15} />
                Create an experiment
              </Button>
            }
          />
        ) : experiments.length === 0 ? (
          <EmptyState
            title="No matching experiments"
            description="Try another search or clear the status filter."
            action={
              <Button
                onClick={() => {
                  setQuery("");
                  setFilter("all");
                }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table experiment-table">
              <thead>
                <tr>
                  <th>Experiment</th>
                  <th>Status</th>
                  <th>Conditions</th>
                  <th>Task results</th>
                  <th>Created</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {experiments.map((experiment) => (
                  <tr key={experiment.id}>
                    <td>
                      <button
                        className="experiment-link"
                        onClick={() => onOpen(experiment.id)}
                      >
                        <span className="experiment-icon">
                          <FlaskConical size={17} />
                        </span>
                        <span>
                          <strong>{experiment.name}</strong>
                          <small>
                            {experiment.spec.agent_ids.length} agents ·{" "}
                            {experiment.spec.task_ids.length} tasks ·{" "}
                            {experiment.spec.repetitions} trials
                          </small>
                        </span>
                      </button>
                    </td>
                    <td>
                      <Badge status={experiment.state} />
                      {active(experiment.state) && (
                        <div className="mini-progress">
                          <progress
                            value={experiment.progress.completed}
                            max={experiment.progress.total}
                          />
                          <span>
                            {experiment.progress.completed}/
                            {experiment.progress.total}
                          </span>
                        </div>
                      )}
                    </td>
                    <td>
                      <div className="cell-stack">
                        <span>
                          {experiment.spec.scenario_ids.length} test conditions
                        </span>
                        <small>
                          {experiment.spec.engine === "fixture"
                            ? "Demonstration"
                            : "Real model"}{" "}
                          ·{" "}
                          {experiment.spec.mode === "controlled"
                            ? "Controlled evidence"
                            : "Live research"}
                        </small>
                      </div>
                    </td>
                    <td>
                      <div className="outcome-dots">
                        <span className="outcome-good">
                          {experiment.summary.passes} pass
                        </span>
                        <span className="outcome-bad">
                          {experiment.summary.failures} fail
                        </span>
                      </div>
                      {experiment.summary.inconclusive +
                        experiment.summary.infrastructure_errors >
                        0 && (
                        <small className="subtle">
                          {experiment.summary.inconclusive} inconclusive ·{" "}
                          {experiment.summary.infrastructure_errors}{" "}
                          infrastructure
                        </small>
                      )}
                    </td>
                    <td className="date-cell">{date(experiment.created_at)}</td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`Open ${experiment.name}`}
                        onClick={() => onOpen(experiment.id)}
                      >
                        <ChevronRight size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="table-footer">
          <span>
            {experiments.length} experiment{experiments.length !== 1 && "s"} ·
            local workspace
          </span>
          <span>
            <ShieldAlert size={13} />
            Evidence before assumptions
          </span>
        </div>
      </section>
      <div className="workspace-guidance">
        <div className="guidance-item">
          <span className="guidance-number">01</span>
          <div>
            <h2>Keep comparisons fair</h2>
            <p>
              Use the same tasks, limits, model, and evidence for every agent.
            </p>
          </div>
        </div>
        <div className="guidance-item">
          <span className="guidance-number">02</span>
          <div>
            <h2>Test the difficult conditions</h2>
            <p>Introduce controlled faults and inspect how agents recover.</p>
          </div>
        </div>
        <div className="guidance-item">
          <span className="guidance-number">03</span>
          <div>
            <h2>Make improvement measurable</h2>
            <p>
              Save a baseline, change one factor, and run the same conditions
              again.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

function AgentMetrics({
  metrics,
  workspace = false,
}: {
  metrics: AgentMetric[];
  workspace?: boolean;
}) {
  return (
    <div className="table-scroll">
      <table className="data-table metrics-table">
        <thead>
          <tr>
            <th>Agent</th>
            <th>{workspace ? "All checks passed" : "Task success"}</th>
            <th>Avg. runtime</th>
            <th>Tool calls</th>
            <th>Model calls</th>
            <th>Steps</th>
            <th>Tokens</th>
            <th>API fees</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => (
            <tr key={metric.agent_id}>
              <td>
                <div className="agent-cell">
                  <span
                    className={`avatar avatar-${metric.agent_id === "relay" ? "green" : "blue"}`}
                  >
                    {metric.agent_name.slice(0, 1)}
                  </span>
                  <div>
                    <strong>{metric.agent_name}</strong>
                    <small>{metric.total} attempts</small>
                  </div>
                </div>
              </td>
              <td>
                <strong>{rate(metric.success_rate)}</strong>
                <small className="block subtle">
                  {metric.passed} pass · {metric.failed} fail
                  {metric.inconclusive > 0 &&
                    ` · ${metric.inconclusive} unknown`}
                </small>
              </td>
              <td className="mono">{duration(metric.avg_duration_ms)}</td>
              <td className="mono">{number(metric.total_tool_calls)}</td>
              <td className="mono">{number(metric.total_model_calls)}</td>
              <td className="mono">{number(metric.total_steps)}</td>
              <td>
                <span className="mono">
                  {metric.tokens_provenance === "not_applicable"
                    ? "Not applicable"
                    : metric.input_tokens == null ||
                        metric.output_tokens == null
                      ? "Unknown"
                      : number(metric.input_tokens + metric.output_tokens)}
                </span>
                <small className="block subtle">
                  {human(metric.tokens_provenance)}
                </small>
              </td>
              <td>
                <span className="mono">
                  {money(metric.api_cost_usd, metric.cost_provenance)}
                </span>
                <small className="block subtle">
                  {human(metric.cost_provenance)}
                </small>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RecoveryComparison({
  runs,
  agents,
  onInspect,
}: {
  runs: RunSummary[];
  agents: AgentMetric[];
  onInspect: (id: string) => void;
}) {
  const scenarioIds = [
    "normal",
    "search_timeout",
    "model_outage",
    "prompt_injection",
  ].filter((id) => runs.some((run) => run.scenario_id === id));
  if (scenarioIds.length < 2 || agents.length === 0) return null;
  return (
    <section
      className="panel recovery-matrix"
      aria-labelledby="recovery-matrix-title"
    >
      <div className="panel-toolbar">
        <div>
          <h2 id="recovery-matrix-title">Recovery under failure</h2>
          <p>
            Task checks passed in each condition. Select a result to inspect an
            attempt.
          </p>
        </div>
        <ShieldAlert size={19} />
      </div>
      <div className="table-scroll">
        <table className="data-table recovery-table">
          <caption className="sr-only">
            Task success by condition and agent in this experiment
          </caption>
          <thead>
            <tr>
              <th scope="col">Test condition</th>
              {agents.map((agent) => (
                <th scope="col" key={agent.agent_id}>
                  {agent.agent_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenarioIds.map((scenarioId) => {
              const scenarioRuns = runs.filter(
                (run) => run.scenario_id === scenarioId,
              );
              return (
                <tr key={scenarioId}>
                  <th scope="row">
                    <strong>{scenarioRuns[0].scenario_name}</strong>
                    <small>
                      {scenarioId === "normal"
                        ? "Baseline behavior"
                        : `${scenarioRuns.filter((run) => run.scenario_activated).length} recorded fault activations`}
                    </small>
                  </th>
                  {agents.map((agent) => {
                    const attempts = scenarioRuns.filter(
                      (run) => run.agent_id === agent.agent_id,
                    );
                    const passed = attempts.filter(
                      (run) => run.assessment_status === "pass",
                    ).length;
                    const assessed = attempts.filter(
                      (run) => run.assessment_status !== "inconclusive",
                    ).length;
                    const sample =
                      attempts.find(
                        (run) => run.assessment_status === "fail",
                      ) ?? attempts[0];
                    return (
                      <td key={agent.agent_id}>
                        {sample ? (
                          <button
                            className="recovery-result"
                            onClick={() => onInspect(sample.id)}
                          >
                            <span className="sr-only">
                              Inspect {agent.agent_name}{" "}
                              {scenarioRuns[0].scenario_name} result:{" "}
                            </span>
                            <span
                              className={`recovery-ratio ${assessed && passed === assessed ? "good" : assessed ? "warning" : ""}`}
                            >
                              {assessed ? `${passed} / ${assessed}` : "—"}
                            </span>{" "}
                            <span>
                              passed
                              {attempts.length > assessed
                                ? ` · ${attempts.length - assessed} inconclusive`
                                : ""}
                            </span>
                            <ArrowRight size={14} />
                          </button>
                        ) : (
                          <span className="subtle">No attempts yet</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="recovery-matrix-note">
        Results cover the selected tasks and trials. Inspect activation and
        trace events to confirm fault delivery and recovery.
      </p>
    </section>
  );
}

export function ExperimentDetail({
  id,
  onBack,
  onRerun,
  onBaseline,
  onCompare,
  onRetest,
}: {
  id: string;
  onBack: () => void;
  onRerun: (experiment: Experiment) => void;
  onBaseline: (experiment: Experiment) => void;
  onCompare: () => void;
  onRetest: (preset: ExperimentPreset) => void;
}) {
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"results" | "runs" | "configuration">(
    "results",
  );
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let disposed = false;
    let timer: number | undefined;
    const load = async () => {
      try {
        const value = await api<Experiment>(
          `/experiments/${encodeURIComponent(id)}`,
        );
        if (!disposed) {
          setExperiment(value);
          setError("");
          if (active(value.state))
            timer = window.setTimeout(
              () => void load(),
              document.hidden ? 6000 : 1800,
            );
        }
      } catch (err) {
        if (!disposed) {
          setError(errorMessage(err));
          timer = window.setTimeout(() => void load(), 6000);
        }
      }
    };
    void load();
    return () => {
      disposed = true;
      window.clearTimeout(timer);
    };
  }, [id]);
  const cancel = async () => {
    setBusy(true);
    try {
      await post(`/experiments/${id}/cancel`, {});
      setExperiment(await api<Experiment>(`/experiments/${id}`));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const exportReport = async (format: "json" | "csv") => {
    try {
      await downloadReport(id, format);
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  if (!experiment)
    return (
      <>
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft size={15} />
          Experiments
        </Button>
        {error ? <Notice kind="error">{error}</Notice> : <Skeleton />}
      </>
    );
  const runs = experiment.runs ?? [];
  const displayedRuns = runs.filter(
    (run) => filter === "all" || run.assessment_status === filter,
  );
  const assessed = experiment.summary.passes + experiment.summary.failures;
  return (
    <>
      <div className="breadcrumb">
        <button onClick={onBack}>Experiments</button>
        <ChevronRight size={13} />
        <span>{experiment.name}</span>
      </div>
      <PageHeader
        eyebrow="Experiment"
        title={experiment.name}
        description={`${experiment.spec.agent_ids.length} agents · ${experiment.spec.task_ids.length} tasks · ${experiment.spec.scenario_ids.length} conditions · ${experiment.spec.repetitions} trials`}
        actions={
          <>
            <Badge status={experiment.state} />
            {active(experiment.state) ? (
              <Button variant="danger" busy={busy} onClick={cancel}>
                <Square size={13} />
                Cancel
              </Button>
            ) : (
              <Button onClick={() => onRerun(experiment)}>
                <RotateCcw size={15} />
                Rerun
              </Button>
            )}
            <Button onClick={() => void exportReport("json")}>
              <ArrowDownToLine size={15} />
              Export JSON
            </Button>
          </>
        }
      />
      {error && (
        <Notice kind="error" onDismiss={() => setError("")}>
          {error}
        </Notice>
      )}
      {experiment.spec.engine === "fixture" && (
        <Notice>
          This is a deterministic demonstration. It exercises execution, faults,
          and grading; model-token metrics do not apply.
        </Notice>
      )}
      {["partial", "failed", "cancelled"].includes(experiment.state) && (
        <Notice kind="warning">
          Available results are preserved.{" "}
          {experiment.progress.total - experiment.progress.completed} scheduled
          attempts may not have completed; inspect outcomes before drawing
          conclusions.
        </Notice>
      )}
      {active(experiment.state) && (
        <div className="running-strip">
          <Activity size={17} className="pulse" />
          <div>
            <strong>
              {experiment.state === "queued"
                ? "Waiting for the worker"
                : "Experiment in progress"}
            </strong>
            <span>
              {experiment.progress.completed} of {experiment.progress.total}{" "}
              attempts recorded
            </span>
          </div>
          <progress
            max={experiment.progress.total}
            value={experiment.progress.completed}
          />
          <span className="mono">
            {Math.round(
              (experiment.progress.completed /
                Math.max(experiment.progress.total, 1)) *
                100,
            )}
            %
          </span>
        </div>
      )}
      <div className="metrics-strip">
        <Metric
          label={
            experiment.manifest?.workspace
              ? "All checks passed"
              : "Task success"
          }
          value={assessed ? rate(experiment.summary.passes / assessed) : "—"}
          detail={`${experiment.summary.passes} / ${assessed} ${experiment.manifest?.workspace ? "graded attempts · declared checks only" : "assessable attempts"}`}
          icon={<CheckCircle2 size={17} />}
        />
        <Metric
          label="Recorded attempts"
          value={`${experiment.progress.completed}/${experiment.progress.total}`}
          detail="Fresh state for every trial"
          icon={<Activity size={17} />}
        />
        <Metric
          label={
            experiment.manifest?.workspace ? "Checks not met" : "Task failures"
          }
          value={experiment.summary.failures}
          detail={`${experiment.summary.inconclusive} inconclusive assessments`}
          icon={<ShieldAlert size={17} />}
        />
        <Metric
          label="Infrastructure errors"
          value={experiment.summary.infrastructure_errors}
          detail="Reported separately from task quality"
          icon={<Clock3 size={17} />}
        />
      </div>
      <div className="detail-tabs" role="group" aria-label="Experiment section">
        <button
          className={tab === "results" ? "selected" : ""}
          onClick={() => setTab("results")}
        >
          <GitCompareArrows size={15} />
          Comparison
        </button>
        <button
          className={tab === "runs" ? "selected" : ""}
          onClick={() => setTab("runs")}
        >
          <Activity size={15} />
          Runs<span>{runs.length}</span>
        </button>
        <button
          className={tab === "configuration" ? "selected" : ""}
          onClick={() => setTab("configuration")}
        >
          <Braces size={15} />
          Configuration
        </button>
      </div>
      {tab === "results" && (
        <>
          {experiment.manifest?.workspace ? (
            <EvaluationCheckComparison
              id={experiment.id}
              state={experiment.state}
            />
          ) : (
            <RecoveryComparison
              runs={runs}
              agents={experiment.agent_metrics}
              onInspect={setSelectedRun}
            />
          )}
          <section className="panel">
            <SectionTitle
              title="Agent comparison"
              caption="Outcomes and usage under the same recorded conditions."
              actions={
                !active(experiment.state) && (
                  <Button onClick={() => onBaseline(experiment)}>
                    <GitCompareArrows size={15} />
                    Save baseline
                  </Button>
                )
              }
            />
            {experiment.agent_metrics.length ? (
              <AgentMetrics
                metrics={experiment.agent_metrics}
                workspace={!!experiment.manifest?.workspace}
              />
            ) : (
              <EmptyState
                title="Results will appear here"
                description="The worker will record each attempt and its assessment as the experiment progresses."
              />
            )}
          </section>
          <section className="panel condition-panel">
            <SectionTitle
              title="Condition coverage"
              caption="Check exposure as well as the final outcome."
            />
            <div className="condition-grid">
              {experiment.spec.scenario_ids.map((scenario) => {
                const conditionRuns = runs.filter(
                  (run) => run.scenario_id === scenario,
                );
                const activated = conditionRuns.filter(
                  (run) => run.scenario_activated,
                ).length;
                const passed = conditionRuns.filter(
                  (run) => run.assessment_status === "pass",
                ).length;
                const assessedCount = conditionRuns.filter((run) =>
                  ["pass", "fail"].includes(run.assessment_status),
                ).length;
                return (
                  <div className="condition-result" key={scenario}>
                    <span
                      className={`condition-icon ${scenario === "normal" ? "good" : "warning"}`}
                    >
                      {scenario === "normal" ? (
                        <CheckCircle2 size={19} />
                      ) : (
                        <ShieldAlert size={19} />
                      )}
                    </span>
                    <strong>{human(scenario)}</strong>
                    <span>
                      {assessedCount
                        ? `${passed} / ${assessedCount} assessed passed`
                        : "No graded outcomes"}
                    </span>
                    <small>
                      {conditionRuns.length - assessedCount > 0
                        ? `${conditionRuns.length - assessedCount} ungraded or unavailable`
                        : scenario === "normal"
                          ? "Baseline condition"
                          : `${activated} recorded activations`}
                    </small>
                  </div>
                );
              })}
            </div>
          </section>
          <div className="next-step-strip">
            <div>
              <h3>Inspect the behavior behind the result</h3>
              <p>
                Open a run to see its outputs, grader evidence, and event
                timeline.
              </p>
            </div>
            <LinkAction onClick={() => setTab("runs")}>Inspect runs</LinkAction>
          </div>
        </>
      )}
      {tab === "runs" && (
        <section className="panel">
          <div className="panel-toolbar">
            <SectionTitle
              title="Recorded runs"
              caption="Each row is an independently recorded attempt."
            />
            <label className="compact-select">
              <ListFilter size={14} />
              <select
                aria-label="Filter run assessments"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              >
                <option value="all">All assessments</option>
                <option value="pass">Passed</option>
                <option value="fail">Failed</option>
                <option value="inconclusive">Inconclusive</option>
              </select>
            </label>
          </div>
          {displayedRuns.length ? (
            <div className="table-scroll">
              <table className="data-table runs-table">
                <thead>
                  <tr>
                    <th>Agent & task</th>
                    <th>Condition</th>
                    <th>Assessment</th>
                    <th>Outcome</th>
                    <th>Time</th>
                    <th>Trial</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {displayedRuns.map((run) => (
                    <RunRow
                      key={run.id}
                      run={run}
                      onOpen={() => setSelectedRun(run.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No recorded runs in this view"
              description="Wait for execution or choose another assessment filter."
            />
          )}
        </section>
      )}
      {tab === "configuration" && (
        <section className="panel padded-panel">
          <SectionTitle
            title="Recorded configuration"
            caption="Model, limits, evidence, and immutable inputs for this experiment."
          />
          <JsonBlock
            value={{ spec: experiment.spec, manifest: experiment.manifest }}
          />
          <div className="button-group">
            <Button onClick={() => void exportReport("csv")}>
              <ArrowDownToLine size={15} />
              Export CSV
            </Button>
            <Button onClick={onCompare}>
              <GitCompareArrows size={15} />
              Compare experiments
            </Button>
          </div>
        </section>
      )}
      {selectedRun && (
        <RunInspector
          id={selectedRun}
          onClose={() => setSelectedRun(null)}
          onRetest={(run) => {
            setSelectedRun(null);
            onRetest({
              name: `${run.task_name} · ${run.scenario_name} regression`,
              agent_ids: experiment.spec.agent_ids,
              task_ids: [run.task_id],
              scenario_ids:
                run.scenario_id === "normal"
                  ? ["normal"]
                  : ["normal", run.scenario_id],
              repetitions: Math.max(3, experiment.spec.repetitions),
              engine: experiment.spec.engine,
              mode: experiment.spec.mode,
              model: experiment.spec.model,
              limits: experiment.spec.limits,
            });
          }}
        />
      )}
    </>
  );
}

function RunRow({ run, onOpen }: { run: RunSummary; onOpen: () => void }) {
  return (
    <tr>
      <td>
        <button className="run-link" onClick={onOpen}>
          <strong>{run.agent_name}</strong>
          <small>{run.task_name}</small>
        </button>
      </td>
      <td>
        <span>{run.scenario_name}</span>
        <small className="block subtle">
          {run.scenario_id === "normal"
            ? "Baseline"
            : run.scenario_activated
              ? "Activated"
              : "Not activated"}
        </small>
      </td>
      <td>
        <Badge status={run.assessment_status} />
      </td>
      <td>{human(run.outcome)}</td>
      <td className="mono">{duration(run.duration_ms)}</td>
      <td className="mono">{run.repetition}</td>
      <td>
        <button
          className="icon-button"
          aria-label={`Inspect ${run.agent_name} ${run.task_name} ${run.scenario_name} trial ${run.repetition}`}
          onClick={onOpen}
        >
          <ArrowRight size={16} />
        </button>
      </td>
    </tr>
  );
}

function RunInspector({
  id,
  onClose,
  onRetest,
}: {
  id: string;
  onClose: () => void;
  onRetest: (run: RunDetail) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef(document.activeElement as HTMLElement | null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"trace" | "output" | "assessment">("trace");
  useEffect(() => {
    let disposed = false;
    api<RunDetail>(`/runs/${encodeURIComponent(id)}`)
      .then((value) => {
        if (!disposed) setRun(value);
      })
      .catch((err) => {
        if (!disposed) setError(errorMessage(err));
      });
    return () => {
      disposed = true;
    };
  }, [id]);
  useEffect(() => {
    const dialog = dialogRef.current;
    const opener = returnFocus.current;
    const old = document.body.style.overflow;
    dialog?.showModal();
    const releaseFocus = containDialogFocus(dialog);
    document.body.style.overflow = "hidden";
    return () => {
      releaseFocus();
      dialog?.close();
      document.body.style.overflow = old;
      if (opener?.isConnected) opener.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialogRef}
      className="run-inspector"
      aria-labelledby="inspector-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) {
          const rect = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            onClose();
        }
      }}
    >
      <div className="inspector-header">
        <div>
          <h2 id="inspector-title">{run?.agent_name ?? "Loading run"}</h2>
          <p>{run?.task_name ?? "Retrieving recorded events…"}</p>
        </div>
        <Button onClick={onClose}>
          <ArrowRight size={16} />
          <span className="sr-only">Close run inspector</span>
        </Button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {run ? (
        <>
          <div className="inspector-meta">
            <Badge status={run.assessment_status} />
            <span>{run.scenario_name}</span>
            <span className="mono">{duration(run.duration_ms)}</span>
            <span>Trial {run.repetition}</span>
          </div>
          <div className="detail-tabs">
            <button
              className={tab === "trace" ? "selected" : ""}
              onClick={() => setTab("trace")}
            >
              Timeline<span>{run.events.length}</span>
            </button>
            <button
              className={tab === "output" ? "selected" : ""}
              onClick={() => setTab("output")}
            >
              Output
            </button>
            <button
              className={tab === "assessment" ? "selected" : ""}
              onClick={() => setTab("assessment")}
            >
              Evaluation
            </button>
          </div>
          <div
            className="inspector-body"
            tabIndex={0}
            role="region"
            aria-label={
              tab === "trace"
                ? "Run timeline"
                : tab === "output"
                  ? "Agent output"
                  : "Run evaluation"
            }
          >
            {tab === "trace" && (
              <div className="timeline">
                {run.events.map((event) => (
                  <details
                    className={`trace-event ${event.type === "fault_injected" ? "fault-event" : ""}`}
                    key={event.sequence}
                  >
                    <summary>
                      <span className="event-sequence">{event.sequence}</span>
                      <span className="event-content">
                        <strong>{event.title}</strong>
                        <small>{human(event.type)}</small>
                      </span>
                      <span className="event-time mono">
                        {event.duration_ms != null
                          ? duration(event.duration_ms)
                          : new Date(event.timestamp).toLocaleTimeString("en", {
                              hour12: false,
                            })}
                      </span>
                      <ChevronRight size={13} />
                    </summary>
                    <JsonBlock value={event.data} />
                  </details>
                ))}
              </div>
            )}
            {tab === "output" && (
              <>
                <SectionTitle title="Agent response" />
                <Notice>
                  The grader checks the structured fact list. Claims in the
                  free-text summary are not independently assessed.
                </Notice>
                {run.output ? (
                  <div className="output-text">
                    <p>{run.output.summary}</p>
                    {run.output.facts.length > 0 && (
                      <ul className="output-facts">
                        {run.output.facts.map((fact, index) => (
                          <li key={index}>
                            <p>{fact.text}</p>
                            <div className="source-tags">
                              {fact.source_ids.map((source) => (
                                <span className="mono" key={source}>
                                  {source}
                                </span>
                              ))}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <EmptyState
                    title="No final response"
                    description="Inspect the timeline to see whether execution failed, stopped, or was interrupted."
                  />
                )}
              </>
            )}
            {tab === "assessment" && (
              <>
                <SectionTitle
                  title="Grader evidence"
                  caption="Checks applied to the recorded output and conditions."
                />
                <Notice>
                  {run.assessment?.limitations?.length
                    ? run.assessment.limitations.join(" ")
                    : "The grader checks reference facts, citations, and fault coverage. Arbitrary claims in the free-text summary remain unassessed."}
                </Notice>
                {run.assessment ? (
                  <div className="assessment-list">
                    {run.assessment.checks.map((check, index) => (
                      <div className="assessment-check" key={index}>
                        <Badge
                          status={
                            check.passed == null
                              ? "inconclusive"
                              : check.passed
                                ? "pass"
                                : "fail"
                          }
                        />
                        <div>
                          <strong>{check.name}</strong>
                          <p>{check.evidence}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="Assessment unavailable"
                    description="This attempt does not have enough recorded evidence for grading."
                  />
                )}
              </>
            )}
          </div>
          <div className="inspector-retest">
            <span>Keep this task and condition as a focused test.</span>
            <Button onClick={() => onRetest(run)}>
              <RotateCcw size={14} /> Retest this case
            </Button>
          </div>
          <div className="inspector-footer">
            <span className="mono">{id}</span>
            <span>
              {run.tool_calls == null
                ? "Unknown tool usage"
                : `${number(run.tool_calls)} tool calls`}{" "}
              ·{" "}
              {run.model_calls == null
                ? "Unknown model usage"
                : `${number(run.model_calls)} model calls`}
              {" · "}
              {run.steps == null
                ? "Unknown steps"
                : `${number(run.steps)} steps`}
            </span>
          </div>
        </>
      ) : (
        !error && <Skeleton />
      )}
    </dialog>
  );
}
