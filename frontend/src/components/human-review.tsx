import { useEffect, useState } from "react";
import { api, post, errorMessage } from "../lib/api";
import { Button, Notice } from "./ui";

interface Review {
  state: string;
  rationale: string;
  finding_id: string;
  run_id: string;
}
export function HumanReview({
  runId,
  evaluationId,
  findingId,
}: {
  runId: string;
  evaluationId: string;
  findingId: string;
}) {
  const [state, setState] = useState("NEEDS MANUAL REVIEW");
  const [rationale, setRationale] = useState("");
  const [saved, setSaved] = useState<Review[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    void api<{ artifacts: { kind: string; data: Review }[] }>(
      `/workspace/evaluations/${evaluationId}`,
    )
      .then((value) =>
        setSaved(
          value.artifacts
            .filter(
              (item) =>
                item.kind === "human_review" &&
                item.data.run_id === runId &&
                item.data.finding_id === findingId,
            )
            .map((item) => item.data),
        ),
      )
      .catch((err) => setError(errorMessage(err)));
  }, [evaluationId, runId, findingId]);
  return (
    <details>
      <summary>Review this claim yourself</summary>
      <p className="muted">
        Your judgment is stored separately. It does not overwrite automated
        checks or establish independent ground truth.
      </p>
      {saved.map((value, index) => (
        <p key={index}>
          <strong>Human review: {value.state}</strong> · {value.rationale}
        </p>
      ))}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          void post<{ data: Review }>(`/workspace/runs/${runId}/reviews`, {
            finding_id: findingId,
            state,
            rationale,
          })
            .then((value) => {
              setSaved((items) => [...items, value.data]);
              setRationale("");
            })
            .catch((err) => setError(errorMessage(err)))
            .finally(() => setBusy(false));
        }}
      >
        <label className="field">
          Human verification state
          <select
            value={state}
            onChange={(event) => setState(event.target.value)}
          >
            {[
              "VERIFIED",
              "PARTIALLY VERIFIED",
              "UNSUPPORTED",
              "CONTRADICTED",
              "NEEDS MANUAL REVIEW",
            ].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Review rationale
          <textarea
            required
            maxLength={2000}
            value={rationale}
            onChange={(event) => setRationale(event.target.value)}
          />
        </label>
        <Button type="submit" busy={busy}>
          Save human review
        </Button>
      </form>
      {error && <Notice kind="error">{error}</Notice>}
    </details>
  );
}
