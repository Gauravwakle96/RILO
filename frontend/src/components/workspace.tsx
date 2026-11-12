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
import { SourcePanel } from "./source-panel";
import { CandidateRerun } from "./candidate-rerun";
import { HumanReview } from "./human-review";
import { repositoryZip } from "../lib/repository-zip";

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

function conversationFromLocation(category: Category): string {
  const [route, id] = window.location.hash.replace(/^#\/?/, "").split("/");
  return route === category && /^[a-zA-Z0-9_-]{1,80}$/.test(id || "") ? id : "";
}

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
                <HumanReview
                  runId={run.id}
                  evaluationId={run.experiment_id}
                  findingId={finding.id}
                />
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
  const [historyQuery, setHistoryQuery] = useState("");
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPages, setHistoryPages] = useState(1);
  const [renameTitle, setRenameTitle] = useState("");
  const [showRename, setShowRename] = useState(false);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [selectedId, setSelectedId] = useState(() =>
    conversationFromLocation(category),
  );
  const currentSelection = useRef(selectedId);
  const selectConversation = (id: string) => {
    currentSelection.current = id;
    setSelectedId(id);
    setSelected(null);
    window.location.hash = `/${category}${id ? `/${id}` : ""}`;
  };
  useEffect(() => {
    const changed = () => {
      const id = conversationFromLocation(category);
      if (currentSelection.current !== id) {
        currentSelection.current = id;
        setSelectedId(id);
        setSelected(null);
      }
    };
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, [category]);
  const [draft] = useState<Record<string, unknown>>(() => {
    try {
      const value = JSON.parse(
        sessionStorage.getItem(`rilo-draft-${category}`) || "{}",
      );
      return value && typeof value === "object" && !Array.isArray(value)
        ? value
        : {};
    } catch {
      return {};
    }
  });
  const [message, setMessage] = useState(
    typeof draft.message === "string" ? draft.message : "",
  );
  const [context, setContext] = useState(
    typeof draft.context === "string" ? draft.context : "",
  );
  const [url, setUrl] = useState(
    typeof draft.url === "string" ? draft.url : "",
  );
  const [modelA, setModelA] = useState("");
  const [modelB, setModelB] = useState("");
  const [instructionsA, setInstructionsA] = useState("");
  const [instructionsB, setInstructionsB] = useState("");
  const [repositoryRef, setRepositoryRef] = useState("");
  const [versionA, setVersionA] = useState("");
  const [versionB, setVersionB] = useState("");
  const [versions, setVersions] = useState<
    Record<string, { version: string }[]>
  >({});
  const [temperatureA, setTemperatureA] = useState(0);
  const [temperatureB, setTemperatureB] = useState(0);
  const [retriesA, setRetriesA] = useState("");
  const [retriesB, setRetriesB] = useState("");
  const [sourceReferences, setSourceReferences] = useState<string[]>([]);
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
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        sessionStorage.setItem(
          `rilo-draft-${category}`,
          JSON.stringify({ message, context, url }),
        );
      } catch {
        /* Drafts are optional when browser storage is disabled. */
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [category, message, context, url]);
  const submission = useRef<{ payload: string; key: string } | null>(null);
  const model =
    selected?.model ??
    catalog.settings?.config.model ??
    "ollama/qwen2.5-coder:7b";
  useEffect(() => {
    let disposed = false;
    void Promise.allSettled(
      [agentA, agentB].map(async (id) => ({
        id,
        values: await api<{ version: string }[]>(
          `/agents/${encodeURIComponent(id)}/versions`,
        ),
      })),
    ).then((results) => {
      if (disposed) return;
      const values: Record<string, { version: string }[]> = {};
      for (const result of results) {
        if (result.status === "fulfilled")
          values[result.value.id] = result.value.values;
        else setError(errorMessage(result.reason));
      }
      setVersions(values);
    });
    return () => {
      disposed = true;
    };
  }, [agentA, agentB]);
  const refresh = useCallback(async () => {
    const requestedId = currentSelection.current;
    try {
      const history = await api<{ items: Conversation[]; pages: number }>(
        `/workspace/history?kind=conversations&category=${category}&query=${encodeURIComponent(historyQuery)}&page=${historyPage}&size=50`,
      );
      setConversations(history.items);
      setHistoryPages(history.pages);
      if (requestedId) {
        const value = await api<Conversation>(
          `/workspace/conversations/${requestedId}`,
        );
        if (value.category !== category)
          throw new Error(
            "This conversation belongs to a different workspace. Open it from Reports.",
          );
        if (currentSelection.current === requestedId) setSelected(value);
      }
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [historyQuery, historyPage, category]);
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
  const latestSnapshot =
    selected?.turns?.at(-1)?.experiment?.manifest?.snapshot;
  const latestSnapshotId =
    latestSnapshot &&
    typeof latestSnapshot === "object" &&
    !Array.isArray(latestSnapshot) &&
    typeof latestSnapshot.id === "string"
      ? latestSnapshot.id
      : "";
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
        slots: conversation
          ? conversation.slots
          : [
              {
                agent_id: agentA,
                version: versionA || undefined,
                model: modelA || model,
                instructions: instructionsA,
                temperature: temperatureA,
                max_retries: retriesA ? Number(retriesA) : undefined,
              },
              {
                agent_id: agentB,
                version: versionB || undefined,
                model: modelB || model,
                instructions: instructionsB,
                temperature: temperatureB,
                max_retries: retriesB ? Number(retriesB) : undefined,
              },
            ],
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
          source_references: sourceReferences,
          max_pages: maxPages,
          max_depth: maxDepth,
          run_tests: runTests,
          dependency_advisories: dependencyAdvisories,
          ...(repositoryRef ? { repository_ref: repositoryRef } : {}),
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
      setSourceReferences([]);
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
    setUrl("");
    setSourceReferences([]);
    setUploads([]);
    setError("");
    setShowRename(false);
  };
  const exportReport = async (id: string) => {
    try {
      await downloadEvaluation(id, reportFormat);
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  const uploadFiles = async (files: FileList | File[] | null) => {
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
            {selected?.turns?.length && !pending ? (
              <Button
                onClick={() => {
                  void post<Conversation>(
                    `/workspace/conversations/${selected.id}/continue`,
                    {},
                  )
                    .then((value) => {
                      selectConversation(value.id);
                      setSelected(value);
                      setMessage("");
                    })
                    .catch((err) => setError(errorMessage(err)));
                }}
              >
                Continue with history excerpts
              </Button>
            ) : null}
          </div>
        }
      />
      {error && <Notice kind="error">{error}</Notice>}
      {selected?.continuation && (
        <Notice kind="info">
          Continuation uses the last three shared tasks and short excerpts from
          each agent’s own answers. Older text is omitted; the original full
          conversation remains saved.
        </Notice>
      )}
      <div className="product-toolbar">
        <input
          aria-label="Find conversations"
          placeholder="Find conversations"
          value={historyQuery}
          onChange={(e) => {
            setHistoryQuery(e.target.value);
            setHistoryPage(1);
          }}
        />
        <Button
          disabled={historyPage <= 1}
          onClick={() => setHistoryPage((value) => value - 1)}
        >
          Previous conversations
        </Button>
        <span>
          Page {historyPage} of {historyPages}
        </span>
        <Button
          disabled={historyPage >= historyPages}
          onClick={() => setHistoryPage((value) => value + 1)}
        >
          Next conversations
        </Button>
        {selected && (
          <Button
            onClick={() => {
              setRenameTitle(selected.title);
              setShowRename((value) => !value);
            }}
          >
            Rename conversation
          </Button>
        )}
      </div>
      {showRename && selected && (
        <form
          className="product-toolbar"
          onSubmit={(event) => {
            event.preventDefault();
            void api(`/workspace/conversations/${selected.id}`, {
              method: "PATCH",
              body: JSON.stringify({ title: renameTitle }),
            })
              .then(async () => {
                setShowRename(false);
                await refresh();
              })
              .catch((err) => setError(errorMessage(err)));
          }}
        >
          <label className="field">
            Conversation title
            <input
              required
              minLength={1}
              maxLength={120}
              value={renameTitle}
              onChange={(e) => setRenameTitle(e.target.value)}
            />
          </label>
          <Button type="submit">Save title</Button>
        </form>
      )}
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
            {selected &&
              !conversations.some((item) => item.id === selected.id) && (
                <option value={selected.id}>{selected.title}</option>
              )}
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
          {!active(turn.experiment.state) &&
            selected?.slots &&
            turn.experiment.manifest?.snapshot && (
              <CandidateRerun
                evaluation={turn.experiment}
                slots={selected.slots}
                onQueued={(exp) => {
                  const task = exp.manifest?.workspace as {
                    conversation_id?: string;
                  };
                  if (task?.conversation_id)
                    selectConversation(task.conversation_id);
                }}
              />
            )}
          <div className="paired-responses">
            {orderedRuns(turn.runs).map((run) => (
              <div key={run.id}>
                <AgentResponse
                  run={run}
                  model={
                    selected.execution_agents?.find(
                      (agent) => agent.id === run.agent_id,
                    )?.config.model || selected.model
                  }
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
        {!selected && (
          <details className="slot-configuration">
            <summary>Compare models and instructions</summary>
            <div className="workspace-controls">
              <label className="field">
                Model A
                <input
                  value={modelA}
                  onChange={(e) => setModelA(e.target.value)}
                  placeholder={model}
                />
              </label>
              <label className="field">
                Model B
                <input
                  value={modelB}
                  onChange={(e) => setModelB(e.target.value)}
                  placeholder={model}
                />
              </label>
              <label className="field">
                Version A
                <select
                  value={versionA}
                  onChange={(e) => setVersionA(e.target.value)}
                >
                  <option value="">Current version</option>
                  {versions[agentA]?.map((value) => (
                    <option key={value.version} value={value.version}>
                      {value.version}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Version B
                <select
                  value={versionB}
                  onChange={(e) => setVersionB(e.target.value)}
                >
                  <option value="">Current version</option>
                  {versions[agentB]?.map((value) => (
                    <option key={value.version} value={value.version}>
                      {value.version}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Temperature A
                <input
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={temperatureA}
                  onChange={(e) => setTemperatureA(Number(e.target.value))}
                />
              </label>
              <label className="field">
                Temperature B
                <input
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={temperatureB}
                  onChange={(e) => setTemperatureB(Number(e.target.value))}
                />
              </label>
              <label className="field">
                Recovery A
                <select
                  value={retriesA}
                  onChange={(e) => setRetriesA(e.target.value)}
                >
                  <option value="">Profile default</option>
                  <option value="0">No retry</option>
                  <option value="1">One bounded retry</option>
                </select>
              </label>
              <label className="field">
                Recovery B
                <select
                  value={retriesB}
                  onChange={(e) => setRetriesB(e.target.value)}
                >
                  <option value="">Profile default</option>
                  <option value="0">No retry</option>
                  <option value="1">One bounded retry</option>
                </select>
              </label>
              <label className="field">
                Instructions A
                <textarea
                  maxLength={1200}
                  value={instructionsA}
                  onChange={(e) => setInstructionsA(e.target.value)}
                  placeholder="Optional instructions for this version"
                />
              </label>
              <label className="field">
                Instructions B
                <textarea
                  maxLength={1200}
                  value={instructionsB}
                  onChange={(e) => setInstructionsB(e.target.value)}
                  placeholder="Optional instructions for this version"
                />
              </label>
            </div>
            <small>
              Use installed ollama/model names or agentrouter/model. Sources
              stay identical; each configuration is recorded independently.
            </small>
          </details>
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
        {(category === "repository" ||
          category === "website" ||
          category === "chat" ||
          category === "search") && (
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
        {category === "repository" && (
          <label className="field">
            Import local repository folder
            <input
              type="file"
              {...{ webkitdirectory: "" }}
              multiple
              disabled={busy || pending}
              onChange={(event) => {
                const files = Array.from(event.target.files || []);
                setBusy(true);
                void repositoryZip(files)
                  .then((result) => uploadFiles([result.file]))
                  .catch((err) => setError(errorMessage(err)))
                  .finally(() => setBusy(false));
              }}
            />
            <small>
              Creates a bounded ZIP in your browser. Skips dependency/build
              folders and common credential files. Review your source folder
              before sharing it with a connected provider.
            </small>
          </label>
        )}
        {category === "repository" && (
          <label className="field">
            Branch or commit (optional)
            <input
              value={repositoryRef}
              onChange={(e) => setRepositoryRef(e.target.value)}
              placeholder="Default branch, or exact commit SHA"
              maxLength={200}
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
              Up to 8 MB each. Scanned PDFs use local Tesseract OCR when
              installed.
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
        {latestSnapshotId && (
          <SourcePanel
            key={latestSnapshotId}
            snapshotId={latestSnapshotId}
            references={sourceReferences}
            onChange={setSourceReferences}
          />
        )}
        <TaskCheckEditor checks={checks} onChange={setChecks} />
        <div className="composer-footer">
          <small>
            {selected?.search_provider === "tavily" ||
            (!selected && search === "tavily")
              ? "Tavily captures shared live sources. Basic search consumes credits."
              : "Search off. Investigates supplied public URLs or captured context with your local model; no web discovery."}
          </small>
          <Button
            variant="primary"
            type="submit"
            busy={busy}
            disabled={pending || (!!selectedId && !selected) || !message.trim()}
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
          Local model input is bounded. Continue in a new conversation with
          disclosed excerpts when the context budget is reached; the original
          history remains saved.
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
