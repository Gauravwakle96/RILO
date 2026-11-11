# Rilo: complete product plan

Prepared: 7 November 2026. Updated: 9 November 2026. This document retains the original product vision. The local dashboard, API, durable worker, SDK/CLI, repeated task/failure suite, baselines, reports and Bifrost inference are implemented. See [README.md](README.md) and [verification](docs/VERIFICATION.md) for the current release; Tavily live acceptance and broader team features remain outstanding.

## 1. Product decision

Rilo, pronounced REE-loh, helps developers answer three questions:

1. Does this agent complete our actual tasks?
2. What happens when its model, tools, or retrieved information fail?
3. Did our latest change make it better or worse?

The initial product is a local web application with a reusable Python execution engine. Research agents are the first supported category. A working Python SDK and CLI ship in this first local release; independent developer adoption is still a beta acceptance gate. Self-hosted team operation follows once isolation, authorization, concurrency, and durable execution are validated.

The product is a testing and diagnosis platform. It does not build every agent for its users, certify an agent as universally safe, or guarantee production behavior from a small benchmark.

## 2. Users and real problems

| User | Current problem | Useful outcome |
| --- | --- | --- |
| Solo AI developer | A demonstration succeeds, but failures are hard to reproduce | A small repeatable suite that exposes recovery behavior |
| Team choosing an agent | Comparisons mix different tasks, tools, models, and budgets | Comparisons with explicit conditions and comparable evidence |
| Developer changing prompts or models | An improvement in one case silently breaks another | Regression results against a pinned baseline |
| Reliability or security engineer | Tool failures and hostile retrieved content are not tested consistently | Controlled scenarios, bounded actions, and inspectable traces |
| Product owner | Quality, latency, and cost trade-offs are unclear | Separate measures of completion, reliability, runtime, and expenditure |

Start with independent developers and small teams building research/RAG agents. Validate their recurring workflow before expanding to every agent category.

## 3. Positioning and differentiation

Evaluation, tracing, datasets, and experiment comparison already exist in products such as LangSmith. Rilo's intended focus is making reproducible failure testing straightforward in a local environment, with transparent comparison conditions and evidence explaining recovery.

Four product pillars:

- **Controlled failures:** reusable model, tool, and retrieved-content scenarios with recorded triggers.
- **Comparable evidence:** fixed evidence sets for controlled experiments, alongside separately labeled live research.
- **Inspectable results:** timelines and grader evidence linked to each reported outcome.
- **Repeatable improvements:** versioned agents, tasks, scenarios, data, and evaluators; rerun after a change.

These are a proposed product focus, not a claim that no existing tool has similar features. Competitive validation remains part of discovery.

## 4. Product surfaces

| Surface | First useful behavior | Release |
| --- | --- | --- |
| Browser dashboard | Register agents, configure tests, inspect progress, compare results | Prototype |
| Execution API | Queue bounded experiments, read events and results, cancel work | Prototype |
| Python SDK | Connect existing callable agents and emit trace events | Minimal adapter in prototype; supported SDK in beta |
| CLI | Run suites headlessly and export machine-readable reports | Developer beta |
| CI integration | Compare a candidate with a baseline and return a gate result | Developer beta |
| Team workspace | Share projects, access policies, baselines, and retained evidence | Self-hosted team release |
| Desktop package | Convenient installer around the local web application | Only after users demonstrate a need |

## 5. Core modules

1. Agent registry: versioned adapter configuration, capabilities, model policy, and health checks.
2. Task library: immutable tasks, expected behavior, source/date constraints, and evaluator versions.
3. Scenario library: bounded, reproducible failures with explicit eligibility and trigger definitions.
4. Evidence library: source identifiers, permitted snapshots, hashes, collection time, and licensing metadata.
5. Experiment builder: agents, tasks, conditions, repetitions, limits, and comparison policy.
6. Run engine: persistent jobs, fresh run state, timeouts, cancellation, and event collection.
7. Evaluation engine: deterministic checks and calibrated semantic assessments with evidence.
8. Comparison view: outcomes, uncertainty, coverage, cost/runtime, and baseline changes.
9. Trace inspector: observable steps, model/tool calls, injected failures, retries, outputs, and errors.
10. Reports and regression policies: exported evidence, configurable thresholds, and inconclusive outcomes.

## 6. Developer journey

Install locally -> check model and tool connectivity -> connect agents -> choose a task suite -> inspect scenario compatibility -> set limits -> run -> compare -> inspect a failure -> change the agent -> rerun the same conditions -> save a baseline -> automate subsequent checks.

Onboarding should offer two real example agents, one plain Python and one LangGraph-based, using a user-configured local model through Bifrost. Demo agents establish that different implementations can be connected; they are not evidence of support for every framework.

Agent integration may need an adapter, endpoint configuration, or native callbacks. The platform must not require rewriting the agent's internal decision loop. Unsupported instrumentation or failure injection is reported explicitly.

## 7. First research task pack

The initial pack has five tasks: a recent company briefing, similarly named company disambiguation, conflicting-source handling, insufficient-evidence handling, and multi-step research with bounded recovery.

Each task has a fixed reference time, allowed evidence, expected facts or uncertainty, structured output requirements, and a versioned rubric. Meeting-briefing tasks accept a company/person and meeting time and cover the preceding 30 days.

Normal operation plus three scenarios form the initial condition set:

- first eligible search call times out;
- one eligible model request returns a controlled unavailable-model response;
- a retrieved document includes an instruction conflicting with the legitimate task.

Real-engine runs use actual models. A separately labeled fixture engine provides deterministic Python synthesis for offline checks. Faults are explicitly injected test conditions. No outage is induced in an external provider.

## 8. Execution and evidence modes

| Mode | Models and tools | Purpose | Important limit |
| --- | --- | --- | --- |
| Live | Real model calls; live Tavily retrieval | Test current research behavior | Web evidence can change between runs |
| Controlled evidence | Real model calls; search over a fixed permitted evidence corpus | Compare agent behavior on the same available documents | Corpus coverage limits conclusions |
| Trace playback | Display an already recorded run | Inspect an event sequence | Playback is not a new benchmark execution |

Exact-response tool fixtures may be added for protocol-level tests. A query not covered by a fixture is a fixture gap, not proof that an agent failed. A fixed searchable corpus is preferable for allowing different research paths during controlled comparisons.

Record the actual model, provider, cache mode, adapter capabilities, task/rubric versions, evidence hash, limits, and scenario version. Saved inputs do not make live LLM generation deterministic.

## 9. Scope and acceptance

### Prototype acceptance

- Two independently implemented agents connect through adapters.
- Both run the same five tasks with at least three trials under normal and three failure conditions.
- Metrics include task outcomes, observable steps, tool/model calls, tokens where available, API fee accounting, and execution time.
- Bifrost and Tavily are integrated meaningfully and shown in real runs.
- The dashboard shows progress, scenario activation, incomplete instrumentation, uncertainty, and detailed traces.
- Controlled evidence tests can be rerun; trace playback is clearly labeled.
- Limits, cancellation, malformed outputs, failed dependencies, and interrupted jobs have explicit behavior.
- Reports identify agent failures separately from infrastructure errors and missing evaluation evidence.
- Public repository documentation and a demonstrated prototype support the hackathon submission.

### Developer-beta acceptance

- A developer outside the project connects an existing agent without rewriting its control loop.
- At least two integration styles have documented compatibility and contract tests.
- Tasks, scenarios, graders, and baselines are versioned and exportable.
- CLI/API operations are repeatable and supported through documented contracts.
- Restart, cancellation, retention, backups, and private data handling are validated.
- A regression gate can return pass, fail, or inconclusive with supporting evidence.
- Pilot users successfully diagnose and retest a real agent issue.

Prototype acceptance does not imply team-hosted or arbitrary-code execution readiness.

## 10. UX and design direction

Use a restrained developer-tool interface. Prioritize comparisons and evidence over a decorative overall score.

Primary navigation: Overview, Agents, Suites, Scenarios, Experiments, Compare, Evidence, Settings. Within an experiment: Summary, Runs, Trace, Evaluation, Usage, Configuration.

Typography: Inter for interface text and JetBrains Mono for identifiers, code, and trace data; self-host licensed font files at implementation. Planned sizes: 12, 14, 16, 20, 28, and 36 px. Spacing uses a 4 px base with 8/12/16/24/32 px common intervals.

Use neutral slate surfaces, a blue action accent, and semantic statuses accompanied by text/icons. Provide light and dark themes. Validate actual color pairs against WCAG AA; no contrast claim is made before UI checks.

Display successes/valid attempts, total attempts, infrastructure failures, unknown metrics, and confidence/variation where justified. Do not turn unavailable usage into zero or hide failed runs from denominators.

Support empty/loading/error/cancelled/partial states, keyboard operation, visible focus, reduced motion, accessible charts/tables, and mobile/tablet/desktop layouts. Trace views should wrap or scroll explicitly; small screens switch to a single-run view before side-by-side comparison.

Local onboarding asks for project, agent configuration, and service connectivity. Secrets are supplied to the backend and never embedded in the frontend or reports. The UI shows actual preflight errors rather than invented example progress.

## 11. Human involvement and automation

Humans initially select representative tasks, validate reference examples, connect agents, and decide acceptable release policies. Runs, repetitions, failure scheduling, event recording, deterministic grading, comparison, and configured regression checks can operate automatically.

Human review is needed when semantic evidence is genuinely unresolved or when changing a rubric. Uncertainty is an allowed result. Rilo does not autonomously change a developer's production prompts, deploy fixes, or grant tools broader permissions.

## 12. Costs and deployment

The default is a local single-user deployment using the existing computer: React/Vite, FastAPI, a separate Python worker, SQLite, self-hosted Bifrost, and local Ollama models. No paid integration is required.

Tavily's checked free plan offers 1,000 credits/month without a credit card. Basic searches use one credit; advanced searches use two. Free limits and terms may change; preflight must check configured limits and remaining usable quota.

Illustrative full demonstration: 2 agents x 5 tasks x 3 repetitions x 4 conditions = 120 attempts. If each attempt makes three basic searches, that is 360 search credits, before additional testing. Every actual search/retry is counted. A full run is admitted only if its configured upper bounds fit available quotas; partial runs are labeled.

Default local concurrency is one. Measure actual hardware throughput before estimating completion time. Zero API fees do not imply zero electricity, internet, storage, or hardware cost. A hosted backend and scaled team operation have separate operating costs.

## 13. Product discovery and business model

Before expanding scope, work with 5-10 willing pilot developers. Ask them to bring recurring tasks and a failure they have difficulty reproducing. Observe integration friction, whether the test identifies useful behavior, and whether they rerun after a change. Interviews/contact require the user's separate authorization; none are performed by this plan.

Track time to first valid comparison, independent integration success, repeated suite usage, diagnosed/reproduced issues, and whether changes improve measured outcomes. Set numeric adoption targets after pilot evidence establishes a baseline.

Recommended direction: open-source core under Apache-2.0, with local/self-hosted execution and bring-your-own model credentials. Potential paid offerings later include managed execution, team access controls, scheduled checks, retention, and support. Pricing and willingness to pay remain hypotheses. No billing or paid service is enabled.

## 14. Future scope

- Research/RAG: source grounding, freshness, retrieval failures, and document-instruction resistance.
- Customer support: policy accuracy, appropriate uncertainty, and permitted actions in simulated workflows.
- Coding: functional tests, resource efficiency, and constrained execution in isolated repositories.
- Business workflows: duplicate actions, recovery, and idempotency in simulated services.
- Team operation: access policies, shared evidence, runners, schedules, and baselines.
- Production feedback: opt-in redacted traces can become new regression tests; production side effects are never replayed automatically.
- Improvement experiments: developers approve candidate changes; Rilo compares their measured effects.

Add task packs and evaluators to the same core before creating unrelated products. Every new tool/action category needs its own evaluation and execution-boundary review.

## 15. Delivery and limitations

The 15 November 2026 hackathon prototype is the first milestone. The developer beta, team release, and managed service have separate acceptance gates, described in [ROADMAP.md](docs/ROADMAP.md).

Outstanding decisions to verify during implementation: local hardware/model capability, exact dependency versions, initial adapter support, source retention rights, naming availability, and actual benchmark runtime. These do not prevent planning; they determine admission checks and release scope.

No current benchmark accuracy, security certification, customer adoption, or hackathon score is claimed. The plan's source basis and licensing decisions are in [RESEARCH.md](docs/RESEARCH.md).
