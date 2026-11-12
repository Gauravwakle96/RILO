import { useCallback, useEffect, useState } from "react";
import { RecordControls } from "./saved-data";
import {
  ArrowUpRight,
  Database,
  Download,
  FlaskConical,
  Search,
  ShieldCheck,
} from "lucide-react";
import { api, errorMessage, post } from "../lib/api";
import type { Experiment, Settings } from "../types";
import type { Readiness } from "../workspace-types";
import { Badge, Button, Notice } from "./ui";

export function LocalHistory() {
  const [kind, setKind] = useState<"experiments" | "conversations">(
    "experiments",
  );
  const [archived, setArchived] = useState(false);
  const [revision, setRevision] = useState(0);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{
    items: (Experiment & { title?: string })[];
    pages: number;
    total: number;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    const timer = setTimeout(() => {
      void api<NonNullable<typeof data>>(
        `/workspace/history?kind=${kind}&archived=${archived}&query=${encodeURIComponent(query)}&page=${page}`,
      )
        .then((value) => {
          if (!disposed) {
            setData(value);
            setError("");
          }
        })
        .catch((err) => {
          if (!disposed) setError(errorMessage(err));
        });
    }, 250);
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [query, page, kind, archived, revision]);
  return (
    <section className="panel padded-panel local-card">
      <h2>
        <Search size={18} /> Search all evaluations
      </h2>
      <div className="product-toolbar">
        <label className="field">
          Saved record type
          <select
            value={kind}
            onChange={(event) => {
              setKind(event.target.value as typeof kind);
              setPage(1);
            }}
          >
            <option value="experiments">Evaluations</option>
            <option value="conversations">Conversations</option>
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={archived}
            onChange={(event) => {
              setArchived(event.target.checked);
              setPage(1);
            }}
          />{" "}
          Show archived records
        </label>
        <input
          aria-label="Search all evaluations"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
          placeholder="Find any saved evaluation"
        />
        <span>{data?.total ?? "…"} records</span>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {data?.items.map((item) => (
        <div className="workspace-record-row" key={item.id}>
          <a
            href={
              kind === "experiments"
                ? `#/experiments/${item.id}`
                : `#/${(item as unknown as { category: string }).category}/${item.id}`
            }
          >
            {item.name || item.title} <ArrowUpRight size={13} />
          </a>
          {item.state && <Badge status={item.state} />}
          <small>{new Date(item.created_at).toLocaleString()}</small>
          <RecordControls
            kind={kind}
            id={item.id}
            archived={archived}
            onChanged={() => setRevision((value) => value + 1)}
          />
        </div>
      ))}
      {!data?.items.length && data && (
        <p className="muted">
          No matching evaluations. Try another search or start a task.
        </p>
      )}
      <div className="product-toolbar">
        <Button disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Previous
        </Button>
        <span>
          Page {page} of {data?.pages || 1}
        </span>
        <Button
          disabled={!data || page >= data.pages}
          onClick={() => setPage(page + 1)}
        >
          Next
        </Button>
      </div>
    </section>
  );
}

export function LocalSetup({ settings }: { settings: Settings | null }) {
  const [status, setStatus] = useState<Readiness | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState("");
  const test = async () => {
    setBusy(true);
    setError("");
    try {
      setStatus(
        await post<Readiness>("/workspace/preflight", {
          configuration: {
            title: "Connection test",
            model: model || settings?.config.model,
          },
          require_checks: true,
          test_inference: true,
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel padded-panel local-card">
      <h2>
        <ShieldCheck size={18} /> Your local workspace
      </h2>
      <p className="muted">
        Start with one task, shared sources and two independent responses. Test
        the connection before a large evaluation.
      </p>
      <div className="setup-steps">
        <span>1 · Choose your task</span>
        <span>2 · Add sources and checks</span>
        <span>3 · Compare and retest</span>
      </div>
      <div className="product-toolbar">
        <a className="button button-primary" href="#/chat">
          Start a comparison <ArrowUpRight size={15} />
        </a>
        <a className="button button-violet" href="#/benchmarks">
          Saved tests <FlaskConical size={15} />
        </a>
        <a className="button button-ghost" href="#/guide">
          Open guide
        </a>
      </div>
      <details>
        <summary>Check an actual model response</summary>
        <div className="product-toolbar">
          <input
            aria-label="Connection test model"
            placeholder={settings?.config.model}
            value={model}
            onChange={(e) => setModel(e.target.value)}
          />
          <Button variant="teal" busy={busy} onClick={() => void test()}>
            Test inference
          </Button>
        </div>
        <small>
          Local models use Bifrost. bynara/model or agentrouter/model sends this
          small test to the selected provider when configured.
        </small>
      </details>
      {error && <Notice kind="error">{error}</Notice>}
      {status?.checks.map((check) => (
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
    </section>
  );
}

export function LocalStorage({
  settings,
  onRefresh,
}: {
  settings: Settings | null;
  onRefresh: () => Promise<void>;
}) {
  const [data, setData] = useState<Record<string, number | string> | null>(
    null,
  );
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(
    () =>
      api<Record<string, number | string>>("/workspace/storage")
        .then(setData)
        .catch((err) => setError(errorMessage(err))),
    [],
  );
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const action = async (operation: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      const result = await operation();
      const cleanup = result as { removed_files?: number };
      setMessage(
        typeof cleanup.removed_files === "number"
          ? `Removed ${cleanup.removed_files} unreferenced files. Saved evaluations are preserved.`
          : "Connection policy saved. New external requests use this setting immediately; requests already in progress may finish.",
      );
      await refresh();
      await onRefresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel padded-panel local-card">
      <h2>
        <Database size={18} /> Privacy and local storage
      </h2>
      <p className="muted">
        Sources, results and history stay in the local data folder. Connected
        features send selected content to their provider.
      </p>
      <div className="product-toolbar">
        <Button
          variant="teal"
          busy={busy}
          onClick={() =>
            void action(() =>
              api("/settings", {
                method: "PATCH",
                body: JSON.stringify({ offline: !settings?.config.offline }),
              }),
            )
          }
        >
          {settings?.config.offline
            ? "Enable connected features"
            : "Switch to offline mode"}
        </Button>
        <Badge status={settings?.config.offline ? "ready" : "unknown"}>
          {settings?.config.offline
            ? "Offline mode"
            : "Connected features allowed"}
        </Badge>
      </div>
      <div className="storage-meters">
        {["database", "uploads", "objects", "free_disk"].map((key) => (
          <div key={key}>
            <small>{key.replaceAll("_", " ")}</small>
            <strong>
              {data ? (Number(data[key]) / 1_000_000).toFixed(1) + " MB" : "…"}
            </strong>
          </div>
        ))}
      </div>
      <p className="muted">
        {String(data?.data_directory || "Loading storage…")}
      </p>
      <div className="product-toolbar">
        <Button
          busy={busy}
          disabled={!Number(data?.orphan_files)}
          onClick={() =>
            void action(() => post("/workspace/storage/cleanup", {}))
          }
        >
          Clean {data?.orphan_files || 0} unreferenced files
        </Button>
        <a className="button button-violet" href="/api/v1/workspace/backup">
          <Download size={15} /> Download private backup
        </a>
      </div>
      <small>
        Cleanup preserves all saved sources and evaluations. Backups contain
        private data; store them securely. Restore into a new folder with the
        documented restore command.
      </small>
      {error && <Notice kind="error">{error}</Notice>}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
