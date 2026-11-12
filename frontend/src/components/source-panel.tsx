import { useState } from "react";
import { api, errorMessage } from "../lib/api";
import { Button, Notice } from "./ui";

interface Source {
  id: string;
  reference: string;
  content: string;
  page?: number;
  title?: string;
}
interface Snapshot {
  id: string;
  hash: string;
  sources: Source[];
}

export function SourcePanel({
  snapshotId,
  references,
  onChange,
}: {
  snapshotId: string;
  references: string[];
  onChange: (values: string[]) => void;
}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      const value = await api<Snapshot>(`/workspace/snapshots/${snapshotId}`);
      setSnapshot(value);
      setSelected(value.sources[0]?.id || "");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const source = snapshot?.sources.find((value) => value.id === selected);
  return (
    <details className="source-inspector">
      <summary>Inspect captured sources and focus your next task</summary>
      {!snapshot && (
        <Button type="button" busy={busy} onClick={() => void load()}>
          Load captured sources
        </Button>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {snapshot && (
        <>
          <p className="muted">
            {snapshot.sources.length} captured sources. Each answer uses a
            bounded selection; full source capture does not mean every line was
            analyzed.
          </p>
          <label className="field">
            Captured source
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {snapshot.sources.map((value) => (
                <option key={value.id} value={value.id}>
                  {value.reference}
                  {value.page ? ` · page ${value.page}` : ""}
                </option>
              ))}
            </select>
          </label>
          {source && (
            <>
              <div className="product-toolbar">
                <Button
                  type="button"
                  variant="teal"
                  onClick={() =>
                    onChange(
                      references.includes(source.reference)
                        ? references.filter(
                            (value) => value !== source.reference,
                          )
                        : [...references, source.reference],
                    )
                  }
                >
                  {references.includes(source.reference)
                    ? "Remove focus"
                    : "Focus next task on this source"}
                </Button>
                {source.page && <span>Page {source.page}</span>}
              </div>
              <pre>
                {source.content
                  .split("\n")
                  .slice(0, 250)
                  .map((line, index) => `${index + 1}  ${line}`)
                  .join("\n")
                  .slice(0, 20000)}
              </pre>
              <small>
                Preview shows up to 250 lines / 20,000 characters of the
                captured source.
              </small>
            </>
          )}
          <p className="muted">
            {references.length
              ? `Next task selects passages from ${references.length} chosen source reference(s).`
              : "Next task searches all captured sources."}
          </p>
          {!!references.length && (
            <Button type="button" onClick={() => onChange([])}>
              Clear source focus
            </Button>
          )}
        </>
      )}
    </details>
  );
}
