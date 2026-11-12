# Rilo product readiness and priorities

Delivery update: the assessment below is the preserved pre-change review.
See [LOCAL_PRODUCT_IMPLEMENTATION.md](LOCAL_PRODUCT_IMPLEMENTATION.md) for the
implemented local history, comparison slots, adapters, diagnostics, source inspection,
checks, suites, storage, privacy controls and current acceptance evidence. Its
remaining limits supersede the earlier implementation proposals where applicable.

Assessment date: 12 November 2026. This is a code and documentation review,
supported by focused automated checks. It is not a load-test report, independent
security audit, customer study, or product-quality score.

## Product decision

Start with a local developer product for investigating research and document-agent
failures. A developer connects two agent versions, supplies representative tasks
and sources, defines success, investigates failures, and reruns a saved suite after
a change. The useful outcome is evidence for a release decision.

Keep chat, repositories, documents, websites and search as input workspaces within
that workflow. Broad source ingestion does not establish expertise in every domain.
Do not position bounded repository review as an exhaustive security scanner.

## Current assessment

| Dimension | Current evidence | Main gap |
| --- | --- | --- |
| Usability | Shared tasks, independent histories, preflight, retries, traces, exports and lower-left guide exist | Many navigation destinations and manual evaluation configuration; no observed first-use study |
| Reliability | Durable records, worker leases, cancellation, bounded execution and repair, ownership checks and backup/restore exist | End-to-end availability and restart behavior under sustained load have not been measured |
| Scalability | Bounded ingestion, SQLite WAL and a separate worker keep the local implementation manageable | Single worker, sequential execution and single-instance storage; no established concurrent-user capacity |
| Feasibility | Existing React/FastAPI stack and local inference can support an initial developer release | Setup depends on Node, Python, gateway and model availability; hardware and inference still have real costs |
| Market value | Controlled research faults, captured references and an integrated investigation interface | Evaluation, tracing and regression are established market capabilities; usability and demand need validation |

## Concrete findings from the code

1. `backend/rilo/worker.py` processes an experiment and its runs sequentially.
   This is suitable for constrained local inference. A long experiment can delay
   subsequent work; there is no demonstrated multi-worker scheduling capacity.
2. `backend/rilo/storage.py:Store.experiments` returns at most 200 evaluations.
   `backend/rilo/workspace_store.py:WorkspaceStore.list` returns at most 100
   conversations. Neither list offers user-facing pagination in these interfaces.
3. `backend/rilo/workspace_api.py:dashboard` uses the capped experiment list to
   calculate evaluation totals and loads individual records repeatedly. Totals
   can become a latest-records count rather than an all-history count, and query
   work grows with the returned attempts.
4. `backend/rilo/workspace_engine.py:prepare` selects at most 3,000 source
   characters before further input-budget fitting. Default serialized workspace
   input budget is 6,000 bytes. This protects local execution but limits coverage;
   captured files and analyzed passages are different quantities.
5. `backend/rilo/workspace_store.py:profiles` gives custom HTTP agents no paired
   workspace tasks. The existing custom adapter supports a limited research
   contract, normal controlled-source conditions and final-output observation.
   That limits how developers evaluate their existing applications in all five
   workspaces.
6. `backend/rilo/readiness.py` checks gateway reachability, model listing and the
   worker lease. It correctly avoids promising successful inference. A configured
   gateway or key is not an executed end-to-end acceptance test.
7. Ground-truth quotation retrieval and valid references are scoped measurements.
   They do not establish that a vulnerability claim or arbitrary answer is true.
   Keep those distinctions visible beside the result.

## Market comparison

Official pages checked on 12 November 2026:

| Product | Established capabilities relevant to Rilo | Implication |
| --- | --- | --- |
| [Promptfoo](https://www.promptfoo.dev/docs/intro/) | Use-case evaluations, assertions, custom providers, side-by-side results, CI, caching, concurrency and red teaming | Rilo should reuse its checks and offer a simpler evidence/failure investigation experience; comparison alone is not a differentiator |
| [Langfuse](https://langfuse.com/docs/evaluation/overview) | Production traces, datasets, experiments, manual/automated evaluators, comparison and CI regression gates | Traces and regression are overlapping capabilities; avoid describing Langfuse as tracing only |
| [LangSmith](https://docs.langchain.com/langsmith/evaluation) | Agent datasets, offline/online evaluation, human/code/model evaluation, experiment comparison and production feedback loops | Rilo needs a concrete advantage for a narrower user group rather than matching the whole platform |

Rilo's candidate position is an approachable local workspace for controlled failure
tests and source inspection. Local/private operation is useful, but Promptfoo also
runs locally. Validate whether Rilo reduces setup and investigation effort enough
for users to adopt it.

## Prioritized implementation sequence

### 1. Make first use and results understandable

- Add a guided first comparison: choose a task, connect an available agent/model,
  supply sources, choose explicit checks, run and inspect the result.
- Keep an advanced view for full benchmark configuration.
- Show execution state, passed requirements, reference validity and semantic review
  separately. Include an explicit inconclusive outcome.
- Show source coverage prominently: captured files/pages, selected passages,
  omissions and context limits. Offer a focused follow-up on unexamined sections.
- Add history pagination/search and accurate SQL aggregate totals.
- Show queued/preparing/running/evaluating states, elapsed time and cancellation.
  Use measured runtime estimates only when enough comparable history exists.

Acceptance target: at least four of five new developers complete a first useful
comparison without assistance within ten minutes after prerequisites are ready.
Treat installation time as a separate measured task.

### 2. Make it useful for developers' own agents

- Extend the existing adapter contract to support compatible paired source tasks,
  rather than introducing another execution engine.
- Test connection/schema compatibility before accepting work.
- Version prompts, agent configuration and checks without changing old records.
- Provide an example connecting a real local research/document application.
- Add a documented CI flow with explicit pass, regression and inconclusive exits.
- Preserve unknown tool/token/cost metrics for uninstrumented external agents.
- State cancellation capability honestly; cancelling an HTTP request may not stop
  work inside the remote agent.

Acceptance target: a developer connects an unfamiliar compatible agent, captures
an observed failure, changes the agent, and reruns the same saved task successfully.

### 3. Establish reliability before expanding hosting

- Exercise restart while queued, preparing, generating and evaluating. Preserve
  completed results and identify interrupted work without silently duplicating
  executions. Explicit retries should retain provenance.
- Test provider outages, slow inference, malformed output, full storage, network
  failure, large inputs and report failures through the complete user flow.
- Add bounded queue admission and per-user running/queued limits before public
  multi-user operation.
- Separate infrastructure failures from measured task failures in every view.
- Document deletion/retention for snapshots, uploads, traces and reports.
- Rehearse restore and define supported capacity from measured tests.

Acceptance target: repeated valid-input evaluations under healthy dependencies
complete without runner failures; injected faults produce explainable terminal
states. Model/check failures remain legitimate product results.

### 4. Scale only after measuring the bottleneck

- Keep SQLite and sequential inference for the local release.
- First improve pagination, aggregate queries, request payloads and storage cleanup.
- For a hosted pilot, measure throughput, queue delay, API latency, inference
  latency, error rates, storage growth and per-evaluation operating cost.
- Before horizontal deployment, migrate shared relational data to PostgreSQL and
  snapshots/uploads to a private object store. Preserve existing data through
  migrations and keep owner checks at each boundary.
- Introduce configurable workers and inference concurrency only with fair queue
  scheduling, safe claims, resource budgets and provider-capacity measurements.
- Keep snapshots, histories and evaluation conditions equivalent for paired runs.

No concurrent-user promise or service availability commitment is justified yet.
Open-source software and user-owned local inference can avoid API fees; hosted
compute, storage, bandwidth, support and backups are not inherently free.

## Validation record

The previous completion record reported 208 Python tests, 16 standard browser
tests and remote container acceptance. Those counts are historical.

Fresh checks for this assessment: **25 passed in 70.40 seconds**:

```powershell
uv run pytest tests/backend/test_user_failures.py tests/backend/test_execution.py tests/backend/test_hosted_auth.py tests/backend/test_backup.py -q
```

These cover focused failure/recovery behavior, hosted ownership and backup/restore
against test environments and mocked service boundaries. They do not establish
live model reliability, deployment capacity or market demand.

No new application implementation, browser acceptance, full suite, live Tavily
validation, load testing or external user study is claimed by this assessment.
