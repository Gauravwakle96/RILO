# Developer integration

Rilo’s Python API and CLI control a local server. They do not execute an arbitrary Python import supplied through the browser. The supported integration surfaces are the SDK, HTTP API, built-in boundary workflows, and a local HTTP adapter for existing agents.

## SDK and command-line workflow

Run `uv sync --locked` and `uv run rilo serve` from the project. `RiloClient` reads the private `.rilo/session.key`; supply `data_dir` when using another workspace. Only explicit loopback endpoints are accepted, redirects and proxy environment variables are disabled, and authentication is never exported with results.

Available SDK methods: `agents()`, `tasks()`, `experiments()`, `run(spec, idempotency_key=...)`, `experiment(id)`, `wait(id, timeout=...)`, `cancel(id)`, `baseline(id, name)`, `compare(baseline_id, candidate_id, allow_agent_changes=False)`, and `export(id, Path, format='json'|'csv')`. `request(method, relative_route, ...)` covers additional documented API routes. API failures raise `RiloError`; polling timeouts leave the persisted experiment available for later inspection.

```powershell
uv run rilo run examples/research-fixture.json --wait --idempotency-key local-demo-v1
uv run rilo show EXPERIMENT_ID
uv run rilo baseline EXPERIMENT_ID --name "Before retry change"
uv run rilo compare --baseline OLD_EXPERIMENT_ID --candidate NEW_EXPERIMENT_ID --allow-agent-changes --require-pass
uv run rilo report EXPERIMENT_ID --output reports/result.csv --format csv
```

Exit status `0` means the requested gate passed, `1` means measured task success regressed, and `2` means inconclusive or command/API error. Parse the JSON `gate` to distinguish an inconclusive comparison from a failed API command. The initial gate is an exploratory no-regression policy, not a statistical confidence test or configurable production release policy.

Changing agent behavior must be explicit. Strict comparisons require matching agent versions and implementation hashes. A declared agent change permits that candidate variable while retaining compatible IDs, framework/kind, observation coverage, tasks, evidence, model, execution policy, grader, limits, and repetitions. Undeclared or incompatible conditions cannot produce a passing gate.

## Connect an existing local HTTP agent

Wrap the existing agent entry point in a loopback HTTP service. Rilo sends a bounded request to a registered `/run` endpoint:

```json
{
  "run_id": "run_...",
  "task": {"prompt": "...", "company": "...", "reference_time": "2026-11-01T00:00:00+00:00"},
  "evidence": [{"id": "aurora_launch", "title": "...", "content": "...", "published_at": "..."}],
  "limits": {"max_model_calls": 12, "max_tool_calls": 6, "timeout_seconds": 120}
}
```

The endpoint returns either the output object or `{"output": ...}`:

```json
{
  "output": {
    "summary": "A concise briefing or explanation of uncertainty.",
    "facts": [{"text": "Exact supported source statement.", "source_ids": ["aurora_launch"]}]
  }
}
```

Keep your agent’s control loop intact. Adapt input/output and cite the supplied source identifiers. Summary is at most 6,000 characters, there are at most 20 facts, each fact is bounded, and service responses are capped at 256 KB. Calls do not follow redirects. The adapter has no credential-configuration field; keep its service explicitly local and follow the local trusted-process model.

Use **Agents → Connect agent**, or send `POST /api/v1/agents` with `name`, `version`, `kind='http'`, `description`, and `endpoint='http://127.0.0.1:9000/run'`. Supported HTTP experiments use controlled evidence, `normal` only, and the real-engine selection; the adapter chooses its own execution/provider behavior. It does not observe internal model/tool calls or enforce the adapter’s internal billing limits. Those metrics are null and coverage is `final_output_only`. A cancelled HTTP request does not guarantee the remote service terminated its own work. Live research and injected failures require an instrumented boundary adapter and remain unsupported for this interface.

Version registration creates a new current HTTP configuration while old experiment snapshots remain immutable. Supply a new version string and endpoint through the version API described in [API_CONTRACT.md](API_CONTRACT.md). Existing historical results remain tied to their captured configuration.

## Add tasks and understand grading

Custom tasks use known corpus sources, an explicit timezone/reference window, and required verbatim source statements. Rilo validates that each required statement appears in selected evidence before accepting the task. Select useful task-specific references; an empty or unsupported rubric cannot establish success.

The bundled examples are a limited research benchmark. Matching references and citations is evidence for the structured fact list, not general truth verification. The summary’s arbitrary factual content remains unassessed, and live task quality remains inconclusive without validated semantic references. More source/reference formats and calibrated graders are future work.

## Test and automation

The repository’s Python tests run against temporary workspaces and mocked service boundaries. Playwright uses the running local API/worker for CRUD, experiment, export, trace, baseline, comparison, responsive, keyboard, and axe checks. UI error states that use request interception are labeled simulations in the evidence.

The supplied GitHub Actions workflow runs package checks and a fixture regression demonstration in an isolated local workspace. It has no model/search credentials and does not claim live integration acceptance. Actual provider acceptance is recorded separately in [BENCHMARK.md](BENCHMARK.md).
