# Research, licensing, assumptions, and decisions

Prepared: 7 November 2026. Updated: 9 November 2026. Sources below informed planning and implementation. Exact Python and npm dependencies are now locked and audited; local Bifrost/Ollama inference and fixture/browser flows are verified. [VERIFICATION.md](VERIFICATION.md), [BENCHMARK.md](BENCHMARK.md), and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) provide release evidence. Historical planning assumptions below remain labeled; actual Tavily acceptance is outstanding.

## 1. Primary sources reviewed

| Source | Finding used in the plan |
| --- | --- |
| [Hackathon page](https://hackculture.io/hackathons/ai-global-hackathon) | Six challenges, submission rules, judging dimensions, 15 Nov prototype deadline, 29 Nov judging |
| [Benchmark platform problem statement](https://hackcultureplatform.blob.core.windows.net/event-assets/hackathons/6ac5c8240037f69fb28e23ec/problem_explanation_ck1ellfr6qh.pdf) | Framework independence, identical tasks, repeated runs, controlled failures, metrics, and detailed comparisons |
| [Bifrost repository](https://github.com/maximhq/bifrost) | Apache-2.0 project, self-hosted gateway, Ollama/provider support, operational integrations |
| [Bifrost gateway setup](https://docs.getbifrost.ai/quickstart/gateway/setting-up) | Local gateway setup and compatible model-request interface |
| [Bifrost caching](https://docs.getbifrost.ai/features/semantic-caching) | Exact/semantic caching, TTL, usage metadata, and explicit invalidation already exist |
| [Tavily pricing](https://www.tavily.com/pricing) | Free plan: 1,000 credits/month, no credit card required, at time checked |
| [Tavily search API](https://docs.tavily.com/documentation/api-reference/endpoint/search) | Basic search uses one credit, advanced uses two; dates/domains and usage metadata support research controls |
| [Ollama API](https://docs.ollama.com/api/introduction) | Local-server model API and compatible endpoints; cloud and local operation are distinct |
| [LangSmith evaluation](https://docs.langchain.com/langsmith/evaluation) | Existing offline/online evaluation, datasets, repeated experiments, comparison, and regression workflows |
| [LangGraph quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart) | Graph-based model/tool loop, existing invoke entry point, optional tracing; example provider is not mandatory |
| [FastAPI background-task guidance, official repository](https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/background-tasks.md) | Heavy processing warrants separate job/worker handling; in-process BackgroundTasks is not a persistent experiment queue |
| [SQLAlchemy SQLite dialect documentation source](https://github.com/sqlalchemy/sqlalchemy/blob/main/lib/sqlalchemy/dialects/sqlite/base.py) | SQLite/Python legacy transaction behavior needs explicit treatment for reproducible transactions/migrations |
| [OWASP API Security Top 10](https://github.com/OWASP/API-Security/blob/master/editions/2023/en/0x11-t10.md) | Object-level authorization, authentication, property/function permissions, and resource consumption are key boundaries |
| [Inter license](https://github.com/rsms/inter/blob/master/LICENSE.txt) | SIL Open Font License 1.1 |
| [JetBrains Mono license](https://github.com/JetBrains/JetBrainsMono/blob/master/OFL.txt) | SIL Open Font License 1.1 |

Several direct documentation browser loads and GitHub MCP reads failed with network errors. Relevant official repository documents and font license statements were retrieved successfully through approved read-only requests. Do not describe the initially failed requests as successful checks.

The former OpenTelemetry agent-span documentation URL indicated it had moved to [semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai). Rilo initially uses its own documented JSON event contract; current OpenTelemetry mapping needs separate verification before implementation.

## 2. Skills applied

- [AI product skill](C:/Users/gaura/.agents/skills/ai-product/SKILL.md) and its detailed guide: validated model outputs, prompt versioning, progress, costs, failure handling, and backend execution.
- [ECC agent-eval guidance](C:/Users/gaura/.codex/plugins/cache/ecc/ecc/2.2.3/skills/agent-eval/SKILL.md): representative tasks, repeated trials, versioned fixtures, deterministic checks, and measured cost/time.

ECC's agent-eval examples concern coding agents. Only applicable evaluation principles are adapted to research agents. Its CLI was not installed, and Git worktrees are not treated as an OS security sandbox.

## 3. Architecture decisions

| Decision | Rationale | Revisit when |
| --- | --- | --- |
| Local web application first | Existing computer executes models/tests; browser handles comparison | Users need native installation or team hosting |
| Python core with adapter interfaces | Research agents and evaluation integrate naturally; avoid framework-specific core | A measured performance/integration need requires another runtime |
| React/Vite frontend | Interactive private dashboard without unnecessary SSR infrastructure | A separate public website has SEO requirements |
| SQLite first | One local worker and low setup burden | Concurrent team writers justify PostgreSQL |
| Separate durable worker | Experiments outlast requests and need restart/cancellation accounting | Multiple hosts justify a broker-backed worker system |
| Research category first | Meaningful Tavily integration and read-only initial tools | Validated user demand supports new packs |
| Raw metrics before overall score | Evidence, denominators, and unknowns stay inspectable | A validated domain-specific aggregate is justified |
| Live, controlled evidence, and playback distinct | Prevent misleading reproducibility claims | New protocols require clearly defined additional modes |

## 4. Licensing and maintenance

Bifrost's Apache-2.0 license and both proposed fonts' OFL 1.1 licenses were checked. Include required notices if vendoring or distributing their assets.

React, Vite, FastAPI, Pydantic, LangGraph and testing tools are installed through `package-lock.json` and `uv.lock`. Standard SQLite is used instead of SQLAlchemy/Alembic. Runtime and development dependency audits were executed as recorded in verification. Direct dependency metadata and font licenses are retained in the notices. A downloadable model has its own license; local execution does not waive it.

Tavily is a service governed by its terms. Review permitted storage/replay/redistribution before retaining full source content. Public task packs should use synthetic or appropriately licensed evidence and attribution. Copyrighted web snapshots are not automatically publishable with a public repository.

Rilo's own source uses Apache-2.0 and the license text is included in `LICENSE`. Synthetic corpus content uses CC0. No legal/name availability conclusion is claimed.

## 5. Cost assumptions

No required paid model, paid hosting, commercial database, or managed tracing integration in local mode. Existing hardware is assumed; electricity/internet/storage remain real costs.

Tavily free quota and actual request depth determine whether live research remains free. Three basic searches per 120 attempts would consume 360 credits; development and retries also consume quota. Replay can reduce new research calls but must remain distinguishable from live testing.

Local model structured output, speed and observed task behavior were measured on the user's RTX 3050 laptop with the installed `qwen2.5-coder:7b`; see benchmark evidence. Cloud-provider free tiers are not a dependency of this plan.

Hosted operation and optional paid products have a separate budget and require evidence of developer demand and operating economics.

## 6. Remaining verification

- Working name Rilo: domain, package, repository, and trademark availability before public launch.
- Local hardware, model capabilities, and actual Bifrost/Ollama/Tavily integration.
- Exact dependencies and transitive license/security review.
- Agent adapter compatibility without rewriting internal control loops.
- Source retention and dataset redistribution rights.
- Event completeness, actual token/credit provenance, restart/cancellation behavior, and fair comparisons.
- Reference quality, semantic-grader calibration, actual benchmark outcomes, and user usefulness.

These are implementation/release gates rather than completed checks. Official hackathon scoring weights were not published in the reviewed page; no predicted score or winning probability is part of the product plan.
