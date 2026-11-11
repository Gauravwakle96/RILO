import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { TaskCheck, WorkspaceRun } from "../workspace-types";
import { Button, Badge, Notice } from "./ui";
import TruncatedText from "./promptfoo/TruncatedText";

export function EvaluationCheckComparison({
  id,
  state,
}: {
  id: string;
  state: string;
}) {
  const [data, setData] = useState<{
    runs: WorkspaceRun[];
    artifacts: {
      kind: string;
      data: { explanation?: string; verdict?: string; winner?: string | null };
    }[];
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    void api<NonNullable<typeof data>>(`/workspace/evaluations/${id}`)
      .then((result) => {
        if (!disposed) setData(result);
      })
      .catch((err: unknown) => {
        if (!disposed)
          setError(
            err instanceof Error ? err.message : "Could not load comparison.",
          );
      });
    return () => {
      disposed = true;
    };
  }, [id, state]);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!data || ["queued", "running"].includes(state))
    return (
      <p role="status">
        The task comparison will appear after both independent attempts finish.
      </p>
    );
  return (
    <CheckComparison
      runs={data.runs}
      comparison={
        data.artifacts.find((item) => item.kind === "comparison")?.data
      }
    />
  );
}

const labels: Record<TaskCheck["type"], string> = {
  contains: "Contains exact text",
  icontains: "Contains text (ignore case)",
  "not-contains": "Does not contain exact text",
  "not-icontains": "Does not contain text (ignore case)",
  equals: "Equals exact answer",
  "is-json": "Is valid JSON",
};

export function TaskCheckEditor({
  checks,
  onChange,
}: {
  checks: TaskCheck[];
  onChange: (checks: TaskCheck[]) => void;
}) {
  const update = (index: number, patch: Partial<TaskCheck>) =>
    onChange(
      checks.map((check, i) => (i === index ? { ...check, ...patch } : check)),
    );
  return (
    <section className="task-check-editor" aria-label="Success checks">
      <div className="task-check-heading">
        <div>
          <h3>Define what a good answer must do</h3>
          <p className="muted">
            Checks powered by Promptfoo. Both agents are graded against the same
            rules. No checks means ungraded.
          </p>
        </div>
        <Button
          type="button"
          disabled={checks.length >= 12}
          onClick={() =>
            onChange([
              ...checks,
              {
                id: `check_${crypto.randomUUID().replaceAll("-", "")}`,
                name: `Requirement ${checks.length + 1}`,
                type: "icontains",
                value: "",
                target: "summary",
              },
            ])
          }
        >
          Add success check
        </Button>
      </div>
      {checks.map((check, index) => (
        <fieldset className="task-check-fields" key={check.id}>
          <legend>Check {index + 1}</legend>
          <label className="field">
            Check {index + 1} name
            <input
              required
              maxLength={120}
              value={check.name}
              onChange={(event) => update(index, { name: event.target.value })}
            />
          </label>
          <label className="field">
            Check {index + 1} rule
            <select
              value={check.type}
              onChange={(event) =>
                update(index, {
                  type: event.target.value as TaskCheck["type"],
                  value: event.target.value === "is-json" ? null : "",
                })
              }
            >
              {Object.entries(labels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Check {index + 1} target
            <select
              value={check.target}
              onChange={(event) =>
                update(index, {
                  target: event.target.value as TaskCheck["target"],
                })
              }
            >
              <option value="summary">Answer text</option>
              <option value="response">Full structured response</option>
            </select>
          </label>
          {check.type !== "is-json" && (
            <label className="field">
              Check {index + 1} expected text
              <input
                required
                maxLength={2000}
                value={check.value ?? ""}
                onChange={(event) =>
                  update(index, { value: event.target.value })
                }
                placeholder="For example: SQLite"
              />
            </label>
          )}
          <Button
            type="button"
            variant="ghost"
            aria-label={`Remove check ${index + 1}`}
            onClick={() => onChange(checks.filter((_, i) => i !== index))}
          >
            Remove
          </Button>
        </fieldset>
      ))}
      {!!checks.length && (
        <small className="muted">
          Text checks match spelling and word order literally; ignore case only
          ignores capitalization. They do not assess factual accuracy. Rules are
          stored with this task and preserved on retest.
        </small>
      )}
    </section>
  );
}

export function CheckComparison({
  runs,
  comparison,
  onSave,
  retryChanged = false,
}: {
  runs: WorkspaceRun[];
  comparison?: {
    explanation?: string;
    verdict?: string;
    winner?: string | null;
  };
  onSave?: () => Promise<void>;
  retryChanged?: boolean;
}) {
  const [filter, setFilter] = useState("all");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const rules = Array.from(
    new Map(
      runs.flatMap((run) =>
        (run.assessment?.task_checks?.checks ?? []).map(
          (check) => [check.id, check] as const,
        ),
      ),
    ).values(),
  );
  const displayed = rules.filter(
    (check) =>
      filter === "all" ||
      runs.some(
        (run) =>
          run.assessment?.task_checks?.checks.find((row) => row.id === check.id)
            ?.passed === false,
      ),
  );
  const hasRules = rules.length > 0;
  // Older records may say "tie" when both agents failed. Preserve their stored
  // artifact and explain the original check outcomes accurately in the view.
  const neitherMetChecks =
    runs.length >= 2 &&
    runs.every(
      (run) =>
        run.outcome === "completed" &&
        run.assessment?.task_checks?.status === "fail",
    );
  return (
    <section
      className="comparison-note check-comparison"
      aria-label="Task check comparison"
    >
      <div className="task-check-heading">
        <div>
          <h3>Which agent did better?</h3>
          <small>
            Checks powered by Promptfoo 0.125.1 · evidence and timing shown
            separately
          </small>
        </div>
        <Badge
          status={
            neitherMetChecks
              ? "fail"
              : comparison?.verdict === "checks_leader"
                ? "pass"
                : "inconclusive"
          }
        >
          {retryChanged
            ? "Retry attempts"
            : neitherMetChecks
              ? "Neither met the checks"
              : comparison?.verdict === "checks_leader"
                ? "Leader on declared checks"
                : comparison?.verdict === "tie"
                  ? "Tie on declared checks"
                  : hasRules
                    ? "Check results"
                    : "Ungraded"}
        </Badge>
      </div>
      <p>
        {retryChanged
          ? "These are the latest response attempts. Retries had additional execution opportunities; compare the original paired run in its report."
          : neitherMetChecks
            ? "Neither agent met all the declared checks. Review the failed requirements and source coverage. Literal matching does not correct spelling or word order, and does not measure factual accuracy."
            : ((comparison?.verdict ? comparison.explanation : null) ??
              "Accuracy and a winner remain undetermined without explicit success checks. Compare the recorded answers, evidence and usage.")}
      </p>
      {runs.map(
        (run) =>
          run.assessment?.task_checks?.status === "error" && (
            <Notice key={run.id} kind="warning">
              {run.agent_name}: {run.assessment.task_checks.reason}
            </Notice>
          ),
      )}
      {hasRules && (
        <>
          <label className="field check-filter">
            Show checks
            <select
              aria-label="Show checks"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="all">All checks</option>
              <option value="failed">Failed checks only</option>
            </select>
          </label>
          <div className="check-table-scroll">
            <table className="check-table">
              <caption>
                Identical success checks applied independently to each recorded
                answer
              </caption>
              <thead>
                <tr>
                  <th scope="col">Success requirement</th>
                  {runs.map((run) => (
                    <th scope="col" key={run.id}>
                      {run.agent_name}
                      <small>
                        {run.assessment?.task_checks?.passed ?? "—"}/
                        {run.assessment?.task_checks?.total ?? "—"} checks
                        passed
                      </small>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {displayed.map((check) => (
                  <tr key={check.id}>
                    <th scope="row">
                      {check.name}
                      <small>
                        {labels[check.type]} ·{" "}
                        {check.target === "summary" ? "answer" : "response"}
                      </small>
                      {check.value && (
                        <TruncatedText text={check.value} maxLength={140} />
                      )}
                    </th>
                    {runs.map((run) => {
                      const row = run.assessment?.task_checks?.checks.find(
                        (item) => item.id === check.id,
                      );
                      return (
                        <td key={run.id}>
                          <Badge
                            status={
                              row
                                ? row.passed
                                  ? "pass"
                                  : "fail"
                                : "inconclusive"
                            }
                          >
                            {row
                              ? row.passed
                                ? "Pass"
                                : "Fail"
                              : "Not graded"}
                          </Badge>
                          {row && (
                            <div className="check-reason">
                              <TruncatedText
                                text={row.reason}
                                maxLength={180}
                              />
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!displayed.length && (
            <p>No failed checks in these recorded answers.</p>
          )}
          {onSave && (
            <Button
              disabled={saved}
              busy={saving}
              onClick={() => {
                setSaving(true);
                setError("");
                void onSave()
                  .then(() => setSaved(true))
                  .catch((err: unknown) =>
                    setError(
                      err instanceof Error
                        ? err.message
                        : "Could not save suite.",
                    ),
                  )
                  .finally(() => setSaving(false));
              }}
            >
              {saved ? "Saved in Benchmarks" : "Save task as regression test"}
            </Button>
          )}
          {error && <Notice kind="error">{error}</Notice>}
        </>
      )}
    </section>
  );
}
