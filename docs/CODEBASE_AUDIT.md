# RILO 2.0 codebase audit

Audit date: 9 November 2026. Existing project: `C:\Windows\System32\Rilo`.
This document describes the pre-expansion code inspected during Phase 0. Historical
verification is not used as a substitute for the fresh checks below.

## Existing architecture

- React 19, TypeScript and Vite frontend. Hash navigation in `App.tsx`; reusable
  forms, catalog, experiments, guide and UI modules. Local Inter and JetBrains Mono.
- FastAPI API under `/api/v1`, same-origin production assets, protected local API
  documentation. Pydantic request validation, bounded JSON transport.
- SQLite WAL via `Store`, schema versions 1 and 2. Catalog, agent versions,
  experiments, runs, events, baselines and worker lock. Parameterized SQL.
- Separate durable Python worker, atomic admission/claim, process lock, heartbeat,
  stale-run recovery, cancellation, bounded dispatch and retained failure evidence.
- Scout is a plain Python baseline; Relay is a LangGraph retrieval/filter/synthesis
  workflow with bounded retries. Both use `RunContext` for tools, model calls and
  metrics. HTTP registration is loopback-only, final-output observation only.
- Bifrost uses an authenticated local OpenAI-compatible endpoint. Ollama health and
  model listing are separate checks. Fixture synthesis is explicitly distinguished
  from real model inference. Unknown token/cost observations remain null.
- Controlled search uses a synthetic corpus. Live search uses fixed Tavily basic
  search, validated results and usage trace events. Credentials come from `.env`.
- Research grader v2 checks referenced structured facts, task coverage and explicit
  conflict/uncertainty behavior. It does not verify every free-text summary claim.
- Manifests pin task/source/agent/grader/runtime identities. Comparison rejects
  incompatible conditions; declared agent changes are supported. SDK and CLI expose
  experiments, inspection, reports, baselines, cancellation and regression gates.
- JSON reports contain stored manifests, attempts and traces. CSV escapes spreadsheet
  formulas. Reports do not invoke an LLM to invent results.
- Deployment is local single-user. `rilo serve` starts API and worker;
  `scripts/Start-Rilo.ps1` installs locked dependencies, builds and optionally starts
  Bifrost. GitHub workflow exists in `.github/workflows/verify.yml`.

## Fresh baseline

- `.venv/Scripts/python.exe -m pytest -q`: **127 passed in 111.62 seconds**.
- `npm run test:e2e`: **13 passed in 2.8 minutes** before expansion. These checks exercised the real local API and fixture worker.
- Existing files are uncommitted/untracked in the initialized repository. Preserve
  them; a clean Git diff cannot establish a baseline. No existing tests removed.

## Confirmed existing capabilities

Backend baseline covers API authorization/CSRF/origin controls, endpoint validation,
bounded tool/model transport, worker execution/recovery/cancellation, real-dispatch
contracts with test transports, grading, price provenance, HTTP agent revisions,
SDK/CLI and documentation. Browser checks additionally exercise actual local flows.
Past real Bifrost/Ollama results remain historical evidence, not fresh live validation.

The guide, 12-attempt recovery example, condition table and focused retest exist.
Five research tasks, normal plus three injected scenarios, repetitions, run traces,
baselines and revision comparison are implemented.

## Partial features and technical debt

- Tavily adapter exists but no usable key has been supplied; live validation remains
  unavailable. Its local lifetime credit reservation is not the provider's monthly
  balance, and cancellation does not refund reservations.
- General conversation, repository, document and website tasks have no contracts.
- Research-specific task/source/output assumptions are embedded in `RunContext`.
- Large evidence is embedded in manifests. New repository/document contents need
  content-addressed file storage and bounded selected passages.
- Catalog entries do not yet declare task-specific profile requirements/limitations.
- Existing quality scores depend on known synthetic references. They cannot be
  transferred to unfamiliar repositories or subjective chat.
- Runtime identities make changes detectable, but migrated worker/API versions must
  agree before dispatch. Restart both after an implementation change.
- The API and experiment UI are large modules. Add feature modules and routers rather
  than duplicating their existing responsibilities.

## Missing capabilities

Persistent paired chat/follow-ups, repository/ZIP ingestion, sandbox test runner,
PDF/DOCX processing, bounded public website retrieval, shared evidence objects,
cross-domain verification/disagreement detection, arbitrary versioned benchmark
suites, general evaluation regression comparisons, Markdown and PDF reports.

## Security assessment

Existing local boundary: loopback host checks, allowed origins, HttpOnly SameSite
session, CSRF tokens, local CLI bearer key, no frontend credentials, size limits,
fixed external Tavily endpoint, no redirected local agent requests, redacted traces.

Gaps to resolve before adding external inputs:

- Local session bootstrap is not multi-user authentication. Do not advertise this
  deployment as an Internet-facing team service or silently expose it publicly.
- New URL retrieval needs DNS/IP pinning, redirect validation, robots policy,
  bounded decompressed bodies and explicit public-host rules.
- ZIPs need traversal/symlink/bomb protection. Uploaded data must remain outside the
  public asset directory. No repository instructions may execute on the host.
- PDF/DOCX parsers need file/type/page/output limits and bounded processing.
- Executable tests require an available isolated runner with no network, no secrets,
  explicit commands, time/CPU/memory/output limits and recorded environment.
- Retrieved instructions must remain untrusted model data. Evidence hashes prove
  integrity, not the truth of a model's interpretation.
- Existing rate limiting and sessions are process-local; suitable only for this
  single-server deployment until a shared identity/access architecture is built.

## Database changes and data flows

Add versioned migrations for conversations, paired messages, snapshot metadata,
evidence/verification artifacts, saved suites, comparisons and report records.
Reuse experiments/runs/events and their durable worker instead of a second queue.
Store bulk sources in a private content-addressed directory; pin metadata and
selected evidence to a run. Every shared follow-up gets one shared user message and
agent-specific prior messages; sibling answers never enter generation context.

## Implementation order

0. Audit and fresh baseline (this document).
1. Typed general task/output contracts, migrations, snapshots and shared model calls.
2. Persistent paired chat, optional Tavily selection, traces and cancellation.
3. Repository ingestion, static evidence and isolated test adapter.
4. Evidence integrity, independent verification and conservative disagreement matching.
5. Search source metadata/deduplication and provider availability.
6. Text PDF, DOCX, TXT and Markdown ingestion with honest page semantics.
7. SSRF-protected bounded website capture.
8. Versioned suites, labeled metrics and repeated trials.
9. Compatible historical comparisons and retests.
10. Persisted JSON/CSV/Markdown/PDF reports.
11. Security, full regression/browser checks, deployment and limitations documentation.

## Primary documentation consulted

- [Promptfoo test cases](https://www.promptfoo.dev/docs/configuration/test-cases/):
  declarative inputs/assertions; keep evaluation separate from generation.
- [Inspect tasks](https://inspect.aisi.org.uk/tasks.html): dataset/solver/scorer
  separation and reproducible log records.
- [DeepEval faithfulness](https://deepeval.com/docs/metrics-faithfulness): separate
  retrieval grounding from answer correctness; model judgments require labeling.
- [Langfuse data model](https://langfuse.com/docs/observability/data-model):
  session/trace/observation relationships, reused through existing traces.
- [GitHub contents API](https://docs.github.com/en/rest/repos/contents): commit
  identity, recursive trees and explicit truncation handling.
- [pypdf extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html):
  page-based extraction and its limitations; extraction is not OCR.
- [Tavily search](https://docs.tavily.com/documentation/api-reference/endpoint/search):
  basic search, usage, date metadata and explicit optional configuration.
- [OWASP SSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html):
  destination validation and DNS rebinding protections.

These are engineering references. No third-party application source was copied and
none of these evaluation platforms was installed as duplicate infrastructure.
