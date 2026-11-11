# Rilo — historical pre-expansion planning handoff

> RILO 2 workspace expansion: see [implementation status](RILO_2_IMPLEMENTATION.md), [workspace API](WORKSPACE_API.md), [guide](RILO_2_GUIDE.md), and [fresh verification](RILO_2_VERIFICATION.md). Earlier scope notes below describe the preserved benchmark foundation.

> Historical notice: this document was written before the RILO 2 implementation and
> intentionally preserves the old proposal. Statements such as “not built” and
> “proposed” below are not current product status. Use the linked implementation and
> verification documents for current claims.


Prepared 9 November 2026. This document is ready to copy into ChatGPT. It distinguishes implemented behavior from proposed work. This request is planning only: do not start implementation until explicitly asked.

## Product purpose

Rilo is a local agent-comparison workspace that turns useful tasks and failures into repeatable tests. Its core job is to give different agents the same task, record their actions and evidence, introduce controlled failures, and compare whether each completed the task successfully.

The proposed expansion adds paired task chat, website/repository/document analysis and downloadable reports while retaining evaluation and failure recovery as the center of the product. A general chat interface or PDF generator alone would not capture Rilo's purpose.

Initial users are developers building research/RAG agents and technical users who want evidence-backed website, repository or document reports. Focus on one repeatable developer problem before adding unrelated business agents. Evaluation, tracing and comparisons already exist in other products; Rilo does not claim to be the first agent-testing platform.

## What exists today

- Local React/Vite/TypeScript browser dashboard, Python/FastAPI API, Pydantic validation and standard SQLite WAL storage with schema versions 1 and 2.
- Separate single worker, durable queued experiments, leases, retained cancellation/interruption results, bounded admission and idempotent submission.
- Two actual bundled research workflows: **Scout**, a simple plain-Python search/synthesis baseline; **Relay**, a LangGraph workflow with evidence filtering and bounded retries.
- Register existing loopback HTTP agents and revisions. Their internal steps, model/provider, usage and fault handling are unobserved; they currently support normal controlled-evidence execution and final outputs only.
- Five referenced synthetic research tasks: recent company briefing, similarly named entity disambiguation, conflicting release dates, insufficient funding evidence and multi-step company research.
- Custom tasks against the existing known synthetic sources. This is not arbitrary PDF/website/repository ingestion.
- Normal condition plus controlled first-search timeout, synthesis outage and untrusted-document instruction scenarios, with recorded activation and retry events.
- Fresh attempts, one to five repetitions, randomized recorded order, immutable tasks/evidence/agent/runtime/grader/price snapshots. Current admission supports up to eight selected agents and 200 total attempts.
- Per-run outputs, supported structured fact checks, timelines, observed model/tool boundaries, steps, durations, available reported tokens and supported model-fee estimates. Missing observations remain unknown.
- Baselines, candidate comparisons, explicitly declared agent changes and an exploratory pass/fail/inconclusive task-success regression gate. Strict compatibility and a minimum of three trials are required; a gate pass is not general certification.
- Python SDK, CLI, JSON/CSV exports, local setup scripts, locked dependencies, developer/deployment documentation and a prepared GitHub Actions workflow.
- Real authenticated **Bifrost v2.5.0 → Ollama → qwen2.5-coder:7b** inference on the existing Windows laptop with RTX 3050.
- A clearly labeled deterministic fixture engine with no model inference, distinct from actual-model results.
- Live Tavily request implementation with bounded validated responses and quota controls. **Live acceptance is pending because no TAVILY_API_KEY is configured.**
- Dark/light responsive interface, local licensed Inter/JetBrains Mono fonts, keyboard dialogs/navigation, reduced-motion support, loading/error/empty/partial states and self-hosted searchable API reference.
- Lower-left **Start here** guide with workflow, requirements, functions and result interpretation.
- Reviewable twelve-attempt fixture recovery example, an API-derived recorded model comparison, condition-by-agent success table and **Retest this case** form preserving the recorded model and budgets.

Local app: http://127.0.0.1:8018. Guide: http://127.0.0.1:8018/#/guide. Project directory: `C:\Windows\System32\Rilo`.

### Verified evidence and remaining limits

Recorded verification: 127 Python tests passed with 84.55% line coverage; latest full frontend browser suite 13 passed; lint, type checks, Python/frontend production builds and dependency audits passed. The latest changes were frontend-only, so Python results are recorded verification rather than a claim that the suite was rerun for every UI edit.

Actual-model research matrix: two agents × five tasks × four conditions × three repetitions = 120 attempts. Scout passed 24/60 (40%); Relay passed 48/60 (80%); 72 passes, 48 failures and zero infrastructure errors overall. There were 90 actual model responses, because injected faults stopped some attempts before dispatch. This used synthetic controlled evidence, not live web research. It is a small sample, not a hackathon score or universal quality claim.

Relay recovered better from controlled tool/model faults but still failed insufficient-evidence cases. The current reference grader checks structured referenced facts and task rules; it does not verify every free-text summary claim. Live semantic grading remains inconclusive without independently validated references. Historical grader v1 had a quote-matching false negative; v2 corrected it through a versioned fresh run, not an agent improvement.

**Not built:** paired chat, arbitrary website/report analysis, repository ingestion/review, PDF input, PDF report export, adaptive task router, independent claim verifier, saved failure suites, scheduling, team accounts or remote worker isolation. Public repository publication, external CI execution, public deployment and hackathon submission have not been performed.

## Proposed agent catalog

Start with five selectable agents, using task categories plus search and capability filters. Names should explain their job; inventing many personas is not a substitute for independent useful workflows.

| Website category | Agent | Status | Useful behavior |
| --- | --- | --- | --- |
| Research | Scout | Built | Simple search and answer; retain as a stable baseline |
| Research | Relay | Built | Evidence selection and bounded recovery; improvements should create a new version |
| Websites | Web Analyst | Proposed | Analyze supplied accessible pages, summarize product/docs content, check explicit requirements and cite page passages |
| Repositories | Repo Analyst | Proposed | Explain architecture, dependencies and maintainability findings with commit/file/line evidence; initially read files without running code |
| Documents | Document Analyst | Proposed | Answer questions and summarize uploaded text PDFs/Markdown/text with page/section citations |
| Custom agents | User's HTTP agents | Registration built | Preserve current limited capability reporting until a richer callback contract is built |

Later, add **Cross-source Analyst** only if users need comparisons across multiple websites/documents/repositories against an explicit checklist. A security review agent would need separate reference tasks and validation; it must not claim complete security from model-generated findings.

Agent entries should show supported input/task types, framework/version, tools, evidence formats, fault-injection support, model requirements and observed capabilities. Recommendation badges should explain suitability, not claim unmeasured quality. Unsupported pairings should give a clear reason. The same local model can power all profiles; downloading one large model per agent is unnecessary.

Do not advertise Router, Verifier or Report Formatter as independent benchmark contestants by default. They are supporting modules. A distinct verification-agent product would require its own tasks and correctness evidence.

## What adaptive means

Adaptive means selecting a bounded execution workflow appropriate to the task and available evidence. It does not mean automatic retraining, unlimited autonomy, reliable self-reported confidence or guaranteed correct answers.

Proposed pipeline:

```text
Shared user task and attachments
  → identify task type and check capabilities
  → record a plan, tool policy and limits
  → gather/retrieve relevant evidence
  → produce a structured draft
  → check evidence, citations and requested sections
  → at most one verification-driven correction initially
  → return answer/report with unverified areas
  → evaluate separately against the pinned task criteria
```

Examples of adaptation:

- Research: resolve entity identity, dates, contradictions and missing evidence.
- Website: select permitted pages relevant to the question; respect page/depth/time caps.
- Repository: inspect relevant directories/manifests, retrieve matching code and cite a pinned commit.
- Document: retrieve relevant passages while preserving page/section provenance; distinguish scanned from text PDFs.
- Tool failure: use a predefined bounded retry/backoff path; record attempts and stop at the budget.
- Weak support: omit unsupported assertions or report uncertainty instead of filling gaps with plausible text.

Optional user-visible policy names are **Quick**, **Thorough** and **Recovery-focused**. These are explicit configurations, not independent models or promises. Their tool/model/time limits must be visible. Use matching budgets when claiming a fair agent comparison; report deliberate policy/budget differences as an experiment variable.

Begin with deterministic task selection from the user and attachment type. A local-model router can assist ambiguous cases later, with validated outputs and a way for the user to correct its classification. Prefer relevant retrieval and clear output contracts before fine-tuning or larger models.

All adaptive decisions, tool use, verifier calls and correction attempts count toward measured runtime/usage. Freeze routing/prompt/agent/tool/evaluator versions in the manifest. Preserve Scout as the simple baseline and keep the older Relay version so an improvement can be tested rather than assumed.

The generation workflow can verify against allowed evidence, but it must not see hidden reference answers or final evaluator verdicts while solving the task. Final evaluation is a separate stage. Using the same local model as a judge produces advisory evidence, not an independently established winner.

## Paired chat and task execution

Add a **Task chat** workspace with two modes:

1. **Single agent:** complete a useful task and inspect evidence/artifacts.
2. **Compare agents:** send the same initial instructions, conversation and attachments to two compatible agents and compare the outcomes.

The starting user context is shared. Each agent's generated answers and intermediate outputs stay in its own branch. A paired follow-up sends identical user text to both branches; do not mix one agent's answer into the other's context silently. Editing an earlier input creates a new recorded task/revision rather than overwriting historical results.

Display agent cards side by side, with queued/running/completed/error states and observable progress. On mobile, make each output readable through accessible switches while retaining the shared task and comparison summary. When running sequentially, say that Agent B is queued; do not animate fabricated concurrent work.

Example task: “Analyze this repository. Explain its architecture and identify three maintainability issues with file references. Produce a PDF report.” Both agents use the same commit and corpus. Compare required-section completion, supported findings, reference accuracy, uncertainty handling, runtime and usage. A valid PDF is an artifact check, not proof that its claims are true.

Separate the initial interactive pair from **repeat benchmark**. One conversation can show examples, but it does not satisfy the three-trial gate. Saving the task as a repeated benchmark pins its inputs, references, faults and evaluator.

## Evidence ingestion, grading and reports

### Shared evidence

Capture accessible website content, document text or a repository commit before controlled comparison. Record source identifiers, hashes, collection timestamps, URLs or paths and extraction status. Both agents receive the same permitted corpus and retrieval budget; different retrieval paths are part of the tested behavior.

Initial website analysis should accept supplied public URLs and a small explicit page cap. Whole-site crawling, authenticated pages and arbitrary private-network fetching are additional features. A report based on extracted text cannot claim a full visual/accessibility audit unless corresponding browser measurements are actually collected.

Repository review initially reads selected files at a pinned commit. Do not automatically install dependencies, execute repository code, or modify the source. PDF reading and PDF exporting are separate paths: text extraction first; scanned PDFs require a later bounded local OCR pipeline.

At new trust boundaries, validate URL redirects/network destinations, upload types/sizes, archive traversal, response limits and rendering. Exclude credentials/private runtime directories from repository evidence. Treat retrieved page/file instructions as untrusted data. Avoid presenting unsupported scope as a completed report.

### Evaluation

Replace the research-only assumption with versioned task packs and explicit output schemas. A website task, repository task and document task each need their own success criteria and reference tests.

- Check requested sections and artifact validity deterministically where possible.
- Validate whether cited source/file/page references exist and support the stated finding.
- Check missing-evidence/contradiction handling against known reference cases.
- Keep success, runtime, calls, tokens and estimated fees separate.
- Use calibrated semantic review only when supported by independently labeled examples; open-ended unverified tasks may remain inconclusive.
- Explain partial ingestion, unknown metrics and unassessed claims in the output and exported report.

Do not manufacture an overall “95+” score. A trace-backed finding and a repeatable failed test are more useful than an unsupported quality percentage.

### Reports

Provide Markdown first, then locally generated PDF. Include the task, source snapshot, agent/prompt version, model, conditions, findings/citations, observations, unverified claims and comparison limitations. Keep JSON/CSV evidence export. Report formatting can be deterministic and does not need another model call by default.

## Zero required API-cost strategy

Keep the existing local stack and one resident Ollama model. Use Bifrost for observed model requests; agents should run sequentially on the existing laptop by default. Reuse ingestion snapshots and bounded keyword retrieval before adding a separate embedding service or database.

Open-source local extraction/PDF tooling can avoid paid APIs, but library maintenance/licenses must be checked before selection. Context/file/page sizes, inference speed and report quality need measurement on the actual machine. Large repositories and long/scanned PDFs require bounded processing rather than a claim of unlimited analysis.

Tavily is optional when users supply URLs/files/repository snapshots. It is required for Rilo's current live search integration. Its verified public allowance is 1,000 free credits/month with no card required at time checked; enforce caps and fail clearly when quota is exhausted. Do not silently enable paid billing or cloud-model fallback. A key and successful live acceptance query are still missing here.

Local operation can avoid required model API, database and hosting fees. Electricity, hardware, storage, downloads and internet still have costs; free cloud/public hosting is not promised.

## Website organization

Keep the current navigation and add capabilities in reviewable phases:

- **Experiments:** repeatable tests, recorded real/fixture results, recovery matrix and inspection.
- **Task chat — proposed:** one shared task, inputs/attachments, one/two agent selection, outputs and artifacts.
- **Agents:** Research, Websites, Repositories, Documents and Custom filters, with explicit compatibility.
- **Tasks/evidence:** reusable versioned task packs and permitted snapshots.
- **Scenarios:** supported fault tests; never claim every adapter supports all faults.
- **Compare & baselines:** compatible revision comparisons and declared changes.
- **Start here:** concise requirements and task-specific guidance; update only when those features exist.
- **Settings:** actual integration/model/quota status.

Place PDF downloads beside the finished report. Add saved failure suites to the existing retest workflow rather than a disconnected feature. Avoid flooding the catalog with agents that differ only in names.

## Phased delivery and acceptance

| Phase | Scope | Required proof before proceeding |
| --- | --- | --- |
| 0 | Validate Tavily if a key is supplied; preserve current release | Actual bounded live request and explicit grading/usage limits; existing flows still pass |
| 1 | Paired task chat for supported Scout/Relay research tasks | Identical initial inputs, isolated branches, paired follow-ups, actual recorded outputs and repeated-test conversion |
| 2 | Website and repository ingestion plus Web/Repo Analyst | Pinned shared corpus, valid references, bounded input/error behavior and domain-specific task tests |
| 3 | Markdown/PDF report export | Correct artifact rendering, readable citations, source/version/limit metadata and private-secret exclusion |
| 4 | Document Analyst and text-document extraction | Accurate page/section references, long-document bounds, unsupported scan disclosure; OCR later |
| 5 | Bounded adaptive routing/retrieval/correction | Recorded policy/version, no hidden-reference leakage, total call limits, measured improvement/trade-offs against preserved baselines |
| 6 | Saved failure library and richer regression policies | Reusable focused suites, compatible provenance and explicit success/time/usage thresholds |

Do not implement all phases at once. Extend the existing API/data contracts through migrations rather than forcing chat, artifacts and external evidence into the current research-only schema. Proposed entities include conversations/turns/branches, evidence snapshots/chunks, task packs, versioned policies and report artifacts. Their exact contracts require design before implementation.

Prioritize the smallest end-to-end useful workflow. Each new agent must demonstrate a supported task and meaningful grading, not merely produce an attractive answer. Test actual failures, recovery, cancellation, compatibility, artifacts and mobile/keyboard flows. Independent developer feedback remains a necessary product-validation step.

## Instruction to ChatGPT

Act as a practical product architect and agent-evaluation engineer. Use the current implementation above as the starting point. Help refine the proposed catalog, adaptive policy, paired-chat semantics, evaluation contracts, zero-required-API-cost architecture and phased acceptance criteria. Identify assumptions and trade-offs plainly. Preserve Rilo's agent-comparison/failure-recovery focus. Do not claim proposed features are already built, that local-model output is always correct, that an AI judge proves a winner, that live Tavily is validated, or that a hackathon win/95+ score is guaranteed. Stay in planning mode until I explicitly request implementation.

Useful existing repository documents: `FEATURES.md`, `docs/API_CONTRACT.md`, `docs/ARCHITECTURE.md`, `docs/BENCHMARK.md`, `docs/VERIFICATION.md`, `docs/ROADMAP.md` and `DESIGN.md`.
