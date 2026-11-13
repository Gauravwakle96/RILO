# Storage status and cleanup reliability

## Problem and change

The local server recorded a `FileNotFoundError` and HTTP 500 while reading
`GET /api/v1/workspace/storage`. The size calculation listed files, checked their
existence, then read their metadata again. A cleanup or SQLite sidecar lifecycle
can remove a file between these operations.

Storage measurements now sample each regular file once without following
symlinks. A file removed during sampling is excluded. The reclaimable-file count
and bytes come from the same sampled set. Cleanup tolerates an already removed
orphan and reports only the files it actually removed. Permission and other I/O
errors remain errors; referenced source blobs remain protected by the existing
database checks and transaction. No live user data was deleted to validate this fix.

Storage totals are an observation of changing files, not an atomic filesystem
snapshot. The orphan list and total storage measurements may reflect slightly
different instants.

## Verification on 13 November 2026

- Full backend suite: **257 passed**, 83.10% aggregate coverage, in 397.48 seconds.
- Five new regression cases cover disappearing uploads and SQLite sidecars,
  permission errors, a disappearing orphan during status retrieval, and a
  disappearing orphan during cleanup. The route tests preserve referenced sources
  and verify actual cleanup counts.
- Ruff and mypy passed. Python source and wheel builds passed.
- Three targeted Chromium checks passed in 32.3 seconds: settings/storage UI,
  practical-agent categories and all four assistant/example links. These are
  separate from the previous full standard suite of 27 passes and eight skips.
- The restarted local API and worker passed readiness. Forty storage-status
  requests on four concurrent clients returned usable nonnegative measurements.
  This exercises reads; it does not establish broad production capacity.
- The default remains `bynara/agnes-2.5-flash`, all four practical profiles remain
  available, and no evaluations were queued or running at the final check.
- The public candidate-file credential scan found no matches; `git diff --check`
  passed. This change adds no dependencies.

The practical-assistant release `e73e4f7` also passed its
[GitHub verification workflow](https://github.com/Gauravwakle96/RILO/actions/runs/43272855900).
That historical result is separate from this fix's local verification and its
subsequent workflow run.

## Dependency advisory discovered during publication

The storage-fix build `b4f3339` passed its Python lint/typing/tests/package stage
and container build, then failed the npm audit in the frontend-check stage.
Two new moderate advisories affected the transitive `@hono/node-server` 2.1.5
dependency in the Promptfoo runtime. The browser stage did not run in that failed
workflow. This does not invalidate its recorded local tests.

The follow-up pins the patched dependency to 2.1.6 without changing Promptfoo
0.125.1 or hiding audit failures. It changes only that package's lockfile entry,
using CI's npm 11.6.1. See the
[integration notes](PROMPTFOO_INTEGRATION.md) for advisory references. Previous
evaluations retain their captured implementation identity; future evaluations
record the updated runtime lockfile hash. API and worker must restart after the
dependency update so they share the same loaded identity.

The patched runtime passed a clean install with npm 11.6.1, both npm dependency
audits (zero reported vulnerabilities), frontend lint/typecheck/build and the
Python source/wheel build. Fifty-four targeted backend integration tests passed
in 111.98 seconds, covering actual Promptfoo assertions, practical assistants,
local storage and CLI runtime. The full 257-test result above predates this
dependency patch. The restarted patched services again passed readiness and
forty concurrent storage-status reads.

The opt-in actual-inference Chromium test also passed in 3.1 minutes using
`bynara/agnes-2.5-flash`. It exercised paired replies, two declared text checks,
PDF download, saved regression suite and retest with the patched Promptfoo
runtime. The saved original evaluation is `exp_bacab9bdf2e84cf3` in conversation
`conv_b4dac25451a345be`; both agents completed and passed the declared checks.
Its source text is an explicit supplied SQLite/Redis example, not a live research
query or general accuracy benchmark. The
[captured check matrix](ui-evidence/promptfoo-real-paired-checks.png) is refreshed
from this actual browser run.

## Setup portability and browser test follow-up

The patched release with live evidence, `2a1fdb5`, passed all
[GitHub checks](https://github.com/Gauravwakle96/RILO/actions/runs/43396589847).
An earlier patched-runtime workflow had intermittent browser failures: a direct
test API request returned an error object before filtering records, and the
following mobile check missed API readiness. The comparison test now explicitly
establishes its own API session and asserts HTTP success and array shape before
using the records. The comparison and 390-pixel tests passed locally afterward.
No authorization checks or failing test cases were removed.

Newer npm 11.11.0 also required five existing optional dependency paths omitted by
npm 11.6.1's lockfile layout. The lockfile now includes those resolved optional
entries while retaining earlier nested entries required by npm 11.6.1. Both npm
versions accept the lockfile in clean-install dry runs. This does not add database
services or provider integrations to Rilo; they remain transitive optional
dependencies of the assertion package. Existing locked versions are preserved.

The final npm 11.11.0 clean install passed with zero reported vulnerabilities.
All eighteen Promptfoo backend tests passed in 46.52 seconds afterward. The
Python package built successfully, and the final restarted API/worker passed
readiness plus forty concurrent storage reads. The two targeted comparison/mobile
browser tests passed in 36.4 seconds and frontend lint passed. The existing
provider/model settings and evaluation history were preserved throughout.

The full CI browser suite subsequently exposed a request-burst limit: it runs
much faster than the Windows local suite and reached the unchanged per-minute
API budget near its comparison tests. Workspace browser tests now wait, with a
65-second bound, when the setup session receives HTTP 429. They do not disable
rate limiting, repeat mutations or silently turn failed responses into empty
results. Other setup errors still fail immediately. Existing test assertions and
security limits are preserved.
