import { useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Bot,
  FlaskConical,
  Layers,
  Play,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { post, errorMessage } from "../lib/api";
import type {
  Agent,
  Catalog,
  Experiment,
  ExperimentPreset,
  ExperimentSpec,
  Source,
  Task,
} from "../types";
import { Button, Modal, Notice, SelectCard } from "./ui";

const toggle = (values: string[], value: string) =>
  values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];

export function ExperimentForm({
  catalog,
  initial,
  preset,
  onClose,
  onCreated,
}: {
  catalog: Catalog;
  initial?: ExperimentSpec;
  preset?: ExperimentPreset;
  onClose: () => void;
  onCreated: (experiment: Experiment) => void;
}) {
  const [name, setName] = useState(
    initial ? `${initial.name} · rerun` : (preset?.name ?? ""),
  );
  const [agents, setAgents] = useState(
    initial?.agent_ids ??
      preset?.agent_ids ??
      catalog.agents.slice(0, 2).map((agent) => agent.id),
  );
  const [tasks, setTasks] = useState(
    initial?.task_ids ??
      preset?.task_ids ??
      catalog.tasks.slice(0, 1).map((task) => task.id),
  );
  const [scenarios, setScenarios] = useState(
    initial?.scenario_ids ??
      preset?.scenario_ids ?? ["normal", "search_timeout"],
  );
  const [engine, setEngine] = useState(
    initial?.engine ??
      preset?.engine ??
      (catalog.agents.some(
        (agent) => agents.includes(agent.id) && agent.kind === "http",
      )
        ? "bifrost"
        : "fixture"),
  );
  const [mode, setMode] = useState(
    initial?.mode ?? preset?.mode ?? "controlled",
  );
  const [model, setModel] = useState(
    initial?.model ??
      preset?.model ??
      catalog.settings?.config.model ??
      "ollama/qwen2.5-coder:7b",
  );
  const [repetitions, setRepetitions] = useState(
    initial?.repetitions ?? preset?.repetitions ?? 3,
  );
  const [timeout, setTimeout] = useState(
    initial?.limits.timeout_seconds ?? preset?.limits?.timeout_seconds ?? 120,
  );
  const [toolLimit, setToolLimit] = useState(
    initial?.limits.max_tool_calls ?? preset?.limits?.max_tool_calls ?? 6,
  );
  const [modelLimit, setModelLimit] = useState(
    initial?.limits.max_model_calls ?? preset?.limits?.max_model_calls ?? 12,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submission = useRef<{ fingerprint: string; key: string } | null>(null);
  const attempts =
    agents.length * tasks.length * scenarios.length * repetitions;
  const hasHttpAgent = catalog.agents.some(
    (agent) => agents.includes(agent.id) && agent.kind === "http",
  );
  const valid =
    name.trim().length > 0 &&
    agents.length > 0 &&
    tasks.length > 0 &&
    scenarios.length > 0 &&
    attempts <= 200 &&
    (!hasHttpAgent ||
      (engine === "bifrost" &&
        mode === "controlled" &&
        scenarios.length === 1 &&
        scenarios[0] === "normal")) &&
    Number.isInteger(repetitions) &&
    repetitions >= 1 &&
    repetitions <= 5 &&
    !(
      mode === "live" &&
      (!catalog.settings?.integrations.tavily.configured ||
        catalog.agents.some(
          (agent) => agents.includes(agent.id) && agent.kind === "http",
        ))
    );
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError("");
    const spec = {
      name: name.trim(),
      agent_ids: agents,
      task_ids: tasks,
      scenario_ids: scenarios,
      repetitions,
      engine,
      mode,
      model,
      limits: {
        timeout_seconds: timeout,
        max_tool_calls: toolLimit,
        max_model_calls: modelLimit,
      },
    };
    const fingerprint = JSON.stringify(spec);
    if (submission.current?.fingerprint !== fingerprint)
      submission.current = { fingerprint, key: crypto.randomUUID() };
    try {
      onCreated(
        await post<Experiment>("/experiments", spec, submission.current.key),
      );
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };
  return (
    <Modal
      title={initial ? "Rerun experiment" : "New experiment"}
      description="Keep conditions explicit. Every attempt starts with fresh agent state."
      onClose={onClose}
      wide
    >
      <form onSubmit={submit} className="experiment-form">
        <div className="modal-body">
          {error && <Notice kind="error">{error}</Notice>}
          <label className="field">
            Experiment name
            <input
              autoFocus
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Research recovery check"
            />
          </label>
          <div className="form-columns">
            <fieldset>
              <legend>
                <Bot size={15} />
                Agents<span>{agents.length} selected</span>
              </legend>
              <div className="selection-list">
                {catalog.agents
                  .filter((agent) => !agent.config.workspace_categories)
                  .map((agent) => (
                    <SelectCard
                      key={agent.id}
                      checked={agents.includes(agent.id)}
                      onChange={() => {
                        const next = toggle(agents, agent.id);
                        setAgents(next);
                        if (
                          catalog.agents.some(
                            (selected) =>
                              next.includes(selected.id) &&
                              selected.kind === "http",
                          )
                        ) {
                          setEngine("bifrost");
                          setMode("controlled");
                          setScenarios(["normal"]);
                        }
                      }}
                      title={agent.name}
                      description={`${agent.framework} · ${agent.version}`}
                    />
                  ))}
              </div>
            </fieldset>
            <fieldset>
              <legend>
                <Layers size={15} />
                Tasks<span>{tasks.length} selected</span>
              </legend>
              <div className="selection-list">
                {catalog.tasks.map((task) => (
                  <SelectCard
                    key={task.id}
                    checked={tasks.includes(task.id)}
                    onChange={() => setTasks(toggle(tasks, task.id))}
                    title={task.title}
                  />
                ))}
              </div>
            </fieldset>
          </div>
          <fieldset>
            <legend>
              <ShieldCheck size={15} />
              Test conditions
            </legend>
            <div className="scenario-selection">
              {catalog.scenarios.map((scenario) => (
                <SelectCard
                  key={scenario.id}
                  checked={scenarios.includes(scenario.id)}
                  disabled={hasHttpAgent && scenario.id !== "normal"}
                  onChange={() => {
                    if (!hasHttpAgent || scenario.id === "normal")
                      setScenarios(toggle(scenarios, scenario.id));
                  }}
                  title={scenario.name}
                  description={scenario.description}
                />
              ))}
            </div>
          </fieldset>
          <div className="form-columns">
            <label className="field">
              Execution engine
              <select
                value={engine}
                onChange={(event) => {
                  setEngine(event.target.value as "fixture" | "bifrost");
                  if (event.target.value === "fixture") setMode("controlled");
                }}
              >
                <option value="fixture" disabled={hasHttpAgent}>
                  Demonstration · deterministic fixture
                </option>
                <option value="bifrost">Real model · Bifrost gateway</option>
              </select>
              <small>
                {engine === "fixture"
                  ? "Exercises the runner and faults with deterministic responses. No AI token metrics."
                  : "Makes actual model requests through your configured gateway."}
              </small>
            </label>
            <label className="field">
              Research evidence
              <select
                value={mode}
                onChange={(event) =>
                  setMode(event.target.value as "controlled" | "live")
                }
              >
                <option value="controlled">
                  Controlled · fixed reference corpus
                </option>
                <option
                  value="live"
                  disabled={
                    engine === "fixture" ||
                    !catalog.settings?.integrations.tavily.configured ||
                    catalog.agents.some(
                      (agent) =>
                        agents.includes(agent.id) && agent.kind === "http",
                    )
                  }
                >
                  Live · Tavily web research
                </option>
              </select>
              <small>
                {mode === "controlled"
                  ? "All agents search the same available evidence."
                  : "Requires a Tavily key in the backend environment. Search credits apply."}
              </small>
            </label>
          </div>
          {hasHttpAgent && (
            <Notice>
              HTTP adapters provide final-output observations under normal
              controlled conditions. Their internal model, tool, and step usage
              stays unknown.
            </Notice>
          )}
          {engine === "bifrost" && (
            <>
              <label className="field">
                Model
                <input
                  required
                  value={model}
                  maxLength={120}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder="ollama/qwen2.5-coder:7b"
                />
              </label>
              {![
                "ready",
                "healthy",
                "available",
                "connected",
                "ok",
                "reachable",
              ].includes(
                catalog.settings?.integrations.bifrost.status ?? "",
              ) && (
                <Notice kind="warning">
                  Check gateway connectivity in Settings before running a
                  real-model experiment. A gateway error will remain visible.
                </Notice>
              )}
            </>
          )}
          <details className="limits-details" open>
            <summary>
              <Terminal size={15} />
              Repetitions & limits
            </summary>
            <div className="limits-grid">
              <label className="field">
                Repetitions
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={repetitions}
                  onChange={(event) =>
                    setRepetitions(Number(event.target.value))
                  }
                  required
                />
              </label>
              <label className="field">
                Time / attempt (s)
                <input
                  type="number"
                  min={5}
                  max={600}
                  value={timeout}
                  onChange={(event) => setTimeout(Number(event.target.value))}
                  required
                />
              </label>
              <label className="field">
                Tool calls / attempt
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={toolLimit}
                  onChange={(event) => setToolLimit(Number(event.target.value))}
                  required
                />
              </label>
              <label className="field">
                Model calls / attempt
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={modelLimit}
                  onChange={(event) =>
                    setModelLimit(Number(event.target.value))
                  }
                  required
                />
              </label>
            </div>
          </details>
          {attempts > 200 && (
            <Notice kind="error">
              This configuration schedules {attempts} attempts. Reduce
              selections or repetitions to stay within 200.
            </Notice>
          )}
        </div>
        <div className="modal-footer">
          <div className="attempt-preview">
            <FlaskConical size={18} />
            <span>
              <strong>{attempts} attempts</strong>
              <small>
                {agents.length} agents × {tasks.length} tasks ×{" "}
                {scenarios.length} conditions × {repetitions} trials
              </small>
            </span>
          </div>
          <div className="button-group">
            <Button type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              busy={busy}
              disabled={!valid}
            >
              <Play size={15} />
              Run experiment
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

export function AgentForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (agent: Agent) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:9000/run");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onCreated(
        await post<Agent>("/agents", {
          name,
          description,
          kind: "http",
          endpoint,
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Connect an agent"
      description="Register an existing local HTTP agent without rewriting its decision loop."
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          {error && <Notice kind="error">{error}</Notice>}
          <label className="field">
            Agent name
            <input
              autoFocus
              required
              maxLength={100}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="My research agent"
            />
          </label>
          <label className="field">
            Description
            <textarea
              maxLength={500}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What does this agent do?"
            />
          </label>
          <label className="field">
            Local run endpoint
            <input
              type="url"
              required
              maxLength={300}
              value={endpoint}
              onChange={(event) => setEndpoint(event.target.value)}
            />
          </label>
          <Notice>
            Use an explicitly registered loopback endpoint. Trace and fault
            support depend on the adapter’s declared capabilities.
          </Notice>
        </div>
        <div className="modal-footer">
          <span className="subtle">HTTP adapter</span>
          <div className="button-group">
            <Button type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" busy={busy}>
              Connect agent
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

export function AgentVersionForm({
  agent,
  onClose,
  onSaved,
}: {
  agent: Agent;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [version, setVersion] = useState("");
  const [endpoint, setEndpoint] = useState(
    typeof agent.config.endpoint === "string" ? agent.config.endpoint : "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post(`/agents/${encodeURIComponent(agent.id)}/versions`, {
        version: version.trim(),
        endpoint,
      });
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };
  return (
    <Modal
      title={`New version of ${agent.name}`}
      description="Keep the same agent identity and record a new implementation for regression testing."
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          {error && <Notice kind="error">{error}</Notice>}
          <label className="field">
            Version label
            <input
              autoFocus
              required
              maxLength={40}
              placeholder="e.g. 1.1.0"
              value={version}
              onChange={(event) => setVersion(event.target.value)}
            />
            <small>
              Use a new label. Existing experiments retain their original agent
              snapshot.
            </small>
          </label>
          <label className="field">
            Local run endpoint
            <input
              type="url"
              required
              maxLength={300}
              value={endpoint}
              onChange={(event) => setEndpoint(event.target.value)}
            />
          </label>
          <Notice>
            Run the same tasks with this version, then declare the agent change
            when comparing against your baseline.
          </Notice>
        </div>
        <div className="modal-footer">
          <span className="subtle">Current version: {agent.version}</span>
          <div className="button-group">
            <Button type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" busy={busy}>
              Register version
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

export function TaskForm({
  sources,
  onClose,
  onCreated,
}: {
  sources: Source[];
  onClose: () => void;
  onCreated: (task: Task) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [company, setCompany] = useState("");
  const [reference, setReference] = useState(
    new Date().toISOString().slice(0, 16),
  );
  const [facts, setFacts] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onCreated(
        await post<Task>("/tasks", {
          title,
          description,
          prompt,
          company,
          reference_time: new Date(`${reference}Z`).toISOString(),
          required_facts: facts
            .split("\n")
            .map((value) => value.trim())
            .filter(Boolean),
          source_ids: selected,
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Create a referenced task"
      description="Define what success looks like and which evidence is available."
      onClose={onClose}
      wide
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          {error && <Notice kind="error">{error}</Notice>}
          <div className="form-columns">
            <label className="field">
              Task title
              <input
                autoFocus
                required
                value={title}
                maxLength={120}
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
            <label className="field">
              Company or entity
              <input
                required
                value={company}
                maxLength={120}
                onChange={(event) => setCompany(event.target.value)}
              />
            </label>
          </div>
          <label className="field">
            Description
            <input
              value={description}
              maxLength={500}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <label className="field">
            Task instructions
            <textarea
              required
              minLength={10}
              value={prompt}
              maxLength={6000}
              onChange={(event) => setPrompt(event.target.value)}
              rows={4}
            />
          </label>
          <div className="form-columns">
            <label className="field">
              Expected facts · one per line
              <textarea
                required
                value={facts}
                maxLength={4000}
                onChange={(event) => setFacts(event.target.value)}
                rows={4}
              />
              <small>
                Provide at least one verifiable reference statement for the
                grader. Use one statement per line, up to 12.
              </small>
            </label>
            <label className="field">
              Reference time (UTC)
              <input
                type="datetime-local"
                required
                value={reference}
                onChange={(event) => setReference(event.target.value)}
              />
              <small>Keep this fixed for a reproducible comparison.</small>
            </label>
          </div>
          <fieldset>
            <legend>
              Available sources<span>{selected.length} selected</span>
            </legend>
            <div className="selection-list">
              {sources.map((source) => (
                <SelectCard
                  key={source.id}
                  checked={selected.includes(source.id)}
                  onChange={() => setSelected(toggle(selected, source.id))}
                  title={source.title}
                  description={source.id}
                />
              ))}
            </div>
          </fieldset>
        </div>
        <div className="modal-footer">
          <span className="subtle">Versioned reference task</span>
          <div className="button-group">
            <Button type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              busy={busy}
              disabled={
                selected.length === 0 ||
                selected.length > 12 ||
                !facts.trim() ||
                facts.split("\n").filter((value) => value.trim()).length > 12
              }
            >
              Create task
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

export function BaselineForm({
  experiment,
  onClose,
  onSaved,
}: {
  experiment: Experiment;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(experiment.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post("/baselines", { name, experiment_id: experiment.id });
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Save baseline"
      description="Pin this experiment’s conditions and results for future comparisons."
      onClose={onClose}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          {error && <Notice kind="error">{error}</Notice>}
          <label className="field">
            Baseline name
            <input
              autoFocus
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <div className="reference-strip">
            <strong>{experiment.name}</strong>
            <span className="mono">{experiment.id}</span>
          </div>
        </div>
        <div className="modal-footer">
          <span className="subtle">
            {experiment.progress.completed} recorded attempts
          </span>
          <Button type="submit" variant="primary" busy={busy}>
            Save baseline
          </Button>
        </div>
      </form>
    </Modal>
  );
}
