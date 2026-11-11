import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowUpRight,
  FileDown,
  MessageSquare,
  Plus,
  Send,
  Square,
} from "lucide-react";
import type { Catalog, Experiment } from "../types";
import type {
  Category,
  Conversation,
  WorkspaceRun,
  TaskCheck,
  Readiness,
} from "../workspace-types";
import { TaskCheckEditor, CheckComparison } from "./task-checks";
import TruncatedText from "./promptfoo/TruncatedText";
import {
  api,
  downloadConversation,
  downloadEvaluation,
  errorMessage,
  post,
} from "../lib/api";
import { active } from "../lib/format";
import { Badge, Button, EmptyState, Notice, PageHeader } from "./ui";

const descriptions: Record<Category, string> = {
  chat: "One task. Two independent answers. Inspect the evidence and compare what each agent actually did.",
  repository:
    "Capture a repository, inspect code findings and trace every reference to the same source snapshot.",
  documents:
    "Ask questions across your documents, with captured passages and page references.",
  website:
    "Analyze a bounded set of public pages and inspect the source behind each finding.",
  search:
    "Research a question with optional live search and shared, traceable sources.",
};
const names: Record<Category, string> = {
  chat: "Chat",
  repository: "Repository",
  documents: "Documents",
  website: "Website",
  search: "Search",
};

function AgentResponse({
  run,
  model,
  conversational = false,
}: {
  run: WorkspaceRun;
  model: string;
  conversational?: boolean;
}) {
  const metric = run.assessment?.metrics;
  const inputFailed = run.events.some((event) => event.type === "input_error");
  const observations =
    run.assessment?.observations ??
    (conversational ? run.assessment?.findings : []);
  return (
    <article className="panel agent-response">
      <header>
        <div>
          <strong>{run.agent_name}</strong>
          <small>{model}</small>
        </div>
        <Badge status={run.outcome}>
          {inputFailed ? "Source capture failed" : undefined}
        </Badge>
      </header>
      <div className="agent-response-body">
        {run.output ? (
          <div className="response-text">
            <TruncatedText
              key={run.id}
              text={run.output.summary}
              maxLength={1400}
            />
          </div>
        ) : active(run.outcome) ? (
          <p role="status">
            {run.outcome === "queued"
              ? "Waiting for its independent turn…"
              : "Working from the shared snapshot…"}
          </p>
        ) : (
          <Notice kind="warning">
            {run.assessment?.checks.map((check) => check.evidence).join(" ") ||
              "No response was recorded."}
          </Notice>
        )}
        {conversational && run.output && (
          <p className="muted">
            Conversation response · no sources supplied. Factual accuracy has
            not been verified.
          </p>
        )}
        {conversational && !!observations?.length && (
          <details>
            <summary>Additional response notes · not evidence-verified</summary>
            {observations.map((item, index) => (
              <p key={index}>
                <strong>{item.title}</strong>: {item.claim}
              </p>
            ))}
          </details>
        )}
        {!conversational && !!run.assessment?.findings?.length && (
          <div className="workspace-findings">
            <h3>Findings & evidence</h3>
            {run.assessment.findings.map((finding) => (
              <details key={finding.id}>
                <summary>
                  <span>{finding.title}</span>
                  <Badge
                    status={
                      finding.verification.state === "VERIFIED"
                        ? "pass"
                        : "inconclusive"
                    }
                  >
                    {finding.verification.state}
                  </Badge>
                </summary>
                <p>{finding.claim}</p>
                <p className="muted">{finding.explanation}</p>
                <small>
                  {finding.verification.scope} · {finding.verification.method}
                </small>
                {finding.verification.citations.map((citation, index) => (
                  <blockquote key={index}>
                    <strong>
                      {citation.source_reference || citation.source_id}
                    </strong>
                    <small>
                      {citation.page ? `Page ${citation.page} · ` : ""}
                      {citation.start_line
                        ? `Lines ${citation.start_line}–${citation.end_line}`
                        : "Captured passage"}{" "}
                      ·{" "}
                      {citation.valid
                        ? "Reference matched"
                        : "Invalid reference"}
                    </small>
                    <pre>{citation.captured_content ?? citation.quote}</pre>
                    <small>{citation.matching_method}</small>
                    {citation.reasons.map((reason) => (
                      <p key={reason}>{reason}</p>
                    ))}
                  </blockquote>
                ))}
              </details>
            ))}
          </div>
        )}
      </div>
      <footer>
        <span>
          {inputFailed
            ? "Agent not started"
            : run.duration_ms == null
              ? "Unknown latency"
              : `${(run.duration_ms / 1000).toFixed(1)}s`}
        </span>
        <span>
          Tokens:{" "}
          {run.input_tokens == null || run.output_tokens == null
            ? "Unknown"
            : run.input_tokens + run.output_tokens}
        </span>
        <span>
          Citations:{" "}
          {metric?.citation_validity == null
            ? conversational
              ? "Not applicable"
              : "Not assessed"
            : `${Math.round(metric.citation_validity * 100)}% valid`}
        </span>
      </footer>
      <details className="workspace-trace">
        <summary>Execution trace · {run.events.length} events</summary>
        {run.events.map((event) => (
          <div key={event.sequence}>
            <small>{event.timestamp}</small>
            <strong>{event.title}</strong>
            <pre>{JSON.stringify(event.data, null, 2)}</pre>
          </div>
        ))}
      </details>
    </article>
  );
}

export function WorkspaceView({
  category,
  catalog,
}: {
  category: Category;
  catalog: Catalog;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const currentSelection = useRef("");
  const selectConversation = (id: string) => {
    currentSelection.current = id;
    setSelectedId(id);
    setSelected(null);
  };
  const [message, setMessage] = useState("");
  const [context, setContext] = useState("");
  const [url, setUrl] = useState("");
  const [uploads, setUploads] = useState<{ id: string; name: string }[]>([]);
  const [agentA, setAgentA] = useState("scout");
  const [agentB, setAgentB] = useState("relay");
  const [search, setSearch] = useState<"off" | "tavily">("off");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reportFormat, setReportFormat] = useState<
    "pdf" | "md" | "json" | "csv"
  >("pdf");
  const [maxPages, setMaxPages] = useState(3);
  const [maxDepth, setMaxDepth] = useState(1);
  const [runTests, setRunTests] = useState(false);
  const [dependencyAdvisories, setDependencyAdvisories] = useState(false);
  const [semanticReview, setSemanticReview] = useState(false);
  const [checks, setChecks] = useState<TaskCheck[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const submission = useRef<{ payload: string; key: string } | null>(null);
  const model =
    selected?.model ??
    catalog.settings?.config.model ??
    "ollama/qwen2.5-coder:7b";
  const refresh = useCallback(async () => {
    const requestedId = currentSelection.current;
    try {
      setConversations(await api<Conversation[]>("/workspace/conversations"));
      if (requestedId) {
        const value = await api<Conversation>(
          `/workspace/conversations/${requestedId}`,
        );
        if (currentSelection.current === requestedId) setSelected(value);
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);
  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 2500);
    return () => {
      clearTimeout(initial);
      clearInterval(timer);
    };
  }, [refresh, selectedId]);
  const pending =
    selected?.turns?.some(
      (turn) =>
        active(turn.experiment.state) ||
        turn.retry_experiments?.some((retry) => active(retry.state)),
    ) ?? false;
  const orderedRuns = (runs: WorkspaceRun[]) =>
    [...runs].sort(
      (a, b) =>
        (selected?.agent_ids.indexOf(a.agent_id) ?? 0) -
        (selected?.agent_ids.indexOf(b.agent_id) ?? 0),
    );
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      let conversation = selected;
      const configuration = {
        title: message.slice(0, 100),
        category,
        agent_ids: conversation?.agent_ids ?? [agentA, agentB],
        model,
        search_provider: conversation?.search_provider ?? search,
        semantic_review: semanticReview,
      };
      const ready = await post<Readiness>("/workspace/preflight", {
        configuration,
        require_checks: checks.length > 0,
      });
      setReadiness(ready);
      if (!ready.ready)
        throw new Error(
          "Resolve the readiness checks below, then send again. Your task has been kept.",
        );
      if (!conversation) {
        conversation = await post<Conversation>(
          "/workspace/conversations",
          configuration,
        );
        selectConversation(conversation.id);
        setSelected(conversation);
      }
      const payload = {
        message,
        checks,
        inputs: {
          text: context,
          ...(url ? { url } : {}),
          upload_ids: uploads.map((upload) => upload.id),
          max_pages: maxPages,
          max_depth: maxDepth,
          run_tests: runTests,
          dependency_advisories: dependencyAdvisories,
        },
      };
      const identity = JSON.stringify([conversation.id, payload]);
      if (submission.current?.payload !== identity)
        submission.current = { payload: identity, key: crypto.randomUUID() };
      await post<Experiment>(
        `/workspace/conversations/${conversation.id}/turns`,
        payload,
        submission.current.key,
      );
      submission.current = null;
      selectConversation(conversation.id);
      setSelected(
        await api<Conversation>(`/workspace/conversations/${conversation.id}`),
      );
      setMessage("");
      setContext("");
      setUrl("");
      setUploads([]);
      setChecks([]);
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const cancel = async (id: string) => {
    try {
      await post(`/experiments/${id}/cancel`, {});
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  const retryResponse = async (runId: string) => {
    setBusy(true);
    setError("");
    setChecks([]);
    setReadiness(null);
    try {
      await post(`/workspace/runs/${runId}/retry`, {});
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const newChat = () => {
    selectConversation("");
    setSelected(null);
    setMessage("");
    setContext("");
    setUploads([]);
    setError("");
  };
  const exportReport = async (id: string) => {
    try {
      await downloadEvaluation(id, reportFormat);
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  const uploadFiles = async (files: FileList | null) => {
    if (!files) return;
    setBusy(true);
    setError("");
    try {
      const next: { id: string; name: string }[] = [];
      for (const file of Array.from(files)) {
        if (file.size > 8_000_000)
          throw new Error("Files must be 8 MB or smaller.");
        next.push(
          await api<{ id: string; name: string }>("/workspace/uploads", {
            method: "POST",
            body: file,
            headers: {
              "Content-Type": "application/octet-stream",
              "X-Filename": encodeURIComponent(file.name),
            },
          }),
        );
      }
      setUploads((previous) => [...previous, ...next]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const retest = async (id: string) => {
    setBusy(true);
    try {
      const exp = await post<Experiment>(
        `/workspace/evaluations/${id}/retest`,
        {},
      );
      const task = exp.manifest?.workspace as
        { conversation_id?: string } | undefined;
      if (task?.conversation_id) {
        selectConversation(task.conversation_id);
        setSelected(
          await api<Conversation>(
            `/workspace/conversations/${task.conversation_id}`,
          ),
        );
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <PageHeader
        title={names[category]}
        description={descriptions[category]}
        actions={
          <div className="header-actions">
            {selected && (
              <Button
                onClick={() =>
                  void downloadConversation(selected.id).catch((err) =>
                    setError(errorMessage(err)),
                  )
                }
              >
                <FileDown size={16} />
                Export conversation
              </Button>
            )}
            <Button onClick={newChat}>
              <Plus size={16} />
              New {category === "chat" ? "conversation" : "analysis"}
            </Button>
          </div>
        }
      />
      {error && <Notice kind="error">{error}</Notice>}
      <div className="workspace-history-bar">
        <label className="field">
          Saved conversations
          <select
            value={selectedId}
            onChange={(event) => {
              selectConversation(event.target.value);
            }}
          >
            <option value="">New conversation</option>
            {conversations
              .filter((c) => c.category === category)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
          </select>
        </label>
        <label className="field">
          Report format
          <select
            value={reportFormat}
            onChange={(event) =>
              setReportFormat(event.target.value as typeof reportFormat)
            }
          >
            <option value="pdf">PDF</option>
            <option value="md">Markdown</option>
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
          </select>
        </label>
        <span className="muted">Local workspace · {model}</span>
      </div>
      {!selected?.turns?.length && (
        <section className="panel workspace-intro">
          <MessageSquare size={25} />
          <div>
            <h2>See the work behind the answer</h2>
            <p>
              Both agents receive the same task and sources. Each keeps its own
              history. Evidence checks stay separate from answer generation.
            </p>
          </div>
        </section>
      )}
      {!selected && (
        <label className="comparison-option">
          <input
            type="checkbox"
            checked={semanticReview}
            onChange={(event) => setSemanticReview(event.target.checked)}
          />
          <span>
            Independent semantic review
            <small>
              Adds a separate local model call after both answers. Advisory
              judgments stay separate from deterministic evidence checks.
            </small>
          </span>
        </label>
      )}
      {selected?.turns?.map((turn, index) => (
        <section className="workspace-turn" key={turn.id}>
          <header className="workspace-turn-heading">
            <div>
              <small>
                Shared task {index + 1} ·{" "}
                {new Date(turn.created_at).toLocaleString()}
              </small>
              <h2>{turn.message}</h2>
            </div>
            <div className="header-actions">
              <Badge status={turn.experiment.state} />
              {active(turn.experiment.state) ? (
                <Button
                  variant="danger"
                  onClick={() => void cancel(turn.experiment.id)}
                >
                  <Square size={14} />
                  Cancel
                </Button>
              ) : (
                <>
                  <Button onClick={() => void exportReport(turn.experiment.id)}>
                    <FileDown size={15} />
                    Export {reportFormat.toUpperCase()}
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() => void retest(turn.experiment.id)}
                  >
                    {turn.experiment.manifest?.snapshot
                      ? "Retest"
                      : "Retry source capture"}
                  </Button>
                </>
              )}
              <a
                href={`#/experiments/${turn.experiment.id}`}
                className="button button-ghost"
              >
                Inspect run
                <ArrowUpRight size={14} />
              </a>
            </div>
          </header>
          <div className="paired-responses">
            {orderedRuns(turn.runs).map((run) => (
              <div key={run.id}>
                <AgentResponse
                  run={run}
                  model={selected.model}
                  conversational={
                    selected.category === "chat" &&
                    Array.isArray(turn.experiment.manifest?.sources) &&
                    turn.experiment.manifest.sources.length === 0
                  }
                />
                {!pending &&
                  !!turn.experiment.manifest?.snapshot &&
                  index === (selected?.turns?.length ?? 0) - 1 &&
                  run.outcome !== "completed" && (
                    <Button
                      disabled={busy}
                      onClick={() => void retryResponse(run.id)}
                    >
                      Retry {run.agent_name} response
                    </Button>
                  )}
              </div>
            ))}
          </div>
          {!!turn.retry_experiments?.length && (
            <details className="comparison-note">
              <summary>Response retries · original attempts preserved</summary>
              {turn.retry_experiments.map((retry) => (
                <div key={retry.id}>
                  <a href={`#/experiments/${retry.id}`}>{retry.name}</a>{" "}
                  <Badge status={retry.state} />
                  {active(retry.state) && (
                    <Button onClick={() => void cancel(retry.id)}>
                      Cancel retry
                    </Button>
                  )}
                </div>
              ))}
              <small>
                Original reports retain their original attempts. Retry reports
                and traces are separate.
              </small>
            </details>
          )}
          {!active(turn.experiment.state) && (
            <CheckComparison
              key={turn.id}
              runs={orderedRuns(turn.runs)}
              comparison={
                turn.artifacts?.find(
                  (artifact) => artifact.kind === "comparison",
                )?.data as
                  | {
                      explanation?: string;
                      verdict?: string;
                      winner?: string | null;
                    }
                  | undefined
              }
              retryChanged={!!turn.retry_experiments?.length}
              onSave={
                turn.experiment.state === "completed" &&
                !turn.retry_experiments?.length
                  ? async () => {
                      await post("/workspace/suites", {
                        name:
                          turn.message.slice(0, 80) +
                          " · " +
                          turn.experiment.id.slice(-6),
                        version: "1",
                        source_experiment_id: turn.experiment.id,
                        repetitions: 1,
                      });
                    }
                  : undefined
              }
            />
          )}
          {!active(turn.experiment.state) && (
            <div className="comparison-note">
              <strong>Evidence and execution details</strong>
              <p>
                {turn.runs.filter((run) => run.outcome === "completed").length}
                /2 agents completed. Task check results above are separate from
                factual accuracy and evidence verification.
              </p>
              {turn.artifacts
                ?.filter((artifact) => artifact.kind !== "comparison")
                .map((artifact) => (
                  <details key={artifact.id}>
                    <summary>
                      {artifact.kind === "semantic_review"
                        ? "Independent semantic review (advisory)"
                        : "Structured finding comparison"}
                    </summary>
                    <pre className="management-result">
                      {JSON.stringify(artifact.data, null, 2)}
                    </pre>
                  </details>
                ))}
              <details>
                <summary>Captured source and execution conditions</summary>
                <pre className="management-result">
                  {JSON.stringify(
                    {
                      snapshot: turn.experiment.manifest?.snapshot,
                      selection: turn.experiment.manifest?.selection,
                      rubric: turn.experiment.manifest?.rubric,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </div>
          )}
        </section>
      ))}
      <form className="panel workspace-composer" onSubmit={submit}>
        {readiness && (
          <details className="readiness-checks" open={!readiness.ready}>
            <summary>
              Readiness check ·{" "}
              {readiness.ready ? "dependencies available" : "action needed"}
            </summary>
            {readiness.checks.map((check) => (
              <p key={check.name}>
                <Badge
                  status={
                    check.ready === true
                      ? "ready"
                      : check.ready === false
                        ? "unavailable"
                        : "unknown"
                  }
                >
                  {check.name}
                </Badge>{" "}
                {check.detail}
              </p>
            ))}
            <small>{readiness.scope}</small>
          </details>
        )}
        {category === "repository" && (
          <label className="comparison-option">
            <input
              type="checkbox"
              checked={dependencyAdvisories}
              onChange={(event) =>
                setDependencyAdvisories(event.target.checked)
              }
            />
            <span>
              Check known dependency advisories
              <small>
                Sends captured package names and exact versions to OSV. No
                repository source is sent. Supports package-lock.json and pinned
                requirements.txt.
              </small>
            </span>
          </label>
        )}
        {!selected && (
          <div className="workspace-controls">
            {[
              ["Agent A", agentA, setAgentA],
              ["Agent B", agentB, setAgentB],
            ].map(([label, value, setter]) => (
              <label className="field" key={label as string}>
                {label as string}
                <select
                  value={value as string}
                  onChange={(event) =>
                    (setter as (value: string) => void)(event.target.value)
                  }
                >
                  {catalog.agents
                    .filter(
                      (agent) =>
                        ["scout", "relay"].includes(agent.id) ||
                        (Array.isArray(agent.config.workspace_categories) &&
                          agent.config.workspace_categories.includes(category)),
                    )
                    .map((agent) => (
                      <option value={agent.id} key={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                </select>
              </label>
            ))}
            <label className="field">
              Web search
              <select
                aria-label="Web search"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value as "off" | "tavily")
                }
              >
                <option value="off">Off · no Tavily credits</option>
                <option
                  value="tavily"
                  disabled={!catalog.settings?.integrations.tavily.configured}
                >
                  Tavily · live sources
                  {!catalog.settings?.integrations.tavily.configured
                    ? " · key required"
                    : ""}
                </option>
              </select>
            </label>
          </div>
        )}
        <label className="field">
          {selected
            ? "Send the same follow-up to both agents"
            : "What should the agents do?"}
          <textarea
            required
            maxLength={6000}
            rows={4}
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder={
              category === "chat"
                ? "Explain a design decision, compare approaches, or ask a question…"
                : "Describe what to analyze and what evidence matters…"
            }
          />
        </label>
        {(category === "repository" || category === "website") && (
          <label className="field">
            {category === "repository"
              ? "GitHub repository URL"
              : "Public website URL"}
            <input
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder={
                category === "repository"
                  ? "https://github.com/owner/repository"
                  : "https://example.org"
              }
            />
          </label>
        )}
        {(category === "repository" ||
          category === "documents" ||
          category === "chat") && (
          <label className="field">
            {category === "repository"
              ? "Repository ZIP (optional alternative to URL)"
              : "Attach documents · PDF, DOCX, TXT, Markdown"}
            <input
              type="file"
              multiple={category !== "repository"}
              accept={
                category === "repository" ? ".zip" : ".pdf,.docx,.txt,.md"
              }
              onChange={(event) => void uploadFiles(event.target.files)}
              disabled={busy || pending}
            />
            <small>
              Up to 8 MB each. Scanned PDFs use local Tesseract OCR when installed.
            </small>
          </label>
        )}
        {!!uploads.length && (
          <div className="upload-list">
            {uploads.map((upload) => (
              <span key={upload.id}>
                {upload.name}
                <Button
                  variant="ghost"
                  type="button"
                  onClick={() =>
                    setUploads((items) =>
                      items.filter((item) => item.id !== upload.id),
                    )
                  }
                >
                  Remove
                </Button>
              </span>
            ))}
          </div>
        )}
        {category === "website" && (
          <div className="workspace-controls">
            <label className="field">
              Maximum pages
              <input
                type="number"
                min={1}
                max={10}
                value={maxPages}
                onChange={(event) => setMaxPages(Number(event.target.value))}
              />
            </label>
            <label className="field">
              Crawl depth
              <input
                type="number"
                min={0}
                max={2}
                value={maxDepth}
                onChange={(event) => setMaxDepth(Number(event.target.value))}
              />
            </label>
          </div>
        )}
        {category === "repository" && (
          <label className="comparison-option">
            <input
              type="checkbox"
              checked={runTests}
              onChange={(event) => setRunTests(event.target.checked)}
            />
            <span>
              Run Python unittest discovery in the isolated runner
              <small>
                Requires an available Docker image pinned by digest. No
                dependency installation. Unavailable runners are recorded
                explicitly.
              </small>
            </span>
          </label>
        )}
        <details>
          <summary>Supporting context</summary>
          <label className="field">
            Source text
            <textarea
              rows={4}
              maxLength={20000}
              value={context}
              onChange={(event) => setContext(event.target.value)}
              placeholder="Paste supporting text. This becomes part of the shared captured evidence."
            />
          </label>
        </details>
        <TaskCheckEditor checks={checks} onChange={setChecks} />
        <div className="composer-footer">
          <small>
            {selected?.search_provider === "tavily" ||
            (!selected && search === "tavily")
              ? "Tavily captures shared live sources. Basic search consumes credits."
              : "Search off. Uses your supplied context and local model."}
          </small>
          <Button
            variant="primary"
            type="submit"
            busy={busy}
            disabled={
              pending ||
              (!!selectedId && !selected) ||
              !message.trim() ||
              (!selected && agentA === agentB)
            }
          >
            <Send size={15} />
            {pending ? "Agents are working" : "Send to both agents"}
          </Button>
        </div>
        {!catalog.settings?.integrations.tavily.configured && !selected && (
          <small className="muted">
            Tavily is optional. Configure TAVILY_API_KEY privately and restart
            services to enable live search.
          </small>
        )}
        <small className="muted">
          Local model input is bounded. Long histories are rejected with a clear
          error; start a new conversation when the configured context budget is
          reached.
        </small>
      </form>
      {!conversations.length && !selected && (
        <EmptyState
          title="Your history starts here"
          description="Completed answers, evidence, failures and traces stay in this workspace."
        />
      )}
    </>
  );
}
