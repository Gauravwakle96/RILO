# Local product implementation

Scope: improve the existing Rilo installation, interface, independent agent
configuration, local adapters, evidence coverage, evaluation, suites, history and
data management. Preserve existing experiments and defaults. No hosted expansion.

## Delivery order

1. Baseline and private backup; indexed history, accurate totals and local storage.
2. Colorful accessible interface, guided setup, normal launch without reinstall.
3. Independent comparison slots, model/prompt settings and compatible HTTP agents.
4. Source selection, richer deterministic checks, multi-case suites and retests.
5. Backup/restore, offline enforcement, diagnostics and failure acceptance.
6. Full regression, browser acceptance, documentation and limits.

Local mode remains browser-based over loopback with SQLite and sequential inference.
Any measured result must identify the executed checks. Optional internet integrations
remain explicit. Do not describe incomplete or untested capabilities as delivered.

Fresh baseline and delivery evidence will be appended as checks finish.

## Delivered and verified, 12 November 2026

- Preserved SQLite data and created a private pre-change backup.
- Migration 6 indexes history; paginated evaluation/conversation search and SQL
  dashboard aggregates replace capped totals.
- Independent A/B slots pin agent versions and configurations; the same profile
  can use different models/instructions. Histories remain isolated.
- Per-slot pricing is captured at admission; unknown usage/cost remains unknown.
- Local workspace-v1 adapters receive shared sources and only their own history.
  Internal model/tool metrics remain explicitly unobserved; legacy research stays.
- Chat captures a single URL in the user message or explicit URL input. Uploaded
  documents and website context can be combined. Repository refs resolve a captured
  GitHub revision. Retrieved instructions are never executed.
- Source inspector shows actual captured files/pages, bounded previews and focused
  selection for the next task; invalid references are rejected.
- Added JSON-field equality, length, findings and citation-integrity checks.
  Literal checks retain Promptfoo; each result identifies its method.
- Multi-case suites preserve each case's task, snapshot, checks and labels.
  Case identity is part of regression compatibility. Partial submissions identify
  queued cases. CLI/SDK support suite-case/retest workflows.
- Blue/violet/teal controls, guided setup, actual inference diagnostics, conversation
  rename/search, tab-local draft text and storage usage/cleanup.
- Private streaming backup and shared CLI restore reject links, traversal, duplicate
  members, changed and unmanifested payloads. Restore requires an empty/new folder.
- Offline policy refreshes in workers before new external requests and blocks remote
  Bifrost routes, AgentRouter, retrieval and opaque adapters. Already dispatched
  requests may finish; this is application policy, not a network firewall.
- AgentRouter credential saved in ignored private .env and services restarted.
  Live chat-completions test returned HTTP 401; account access remains unavailable.
  Original Ollama default preserved. Tavily remains optional.

## Verification evidence

- Fresh baseline: 208 Python tests passed.
- Current full suite: 230 passed, 83% aggregate coverage.
- Ruff, mypy, frontend lint, TypeScript and production build passed.
- Python runtime and frontend/Promptfoo production dependency audits returned
  no known vulnerabilities.
- Actual public-page capture and Ollama inference: `exp_43f13520d226445c`, both
  agents completed, all 5 emitted citations matched captured passages. This verifies
  references, not all prose or instruction adherence.
- Standard browser suite: 21 passed, 8 skipped. Checks cover guide focus, both
  themes, 390/768/1440 layouts, legacy HTTP version/testing and source inspection.
  Skips identify opt-in live cases and unavailable historical fixtures; they are
  not counted as passes.
- Additional actual live browser acceptance: 4/4 passed for paired chat with isolated
  follow-ups/retest reports, public GitHub ingestion with captured commit/file citations,
  PDF upload with page-2 references, and website/source-only research. Docker acceptance
  was not included in this run. Tavily and private GitHub were not tested live.

## Material limits and follow-up work

Local single-user, sequential inference, ten-evaluation queue. A temporary-store
fixture capacity exercise completed 30 evaluations / 60 attempts with no unfinished
runs and 100 history/dashboard reads on four reader threads. Median read latency
was 51 ms and p95 111 ms. This does not establish model throughput, customer
usability or hosted capacity. Context remains bounded; explicit extractive
continuations retain original history and disclose omitted text.
Repository capture is not exhaustive analysis; selected passages are disclosed.
Runtime repository tests require the opt-in constrained Docker runner. Live private
GitHub/Tavily need credentials. AgentRouter was excluded from this delivery scope.

Cleanup removes only unreferenced blobs. Local archive/restore and confirmed deletion
are implemented. Deletion preserves shared sources and protects baseline, suite,
retest, regression and continuation dependencies. Editable A/B reruns preserve the
original task, histories, snapshot and checks; candidate changes are recorded.
Persisted suite batches provide combined results, case links, JSON export and
idempotent admission of missing cases. Folder import makes an actual bounded ZIP
in the browser and skips dependency/build folders and common credential filenames.
Bundled OFL fonts with HarfBuzz shaping support Latin, Greek, Cyrillic, Devanagari
and Arabic reports. Unsupported scripts fail with a Markdown/JSON alternative.
Human finding reviews persist independently and do not overwrite automated checks.

Public URL investigation is supported in Search without Tavily. Missing-source
requests fail before queuing. Retrieval uses a fixed TLS-verified Cloudflare DNS
fallback only when system DNS fails, validates all returned IP addresses and pins
the connection. Dashboard records explain source-preparation failures.

Bynara integration added at the user's request: private credential saved, model
listing returned HTTP 200, auto/bynara returned model-not-found HTTP 404, and
agnes-3-flash inference returned insufficient-credit HTTP 402. A separate
agnes-2.5-flash request returned HTTP 200 with observed usage (285 input / 77
output tokens). Paired evaluation `exp_ee8e637290f9468c` completed both agents and
passed two declared checks on each response (finding present and captured-reference
validity). Scout reported 881 input / 196 output tokens; Relay reported 888 / 357.
At the user's subsequent request the active local configuration now selects
`bynara/agnes-2.5-flash` for new tasks. Existing runs retain their pinned models;
installed Ollama and Bifrost settings were preserved.

External first-use studies, independent security/semantic-accuracy evaluation and
broad real-workload capacity remain validation limits, not completed certifications.
No flawless-product claim or hackathon score guarantee is made.

## Final delivery verification

The final local website investigation `exp_5c825bac596c4baf` captured example.com,
completed both agents and passed both declared checks on each response (findings
present and valid captured references). All six emitted citations matched the
captured page. This is a real public fetch and Bifrost/Ollama inference, not a
fixture or general factual-accuracy measurement. The original failed records are
preserved, including the missing-source and DNS failures diagnosed during work.

Final checks after the local product and provider changes:

- Full Python suite after all changes: 242 passed, 83% aggregate coverage.
- Standard browser suite: 24 passed, 8 explicitly skipped. Skips cover opt-in live
  cases and unavailable historical fixtures; they are not counted as passes.
- Ruff, mypy, frontend lint/typecheck and production build passed.
- Python source/wheel build passed; all three fonts and OFL license are in the wheel.
- Locked Python runtime, frontend and Promptfoo production dependency audits found
  no known vulnerabilities. Public candidate-file credential scan found no matches.
- Fresh live browser acceptance passed for all four scenarios across separate
  runs: paired chat, public GitHub, PDF, and website/source-only research. The final
  website scenario passed independently in 1.3 minutes. A prior overlapping-run
  trace-output collision was not counted as a successful acceptance check.
- Final targeted browser checks: 4 passed in 17.6 seconds after making the folder
  ZIP validation portable and exercising archive/restore with a separately created
  test conversation. The settings check includes the Bynara integration. Frontend
  lint/typecheck/build passed; the active UI shows `bynara/agnes-2.5-flash`.
- Publication follow-up: saved conversation links now restore the selected chat
  on reload and browser navigation, including links from Reports. Six targeted
  browser checks passed in 21.3 seconds after this fix; lint/typecheck/build passed
  again. These targeted results are separate from the full standard-suite totals.
