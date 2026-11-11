# Rilo

**Measure recovery. Inspect evidence. Repeat the test.**

[![Verify Rilo](https://github.com/Gauravwakle96/RILO/actions/workflows/verify.yml/badge.svg)](https://github.com/Gauravwakle96/RILO/actions/workflows/verify.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Rilo is a local **AI agent benchmarking and verification workspace**. Give two independent agents the same task and captured sources, inspect their answers and execution traces, introduce controlled failures, and repeat the evaluation after a change. Developers can see **which agent met their requirements, what it consumed, and where it failed**.

Built for the Global AI Hackathon's Bifrost challenge: **[Build a Benchmarking Platform for AI Agents, Not Just Models](https://hackcultureplatform.blob.core.windows.net/event-assets/hackathons/6ac5c8240037f69fb28e23ec/problem_explanation_ck1ellfr6qh.pdf)**. The benchmark category is **research agents**; the same workspace also supports chat, repository, document and website tasks.

[Quick start](#quick-start) · [Measured results](#measured-results) · [Judge's guide](docs/HACKATHON.md) · [Architecture](#how-it-works) · [Verification](docs/RILO_2_VERIFICATION.md)

![Recorded agent recovery comparison in Rilo](docs/ui-evidence/model-v2-comparison.png)

*An actual recorded benchmark: both agents passed 12/15 normal-condition attempts. Their behavior diverged when a search or model call failed. This screenshot shows the benchmark interface at the time of capture.*

## The problem

A successful agent demo can hide fragile tool handling, unnecessary calls and unsupported answers. Choosing a model alone does not tell a developer whether an agent's prompts, orchestration, tools and recovery logic work together. Comparing runs with different sources or budgets makes that decision harder.

Rilo turns that decision into an inspectable experiment: fix the inputs, record the conditions, evaluate each agent independently, and trace a failed check back to the answer, source or failed operation. Save the task as a regression suite and use it again when the agent changes.

## Measured results

On **9 November 2026**, a full research benchmark recorded **120 attempts**: two agents × five tasks × four conditions × three repetitions, using the same `qwen2.5-coder:7b` model through **Bifrost v2.5.0 → Ollama**.

| Recorded outcome | Scout: plain Python | Relay: LangGraph |
| --- | ---: | ---: |
| Passed / total attempts | 24 / 60 | 48 / 60 |
| Task success within this suite | 40% | 80% |
| Normal conditions | 12 / 15 | 12 / 15 |
| First search call times out | 0 / 15 | 12 / 15 |
| First synthesis call unavailable | 0 / 15 | 12 / 15 |
| Misleading source instruction | 12 / 15 | 12 / 15 |
| Mean attempt duration | 5.8 seconds | 10.0 seconds |

**What this reveals:** Relay's bounded recovery improved completion under the injected failures, with greater execution time. Both agents still failed the insufficient-evidence task. Rilo preserves those failures so the next improvement has a concrete test.

These are **historical measurements on controlled synthetic sources with real model inference**, not live-web accuracy or a hackathon score. The 120 attempts contain 90 actual model responses; some controlled failures prevented dispatch. Three repeated trials are a small sample, and later runs can differ.

Inspect the [methodology and limitations](docs/BENCHMARK.md), [compact results](docs/benchmark-evidence/summary-v2.json), [complete outputs and traces](docs/benchmark-evidence/model-v2.json), and [CSV](docs/benchmark-evidence/model-v2.csv). No private database is required to read these artifacts.

## Why use Rilo?

| Developer need | Rilo's implemented answer |
| --- | --- |
| Compare different agent implementations | Plain Python, LangGraph and a registered local HTTP-agent contract. Existing HTTP agents keep their implementation; unobserved internals remain unknown. |
| Understand recovery, resource use and failure | Inject a search timeout, synthesis outage or misleading instruction into the research suite; inspect activation, tool/model events, retries and outcomes. |
| Keep comparisons fair | Shared source snapshots, independent histories, recorded model/budgets, versioned checks and repeated trials. Neither agent sees its peer's answer during generation. |
| Define a useful result | Real **Promptfoo 0.125.1** assertions grade declared text/JSON requirements. The comparison shows passed checks, failures and scoped conclusions. |
| Check the source behind a finding | Inspect exact captured file lines, PDF pages or website passages. Valid references and claim correctness are reported separately. |
| Prevent the same failure returning | Save versioned suites, rerun captured tasks, compare baselines and investigate newly failed checks. Export the record as PDF, Markdown, JSON or CSV. |

Rilo's contribution is the combination of **controlled agent failures, independent execution, source verification and a repeatable developer workflow** in a local workspace. It builds on established tools: Promptfoo supplies the assertion engine and one adapted React component; Rilo supplies its worker, agent adapters, captured contexts, evidence checks, comparisons and reports. See [implementation and attribution](docs/PROMPTFOO_INTEGRATION.md).

## Five ways to use the workspace

| Workspace | Working flow |
| --- | --- |
| **Chat** | Send shared messages to two agents, keep separate histories, attach context, compare replies, cancel or retry, and export the conversation. Source-free conversation is not assigned a factual-accuracy score. |
| **Repository** | Capture a public GitHub commit or ZIP; analyze bounded source files with real paths and line references. Python static checks, optional OSV lookups and isolated Docker test profiles add separate evidence. |
| **Documents** | Analyze text-based PDF, DOCX, TXT and Markdown. PDF citations retain real page numbers; other formats use captured line references. |
| **Website** | Capture a bounded set of public pages with robots.txt, DNS and redirect checks. A site with no readable body produces an actionable capture error. |
| **Search** | Compare research on supplied sources or explicitly enable Tavily for a shared live search. Search is off by default. |

Scout is the concise baseline; Relay adds bounded recovery. Web, Repo and Document Analyst profiles specialize the same engine. Custom HTTP agents currently support the research benchmark contract, not paired chat.

### A real repository recovery example

Rilo captured **40 files** from [KYRO](https://github.com/Gauravwakle96/KYRO) at commit `a03f97ded1f5da474cf16eefe08afec1b5133e07`. Repo Analyst and Relay independently described the project using the same selected README passage. Repo Analyst first omitted citations; its single repair attempt added them, with the original response retained in the trace.

Both completed, and all emitted citations matched captured passages. This verifies references within a bounded overview, not every claim or the security of the repository. The configured Docker unittest runner found zero tests and returned a failure; that outcome remains in the report.

[Read the PDF report](docs/ui-evidence/kyro-recovery-2026-11-10.pdf) · [Inspect the complete JSON record](docs/ui-evidence/kyro-recovery-2026-11-10.json) · [Diagnosis and verification](docs/USER_FAILURE_FIXES_2026-11-10.md)

## Quick start

**Requirements:** Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and [Node.js](https://nodejs.org/) **22.22+** (Node 24 used in CI). Python **3.13** is pinned in `.python-version`. Ollama and a downloaded model are needed for real AI responses; Docker is optional for isolated repository tests.

### 1. Install and start the workspace

```sh
git clone https://github.com/Gauravwakle96/RILO.git
cd RILO
uv sync --locked
npm ci --prefix frontend
npm ci --prefix backend/rilo/promptfoo_runtime
npm run build --prefix frontend
uv run rilo serve
```

Open **http://127.0.0.1:8018**. This starts the API, built frontend and a separate durable worker. A fresh clone starts with an empty evaluation history. The committed reports are evidence to inspect; they are not silently loaded as new results. Press `Ctrl+C` to stop the API and worker.

On Windows, `START_RILO.cmd` performs setup/build/start. After the first build, `START_RILO.cmd -SkipBuild` skips rebuilding the frontend. The lower-left **Start here** guide explains requirements and actions.

### 2. Try the workflow without a model

In another terminal, from the repository directory:

```sh
uv run rilo demo --full --wait
```

This schedules 120 **explicitly labeled deterministic fixture attempts**. It exercises scheduling, faults, traces and evaluation without an API key or model. Fixture synthesis uses Python logic, not AI inference. For a shorter UI walkthrough, choose **Try recovery example** in the guide.

### 3. Connect real local inference through Bifrost

Install and start [Ollama](https://ollama.com/). In a separate terminal:

```sh
ollama pull qwen2.5-coder:7b
uv run python scripts/setup_gateway.py --start
```

The helper downloads the official pinned Bifrost binary, configures its local Ollama provider and creates restricted gateway credentials in private `.env`. Leave the gateway running. **Restart `uv run rilo serve` after this setup** so both API and worker load the credentials. Existing model/provider settings are preserved. On Windows, `START_RILO.cmd -Gateway` can launch the project gateway and workspace together.

Check service status and run the full real-model research suite:

```sh
uv run rilo doctor
uv run rilo run examples/research-model.json --wait --timeout 2400
```

The recorded 120-attempt model run took about 16 minutes on the development laptop. Hardware, model state and load affect runtime. Both workspace agents run sequentially to fit local hardware. Core local inference needs no paid API, although hardware, downloads, electricity and optional services have their own costs.

### 4. Try a paired task with explicit checks

1. Open **Chat** and select **Scout** and **Relay**.
2. In **Supporting context**, enter: `The application stores records in SQLite. It caches lookups in Redis.`
3. Ask: `Name the database and cache in one sentence.` Add two case-insensitive contains checks: `SQLite` and `Redis`.
4. Send to both agents. Inspect the answers, check matrix, citations, usage and traces.
5. Choose **Save task as regression test**, then **Retest** or run the saved suite in **Benchmarks**. Use **Regression Lab** to compare compatible runs.

Text checks match spelling and word order literally. No checks means ungraded; two failures mean neither met the requirements. Rilo does not change a failing rule to manufacture a winner.

## How it works

```mermaid
flowchart TD
    UI[React and TypeScript workspace] --> API[FastAPI: validated requests and local session]
    API --> Queue[(SQLite: durable jobs and history)]
    Queue --> Worker[Python worker]
    Worker --> Context[Capture and select shared source snapshot]
    Context --> A[Agent A: own history]
    Context --> B[Agent B: own history]
    A -. model requests .-> Bifrost[Bifrost gateway]
    B -. model requests .-> Bifrost
    Bifrost --> Ollama[Ollama local model]
    A --> Results[Recorded answers, events and usage]
    B --> Results
    Results --> Checks[Promptfoo checks and independent evidence verification]
    Checks --> Reports[Comparison, reports and regression suites]
    Reports --> Queue
```

**Bifrost's role:** authenticated model routing, returned model/provider metadata, token usage and observable request boundaries. Rilo records agent steps and tool behavior around those requests; gateway visibility alone does not describe an entire agent.

**Tavily's role:** optional live search before generation, with one shared capture for paired workspace tasks. The adapter has contract/error tests; **live Tavily acceptance is not yet validated because no key was configured**. GitHub ingestion, documents, readable websites and source-based chat work without Tavily.

```text
backend/rilo/
  api.py, storage.py, worker.py        API, SQLite migrations, durable execution
  agents.py, engine.py                 Research workflows and observed boundaries
  workspace_engine.py                 Independent paired task execution
  ingestion.py, snapshots.py           Input capture and content-addressed sources
  verification.py, promptfoo_checks.py Evidence verification and task assertions
  workspace_evaluation.py, reports.py  Comparisons and persisted-data reports
frontend/src/                          React workspace and reusable components
tests/                                Backend, boundary, SDK and CLI tests
frontend/tests/                       Browser workflows and opt-in live checks
docs/                                 Guides, evidence, architecture and licenses
```

Large uploads and source objects live in the ignored `.rilo/` directory, with metadata and execution records in SQLite. No extra message broker or distributed services are required. See the [architecture](docs/ARCHITECTURE.md) and [workspace API](docs/WORKSPACE_API.md).

## Configuration and developer automation

Use [.env.example](.env.example) as the reference. Keep credentials in private `.env`, which is excluded from Git.

| Setting | Purpose |
| --- | --- |
| `RILO_BIFROST_URL`, `RILO_MODEL` | Local gateway endpoint and selected model. The helper starts Bifrost on port 8086. |
| `BIFROST_API_KEY` | Private gateway credential generated by the helper or configured for your gateway. |
| `TAVILY_API_KEY` | Optional live search; select Tavily in the UI only after configuration. |
| `GITHUB_TOKEN` | Optional authorized private-repository access. Never sent to agents. |
| `RILO_SANDBOX_IMAGE` | Optional preinstalled Docker image pinned by digest for fixed test profiles. |
| `RILO_WORKSPACE_INPUT_BYTES` | Bounded serialized input; defaults to 6,000 bytes. Increase only after validating model context. |
| `RILO_MODEL_PRICING_JSON` | Optional explicit token-price map. Missing usage/pricing stays unknown. |
| `RILO_DATA_DIR` | Private local storage; defaults to `.rilo`. |

Restart the API and worker after changing environment variables. Search availability, provider reachability, model availability and worker readiness are shown separately.

The Python SDK and CLI support repeatable research benchmarks:

```sh
uv run rilo baseline EXPERIMENT_ID --name "Research reference"
uv run rilo compare --baseline BASELINE_EXPERIMENT_ID --candidate CANDIDATE_EXPERIMENT_ID --require-pass
uv run rilo report EXPERIMENT_ID --output reports/evidence.json
```

The CLI comparison exits `0` for pass, `1` for a measured regression and `2` for inconclusive evidence. Declare agent changes explicitly with `--allow-agent-changes`; incompatible task, model, source or grading conditions do not become a valid ranking. See [SDK and HTTP-agent integration](docs/DEVELOPERS.md).

## Verification and boundaries

The **10 November 2026 local verification** recorded **198 Python tests passing, 84.04% coverage, 18 standard browser tests passing**, and two additional browser checks against real user-reported failures. Type checks, lint, frontend/Python builds and dependency audits also passed. These are dated checks, not a guarantee of error-free behavior; the badge above links to the current GitHub workflow.

The [11 November publication checks](docs/PUBLICATION_VERIFICATION.md) reran all **198 Python tests** with **84.13% coverage**, plus backend/frontend lint, types and build checks. GitHub CI runs separately on the published source.

```sh
uv run ruff check backend/rilo tests scripts examples
uv run mypy backend/rilo
uv run pytest --cov=rilo --cov-fail-under=80
npm run lint --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

For browser tests, start the API/worker with an idle queue, then run from `frontend/`: `npx playwright install chromium` and `npm run test:e2e`. The suite uses actual local fixture jobs; explicitly labeled boundary simulations and opt-in live-model checks are separate. [Full verification record](docs/RILO_2_VERIFICATION.md).

- **Deployment:** local, single-user application. Public multi-user hosting and tenant authorization are not implemented.
- **Evidence:** source integrity is different from factual correctness. Semantic review is advisory; repository accuracy requires suitable independent ground truth.
- **Repositories:** bounded capture and passage selection, not a complete security audit. Private GitHub access has not undergone live acceptance without credentials.
- **Untrusted inputs:** SSRF/DNS/redirect checks, archive path checks, upload/response bounds, session/CSRF protection and secret redaction have automated coverage. Optional repository code runs in constrained Docker containers with no host mounts or network; this is not an independent security certification.
- **Documents and websites:** text PDFs only; no OCR. Page scripts are not executed, so JavaScript-only content may need a readable URL or pasted text. Standard PDF export fonts have limited non-Latin coverage.
- **Statistics and fees:** small repeated samples are not broad reliability claims. Unknown metrics remain unknown; local zero-rate API estimates exclude compute and energy.

## Documentation and attribution

| Read next | Contents |
| --- | --- |
| [Judge's guide](docs/HACKATHON.md) / [Pitch outline](docs/PITCH.md) | Challenge mapping, demo sequence and submission summary |
| [Workspace guide](docs/RILO_2_GUIDE.md) | Inputs, profiles, checks, reports and requirements |
| [Benchmark evidence](docs/BENCHMARK.md) | Research results, methodology, preserved failures and raw records |
| [Developer guide](docs/DEVELOPERS.md) / [Deployment](docs/DEPLOYMENT.md) | SDK, CLI, local startup, storage and troubleshooting |
| [Implementation](docs/RILO_2_IMPLEMENTATION.md) / [Verification](docs/RILO_2_VERIFICATION.md) | Delivered capabilities, test evidence and remaining work |
| [Promptfoo integration](docs/PROMPTFOO_INTEGRATION.md) / [Third-party notices](THIRD_PARTY_NOTICES.md) | Actual upstream reuse, licenses and boundaries |

Rilo source is **Apache-2.0**. Original synthetic research fixtures are **CC0**. Reused Promptfoo code is **MIT** with attribution; fonts retain their **OFL** notices. KYRO excerpts in the sample report retain their own [MIT notice](docs/licenses/KYRO-MIT.txt). Model weights and downloaded gateway binaries are not included. Historical plans are preserved in the documentation and are not additional completion claims.

Built by [Gaurav Wakle](https://github.com/Gauravwakle96). Pronounced **REE-loh**.
