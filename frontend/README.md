# Rilo workspace frontend

The React/TypeScript workspace connects to the real local Rilo API. It provides experiment creation, results, trace/output/evaluation inspection, cancellation, reports, reruns, referenced tasks, HTTP-agent registration, integration settings and baseline comparison. Fixture demonstration and Bifrost execution are explicitly distinguished; unknown resource usage stays unknown.

## Run locally

Use the root setup instructions to start the API and its single worker on `127.0.0.1:8018`. Then, in this directory:

```powershell
npm ci
npm run dev
```

Open `http://127.0.0.1:5187`. Vite proxies `/api`, `/docs` and `/openapi.json` to the local API. The root launcher serves `dist` through the API after `npm run build`; a Vite preview alone does not include the development API proxy.

The lower-left **Start here** entry opens the non-blocking `/#/guide` route. **Try recovery example** prepares a twelve-attempt fixture form for review. Experiment results include condition-by-agent task success and **Retest this case** prepares a focused task/fault test while preserving the recorded model and budgets. `src/lib/presets.ts` supplies the fixture example; `src/components/guide.tsx` keeps requirements and metric/grading limits explicit.

## Check the frontend

```powershell
npm run lint
npm run typecheck
npm run build
npm audit --audit-level=moderate
npx playwright install chromium
npm run test:e2e
```

Browser tests require a running local API and worker. Tests create actual local fixture experiments, referenced tasks and baselines; they also cancel one test experiment. Run them against a development workspace. `CI_SKIP_LIVE_TRACE=1` skips inspection of any pre-existing Bifrost experiment history. The core fixture workflow continues to use actual API records. Loading, partial-catalog, connection-error and denied-session cases use explicitly labeled network simulations.

Screenshots, axe observations, the actual workflow IDs, and the ECC evidence record are saved under `../docs/ui-evidence`. Tests cover 390×844, 768×1024 and 1440×900, dark/light themes, keyboard dialogs and navigation, reduced motion, page overflow, creation/inspection/export/rerun/comparison, task validation, settings, and cancellation. Axe is an automated check, not a complete accessibility certification.

## Structure and boundaries

`src/components/forms.tsx` contains validated creation flows; `experiments.tsx` handles results and the inspector; `catalog.tsx` handles catalogs, comparisons and settings. `src/lib/api.ts` owns session bootstrap, CSRF headers, request errors and report downloads. Session credentials stay in memory and HttpOnly cookies. Only theme choice persists in localStorage. No model/provider secrets are rendered or stored by the frontend.

The included Inter and JetBrains Mono fonts use the SIL Open Font License; lucide icons are ISC licensed. Dependencies are pinned with a lockfile. The minimatch override addresses the development-tool advisory GHSA-g3hv-75wg-m249; it is verified by lint and audit.

The grader assesses structured reference facts, citation evidence and scenario coverage. Arbitrary claims in a free-text summary remain unassessed and the inspector explains this limit. Results apply to the tested tasks and conditions. Live Tavily research needs the backend credential and is unavailable to basic HTTP adapters. Multi-user tenancy and public hosting are outside this local release.
