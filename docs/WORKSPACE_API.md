# Paired workspace API

All routes use `/api/v1/workspace` and session/CSRF authentication. Local mode also
supports the private CLI bearer key. Hosted mode uses persistent users and per-user
ownership behind HTTPS; it does not accept the local bearer shortcut.

| Route | Purpose |
| --- | --- |
| GET /profiles | Task formats, tools, requirements and limits per profile |
| GET /capabilities | Optional integration availability without credentials |
| POST /preflight | Check configuration's model, gateway, worker and optional grader readiness |
| GET /dashboard | Aggregates from persisted executions |
| GET /history | Paginated experiments/conversations: kind, query, page, size and optional conversation category |
| GET /storage | Local database/blob usage and orphan-file preview |
| POST /storage/cleanup | Remove only unreferenced blobs while the queue is idle |
| GET /backup | Stream a consistent private backup while the queue is idle |
| PATCH /conversations/{id} | Rename with a validated title |
| GET, POST /conversations | List/create paired conversations |
| GET /conversations/{id} | Shared turns, effective responses and original/retry attempts |
| GET /conversations/{id}/export | All shared messages and separate responses as JSON |
| POST /conversations/{id}/turns | Queue shared input; optional Idempotency-Key |
| POST /runs/{id}/retry | Retry latest failed response; preserve other branch |
| POST /uploads | Raw bytes with URL-encoded X-Filename; maximum 8 MB |
| GET /snapshots/{id} | Private captured sources and metadata |
| GET /evaluations/{id} | Outputs, evidence and artifacts |
| POST /evaluations/{id}/retest | Reuse captured snapshot/prompt/history, or retry failed input capture under current runtime |
| GET /evaluations/{id}/report | format query: pdf, md, json or csv |
| GET /reports | Generated report references |
| GET, POST /suites | Immutable versioned benchmark suites |
| POST /suites/{id}/run | Repeated trials on captured sources |
| POST /regressions | Compare baseline_id and candidate_id |

Cancel through `POST /api/v1/experiments/{id}/cancel`. Existing benchmark SDK/CLI,
trace, report and comparison routes remain available.

Create a conversation with `title`, `category` (chat/repository/documents/website/search),
`agent_ids` (two compatible profiles), `model`, `search_provider` (off/tavily), and
optional `semantic_review`. Then send a turn:

```json
{
  "message": "Inspect architecture and security. Cite actual source lines and qualify uncertainty.",
  "inputs": {
    "url": "https://github.com/pallets/itsdangerous",
    "run_tests": false,
    "dependency_advisories": false
  }
}
```

For follow-ups, send `message` with empty inputs to retain the previous snapshot.
Both branches receive the follow-up and only their own previous outputs. One active
turn/retry per conversation is admitted atomically. Two manual retries per response
are allowed; originals are retained. Terminal states distinguish completed, partial
and failed paired execution. Completed does not mean accurate.

Suites accept `name`, `version`, `source_experiment_id`, `repetitions` (1–5), and
optional labels `{label_id, reference, expected_quote}`. Labels must exist in captured
sources. Precision/recall/F1 evaluate quotation retrieval only. The repository rubric
has no aggregate score until independently measured criteria exist.

Turns also accept `checks` (0–12):

```json
{
  "message": "Name the database used in this project",
  "inputs": {"text": "The project uses SQLite."},
  "checks": [{"id":"storage","name":"Names the database","type":"icontains","value":"SQLite","target":"summary"}]
}
```

Check types are `equals`, `contains`, `icontains`, `not-contains`,
`not-icontains`, `is-json`. Targets: `summary` or `response`. JSON checks omit
`value`. No scripts, schemas, providers, hooks or file/package references. Grading
uses the actual pinned Promptfoo package. `assessment.task_checks` separates
pass/fail/ungraded/error; scores measure only the declared rules.

Suites inherit checks from their source evaluation unless an explicit `checks`
list is supplied. A new suite version is required to change rules. Comparisons
report `baseline_check_score`, `candidate_check_score`, `check_score_delta`,
`newly_failed_checks` and `now_passing_checks`; mismatched rules invalidate the
regression gate. Existing quotation metrics remain separate.

Preflight body: `{"configuration":{"title":"Check","model":"ollama/qwen2.5-coder:7b"},"require_checks":true}`.
It performs health/list checks, not inference, and returns readiness details.

`test_inference: true` executes a small real request for each selected model.
Local Ollama uses Bifrost; `bynara/MODEL_ID` uses the fixed Bynara endpoint and
private BYNARA_API_KEY. Credentials are never returned. HTTP 402 is insufficient
provider credit; HTTP 404 means the selected model/endpoint is unavailable.

Local retention: `POST /workspace/records/{experiments|conversations}/{id}` with
`action: archive|restore|delete`. Deletion needs `confirmation` equal to the exact
record ID, an idle queue and no retained dependency. History accepts `archived=true`.
Shared snapshots/uploads are retained; archive is reversible.

Candidate reruns: `POST /workspace/evaluations/{id}/retest` accepts optional two-slot
configuration. An empty body retains original settings. Original task, checks,
history and captured snapshot remain pinned; candidate changes need declaration
when comparing regression conditions.

`POST /workspace/conversations/{id}/continue` creates an explicitly extractive
continuation with last-three-turn excerpts per agent and retained source snapshot.
It preserves the original conversation and does not mix independent answers.

`POST /workspace/suites/{id}/batches` persists a whole suite admission. Inspect
`GET /workspace/batches/{id}`, resume missing cases with `POST .../{id}/resume`,
or export `GET .../{id}/export`. Results reflect recorded per-case checks only.

`POST /workspace/runs/{id}/reviews` accepts finding_id, verification state and
rationale. Reviews are appended as human_review artifacts; original findings and
automated checks stay intact. Reports include the separate human judgments.
