# Verification record

RILO 2.0 expansion results are recorded separately in [RILO_2_VERIFICATION.md](RILO_2_VERIFICATION.md). The records below describe the earlier benchmark release.

Rilo v0.1.0 was verified locally on **9 November 2026**. The implemented dashboard, API, single worker, local gateway inference and developer flows are exercised below. Live Tavily acceptance and external CI remain unperformed.

## Environment and result

Target: Windows 11, Python 3.13.15, SQLite 3.53.1, Node.js 24.14.1. Production dashboard/API at `http://127.0.0.1:8018`; Vite development at `5187`; project Bifrost v2.5.0 at `8086`; existing Ollama at `11434`, using `qwen2.5-coder:7b`.

| Check | Actual result |
| --- | --- |
| Python tests | **127 passed**, 137.07 seconds |
| Python line coverage | **84.55%**, 1,368 / 1,618 statements |
| Ruff | Passed across backend, tests, scripts and examples |
| mypy | Passed, 14 backend source files |
| Python package | Source archive and wheel built successfully |
| Frontend lint and TypeScript | Passed |
| Frontend production build | Passed; approximately 94.71 KB compressed JavaScript and 9.83 KB compressed CSS |
| Full latest browser workflow suite | **13 passed**, approximately 2.6 minutes; includes guide, recovery example and focused retest |
| Production benchmark inspection | Six checked screens; zero axe violations, JavaScript errors or failed requests |
| API documentation | Production and development browser checks passed; 26 operations / 10 schemas, no external requests |
| Node dependency audit | Zero known vulnerabilities, 195 dependencies reported |
| Locked Python dependency audit | Runtime: 45 dependencies; runtime plus development: 58; zero known vulnerabilities |
| Final source/evidence review | Latest source/evidence scan: 205 files checked against configured secret values; zero matches or broken local Markdown links. Earlier whitespace review also passed. |
| Model integration | Actual authenticated Bifrost/Ollama responses with reported usage; unauthenticated inference rejected |
| Fixture developer automation | Two 120-attempt matrices completed; strict compatible comparison passed; CLI exit code 0; SDK 18-attempt flow completed |

Test output is retained locally in ignored `.rilo/final-pytest.xml`; [coverage-backend.json](../coverage-backend.json) records line coverage. Coverage includes meaningful API, input/output, grading, pricing/version, queue/worker, SDK and CLI behavior. Child-process launcher behavior is tested separately; subprocess lines do not all contribute to parent-process coverage.

## Executed commands

Run from the project directory:

```powershell
uv run ruff check backend/rilo tests scripts examples
uv run mypy backend/rilo
uv run pytest --cov=rilo --cov-report=term-missing --cov-report=json:coverage-backend.json
uv build
npm run lint --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
npm audit --prefix frontend
node tests/backend/browser_docs.mjs http://127.0.0.1:8018
node tests/backend/browser_docs.mjs http://127.0.0.1:5187
node tests/developer/browser_benchmark.mjs http://127.0.0.1:8018
uv run python examples/compare.py
```

The benchmark browser runner uses IDs from the included recorded model matrix; run it against the populated local workspace, not an empty installation. The regular Playwright suite creates fixture records itself and runs against an idle queue. CI skips looking for historical live-model traces.

`uvx pip-audit` was run against exported **locked** runtime and runtime-plus-development requirement sets, not an unrelated global Python environment. Audit inputs/results are private ignored `.rilo/pip-audit*.json` artifacts. Package metadata/licenses were reviewed; frontend lockfile license fields, Apache-2.0 source license, CC0 corpus and local font notices are retained. The Bifrost download is pinned and hashed; its recorded hash is not an independent upstream signature verification.

## Important behavior checked

Backend tests cover validated experiment admission, request limits and idempotency, loopback-only adapters/model URLs, fixed Tavily endpoint, bounded external responses, credential redaction, local session/CSRF/origin/host rules, queue interruption/cancellation accounting, conservative unknown metrics, price/model provenance, HTTP version history, manifest compatibility, grader passage matching, and gate pass/fail/inconclusive results.

The Windows runtime test starts Rilo on a separate local port and checks shutdown of its owned API/worker process tree. The actual release was restarted after final API changes with an idle queue; persisted records remained available and one worker was started. Gateway and existing Ollama settings were preserved.

The latest full browser suite exercises actual experiment creation, polling, outputs, evaluations, traces, JSON export, rerun, baseline save and strict comparison. It also checks cancellation, reference tasks, endpoint validation, HTTP agent revisions, settings and responsive catalog views. Loading, partial-data, connection-refusal and session-denial screens use explicitly labeled network simulations. Declared-change field rendering is simulated separately; the real API request contains the actual flag and backend tests exercise differing-agent compatibility.

## Browser and accessibility evidence

Representative viewports are **390×844**, **768×1024** and **1440×900**. Actual screens were inspected for document overflow, readable controls, dark/light themes, keyboard dialog containment, Escape dismissal, focus return and reduced motion. Inter and JetBrains Mono load locally; the browser stores only the theme in localStorage. The private dashboard includes `noindex, nofollow` metadata.

| Evidence | Checked behavior |
| --- | --- |
| [frontend-evidence.json](ui-evidence/frontend-evidence.json) | Responsive views, core flows, states and earlier test history |
| [production-review.json](ui-evidence/production-review.json) | Built frontend, fonts, mobile navigation, noindex and zero automated violations |
| [model-v2-browser.json](ui-evidence/model-v2-browser.json) | Actual 120-run metrics, recovery, unhandled fault, failed output/evaluation and mobile trace |
| [api-docs-browser.json](ui-evidence/api-docs-browser.json) | Self-hosted reference, filters, keyboard expansion, protected schema and mobile containment |

Axe produced zero violations on the final checked screens. Incomplete rule observations remain recorded and need human judgment; automated checks do not establish full accessibility certification. Chromium was exercised; Safari and Firefox were not.

## Findings fixed and retries

- Default FastAPI docs relied on an external CDN/inline script that the dashboard CSP blocked. A self-hosted searchable OpenAPI reader now serves local assets without executing mutations. Protected schema access, unknown-asset handling and browser behavior passed; `/redoc` forwarding was added to the Vite server.
- The original reference grader rejected a longer supported quote. Grader v2 has regression tests and a fresh actual-model matrix; prior results remain preserved. See [BENCHMARK.md](BENCHMARK.md).
- Final production benchmark inspection found a scrollable output/evaluation panel lacked keyboard access. The panel now has a focusable named region and visible focus outline. The production benchmark check and full 10-test browser suite passed after the fix.
- An earlier full browser repeat waited behind the long model benchmark and exceeded its fixture wait limit. The latest full repeat ran with an idle queue and all ten tests passed. An earlier evidence script used a guessed task label; the saved runner now reads the recorded run labels.
- ECC Chrome DevTools encountered an existing browser-profile ownership conflict. Project Playwright provided isolated Chromium contexts; existing browser processes, plugin trust and sandbox settings were preserved.

## Target acceptance and limits

| Target | Status and evidence |
| --- | --- |
| Local built dashboard/API and worker | **VERIFIED** by actual browser, SDK/CLI and persistent experiment flows |
| Local Bifrost → Ollama inference | **VERIFIED**, 90 actual responses in the corrected model matrix and authenticated probe |
| Tavily live query | **NOT PERFORMED**: missing private `TAVILY_API_KEY`; implementation/contract tests alone do not establish acceptance |
| GitHub CI | **NOT PERFORMED**: [workflow](../.github/workflows/verify.yml) prepared; repository not published |
| Public deployment and hackathon submission | **NOT PERFORMED**; single-user local release is the implemented deployment target |

The actual-model matrix still exposes an insufficient-evidence defect in the bundled agents. The platform preserves it for inspection; it is not a platform test failure. Arbitrary summary grounding, calibrated live semantic assessment, team authentication and isolated remote workers remain future scope. See [the feature checklist](../FEATURES.md) and [submission preparation](HACKATHON.md).

Local checks support the stated local workflows. They do not promise a hackathon score, public production readiness or reliability on all future tasks.

## Recovery UX refinement acceptance

The **Start here** guide and recovery entry flow were checked in both themes at 390×844, 768×1024 and 1440×900. Section links preserve the guide route and move keyboard focus correctly. The example submits twelve actual fixture attempts. Retesting a recorded real-model failure preserves its model and budgets while preparing the focused task/fault form for review; no model experiment is submitted merely by opening that form.

The full thirteen-test browser suite passed after the refinement. Production checks covered four landing/guide screens and six actual-model inspection screens, with zero reported axe violations, overflow, JavaScript errors or failed requests. The design detector returned no findings for the changed UI; the previously documented Inter exception remains restricted to its value/file. Evidence: [recovery-release.json](ui-evidence/recovery-release.json), the `recovery-guide*` captures and [model-v2-browser.json](ui-evidence/model-v2-browser.json).

An initial recovery-table check found its overridden accessible labels did not agree with visible text. The table now derives its name from the displayed result plus hidden context, and the final browser checks passed. No backend behavior, provider settings or dependencies changed for this refinement.
