import {
  ArrowRight,
  BookOpen,
  Check,
  FlaskConical,
  GitCompareArrows,
  Play,
  Settings2,
  Terminal,
} from "lucide-react";
import type { Catalog, ExperimentPreset, View } from "../types";
import { Button } from "./ui";
import { recoveryPreset } from "../lib/presets";
import type { MouseEvent } from "react";

function jumpTo(event: MouseEvent<HTMLAnchorElement>, id: string) {
  event.preventDefault();
  const section = document.getElementById(id);
  section?.scrollIntoView({ block: "start" });
  section?.focus({ preventScroll: true });
}

export function GuideView({
  catalog,
  onNew,
  onNavigate,
}: {
  catalog: Catalog;
  onNew: (preset?: ExperimentPreset) => void;
  onNavigate: (view: View) => void;
}) {
  const tavilyConfigured =
    catalog.settings?.integrations.tavily.configured ?? false;
  const demoReady =
    ["scout", "relay"].every((id) =>
      catalog.agents.some((agent) => agent.id === id),
    ) && catalog.tasks.length > 0;
  return (
    <div className="guide-view">
      <section className="panel padded-panel">
        <h2>Compare answers with explicit success checks</h2>
        <p>
          Open Chat, Repository, Documents, Website or Search. Choose two
          agents, supply the task and context, then add success checks such as
          “answer contains SQLite”. Rilo checks local service readiness before
          sending.
        </p>
        <p>
          Inspect both answers and the Promptfoo checks table. A leader passed
          more declared checks; a tie means those checks did not distinguish the
          agents. Valid citations and task completion are separate from factual
          accuracy.
        </p>
        <p>
          Use “Save task as regression test” to keep the checks and snapshot in
          Benchmarks. Run it again after a change, then compare the recorded
          runs in Regression Lab. No checks means ungraded; service and
          evaluator failures are reported separately.
        </p>
        <Button onClick={() => onNavigate("chat")}>Open paired chat</Button>
      </section>
      <header className="guide-heading">
        <div>
          <h1>Make your first failure useful.</h1>
          <p>
            Rilo compares AI agents on the same research tasks, introduces
            controlled faults, and keeps the evidence. Find what needs fixing,
            then test your change.
          </p>
        </div>
        <Button
          variant="primary"
          disabled={!demoReady}
          onClick={() => onNew(recoveryPreset(catalog))}
        >
          <Play size={16} /> Try recovery example
        </Button>
      </header>
      <section className="panel padded-panel">
        <h2>Use the paired workspace</h2>
        <p>
          Choose Chat, Repository, Documents, Website or Search. Select two
          compatible agents, add your task and sources, then send the same input
          to both. Follow-ups keep each agent’s own history.
        </p>
        <p>
          Use Bifrost with an available Ollama model. Tavily is optional: leave
          Web search off for uploaded sources and direct website or repository
          analysis. Enable it when fresh search results are needed.
        </p>
        <p>
          Inspect citations and verification scope before trusting a finding.
          Export PDF, Markdown, JSON or CSV, save a benchmark, and retest
          against the same snapshot. Subjective answers and unverified
          interpretations do not receive invented accuracy scores.
        </p>
        <div className="header-actions">
          <Button onClick={() => onNavigate("chat")}>
            Open Chat <ArrowRight size={14} />
          </Button>
          <Button onClick={() => onNavigate("repository")}>
            Analyze a repository <ArrowRight size={14} />
          </Button>
        </div>
      </section>
      <div className="guide-layout">
        <nav className="guide-index" aria-label="Guide sections">
          <a
            href="#guide-first-test"
            onClick={(event) => jumpTo(event, "guide-first-test")}
          >
            Your first test <ArrowRight size={14} />
          </a>
          <a
            href="#guide-requirements"
            onClick={(event) => jumpTo(event, "guide-requirements")}
          >
            What you need <ArrowRight size={14} />
          </a>
          <a
            href="#guide-functions"
            onClick={(event) => jumpTo(event, "guide-functions")}
          >
            What you can do <ArrowRight size={14} />
          </a>
          <a
            href="#guide-results"
            onClick={(event) => jumpTo(event, "guide-results")}
          >
            Read results correctly <ArrowRight size={14} />
          </a>
          <p>
            No account needed.
            <br />
            Experiments are stored locally.
          </p>
        </nav>
        <div className="guide-content">
          <section
            id="guide-first-test"
            className="guide-section"
            tabIndex={-1}
          >
            <h2>Your first useful test</h2>
            <p className="guide-intro">
              The example prepares 12 attempts: two agents, one task, two
              conditions, three trials. Review it before running.
            </p>
            <ol className="guide-steps">
              <li>
                <strong>Run the recovery example.</strong>
                <p>
                  Scout and Relay answer the same task under normal conditions
                  and a search timeout. The deterministic demo needs no API key
                  and makes no model calls.
                </p>
              </li>
              <li>
                <strong>Inspect a failed attempt.</strong>
                <p>
                  Open Runs, choose an attempt, and read Timeline → Output →
                  Evaluation. See where the fault occurred and whether the
                  answer met its reference checks.
                </p>
              </li>
              <li>
                <strong>Keep a focused regression test.</strong>
                <p>
                  Choose Retest this case to prepare the same task and fault for
                  all selected agents. Make your agent change yourself; Rilo
                  does not rewrite it.
                </p>
              </li>
              <li>
                <strong>Compare the next revision.</strong>
                <p>
                  Save a completed focused experiment as a baseline. Rerun the
                  same conditions after your change, then compare. Declare agent
                  changes explicitly.
                </p>
              </li>
            </ol>
          </section>
          <section
            id="guide-requirements"
            className="guide-section"
            tabIndex={-1}
          >
            <h2>What you need</h2>
            <dl className="guide-requirements">
              <div>
                <dt>
                  <Check size={17} /> Quick demonstration
                </dt>
                <dd>
                  A browser and the running Rilo API + worker. No model,
                  account, or search key required.
                </dd>
              </div>
              <div>
                <dt>
                  <Terminal size={17} /> Real local-model testing
                </dt>
                <dd>
                  Bifrost, Ollama, a downloaded model that fits your hardware,
                  and a configured gateway key. Local inference uses your
                  computer’s resources.
                </dd>
              </div>
              <div>
                <dt>
                  <BookOpen size={17} /> Live web research
                </dt>
                <dd>
                  A private Tavily API key and available search credits.{" "}
                  {tavilyConfigured
                    ? "A key is configured; successful live execution still needs checking."
                    : "No Tavily key is configured in this workspace."}{" "}
                  Live answer grading remains inconclusive without independently
                  validated references.
                </dd>
              </div>
            </dl>
            <Button variant="ghost" onClick={() => onNavigate("settings")}>
              <Settings2 size={15} /> Check integration settings{" "}
              <ArrowRight size={14} />
            </Button>
          </section>
          <section id="guide-functions" className="guide-section" tabIndex={-1}>
            <h2>What you can do with Rilo</h2>
            <dl className="guide-functions">
              <div>
                <dt>Choose an agent</dt>
                <dd>
                  Compare the bundled Python and LangGraph agents, or register
                  your local HTTP agent. HTTP adapters expose final outputs;
                  internal metrics and injected faults are unsupported.
                </dd>
              </div>
              <div>
                <dt>Test difficult conditions</dt>
                <dd>
                  Use search timeouts, synthesis outages, and misleading
                  document instructions. Repeat each task with fresh attempt
                  state.
                </dd>
              </div>
              <div>
                <dt>Understand the trade-off</dt>
                <dd>
                  Compare task success, runtime, steps, tool/model calls,
                  available token usage, and supported model-fee estimates.
                </dd>
              </div>
              <div>
                <dt>Bring evidence to a decision</dt>
                <dd>
                  Save baselines, register HTTP agent revisions, export JSON/CSV
                  reports, or run tests from the Python SDK and CLI.
                </dd>
              </div>
            </dl>
            <div className="guide-links">
              <Button onClick={() => onNavigate("agents")}>
                <FlaskConical size={15} /> Explore agents
              </Button>
              <Button onClick={() => onNavigate("compare")}>
                <GitCompareArrows size={15} /> Compare & baselines
              </Button>
              <a href="/docs" target="_blank" rel="noopener noreferrer">
                API reference <ArrowRight size={14} />
              </a>
            </div>
          </section>
          <section id="guide-results" className="guide-section" tabIndex={-1}>
            <h2>Read results correctly</h2>
            <ul className="guide-reading">
              <li>
                <strong>Pass means the recorded checks passed.</strong> The
                grader checks structured referenced facts and task rules; it
                does not verify every claim in a free-text summary.
              </li>
              <li>
                <strong>Unknown is not zero.</strong> Missing token usage or
                pricing stays unknown. Fee estimates exclude search credits,
                hardware, and electricity.
              </li>
              <li>
                <strong>A fair comparison needs matching conditions.</strong>{" "}
                Tasks, evidence, model, grader, limits, and coverage must agree.
                Three trials are the minimum for the exploratory regression
                gate.
              </li>
              <li>
                <strong>
                  Fixture and real-model results measure different things.
                </strong>{" "}
                The demo teaches the workflow. Test your actual model to assess
                its behavior; a small sample does not guarantee future
                reliability.
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
