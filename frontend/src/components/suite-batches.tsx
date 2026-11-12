import { useCallback, useEffect, useState } from "react";
import { api, post, errorMessage } from "../lib/api";
import { Button, Notice } from "./ui";

interface Batch {
  id: string;
  name: string;
  version: string;
  state: string;
  total_cases: number;
  missing_cases: number[];
  admission_error?: string | null;
  cases: { case: number; id: string; name: string; state: string }[];
  agents: {
    agent_id: string;
    attempts: number;
    completed: number;
    assessed: number;
    passed: number;
    task_success: number | null;
  }[];
}
export function SuiteBatches() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(
    () =>
      api<Batch[]>("/workspace/batches")
        .then(setBatches)
        .catch((err) => setError(errorMessage(err))),
    [],
  );
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 5000);
    return () => clearInterval(timer);
  }, [refresh]);
  return (
    <section className="panel padded-panel">
      <h2>Recorded suite runs</h2>
      <p className="muted">
        Each batch retains its case links and aggregates only recorded checks.
        Totals describe this suite’s case mix.
      </p>
      {error && <Notice kind="error">{error}</Notice>}
      {!batches.length && <p>Run a saved suite to create a combined result.</p>}
      {batches.map((batch) => (
        <details key={batch.id}>
          <summary>
            {batch.name} · {batch.version} · {batch.state.replaceAll("_", " ")}{" "}
            · {batch.cases.length}/{batch.total_cases} cases
          </summary>
          <div className="product-toolbar">
            <a
              className="button button-secondary"
              href={`/api/v1/workspace/batches/${batch.id}/export`}
            >
              Export batch JSON
            </a>
            {!!batch.missing_cases.length && (
              <Button
                busy={busy}
                onClick={() => {
                  setBusy(true);
                  void post<Batch>(`/workspace/batches/${batch.id}/resume`, {})
                    .then((value) => {
                      if (value.admission_error)
                        setError(value.admission_error);
                      return refresh();
                    })
                    .catch((err) => setError(errorMessage(err)))
                    .finally(() => setBusy(false));
                }}
              >
                Queue remaining cases
              </Button>
            )}
          </div>
          {batch.agents.map((agent) => (
            <p key={agent.agent_id}>
              <strong>{agent.agent_id}</strong> · {agent.completed}/
              {agent.attempts} executions completed · {agent.passed}/
              {agent.assessed} assessable attempts passed
              {agent.task_success === null
                ? " · No score without checks"
                : ` · ${Math.round(agent.task_success * 100)}% declared-check success`}
            </p>
          ))}
          {batch.cases.map((item) => (
            <p key={item.case}>
              <a href={`#/experiments/${item.id}`}>
                Case {item.case + 1}: {item.name}
              </a>{" "}
              · {item.state}
            </p>
          ))}
        </details>
      ))}
    </section>
  );
}
