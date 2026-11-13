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
