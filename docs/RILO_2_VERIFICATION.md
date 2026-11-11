# RILO 2.0 verification record

9 November 2026. Local Windows 11 application at http://127.0.0.1:8018.
This supplements historical VERIFICATION.md; old benchmark percentages are not
new product or hackathon scores.

## Automated checks

### Completion pass — 11 November 2026

- Final Python suite: **208 passed**, **83.53% coverage**.
- Added Windows-safe verified backup/restore coverage and broader hosted tenant
  isolation across conversations, uploads, snapshots, reports, suites and private
  agents/tasks. Focused acceptance: **32 passed**.
- Ruff and mypy passed. Frontend lint, TypeScript and production build passed; Python
  source/wheel build passed. Standard Playwright acceptance: **16 passed**, **10
  explicitly opt-in live checks skipped**, in 3.9 minutes. Both npm audits reported
  zero known vulnerabilities.
- Container target acceptance was **verified remotely** by GitHub Actions run
  [43072130188](https://github.com/Gauravwakle96/RILO/actions/runs/43072130188).
  The successful container job built the pinned image and checked the packaged Rilo
  CLI, Node, Promptfoo 0.125.1 runtime and Tesseract. Docker Desktop's local Linux
  daemon remained unavailable, so this is remote Linux acceptance rather than a
  local container result.
- Live Tavily is intentionally excluded without a real key. Live private GitHub
  acceptance remains credential-gated and is not represented as executed.

### Public source release — 11 November 2026

Fresh release checks passed 198 Python tests with 84.13% coverage, backend lint and
types, frontend lint/types/build and the frontend dependency audit. Publication
scope, the initial intermittent grader failure and the exact rerun result are in
[PUBLICATION_VERIFICATION.md](PUBLICATION_VERIFICATION.md). GitHub CI results are
linked there separately from historical local browser acceptance.

### User-reported failures fixed — 10 November 2026

- Final Python suite: **198 passed**, **84.04% coverage**, 171.02 seconds.
- Standard browser suite: **18 passed in 4.0 minutes**, eight opt-in tests skipped.
- Two opt-in checks against the user's historical chat and failed literal-check
  records ran separately and passed. The earlier six broader live scenarios were
  not rerun in this repair; real original-input retests are recorded below.
- Live capability chat: `exp_45a8e0837f4b498f`, both completed with correct profile
  identities and no artificial source-free findings.
- Live repository capture: 40 files from a fixed commit.
  In the final recorded evaluation, both agents completed, all emitted
  citations matched captured passages, and Repo Analyst recovered missing
  citations in one recorded retry. Factual accuracy remains unscored.
- Real Hack4Hack static capture correctly refuses title-only content before
  inference. JavaScript rendering remains unavailable. The misspelled literal
  check remains failed and is no longer described as a reassuring tie.
- PDF/Markdown/JSON/CSV reports generated from the persisted repository evaluation;
  extracted PDF confirmed its ID, commit, agent names and source references. The
  original reports remain private; a [public case study](ui-evidence/repository-recovery-2026-11-10.md)
  retains measurements and verification outcomes with identifying details omitted.
- Ruff, mypy, frontend lint/types/build and Python package builds passed. npm
  audits and locked Python pip-audit reported no known vulnerabilities.

See [the repair record](USER_FAILURE_FIXES_2026-11-10.md) for diagnoses, exact
changes, intermediate failures and remaining limits.

### Promptfoo integration update

The earlier results below remain historical. On the updated implementation:

- Fresh pre-integration baseline: 173 Python tests, 83.35% coverage.
- Final full Python suite: **191 passed**, 83.72% coverage, 132.05 seconds.
- Promptfoo-focused suite: **18 passed**, including actual installed-package
  grading and restricted runtime boundary checks.
- Live Promptfoo browser file: **3 passed in 1.2 minutes** (two UI checks plus one
  complete real-model generation → grading → PDF → suite → retest → inspect flow).
- Original `exp_ffc289dbc54248df`, retest `exp_629afeaff1cc4e1d`; identical snapshot
  `snap_e4919bd4f96f412e`; Scout and Relay each passed two declared checks, a tie.
- Ruff, mypy (35 modules), frontend lint/typecheck/build, Python source/wheel build
  passed. Both npm audits show zero known vulnerabilities. Locked Python pip-audit
  found no known vulnerabilities. Secret-pattern scan found no matches.
- Final standard browser suite: **18 passed in 3.6 minutes**, six opt-in live tests
  skipped. The new live Promptfoo scenario was run separately and passed above;
  the five earlier full capability live scenarios were not rerun in this change.
- Browser validation found a transient light-theme contrast issue in the existing
  lower-left guide's background transition. Removed that background transition;
  focused desktop accessibility and the complete browser suite then passed.
- Production-served Regression Lab UI displayed the actual live comparison,
  compatible conditions and 100% → 100% **declared-check** scores for each agent.
  This is not 100% factual accuracy. Desktop and mobile screenshots inspected;
  no page-level mobile overflow, comparison table scrolls horizontally.

See [PROMPTFOO_INTEGRATION.md](PROMPTFOO_INTEGRATION.md) for source reuse, licenses,
safe subset, version pinning, test failures corrected and remaining scope limits.

### Earlier Rilo 2.0 expansion verification

| Check | Actual result |
| --- | --- |
| Fresh pre-edit Python baseline | 127 passed, 111.62 s |
| Fresh pre-edit browser baseline | 13 passed, 2.8 min |
| Expanded Python suite and coverage | 173 passed, 77.21 s; 83.35%, minimum 80% |
| Ruff: backend/tests/scripts/examples | Passed |
| mypy | Passed, 32 modules |
| Frontend ESLint and TypeScript | Passed |
| Production Vite build | Passed; ~102.6 KB JS gzip, 10.6 KB CSS gzip |
| Python source/wheel build | Passed |
| npm audit, full/runtime | Zero known vulnerabilities |
| pip-audit against uv.lock export | No known vulnerabilities |
| Source/document secret-pattern review | No potential matches; values never printed |
| Final standard browser acceptance | 16 passed in 3.4 min; five explicit live tests skipped in this normal run |
| Explicit live browser acceptance | Five scenarios passed across focused runs; includes recorded agent failure/retry |

Tests cover paired history separation, immutable retries, idempotency, context
limits, private URL/DNS/redirect boundaries, ZIP traversal, PDF/DOCX extraction,
source integrity, lines/pages/code indentation, OSV contracts, advisory review,
reports, labeled metrics, regression compatibility, quotas and preserved benchmarks.
The real parser subprocess was tested; child-process branches are not included in
parent-process coverage. Coverage is not proof every platform branch was exercised.

## Real local inference and retrieval

All outputs below use authenticated Bifrost and existing `ollama/qwen2.5-coder:7b`.
Test PDFs and toy repositories are labeled test material; model inference and Docker
execution are actual operations, not fixture responses.

| Capability | Evaluation | Observation |
| --- | --- | --- |
| Chat + advisory review | exp_ca5932b0342c453b | Both completed, each 1/1 valid citations; separate review recorded |
| Shared follow-up | exp_64260b0a19b84a1e | Both retained own answer and same snapshot |
| Click repository | exp_b362b753688843b7 | Both completed; one altered Scout quote correctly rejected |
| ItsDangerous via browser | exp_ba8e0dcf498d4ea5 | Commit 672971d66a2ef9f85151e53283113f33d642dabd; 32 files; valid file evidence from each agent |
| Two-page PDF via browser | exp_f85da7ca837b4200 | Both cited actual page 2 retention sentence |
| example.com via browser | exp_9e30ff79d4804cac | Bounded capture; both completed with source references |
| Search off | exp_583b3050504c4419 | Supplied test source; no Tavily request |
| ZIP + Docker unittest | exp_d12062c9a92b4c7f | One test passed, exit 0, network none, cleanup completed; Scout malformed output, Relay completed |
| Browser chat/retest/regression | exp_c243d72ea3ae4c2a, exp_f8c7174a915945b7, exp_ad07d4061bed44f0 | Follow-up, PDF export, retest and compatible comparison passed |
| Failed-response retry | exp_9b2af3e08c2e49b3 | Actual new inference, wrong JSON field again; original and Relay answer preserved |
| Final Docker/retry browser acceptance | exp_b6a5a093972a49c2, exp_f145fd8fe7b14790 | Isolated unittest passed; Relay recovered on its second call; Scout's separate retry failed visibly with observed usage and retained original |

The live suite found a stale Regression Lab list; current-evaluation fetching fixed
it and the corrected test passed. Docker acceptance checks isolated execution and
recorded retry attempts, not a promise that a model always returns a valid answer.

One run recorded SQLite OperationalError. Lock waiting increased from two to five
seconds; diagnostic text is redacted and retained. This observed issue is not proof
that every contention scenario has been resolved.

## Limits

- Tavily integration/configuration/mocked transport tested; live validation unavailable
  without TAVILY_API_KEY. Default off; these runs consumed no Tavily credits.
- Authorized private GitHub API tested with transports; no live private credential.
- A small versioned calibration fixture exists for evaluator agreement; it is not a
  universal semantic-vulnerability accuracy claim. No independent penetration test,
  external hosted deployment or independently awarded product score.
- Quote integrity differs from conclusion truth. Models can overstate evidence;
  advisory semantic review can err too.
- Bounded repository selection; deterministic AST inventory focuses on Python.
- See the guide/journal for PDF font, OCR-recognition, context and deployment limitations.

Private snapshots, traces, screenshots and raw reports stay in `.rilo`.
No private retrieved contents or credentials were published.

Final API smoke checks: profiles, capabilities, dashboard and whole-conversation
export returned HTTP 200. The unfamiliar-repository report downloaded successfully
in PDF, Markdown, CSV and JSON. Schema versions 1–4 are present and the worker queue
was empty at handoff. Additional agent-catalog and light-theme dashboard axe checks
reported zero violations; representative desktop/mobile screenshots were inspected.

## Browser commands

```powershell
cd frontend
npm run test:e2e
# Explicitly runs actual local inference and public retrieval:
$env:RILO_LIVE_ACCEPTANCE='1'
npx playwright test tests/live-workspaces.spec.ts
```

Normal CI runs skip the five live tests. Live test inputs are created privately in
`.rilo/browser-acceptance`. The Docker/retry scenario verifies actual unittest
execution and that retries perform inference without overwriting original attempts;
it allows recorded agent-schema failure, but not fake success or unavailable inference.
