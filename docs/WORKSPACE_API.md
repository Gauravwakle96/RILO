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
