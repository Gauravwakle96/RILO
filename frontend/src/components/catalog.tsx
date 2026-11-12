import { useEffect, useState } from "react";
import { LocalStorage } from "./local-product";
import type { FormEvent } from "react";
import {
  ArrowRight,
  BookOpen,
  Bot,
  CheckCircle2,
  Code2,
  ExternalLink,
  FileCheck2,
  GitCompareArrows,
  Globe2,
  Link2,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldAlert,
  Terminal,
  Timer,
  Unplug,
  Zap,
} from "lucide-react";
import { api, errorMessage, post } from "../lib/api";
import { AgentVersionForm } from "./forms";
import { active, date, day, duration, human, rate } from "../lib/format";
import type {
  Agent,
  Catalog,
  Comparison,
  JsonObject,
  Settings,
} from "../types";
import {
  Badge,
  Button,
  EmptyState,
  JsonBlock,
  Notice,
  PageHeader,
  SectionTitle,
} from "./ui";

export function AgentsView({
  catalog,
  onAdd,
  onNew,
  onRefresh,
}: {
  catalog: Catalog;
  onAdd: () => void;
  onNew: (agentId?: string) => void;
  onRefresh: () => Promise<void>;
}) {
  const [checks, setChecks] = useState<Record<string, JsonObject>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [versionAgent, setVersionAgent] = useState<Agent | null>(null);
  const [category, setCategory] = useState("all");
  const [profiles, setProfiles] = useState<
    Record<
      string,
      {
        category: string;
        supported_tasks: string[];
        input_formats: string[];
        model_requirements: string;
        tools: string[];
        limitations: string[];
        status: string;
        execution_configuration: JsonObject;
      }
    >
  >({});
  useEffect(() => {
    api<((typeof profiles)[string] & { id: string })[]>("/workspace/profiles")
      .then((items) =>
        setProfiles(Object.fromEntries(items.map((item) => [item.id, item]))),
      )
      .catch((err) => setError(errorMessage(err)));
  }, []);
  const check = async (id: string) => {
    setBusy(id);
    setError("");
    try {
      const result = await post<JsonObject>(`/agents/${id}/check`, {});
      setChecks((previous) => ({ ...previous, [id]: result }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy("");
    }
  };
  return (
    <>
      <PageHeader
        title="Agents"
        description="Connect existing implementations. Keep their behavior and capabilities visible."
        actions={
          <Button variant="primary" onClick={onAdd}>
            <Plus size={16} />
            Connect agent
          </Button>
        }
      />
      {error && (
        <Notice kind="error" onDismiss={() => setError("")}>
          {error}
        </Notice>
      )}
      <label className="field">
        Agent category
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="all">All agents</option>
          {[
            "chat",
            "repository",
            "documents",
            "website",
            "search",
            "custom",
          ].map((item) => (
            <option key={item} value={item}>
              {human(item)}
            </option>
          ))}
        </select>
      </label>
      <div className="agent-grid">
        {catalog.agents
          .filter(
            (agent) =>
              category === "all" ||
              (category === "custom"
                ? agent.kind === "http"
                : profiles[agent.id]?.supported_tasks.includes(category)),
          )
          .map((agent) => (
            <article className="panel agent-panel" key={agent.id}>
              <div className="agent-panel-top">
                <span
                  className={`agent-mark ${agent.id === "relay" ? "green" : "blue"}`}
                >
                  <Bot size={23} />
                </span>
                <Badge>
                  {agent.kind === "http"
                    ? "Registered adapter"
                    : "Included agent"}
                </Badge>
              </div>
              <div className="agent-heading">
                <h2>{agent.name}</h2>
                <span className="mono">{agent.version}</span>
              </div>
              <p>{agent.description}</p>
              <div className="agent-framework">
                <Code2 size={15} />
                <span>{agent.framework}</span>
              </div>
              <div className="capabilities">
                <span className="small-label">Declared capabilities</span>
                <div>
                  {agent.capabilities.map((capability) => (
                    <span key={capability}>
                      <CheckCircle2 size={12} />
                      {human(capability)}
                    </span>
                  ))}
                </div>
              </div>
              {checks[agent.id] && (
                <div className="check-result">
                  <span className="small-label">Connection check</span>
                  <JsonBlock value={checks[agent.id]} />
                </div>
              )}
              {profiles[agent.id] && (
                <details className="profile-details">
                  <summary>Requirements and supported tasks</summary>
                  <p>{profiles[agent.id].model_requirements}</p>
                  <p>
                    Tasks:{" "}
                    {profiles[agent.id].supported_tasks.join(", ") ||
                      "Research benchmarks only"}
                  </p>
                  <p>
                    Inputs:{" "}
                    {profiles[agent.id].input_formats.join(", ") ||
                      "Existing HTTP research contract"}
                  </p>
                  <p>
                    Tools:{" "}
                    {profiles[agent.id].tools.join(", ") ||
                      "Opaque external execution"}
                  </p>
                  <p>{profiles[agent.id].limitations.join(". ")}</p>
                  <p>{human(profiles[agent.id].status)}</p>
                </details>
              )}
              <div className="panel-actions">
                {agent.kind === "http" && (
                  <Button onClick={() => setVersionAgent(agent)}>
                    New version
                  </Button>
                )}
                <Button
                  busy={busy === agent.id}
                  onClick={() => void check(agent.id)}
                >
                  <Link2 size={14} />
                  Check connection
                </Button>
                {Array.isArray(agent.config.workspace_categories) &&
                agent.config.workspace_categories.length > 0 ? (
                  <a
                    className="button button-ghost"
                    href={`#/${agent.config.workspace_categories[0]}`}
                  >
                    Open {String(agent.config.workspace_categories[0])}
                    <ArrowRight size={14} />
                  </a>
                ) : (
                  <Button variant="ghost" onClick={() => onNew(agent.id)}>
                    Test agent
                    <ArrowRight size={14} />
                  </Button>
                )}
              </div>
            </article>
          ))}
      </div>
      {versionAgent && (
        <AgentVersionForm
          agent={versionAgent}
          onClose={() => setVersionAgent(null)}
          onSaved={() => {
            setVersionAgent(null);
            void onRefresh();
          }}
        />
      )}
      <div className="next-step-strip">
        <Terminal size={24} />
        <div>
          <h3>Your agent keeps its own decision loop</h3>
          <p>
            Connect a local HTTP entry point. Observation and failure testing
            depend on what the adapter exposes.
          </p>
        </div>
      </div>
    </>
  );
}

export function TasksView({
  catalog,
  onAdd,
  onNew,
}: {
  catalog: Catalog;
  onAdd: () => void;
  onNew: () => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <>
      <PageHeader
        title="Tasks"
        description="Representative work, explicit references, and a clear definition of success."
        actions={
          <Button variant="primary" onClick={onAdd}>
            <Plus size={16} />
            Create task
          </Button>
        }
      />
      <div className="library-heading">
        <div className="library-title">
          <span className="library-icon">
            <BookOpen size={20} />
          </span>
          <div>
            <h2>Research reliability suite</h2>
            <p>
              {catalog.tasks.length} referenced tasks · controlled source corpus
            </p>
          </div>
        </div>
        <Button onClick={onNew}>
          <PlayIcon />
          Run suite
        </Button>
      </div>
      <section className="panel task-library">
        {catalog.tasks.map((task, index) => (
          <article
            className={`task-row ${open === task.id ? "expanded" : ""}`}
            key={task.id}
          >
            <button
              className="task-summary"
              onClick={() => setOpen(open === task.id ? null : task.id)}
              aria-expanded={open === task.id}
            >
              <span className="task-number mono">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h3>{task.title}</h3>
                <p>{task.description}</p>
              </div>
              <div className="task-meta">
                <span>{task.required_facts.length} reference facts</span>
                <small>{task.source_ids.length} sources</small>
              </div>
              <ArrowRight size={17} />
            </button>
            {open === task.id && (
              <div className="task-expanded">
                <div>
                  <span className="small-label">Task instructions</span>
                  <p className="task-prompt">{task.prompt}</p>
                  <div className="task-reference">
                    <span>{task.company}</span>
                    <span>Reference time: {day(task.reference_time)}</span>
                  </div>
                </div>
                <div>
                  <span className="small-label">Expected facts</span>
                  <ul>
                    {task.required_facts.map((fact, i) => (
                      <li key={i}>{fact}</li>
                    ))}
                  </ul>
                  <div className="source-tags">
                    {task.source_ids.map((id) => (
                      <span className="mono" key={id}>
                        {id}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </article>
        ))}
      </section>
      <Notice>
        Reference facts are grader inputs. Every comparison pins task, source,
        and rubric versions so changes remain inspectable.
      </Notice>
    </>
  );
}

function PlayIcon() {
  return <Zap size={14} />;
}

export function ScenariosView({
  catalog,
  onNew,
}: {
  catalog: Catalog;
  onNew: () => void;
}) {
  const icons = {
    normal: CheckCircle2,
    search_timeout: Timer,
    model_outage: Unplug,
    prompt_injection: ShieldAlert,
  };
  return (
    <>
      <PageHeader
        title="Scenarios"
        description="Reproduce difficult conditions without disrupting real external services."
        actions={
          <Button variant="primary" onClick={onNew}>
            <Plus size={15} />
            Run a scenario
          </Button>
        }
      />
      <div className="scenario-grid">
        {catalog.scenarios.map((scenario) => {
          const Icon = icons[scenario.id as keyof typeof icons] ?? ShieldAlert;
          return (
            <article className="panel scenario-card" key={scenario.id}>
              <div
                className={`scenario-symbol ${scenario.id === "normal" ? "good" : "warning"}`}
              >
                <Icon size={24} />
              </div>
              <span className="small-label">
                {scenario.id === "normal"
                  ? "Baseline condition"
                  : "Controlled fault"}
              </span>
              <h2>{scenario.name}</h2>
              <p>{scenario.description}</p>
              <div className="scenario-footer">
                <span className="mono">{scenario.id}</span>
                <Badge>
                  {scenario.id === "normal" ? "Baseline" : "Activation tracked"}
                </Badge>
              </div>
            </article>
          );
        })}
      </div>
      <section className="panel padded-panel">
        <SectionTitle
          title="Exposure comes before recovery"
          caption="A scenario that never activates is not a successful recovery test."
        />
        <div className="principle-grid">
          <div>
            <strong>Bounded effects</strong>
            <p>
              Faults occur at the test boundary. Limits and cancellation remain
              active.
            </p>
          </div>
          <div>
            <strong>Observable outcomes</strong>
            <p>
              Trace events record when a fault is delivered and how the agent
              responds.
            </p>
          </div>
          <div>
            <strong>Same conditions</strong>
            <p>Pin scenario versions and repeat attempts with fresh state.</p>
          </div>
        </div>
      </section>
    </>
  );
}

export function EvidenceView({ catalog }: { catalog: Catalog }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const sources = catalog.sources.filter((source) =>
    `${source.title} ${source.content} ${source.entity_id}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const chosen = sources.find((source) => source.id === selected) ?? sources[0];
  let liveLink = false;
  try {
    if (chosen) {
      const sourceUrl = new URL(chosen.url);
      liveLink =
        ["http:", "https:"].includes(sourceUrl.protocol) &&
        sourceUrl.hostname !== "example" &&
        !sourceUrl.hostname.endsWith(".example");
    }
  } catch {
    /* Invalid source URLs remain plain text. */
  }
  return (
    <>
      <PageHeader
        title="Evidence"
        description="Inspect the source material available to controlled research experiments."
        actions={
          <span className="count-pill">
            {catalog.sources.length} source records
          </span>
        }
      />
      <Notice>
        The bundled corpus is synthetic reference material. Controlled tests use
        this evidence; live Tavily searches are a separate execution mode.
      </Notice>
      <section className="panel evidence-layout">
        <div className="source-list">
          <label className="search-field">
            <Search size={15} />
            <input
              aria-label="Search evidence"
              placeholder="Search evidence…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          {sources.length ? (
            sources.map((source) => (
              <button
                className={`source-item ${chosen?.id === source.id ? "selected" : ""}`}
                key={source.id}
                onClick={() => setSelected(source.id)}
              >
                <FileCheck2 size={17} />
                <span>
                  <strong>{source.title}</strong>
                  <small>
                    {source.entity_id} · {day(source.published_at)}
                  </small>
                </span>
              </button>
            ))
          ) : (
            <p className="padded subtle">No matching sources.</p>
          )}
        </div>
        <div className="source-reader">
          {chosen ? (
            <>
              <span className="small-label">Source record</span>
              <h2>{chosen.title}</h2>
              <div className="source-meta">
                <Badge>{chosen.license}</Badge>
                <span>{day(chosen.published_at)}</span>
              </div>
              <div className="source-url">
                <Globe2 size={14} />
                {liveLink ? (
                  <a
                    href={chosen.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {chosen.url}
                    <ExternalLink size={12} />
                  </a>
                ) : (
                  <span className="mono">{chosen.url}</span>
                )}
              </div>
              <div className="source-content">{chosen.content}</div>
              <dl className="source-properties">
                <div>
                  <dt>Source ID</dt>
                  <dd className="mono">{chosen.id}</dd>
                </div>
                <div>
                  <dt>Entity</dt>
                  <dd>{chosen.entity_id}</dd>
                </div>
              </dl>
            </>
          ) : (
            <EmptyState
              title="No evidence available"
              description="The source library is empty or your filter has no matches."
            />
          )}
        </div>
      </section>
    </>
  );
}

export function CompareView({ catalog }: { catalog: Catalog }) {
  const eligible = catalog.experiments.filter(
    (experiment) => !active(experiment.state),
  );
  const [baseline, setBaseline] = useState("");
  const [candidate, setCandidate] = useState("");
  const [allowAgentChanges, setAllowAgentChanges] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setComparison(
        await post<Comparison>("/comparisons", {
          baseline_id: baseline,
          candidate_id: candidate,
          ...(allowAgentChanges ? { allow_agent_changes: true } : {}),
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader
        title="Compare"
        description="Check whether a change improves outcomes under comparable conditions."
      />
      {error && <Notice kind="error">{error}</Notice>}
      <section className="panel padded-panel">
        <SectionTitle
          title="Baseline → candidate"
          caption="A comparison checks task, scenario, model, evidence, and limit compatibility."
        />
        {eligible.length > 0 ? (
          <form className="compare-form" onSubmit={submit}>
            <label className="field">
              Baseline experiment
              <select
                required
                value={baseline}
                onChange={(event) => {
                  setBaseline(event.target.value);
                  setComparison(null);
                }}
              >
                <option value="">Choose a baseline</option>
                {eligible.map((experiment) => (
                  <option key={experiment.id} value={experiment.id}>
                    {experiment.name}
                  </option>
                ))}
              </select>
            </label>
            <GitCompareArrows size={22} />
            <label className="field">
              Candidate experiment
              <select
                required
                value={candidate}
                onChange={(event) => {
                  setCandidate(event.target.value);
                  setComparison(null);
                }}
              >
                <option value="">Choose a candidate</option>
                {eligible.map((experiment) => (
                  <option key={experiment.id} value={experiment.id}>
                    {experiment.name}
                  </option>
                ))}
              </select>
            </label>
            <Button
              type="submit"
              variant="primary"
              busy={busy}
              disabled={!baseline || !candidate || baseline === candidate}
            >
              Compare
            </Button>
            <label className="comparison-option">
              <input
                type="checkbox"
                checked={allowAgentChanges}
                onChange={(event) => {
                  setAllowAgentChanges(event.target.checked);
                  setComparison(null);
                }}
              />
              <span>
                <strong>
                  This candidate changes agent code or configuration
                </strong>
                <small>
                  Declare the agent change as the variable being tested. Tasks,
                  model, evidence, limits, and fault coverage must still match.
                </small>
              </span>
            </label>
          </form>
        ) : (
          <EmptyState
            title="Run your first comparison experiment"
            description="Completed or interrupted experiments become available here. Save a baseline once you have a useful reference."
            icon={<GitCompareArrows size={26} />}
          />
        )}
      </section>
      {comparison && (
        <>
          <section className="panel padded-panel">
            <div className="comparison-verdict">
              <span
                className={`verdict-icon ${comparison.gate.status === "pass" ? "good" : "warning"}`}
              >
                <GitCompareArrows size={25} />
              </span>
              <div>
                <h2>
                  {comparison.compatible
                    ? "Conditions are comparable"
                    : "Conditions differ"}
                </h2>
                <p>
                  {comparison.compatible
                    ? "Use the outcome and resource changes to assess the candidate."
                    : "A strict regression decision requires compatible recorded inputs."}
                </p>
              </div>
              <Badge status={comparison.gate.status} />
            </div>
            {comparison.mismatches.length > 0 && (
              <Notice kind="warning">
                Different inputs: {comparison.mismatches.join(", ")}
              </Notice>
            )}
            {!!comparison.declared_changes?.length && (
              <Notice>
                Declared candidate changes:{" "}
                {comparison.declared_changes
                  .map((change) => human(change.field))
                  .join(", ")}
              </Notice>
            )}
            <ul className="gate-reasons">
              {comparison.gate.reasons.map((reason, index) => (
                <li key={index}>{reason}</li>
              ))}
            </ul>
          </section>
          <div className="comparison-cards">
            {[comparison.baseline, comparison.candidate].map(
              (experiment, index) => (
                <section
                  className="panel padded-panel"
                  key={`${index}-${experiment.id}`}
                >
                  <span className="small-label">
                    {index === 0 ? "Baseline" : "Candidate"}
                  </span>
                  <h2>{experiment.name}</h2>
                  <div className="comparison-numbers">
                    <div>
                      <strong>{experiment.summary.passes}</strong>
                      <span>Passed</span>
                    </div>
                    <div>
                      <strong>{experiment.summary.failures}</strong>
                      <span>Failed</span>
                    </div>
                    <div>
                      <strong>
                        {experiment.summary.inconclusive +
                          experiment.summary.infrastructure_errors}
                      </strong>
                      <span>Unresolved</span>
                    </div>
                  </div>
                  {experiment.agent_metrics.map((metric) => (
                    <div className="comparison-agent" key={metric.agent_id}>
                      <strong>{metric.agent_name}</strong>
                      <span>{rate(metric.success_rate)}</span>
                      <small>{duration(metric.avg_duration_ms)}</small>
                    </div>
                  ))}
                </section>
              ),
            )}
          </div>
          {comparison.agent_deltas.length > 0 && (
            <section className="panel padded-panel">
              <SectionTitle title="Recorded changes" />
              <JsonBlock value={comparison.agent_deltas} />
            </section>
          )}
        </>
      )}
      <section className="panel">
        <SectionTitle
          title="Saved baselines"
          caption="Pinned experiments for your next change."
        />
        {catalog.baselines.length ? (
          <div className="baseline-list">
            {catalog.baselines.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setBaseline(item.experiment_id);
                  setComparison(null);
                }}
              >
                <span className="baseline-symbol">
                  <GitCompareArrows size={18} />
                </span>
                <div>
                  <strong>{item.name}</strong>
                  <small>{date(item.created_at)}</small>
                </div>
                <span className="mono">{item.experiment_id.slice(0, 12)}</span>
                <ArrowRight size={15} />
              </button>
            ))}
          </div>
        ) : (
          <div className="small-empty">
            <GitCompareArrows size={19} />
            <span>Open a completed experiment and select Save baseline.</span>
          </div>
        )}
      </section>
    </>
  );
}

export function SettingsView({
  settings,
  onRefresh,
}: {
  settings: Settings | null;
  onRefresh: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<{ url: string; model: string } | null>(
    null,
  );
  const url =
    draft?.url ?? settings?.config.bifrost_url ?? "http://127.0.0.1:8086";
  const model =
    draft?.model ?? settings?.config.model ?? "ollama/qwen2.5-coder:7b";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setSaved(false);
    setError("");
    try {
      await api("/settings", {
        method: "PATCH",
        body: JSON.stringify({ bifrost_url: url, model }),
      });
      await onRefresh();
      setDraft(null);
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const refresh = async () => {
    setBusy(true);
    try {
      await onRefresh();
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader
        title="Settings"
        description="Local execution, model connectivity, and research integration."
        actions={
          <Button busy={busy} onClick={() => void refresh()}>
            <RefreshCw size={15} />
            Check services
          </Button>
        }
      />
      <LocalStorage settings={settings} onRefresh={onRefresh} />
      {error && <Notice kind="error">{error}</Notice>}
      {saved && (
        <Notice kind="success">
          Execution settings saved. New experiments will use this configuration.
        </Notice>
      )}
      <section className="panel">
        <SectionTitle
          title="Integrations"
          caption="Real service checks. Credentials stay in the backend environment."
        />
        <div className="integration-list">
          {(
            ["bifrost", "ollama", "tavily", "agentrouter", "bynara"] as const
          ).map((name) => {
            const integration = settings?.integrations[name];
            return (
              <div className="integration-row" key={name}>
                <span className={`integration-icon integration-${name}`}>
                  {name === "tavily" ? (
                    <Globe2 size={20} />
                  ) : name === "ollama" ? (
                    <Bot size={20} />
                  ) : (
                    <Zap size={20} />
                  )}
                </span>
                <div>
                  <h3>
                    {name === "bifrost"
                      ? "Bifrost gateway"
                      : name === "ollama"
                        ? "Ollama local models"
                        : name === "agentrouter"
                          ? "AgentRouter inference"
                          : name === "bynara"
                            ? "Bynara inference"
                            : "Tavily research"}
                  </h3>
                  <p>
                    {integration?.detail ?? "Service status not yet available."}
                  </p>
                  {name === "ollama" && integration?.models?.length ? (
                    <div className="source-tags">
                      {integration.models.map((value) => (
                        <span key={value} className="mono">
                          {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <Badge status={integration?.status ?? "unknown"} />
              </div>
            );
          })}
        </div>
      </section>
      <div className="settings-grid">
        <section className="panel padded-panel">
          <SectionTitle
            title="Model execution"
            caption="Only explicitly configured local gateway endpoints are accepted."
          />
          <form onSubmit={submit}>
            <label className="field">
              Bifrost URL
              <input
                type="url"
                required
                value={url}
                onChange={(event) => {
                  setDraft({ url: event.target.value, model });
                  setSaved(false);
                }}
              />
            </label>
            <label className="field">
              Default model
              <input
                required
                value={model}
                maxLength={120}
                onChange={(event) => {
                  setDraft({ url, model: event.target.value });
                  setSaved(false);
                }}
              />
            </label>
            <Button variant="primary" type="submit" busy={busy}>
              <Settings2 size={15} />
              Save settings
            </Button>
          </form>
        </section>
        <section className="panel padded-panel">
          <SectionTitle
            title="Live web research"
            caption="Enable Tavily through the backend configuration."
          />
          <p className="settings-prose">
            Add your Tavily key to the ignored <code>.env</code> file using{" "}
            <code>TAVILY_API_KEY</code>, then restart the API and worker. Keep
            the key out of your repository and reports.
          </p>
          <div className="code-note">
            <span className="small-label">Environment variable</span>
            <code>TAVILY_API_KEY=your-key</code>
          </div>
          <p className="settings-prose">
            Controlled evidence experiments run without a Tavily key. Live
            research requires the real integration and uses your available
            search quota.
          </p>
          <p className="settings-prose">
            Each new conversation has a Web search option: Off or Tavily. Off
            uses supplied sources without search credits. A configured key
            enables selection; a completed retrieval establishes that it works.
          </p>
          <p className="settings-prose">
            The local allowance conservatively reserves the configured maximum.
            It is separate from Tavily billing, does not reset monthly, and does
            not refund cancelled reservations.
          </p>
          <span className="small-label">Local workspace · single user</span>
        </section>
      </div>
    </>
  );
}
