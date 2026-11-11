# Local deployment and operation

Rilo v0.1 runs as a private local browser application. The API binds to loopback, serves the built frontend, and uses a separate single worker over SQLite WAL. Public or shared hosting requires a new authentication, tenant, TLS, and execution-isolation design.

## Setup

From the repository directory:

```powershell
uv sync --locked
npm ci --prefix frontend
npm run build --prefix frontend
uv run rilo serve
```

The server runs at `http://127.0.0.1:8018`. `uv run rilo serve --port 8020` uses another local port and admits its matching browser origin. For separate processes, start the API and worker as described in [BACKEND.md](BACKEND.md). Vite development runs on `5187`, with its `/api` proxy forwarding to `8018`.

Windows launcher: `START_RILO.cmd`, optionally `-SkipBuild` and `-Gateway`. It runs a per-process PowerShell execution setting and does not change the user’s persistent policy. `Ctrl+C` ends owned services; the gateway launcher terminates only a gateway process it started. Existing Ollama/provider settings and other projects are preserved.

## Configuration

The RILO 2 workspace uses the same API and durable worker. New private variables:
`GITHUB_TOKEN` for authorized private repositories, `RILO_SANDBOX_IMAGE` for a
preinstalled digest-pinned Docker image, `RILO_WORKSPACE_INPUT_BYTES` (default 6000)
and `RILO_STORAGE_MAX_BYTES` (default 512000000). Tavily is optional and off by default.
See [workspace guide](RILO_2_GUIDE.md). Restart both processes after source/config changes
so queued run identities match the loaded implementation.

Source objects and uploads are private in `.rilo/objects` and `.rilo/uploads`. Back up
the entire data directory and a consistent SQLite backup; backing up only the DB
loses captured source bodies. Stop API/worker before manual archive/restore. Existing
records are never automatically deleted. Do not deploy the single-user session
bootstrap as public authentication.

Copy variable names from `.env.example` into private `.env`, preserving generated or existing credentials. Restart both API and worker after edits. Saved dashboard model/gateway settings take precedence over the corresponding environment defaults for later experiments.

| Variable | Purpose |
| --- | --- |
| `RILO_DATA_DIR` | Private database/session workspace; default `.rilo` |
| `RILO_BIFROST_URL` | Explicit local gateway URL; default `http://127.0.0.1:8086` |
| `RILO_MODEL` | Provider-qualified model; default `ollama/qwen2.5-coder:7b` |
| `BIFROST_API_KEY` | Restricted inference virtual key sent only to the local gateway |
| `BIFROST_SETUP_TOKEN` | Gateway administrative bootstrap; created by its helper |
| `TAVILY_API_KEY` | Needed for real live web search; not needed for controlled evidence |
| `RILO_TAVILY_CREDIT_LIMIT` | Conservative workspace lifetime search reservation allowance; default 900 |
| `RILO_PORT` | Allowed local origin for a separately launched API on a custom port |
| `RILO_MODEL_PRICING_JSON` | Explicit per-model input/output rates per million tokens; absent means unknown fee |

The pricing configuration is a versioned estimate basis. Setting zero for a verified local model expresses its inference API fee; it excludes hardware, electricity, storage, and network costs. Cloud prices must be selected from the intended provider’s current terms. Missing usage, unknown/fallback model provenance, or opaque HTTP agents cannot establish a fee.

Tavily reservations use the maximum possible basic search calls. They are not a provider-quota query and do not reset monthly or refund after a cancelled run. Actual returned credit usage is recorded in traces. Consult provider usage before changing the allowance.

## Gateway and model

`uv run python scripts/setup_gateway.py --start` provisions the project-local official Bifrost v2.5.0 binary and constrained Ollama configuration. Downloads are recorded with URL, bytes and SHA256. The recorded hash identifies the artifact; it is not a separately published signature verification. The helper authenticates inference and keeps administration behind its generated setup token.

Ollama runs separately at `11434`. This project does not reinstall or alter an existing provider. Verify the installed model with `ollama list` and keep the gateway model allowlist consistent. The helper provisions local Ollama only; configure additional providers explicitly through Bifrost rather than silently changing local defaults.

## Private data and backups

`.rilo/rilo.db` stores experiments, catalog versions, results and traces. `.rilo/session.key` authorizes the SDK. `.rilo/settings.json` stores safe model/gateway choices. `.rilo/bifrost` contains the gateway artifact, configuration, and private operational databases. `.env`, `.rilo`, model files, build outputs, logs, and generated caches are ignored by Git.

Stop Rilo before copying its private workspace for backup; include a private `.env` backup only in a location you control. SQLite WAL files may matter for an online copy, so a stopped copy or SQLite backup API is preferable. Restore into a stopped workspace, restart Rilo, and verify experiment counts/reports. Schema version 2 adds archived HTTP agent declarations to the initial version 1 database; prior experiment snapshots are preserved. Later migrations must preserve historical evidence. Report exports are portable evidence, not a complete database restore format.

Do not delete the workspace to fix a display problem. Reload the browser or check process/API status first. Expired running jobs are recorded as interrupted/partial after restart. They are not silently rerun; use Rerun for fresh attempts.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| App is unavailable | Start from the project directory; check that port 8018 is free and frontend/dist exists |
| Experiment stays queued | Worker must be running; one long experiment can hold the queue |
| Bifrost health works but inference fails | Check restricted virtual key, model allowlist and `ollama_key_config.url`; health is not inference acceptance |
| Model output fails | Inspect schema/reference checks and source evidence; failures are retained rather than replaced |
| Live mode unavailable | Configure Tavily key privately and restart services; no key has been validated for the current release |
| Gate is inconclusive | Inspect mismatches, repetitions, completion, infrastructure/semantic coverage and declared candidate changes |
| Browser session rejected | Open the approved loopback address; refresh session after service restart |
| Playwright workflow times out | Run against an idle queue; full model experiments take minutes on local hardware |

See [VERIFICATION.md](VERIFICATION.md) for the tested target and [BENCHMARK.md](BENCHMARK.md) for observed throughput.
