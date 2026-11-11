# Rilo: judge's guide and submission summary

**Project:** Rilo — AI Agent Benchmarking & Verification

**Repository:** https://github.com/Gauravwakle96/RILO

**Primary challenge:** Bifrost Problem Statement 02

**Selected benchmark category:** Research agents

## Submission summary

Rilo helps developers compare complete AI agents under identical tasks and recorded
conditions. It runs independent agent implementations, injects controlled failures,
records traces and usage, verifies source references and saves repeatable regression
tests. A 120-attempt research benchmark using real Bifrost/Ollama inference recorded
Scout at 24/60 passes and Relay at 48/60. Both performed equally in normal conditions;
Relay's bounded recovery explains the difference under injected tool/model failures.
Those results are limited to the included synthetic suite, with raw evidence supplied.

The developer workspace extends the same execution/evidence pipeline to paired chat,
repositories, documents, websites and research. Actual Promptfoo assertions grade
declared requirements; immutable snapshots, original failed attempts and explicit
unknowns keep the comparison auditable. Bifrost provides real model routing and
observed usage. Tavily is optional; its adapter is implemented but live acceptance
remains unvalidated without a configured key.

Rilo targets **Problem Statement 02: Build a Benchmarking Platform for AI Agents, Not Just Models**, choosing the research-agent category. The project is also designed for developers who need to reproduce failures and check an agent revision against a pinned baseline.

Official problem statement: [Bifrost benchmark platform PDF](https://hackcultureplatform.blob.core.windows.net/event-assets/hackathons/6ac5c8240037f69fb28e23ec/problem_explanation_ck1ellfr6qh.pdf), retrieved and read again on 11 November 2026. The PDF names a 1–15 November build window, teams of 1–4, online/global format and 29 November judging. Its footer says “Bifrost + Tavily”; the organizer's submission instructions supplied by the participant explicitly allow a single-technology entry or a combined entry. Rilo's demonstrated submission is the Bifrost challenge. Do not claim Tavily challenge acceptance without the corresponding working demonstration. The exact portal closing timestamp/timezone should be checked at submission.

## Problem and solution

An agent can succeed in a polished demonstration and still fail when a tool times out, a model is unavailable or a document contains misleading instructions. Developers comparing agents often change evidence, budgets, grading or models unintentionally, so a higher apparent score may not mean a better agent.

Rilo runs a fixed research suite under recorded conditions, repeats attempts, injects controlled failures and retains every outcome. Its dashboard links metrics to source evidence, outputs and chronological execution events. Developers save a baseline, declare a candidate change and use an exploratory regression gate to make the difference inspectable.

## Requirement mapping

| Official requirement | Implemented proof | Material limit |
| --- | --- | --- |
| Framework independence | Scout plain Python, Relay LangGraph, local HTTP adapter and revision history | HTTP internal instrumentation and injected failures remain unknown/unsupported |
| Same tasks and measurable criteria | Five-task synthetic suite, pinned manifest, reference checks, steps/calls/tokens/fee basis/time | Reference facts are limited; free-text summary truth is unassessed |
| Repeatability | Three repetitions per agent/task/condition, fresh state, randomized order, immutable hashes | Fixed prompts/local model can return identical results; small suite is not broad statistical proof |
| Failure testing | First search timeout, first synthesis outage, injected document instruction with activation events | Controlled boundary faults; no real external outage is induced |
| Inspection/comparison | Dashboard, trace/output/evaluation tabs, exports, baselines, declared changes and inconclusive gates | Initial gate checks measured success regression rather than a full production policy |
| Bifrost integration | Authenticated actual local-model routing and usage/provider provenance | Optional fallback/cache settings outside Rilo must remain explicit |
| Tavily integration | Real fixed endpoint implementation, bounded basic search, task date windows, validated results and returned credits | **Live acceptance is pending because no key is configured** |

Use actual results from [BENCHMARK.md](BENCHMARK.md). Do not describe fixture synthesis or mocked integration tests as real AI or real Tavily results. The first grader’s observed false negative was corrected through a new grader version; historical reports are preserved and the corrected experiment is a fresh execution.

## Three-minute demo

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:25 | Experiment dashboard and two agent frameworks | “Same model does not mean the same agent behavior.” |
| 0:25–0:55 | Recorded experiment configuration with five tasks, four conditions, three repetitions | Show the 120-attempt design, controlled evidence, limits and real-model engine |
| 0:55–1:25 | Completed actual-model metric table | Compare numerator/denominator, steps, calls, tokens, fee provenance and runtime |
| 1:25–1:55 | Relay search-timeout trace versus Scout error | Show fault delivery, retry, actual response and final evidence check |
| 1:55–2:20 | Failed insufficient-evidence output | Show an honest remaining agent defect and its linked grading evidence |
| 2:20–2:45 | Paired task checks and a saved regression suite | Show the same requirements, actual Promptfoo results, snapshot and retest action |
| 2:45–3:00 | CLI report/compare and settings | Show developer automation and explicitly disclose Tavily acceptance status |

Use precomputed real experiments for timing; starting a full model run during a three-minute presentation is impractical on this laptop. The fixture engine can demonstrate a fresh complete flow quickly if clearly identified. Do not replace benchmark results with edited screenshots.

For a repository-focused follow-up, show the [KYRO PDF report](ui-evidence/kyro-recovery-2026-11-10.pdf): two independent overviews, a captured commit, exact README references, and the original missing-citation response followed by one repair. This demonstrates source verification without claiming an exhaustive security audit.

For a fresh installation, historical JSON/CSV/PDF reports in this repository are
readable evidence; they are not preloaded into the application. Run the README's
fixture example or paired-context walkthrough to generate a new record.

## Submission package

- Local application source, locked dependencies, README, environment example and license notices.
- [Architecture](ARCHITECTURE.md), [developer workflow](DEVELOPERS.md), [evaluation](EVALUATION.md) and [current verification](RILO_2_VERIFICATION.md).
- [Benchmark evidence](BENCHMARK.md), pinned JSON/CSV reports and actual browser screenshots.
- [Slide outline](PITCH.md) and the demo script above.
- Configure Tavily privately, execute a bounded live query and record actual acceptance before claiming both integrations are demonstrated.
- Prepare the public repository and recorded demo using the portal’s current submission requirements.

The source and evidence are prepared for the public repository linked above. The
pitch outline is not an uploaded PPT file. A final deck and the hackathon form still
need to be submitted; a deployed application is optional under the organizer's
instructions. Repository publication alone does not submit the project.

## Assessment

The mandatory platform behaviors are present and backed by actual repeated runs and developer/browser checks. The strongest demonstration is the evidence chain from injected fault to different recovery behavior, followed by a reproducible comparison. The clearest remaining hackathon gap is actual Tavily acceptance; broader calibration and independent developer usefulness also need evidence.

The problem PDF does not publish a weighted numerical scoring rubric. A claimed 95+ score would be invented. Judge outcomes depend on the field, originality, implementation, integration evidence and presentation; use the checklist and actual measurements to assess readiness.
