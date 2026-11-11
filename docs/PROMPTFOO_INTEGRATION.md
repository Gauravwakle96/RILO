# Promptfoo integration

Rilo preserves its Python worker, independent agent
histories, source snapshots and stored experiments. The actual MIT-licensed
Promptfoo npm package is pinned at 0.125.1 and supplies `assertions.runAssertions`
for grading recorded outputs. It does not execute the agents a second time.

The initial flow is: define explicit success checks → execute both agents → grade
each recorded answer → inspect a checks-by-agent table → explain the scoped result
→ save the checks and snapshot as a suite → retest under the same conditions.

Checks are an allowlisted declarative subset, not arbitrary Promptfoo configs.
No uploaded JavaScript/Python, file references, providers, hooks, templates or
network-dependent graders are accepted. Empty checks mean **ungraded**, never a
passing score. Task-check results are separate from evidence integrity and do not
claim comprehensive factual accuracy or security coverage.

The Node process receives only the bounded data needed for grading. Credentials
are excluded from its environment; template expansion, telemetry and outbound
network access through the runtime are disabled. Node's permission model permits
filesystem reads only in the installed grading runtime and temporary directory,
writes only in that temporary directory, and no native addons or child processes.
The network guard blocks the standard Node networking APIs before package import;
it is defense in depth, not a separately certified OS network sandbox.
A timeout or evaluator failure
preserves the original response and produces an explicit evaluation error.

Setup: `npm ci --prefix backend/rilo/promptfoo_runtime` (Node >=22.22.0).
No inference API or account is needed for these deterministic checks.

Upstream references:
- https://github.com/promptfoo/promptfoo/tree/0.125.1
- https://github.com/promptfoo/promptfoo/blob/0.125.1/LICENSE
- https://github.com/promptfoo/promptfoo/blob/0.125.1/src/assertions/index.ts
- https://www.promptfoo.dev/docs/configuration/expected-outputs/

## Implemented flow

- All five task workspaces accept up to 12 explicit success checks per turn.
- Supported checks: equals, contains, case-insensitive contains, their supported
  negative containment variants, and valid JSON. Target answer text or the complete
  structured response. Every rule has an ID/name and literal expected value.
- Agent histories remain independent; grading uses completed outputs. Test labels
  are not inserted into the generation prompt. Inference duration excludes grading.
- Results retain engine/version, rule, target, pass/fail, reason and check score.
- The table includes failed-check filtering and a scoped leader/tie/inconclusive
  explanation. No success checks means ungraded, never a synthetic 100% score.
- Saving a task creates a versioned suite with its checks and snapshot. Retest and
  suite execution preserve checks. Regression comparisons reject changed checks,
  report score differences, newly failed checks and now-passing checks.
- PDF, Markdown, JSON and CSV reports include the persisted checks.
- UI submission checks Bifrost reachability, selected local model availability,
  worker heartbeat and the grading package. It preserves unsent input on failure.
- The lower-left guide explains the flow. Existing condition summaries no longer
  display ungraded attempts as failed checks.

## Reuse and maintenance

Actual upstream code: the installed Promptfoo assertion package and its React
`TruncatedText` component, copied from tag 0.125.1. The full upstream results table
is not copied: it depends on Promptfoo's own routing, stores and backend. Rilo's
matrix uses real Promptfoo grading results inside the existing workspace.

MIT notice: `docs/licenses/promptfoo-MIT.txt`; attribution also appears in
`THIRD_PARTY_NOTICES.md`. npm overrides pin glob 14.0.4, minimatch 11.0.5 and
basic-ftp 6.2.6 to address the eight advisories reported by the initial install.
No force downgrade or advisory suppression was used. The lockfile and adapter
files contribute to the captured workspace implementation hash.

No SQL migration was needed: checks are additive, versioned fields inside existing
turn manifests, suite records and run assessments. Historical records remain
readable and are not assigned new scores retroactively. Model/provider/credentials
and the existing execution queue are preserved.

## Verification, 9 November 2026

- Fresh pre-change baseline: 173 Python tests, 83.35% coverage.
- Final Python suite: 191 passed, 83.72% coverage. Standard browser suite: 18 passed
  in 3.6 minutes, six opt-in live scenarios skipped in that run. The new live
  Promptfoo file separately passed all three tests in 1.2 minutes.
- Actual-package tests cover passing/failing checks, literal template text, invalid
  configurations, empty answers/checks, timeout, package unavailable, persistent
  output, suites, regression detection and exports. No mocked grader is used for
  successful integration paths. Model outputs in unit tests are explicitly stubs.
- Live Playwright flow passed with real Bifrost/Ollama qwen2.5-coder:7b: task,
  shared context, two checks, independent replies, tie, filtering, PDF download,
  saved suite, retest and the new run's comparison table.
- Original live run `exp_ffc289dbc54248df`; retest `exp_629afeaff1cc4e1d`.
  Both used snapshot `snap_e4919bd4f96f412e`; both agents passed 2/2 declared
  checks. This verifies a specific workflow, not general agent accuracy.
- The live test first exposed a filter accessible-name issue, then a stale
  conversation refresh race. Both were corrected and the complete scenario reran
  successfully. A test that assumed randomized execution order was also corrected
  to assert by agent identity.
- Node permission/network boundary test blocks host-file reads, process spawning,
  TCP, HTTP and fetch. No secrets are inherited by the grader.
- Node runtime and frontend audits: zero reported vulnerabilities. Locked Python
  pip-audit: no known vulnerabilities. Lint/types/frontend build and Python
  source/wheel build passed. Full final test counts are in RILO_2_VERIFICATION.md.

## Limits and next useful increments

This integrates a working evaluation flow, not every Promptfoo feature. No YAML
configuration import, arbitrary assertion code, cloud dashboard, red-team suite,
semantic Promptfoo judge or twenty-provider catalog is claimed. Other repositories
have not been bundled without a specific need.

Text checks measure literal requirements and may be gamed; valid JSON only measures
format. Evidence verification remains separate. Sophisticated code/security
correctness needs task-specific independent checks and reviewed datasets. Local
model context, source size and service timeouts remain bounded; readiness is not a
promise that every execution succeeds. Existing Tavily/private-GitHub limitations
remain unchanged. No public multi-user deployment or flawless-product guarantee.

Useful next work is a small library of reviewed task-specific test packs, a guided
expected-answer editor and stronger grounded semantic evaluation, each tested
against known positive and negative cases before exposing a score.
