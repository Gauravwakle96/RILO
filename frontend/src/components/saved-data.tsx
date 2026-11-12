import { useState } from "react";
import { errorMessage, post } from "../lib/api";
import { Button, Notice } from "./ui";

export function RecordControls({
  kind,
  id,
  archived,
  onChanged,
}: {
  kind: "experiments" | "conversations";
  id: string;
  archived: boolean;
  onChanged: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const action = (value: "archive" | "restore" | "delete") => {
    setBusy(true);
    setError("");
    void post(`/workspace/records/${kind}/${id}`, {
      action: value,
      confirmation: text,
    })
      .then(onChanged)
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setBusy(false));
  };
  return (
    <div>
      <div className="product-toolbar">
        <Button
          busy={busy}
          onClick={() => action(archived ? "restore" : "archive")}
        >
          {archived ? "Restore" : "Archive"}
        </Button>
        <Button
          variant="danger"
          disabled={busy}
          onClick={() => setConfirm(!confirm)}
        >
          Delete…
        </Button>
      </div>
      {confirm && (
        <div>
          <p>
            Permanently deletes this record’s execution history. Shared sources
            and uploads are retained. Records used by suites or regressions are
            protected. Download a private backup first.
          </p>
          <label className="field">
            Type {id} to confirm
            <input
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          <Button
            variant="danger"
            disabled={text !== id || busy}
            onClick={() => action("delete")}
          >
            Permanently delete record
          </Button>
        </div>
      )}
      {error && <Notice kind="error">{error}</Notice>}
    </div>
  );
}
