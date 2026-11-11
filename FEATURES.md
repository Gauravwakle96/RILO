# Rilo project and feature checklist

Updated 9 November 2026. Checked items are implemented; external acceptance and future work are identified separately. [VERIFICATION.md](docs/VERIFICATION.md) records actual checks, and [BENCHMARK.md](docs/BENCHMARK.md) records measured experiments.

## RILO 2.0 workspace expansion

- [x] Five task workspaces on the existing worker: Chat, Repository, Documents, Website, Search.
- [x] Independent paired histories, shared follow-ups, cancellation, retries preserving attempts.
- [x] Public GitHub commit capture and ZIP ingestion with real file evidence.
- [x] Text PDFs with actual pages; DOCX/TXT/Markdown with line references.
- [x] Bounded website capture with robots, public-address, DNS and redirect protection.
- [x] Optional Tavily, default off; missing-key errors and shared source capture.
- [x] File-backed source snapshots, hashes, exact quotes and reference validation.
- [x] Independent advisory semantic review, qualified interpretations and potential disagreements.
- [x] Python AST inventory, optional OSV exact-version checks, isolated Docker tests.
- [x] Versioned suites, repeated trials, optional quotation labels and regression comparisons.
- [x] PDF/Markdown/JSON/CSV reports from persisted results.
- [x] Real aggregate dashboard, profiles, traces and local source storage quotas.
- [ ] Live Tavily/private GitHub validation with credentials.
- [ ] Calibrated semantic accuracy/security benchmarks and comprehensive disagreement resolution.
- [ ] Multi-user/team authentication, public deployment, OCR and retention management.

See [implementation limits](docs/RILO_2_IMPLEMENTATION.md) and
[current verification](docs/RILO_2_VERIFICATION.md). These are not hackathon scores.

## Preserved product features

- [x] Local browser application served by the Python API.
- [x] React/TypeScript dashboard with experiments, agents, tasks, scenarios, evidence, comparison and settings.
- [x] Dark/light themes with locally served Inter and JetBrains Mono fonts.
- [x] Responsive mobile, tablet and desktop navigation/layout.
- [x] Keyboard focus, native dialogs, Escape dismissal, reduced-motion support and accessible status text.
- [x] Loading, empty, error, partial, cancelled, success and session-rejection states.
- [x] Lower-left Start here guide: workflow, requirements, functions and result interpretation.
- [x] Reviewable twelve-attempt recovery example with no API key requirement.
- [x] Actual recorded real-model comparison on the experiment landing view.

## Agents and tasks

- [x] Scout: independent plain-Python search/synthesis agent.
- [x] Relay: actual LangGraph workflow with bounded retries and evidence filtering.
- [x] Register an existing loopback HTTP agent without replacing its internal loop.
- [x] Explicit adapter capabilities and unknown internal metrics for opaque HTTP agents.
- [x] HTTP version history with new version registration and immutable historical experiment snapshots.
- [x] Recent company briefing task.
- [x] Similar-name entity matching task.
- [x] Conflicting-source task.
- [x] Insufficient-evidence task.
- [x] Multi-step research task.
- [x] Custom referenced tasks against the known synthetic corpus.

## Automation and reliability

- [x] Create experiments with selected agents, tasks, scenarios and limits.
- [x] Fresh attempt state, 1–5 repetitions and randomized recorded order.
- [x] Full 120-attempt research/failure matrix.
- [x] Durable database-backed queue and independent single worker.
- [x] Search timeout, synthesis outage and untrusted-document instruction scenarios.
- [x] Recorded scenario activation and bounded retries.
- [x] Model/tool call limits, experiment admission limits and attempt timeouts.
- [x] Cancellation with retained attempts/traces.
- [x] Worker leases and explicit partial/interrupted outcomes after failure.
- [x] Idempotent experiment submission.
- [x] Implementation/dependency hashes and worker/manifest compatibility checks.

## Measurements and developer workflow

- [x] Task success, failure, inconclusive and infrastructure categories.
- [x] Explicit steps and model/tool boundary counts.
- [x] Actual response tokens with reported/unknown/not-applicable provenance.
- [x] Explicit configurable model price basis; estimated fees when supported.
- [x] Per-attempt runtime and experiment elapsed timestamps.
- [x] Trace inspector, source-backed fact checks, outputs and grading limitations.
- [x] Condition-by-agent recovery table with direct attempt inspection.
- [x] Retest a recorded case: focused task/fault preset preserving model and budgets.
- [x] Save baselines and compare candidates.
- [x] Declare agent changes while keeping grading/tasks/evidence/model/limits compatible.
- [x] Pass/fail/inconclusive exploratory regression gate.
- [x] Python SDK and headless CLI.
- [x] JSON/CSV report export with retained attempts and redacted credentials.
- [x] Local setup/start scripts, environment example and deployment/developer docs.
- [x] Source/package build and GitHub Actions verification workflow definition.
- [x] Self-hosted searchable API reference with protected schema access.

## Integrations and validation

- [x] Real authenticated Bifrost → local Ollama inference.
- [x] Restricted local model allowlist and private gateway/session credentials.
- [x] Controlled synthetic evidence and deterministic fixture engine, explicitly distinguished from real models.
- [x] Tavily live request implementation with bounds, dates, returned usage and strict response validation.
- [x] Meaningful Python unit/API/worker/SDK/CLI tests and coverage.
- [x] Actual browser workflows and axe checks at 390×844, 768×1024 and 1440×900.
- [x] npm and locked Python dependency audits; configured-secret review.
- [x] Completed actual-model matrix: 120 attempts, Scout 24/60 and Relay 48/60 passed.
- [x] Completed fixture reference/candidate comparison and real CLI pass exit code.
- [x] Final Python verification: 127 passed, 84.55% line coverage.
- [x] Final complete browser workflow suite: 13 passed, including guide and focused retest flows.
- [x] Benchmark and verification documentation with retained JSON/CSV/browser evidence.
- [ ] Live Tavily acceptance: no API key is configured on this machine.
- [ ] External CI execution on GitHub: workflow is prepared, repository has not been published.
- [ ] Public hackathon submission and demo upload: local materials are prepared separately.
- [ ] Independent developer feedback on a recurring real research task.

## Future scope

- [ ] Calibrated semantic grading of live answers and free-text summary claims.
- [ ] Arbitrary third-party agent instrumentation and supported failure injection callbacks.
- [ ] Importable external evidence packs with source/rights management.
- [ ] Scheduled runs, advanced regression policies and statistical confidence analysis.
- [ ] Team accounts, permissions, PostgreSQL deployment and isolated remote workers.
- [ ] Coding, support and business-workflow task packs.
- [ ] Desktop installer and optional hosted service after developer validation.

The current release is a local research-agent testing product. Passing its tests or benchmark does not guarantee a hackathon score or an agent’s behavior on all future tasks.
