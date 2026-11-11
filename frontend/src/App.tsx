import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  Bot,
  ChevronDown,
  ChevronRight,
  FlaskConical,
  GitCompareArrows,
  Layers,
  Menu,
  MessageSquare,
  Globe,
  FileText,
  FolderGit2,
  Search,
  LayoutDashboard,
  Moon,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type {
  Agent,
  Baseline,
  Catalog,
  Experiment,
  ExperimentPreset,
  ExperimentSpec,
  Scenario,
  Settings,
  Source,
  Task,
  View,
} from "./types";
import { api, ApiError, errorMessage, post, session } from "./lib/api";
import { active } from "./lib/format";
import {
  AgentForm,
  BaselineForm,
  ExperimentForm,
  TaskForm,
} from "./components/forms";
import { ExperimentDetail, ExperimentList } from "./components/experiments";
import {
  AgentsView,
  CompareView,
  EvidenceView,
  ScenariosView,
  SettingsView,
  TasksView,
} from "./components/catalog";
import { Button, Notice, Skeleton } from "./components/ui";
import { GuideView } from "./components/guide";
import { recoveryPreset } from "./lib/presets";
import { WorkspaceView } from "./components/workspace";
import { WorkspaceManagement } from "./components/workspace-management";

const navigation: { id: View; label: string; icon: LucideIcon }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "repository", label: "Repository", icon: FolderGit2 },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "website", label: "Website", icon: Globe },
  { id: "search", label: "Search", icon: Search },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "benchmarks", label: "Benchmarks", icon: Layers },
  { id: "regression", label: "Regression Lab", icon: GitCompareArrows },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "experiments", label: "Experiments", icon: FlaskConical },
  { id: "tasks", label: "Tasks", icon: Layers },
  { id: "scenarios", label: "Scenarios", icon: ShieldCheck },
  { id: "evidence", label: "Evidence", icon: BookOpen },
  { id: "compare", label: "Compare & baselines", icon: GitCompareArrows },
];
const emptyCatalog: Catalog = {
  agents: [],
  tasks: [],
  scenarios: [],
  sources: [],
  experiments: [],
  baselines: [],
  settings: null,
};

function savedTheme(): "dark" | "light" {
  try {
    return localStorage.getItem("rilo-theme") === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

function currentLocation(): { view: View; experimentId: string | null } {
  const [view, id] = window.location.hash.replace(/^#\/?/, "").split("/");
  if (view === "experiments" && id) {
    try {
      return { view: "experiments", experimentId: decodeURIComponent(id) };
    } catch {
      return { view: "experiments", experimentId: null };
    }
  }
  return {
    view:
      navigation.some((item) => item.id === view) ||
      view === "settings" ||
      view === "guide"
        ? (view as View)
        : "experiments",
    experimentId: null,
  };
}

export default function App() {
  const sidebarRef = useRef<HTMLElement>(null);
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 800px)").matches,
  );
  const [location, setLocation] = useState(currentLocation);
  const [catalog, setCatalog] = useState<Catalog>(emptyCatalog);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [partial, setPartial] = useState("");
  const [permission, setPermission] = useState(false);
  const [connected, setConnected] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [theme, setTheme] = useState(savedTheme);
  const [modal, setModal] = useState<"experiment" | "agent" | "task" | null>(
    null,
  );
  const [rerunSpec, setRerunSpec] = useState<ExperimentSpec | undefined>(
    undefined,
  );
  const [experimentPreset, setExperimentPreset] = useState<
    ExperimentPreset | undefined
  >();
  const [baselineExperiment, setBaselineExperiment] =
    useState<Experiment | null>(null);
  const [toast, setToast] = useState("");
  const [version, setVersion] = useState("0.1.0");

  useEffect(() => {
    const media = window.matchMedia("(max-width: 800px)");
    const resize = () => setNarrow(media.matches);
    media.addEventListener("change", resize);
    return () => media.removeEventListener("change", resize);
  }, []);

  useEffect(() => {
    if (!narrow || !sidebarOpen) return;
    const sidebar = sidebarRef.current;
    const trigger = document.activeElement as HTMLElement | null;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebar?.querySelector<HTMLButtonElement>(".mobile-close")?.focus();
    const containFocus = (event: KeyboardEvent) => {
      if (event.key !== "Tab" || !sidebar) return;
      const controls = Array.from(
        sidebar.querySelectorAll<HTMLElement>("button:not(:disabled), a[href]"),
      ).filter((element) => element.getClientRects().length > 0);
      const first = controls[0],
        last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", containFocus);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", containFocus);
      if (trigger?.isConnected) trigger.focus();
    };
  }, [narrow, sidebarOpen]);

  const navigate = useCallback((view: View, id?: string) => {
    window.location.hash = `/${view}${id ? `/${encodeURIComponent(id)}` : ""}`;
    setSidebarOpen(false);
  }, []);
  useEffect(() => {
    const changed = () => {
      setLocation(currentLocation());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("rilo-theme", theme);
    } catch {
      /* Theme still works when browser storage is unavailable. */
    }
  }, [theme]);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(""), 5000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const refresh = useCallback(async () => {
    try {
      const sessionInfo = await session();
      setVersion(sessionInfo.app_version);
      const results = await Promise.allSettled([
        api<Agent[]>("/agents"),
        api<Task[]>("/tasks"),
        api<Scenario[]>("/scenarios"),
        api<Source[]>("/sources"),
        api<Experiment[]>("/experiments"),
        api<Baseline[]>("/baselines"),
        api<Settings>("/settings"),
      ]);
      const names = [
        "agents",
        "tasks",
        "scenarios",
        "sources",
        "experiments",
        "baselines",
        "settings",
      ] as const;
      const failures: string[] = [];
      const updates: Partial<Catalog> = {};
      let accessRejected = false;
      for (let index = 0; index < results.length; index++) {
        const result = results[index];
        if (result.status === "fulfilled")
          Object.assign(updates, { [names[index]]: result.value });
        else {
          failures.push(`${names[index]}: ${errorMessage(result.reason)}`);
          if (
            result.reason instanceof ApiError &&
            [401, 403].includes(result.reason.status)
          )
            accessRejected = true;
        }
      }
      setCatalog((previous) => ({ ...previous, ...updates }));
      setPartial(
        failures.length
          ? `Some workspace data is unavailable. ${failures.join(" · ")}`
          : "",
      );
      setError(
        accessRejected
          ? "Your local session cannot access all workspace data. Reload Rilo to establish a new session."
          : "",
      );
      setConnected(Object.keys(updates).length > 0);
      setPermission(accessRejected);
    } catch (err) {
      setError(errorMessage(err));
      setConnected(false);
      setPermission(err instanceof ApiError && [401, 403].includes(err.status));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    let disposed = false;
    const start = () => {
      if (!disposed) void refresh();
    };
    void session().then(start, start);
    return () => {
      disposed = true;
    };
  }, [refresh]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      if (
        !document.hidden &&
        catalog.experiments.some((experiment) => active(experiment.state))
      )
        void refresh();
    }, 2400);
    return () => window.clearInterval(timer);
  }, [catalog.experiments, refresh]);
  const newExperiment = useCallback((preset?: ExperimentPreset) => {
    setRerunSpec(undefined);
    setExperimentPreset(preset);
    setModal("experiment");
  }, []);
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (
        event.key === "/" &&
        !["INPUT", "TEXTAREA", "SELECT"].includes(
          (event.target as HTMLElement).tagName,
        ) &&
        !modal
      ) {
        const search = document.querySelector<HTMLInputElement>(
          ".search-field input",
        );
        if (search) {
          event.preventDefault();
          search.focus();
        }
      }
      if (event.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [modal]);

  const createdExperiment = (experiment: Experiment) => {
    setModal(null);
    setToast("Experiment queued. The worker will record each attempt.");
    navigate("experiments", experiment.id);
    void refresh();
  };
  const renderView = () => {
    if (location.view === "experiments" && location.experimentId)
      return (
        <ExperimentDetail
          key={location.experimentId}
          id={location.experimentId}
          onBack={() => navigate("experiments")}
          onRerun={(experiment) => {
            if (experiment.manifest?.workspace) {
              void post<Experiment>(
                `/workspace/evaluations/${experiment.id}/retest`,
                {},
              )
                .then(createdExperiment)
                .catch((error: unknown) => setToast(errorMessage(error)));
              return;
            }
            setRerunSpec(experiment.spec);
            setExperimentPreset(undefined);
            setModal("experiment");
          }}
          onBaseline={setBaselineExperiment}
          onCompare={() => navigate("compare")}
          onRetest={newExperiment}
        />
      );
    switch (location.view) {
      case "dashboard":
      case "benchmarks":
      case "regression":
      case "reports":
        return (
          <WorkspaceManagement
            key={location.view}
            view={location.view}
            catalog={catalog}
          />
        );
      case "chat":
      case "repository":
      case "documents":
      case "website":
      case "search":
        return (
          <WorkspaceView
            key={location.view}
            category={location.view}
            catalog={catalog}
          />
        );
      case "agents":
        return (
          <AgentsView
            catalog={catalog}
            onRefresh={refresh}
            onAdd={() => setModal("agent")}
            onNew={(agentId) =>
              newExperiment(
                agentId
                  ? {
                      agent_ids: [agentId],
                      ...(catalog.agents.find((agent) => agent.id === agentId)
                        ?.kind === "http"
                        ? { scenario_ids: ["normal"] }
                        : {}),
                    }
                  : undefined,
              )
            }
          />
        );
      case "tasks":
        return (
          <TasksView
            catalog={catalog}
            onAdd={() => setModal("task")}
            onNew={() =>
              newExperiment({ task_ids: catalog.tasks.map((task) => task.id) })
            }
          />
        );
      case "scenarios":
        return <ScenariosView catalog={catalog} onNew={newExperiment} />;
      case "evidence":
        return <EvidenceView catalog={catalog} />;
      case "compare":
        return <CompareView catalog={catalog} />;
      case "settings":
        return <SettingsView settings={catalog.settings} onRefresh={refresh} />;
      case "guide":
        return (
          <GuideView
            catalog={catalog}
            onNew={newExperiment}
            onNavigate={navigate}
          />
        );
      default:
        return (
          <ExperimentList
            catalog={catalog}
            loading={loading}
            onNew={newExperiment}
            onOpen={(id) => navigate("experiments", id)}
            onExample={() => newExperiment(recoveryPreset(catalog))}
            onGuide={() => navigate("guide")}
          />
        );
    }
  };

  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#workspace-main"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("workspace-main")?.focus();
        }}
      >
        Skip to content
      </a>
      {sidebarOpen && (
        <button
          className="sidebar-overlay"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <aside
        ref={sidebarRef}
        id="rilo-navigation"
        className={`sidebar ${sidebarOpen ? "open" : ""}`}
        aria-label="Workspace navigation"
        role={narrow && sidebarOpen ? "dialog" : undefined}
        aria-modal={narrow && sidebarOpen ? true : undefined}
        inert={narrow && !sidebarOpen}
      >
        <div className="brand-row">
          <button
            className="brand"
            onClick={() => navigate("experiments")}
            aria-label="Rilo home"
          >
            <img src="/rilo.svg" alt="" />
            <span>
              rilo<span className="brand-period">.</span>
            </span>
          </button>
          <button
            className="icon-button mobile-close"
            aria-label="Close navigation"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={19} />
          </button>
        </div>
        <div className="workspace-switch">
          <span className="workspace-letter">R</span>
          <div>
            <strong>Evaluation workspace</strong>
            <small>Local · private</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <nav aria-label="Workspace sections">
          {navigation.map((item, index) => (
            <div key={item.id}>
              {(index === 0 || index === 6 || index === 10) && (
                <p className="nav-label">
                  {index === 0
                    ? "WORKSPACE"
                    : index === 6
                      ? "EVALUATION"
                      : "RESEARCH BENCHMARKS"}
                </p>
              )}
              <button
                key={item.id}
                onClick={() => navigate(item.id)}
                className={`nav-item ${location.view === item.id ? "active" : ""}`}
                aria-current={location.view === item.id ? "page" : undefined}
              >
                <item.icon size={18} />
                <span>{item.label}</span>
                {item.id === "experiments" &&
                  catalog.experiments.length > 0 && (
                    <span className="nav-count">
                      {catalog.experiments.length}
                    </span>
                  )}
              </button>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button
            className={`sidebar-guide ${location.view === "guide" ? "selected" : ""}`}
            aria-current={location.view === "guide" ? "page" : undefined}
            onClick={() => navigate("guide")}
          >
            <BookOpen size={19} />
            <span>
              <strong>Start here</strong>
              <small>A short guide to Rilo</small>
            </span>
            <ArrowUpRight size={14} />
          </button>
          <button
            className={`nav-item ${location.view === "settings" ? "active" : ""}`}
            onClick={() => navigate("settings")}
            aria-current={location.view === "settings" ? "page" : undefined}
          >
            <Settings2 size={18} />
            <span>Settings</span>
          </button>
          <div className="sidebar-note">
            <div>
              <span className="small-status-dot" />
              <strong>Runs stay on your machine</strong>
            </div>
            <p>
              Your workspace, evidence, and experiment history are stored
              locally.
            </p>
          </div>
          <div className="sidebar-footer">
            <span className="avatar avatar-neutral">G</span>
            <div>
              <strong>Local developer</strong>
              <small>Rilo {version}</small>
            </div>
            <button
              className="icon-button"
              aria-label={
                theme === "dark"
                  ? "Switch to light theme"
                  : "Switch to dark theme"
              }
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace" inert={narrow && sidebarOpen}>
        <header className="topbar">
          <div className="topbar-location">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              aria-expanded={sidebarOpen}
              aria-controls="rilo-navigation"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={20} />
            </button>
            <span>Evaluation workspace</span>
            <ChevronRight size={13} />
            <strong>
              {navigation.find((item) => item.id === location.view)?.label ??
                (location.view === "guide" ? "Getting started" : "Settings")}
            </strong>
          </div>
          <div className="topbar-right">
            <span
              className={`connection-indicator ${connected ? "online" : ""}`}
            >
              <span />
              {connected
                ? "Local API connected"
                : loading
                  ? "Connecting…"
                  : "API unavailable"}
            </span>
            <button
              className="icon-button"
              aria-label="Refresh workspace"
              onClick={() => void refresh()}
            >
              <RefreshCw size={15} />
            </button>
            <a
              className="topbar-docs"
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
            >
              API docs
              <ArrowUpRight size={13} />
            </a>
          </div>
        </header>
        <main id="workspace-main" className="main-content" tabIndex={-1}>
          {error && (
            <Notice kind="error">
              <strong>
                {permission
                  ? "Local session was rejected."
                  : "Workspace connection failed."}
              </strong>{" "}
              {error}{" "}
              <Button variant="ghost" onClick={() => void refresh()}>
                Reconnect
              </Button>
              {permission && (
                <p>
                  Open Rilo using its approved localhost address and reconnect.
                </p>
              )}
            </Notice>
          )}
          {partial && (
            <Notice kind="warning">
              {partial}
              <Button variant="ghost" onClick={() => void refresh()}>
                Retry
              </Button>
            </Notice>
          )}
          {loading && location.view !== "experiments" ? (
            <Skeleton />
          ) : connected || catalog.experiments.length || loading ? (
            renderView()
          ) : (
            <div className="connection-empty">
              <Activity size={30} />
              <h1>Connect your local workspace</h1>
              <p>
                Start the Rilo API and worker, then reconnect. Your experiments
                will appear here once the service is ready.
              </p>
              <Button variant="primary" onClick={() => void refresh()}>
                <RefreshCw size={15} />
                Reconnect
              </Button>
            </div>
          )}
        </main>
        <footer className="app-footer">
          <span>Rilo · Agent reliability workspace</span>
          <span>Results apply to the tasks and conditions tested.</span>
        </footer>
      </div>
      {toast && (
        <div className="toast" role="status">
          <ShieldCheck size={17} />
          <span>{toast}</span>
          <button
            className="icon-button"
            aria-label="Dismiss message"
            onClick={() => setToast("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      {modal === "experiment" && (
        <ExperimentForm
          catalog={catalog}
          initial={rerunSpec}
          preset={experimentPreset}
          onClose={() => setModal(null)}
          onCreated={createdExperiment}
        />
      )}
      {modal === "agent" && (
        <AgentForm
          onClose={() => setModal(null)}
          onCreated={(agent) => {
            setModal(null);
            setToast(
              `${agent.name} registered. Check its connection before testing.`,
            );
            void refresh();
          }}
        />
      )}
      {modal === "task" && (
        <TaskForm
          sources={catalog.sources}
          onClose={() => setModal(null)}
          onCreated={(task) => {
            setModal(null);
            setToast(`${task.title} created.`);
            void refresh();
          }}
        />
      )}
      {baselineExperiment && (
        <BaselineForm
          experiment={baselineExperiment}
          onClose={() => setBaselineExperiment(null)}
          onSaved={() => {
            setBaselineExperiment(null);
            setToast("Baseline saved for future comparisons.");
            void refresh();
          }}
        />
      )}
    </div>
  );
}
