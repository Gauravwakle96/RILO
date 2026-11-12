import { useState } from "react";
import type { Conversation } from "../workspace-types";
import type { Experiment } from "../types";
import { post, errorMessage } from "../lib/api";
import { Button, Notice } from "./ui";

export function CandidateRerun({
  evaluation,
  slots,
  onQueued,
}: {
  evaluation: Experiment;
  slots: NonNullable<Conversation["slots"]>;
  onQueued: (value: Experiment) => void;
}) {
  const [candidates, setCandidates] = useState(
    slots.map((value) => ({ ...value })),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <details className="slot-configuration">
      <summary>Edit candidates and rerun captured task</summary>
      <p className="muted">
        Keeps the original task, sources, checks and each agent’s prior history.
        Changes are recorded in a new evaluation; the original stays intact.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          void post<Experiment>(
            `/workspace/evaluations/${evaluation.id}/retest`,
            { slots: candidates },
          )
            .then(onQueued)
            .catch((err) => setError(errorMessage(err)))
            .finally(() => setBusy(false));
        }}
      >
        <div className="workspace-controls">
          {candidates.map((value, index) => (
            <div key={index}>
              <label className="field">
                Candidate {index ? "B" : "A"} model
                <input
                  required
                  value={value.model || evaluation.spec.model}
                  onChange={(event) =>
                    setCandidates((items) =>
                      items.map((item, i) =>
                        i === index
                          ? { ...item, model: event.target.value }
                          : item,
                      ),
                    )
                  }
                />
              </label>
              <label className="field">
                Candidate {index ? "B" : "A"} instructions
                <textarea
                  maxLength={1200}
                  value={value.instructions || ""}
                  onChange={(event) =>
                    setCandidates((items) =>
                      items.map((item, i) =>
                        i === index
                          ? { ...item, instructions: event.target.value }
                          : item,
                      ),
                    )
                  }
                />
              </label>
            </div>
          ))}
        </div>
        <Button variant="violet" type="submit" busy={busy}>
          Queue candidate comparison
        </Button>
        {error && <Notice kind="error">{error}</Notice>}
      </form>
    </details>
  );
}
