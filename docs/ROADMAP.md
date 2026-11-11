# Rilo delivery roadmap

Updated 9 November 2026. Core local implementation, SDK/CLI, repeated controlled experiments, Bifrost inference and browser validation are complete; [VERIFICATION.md](VERIFICATION.md) records the actual checks. Live Tavily acceptance, independent developer pilots, public release/submission and team hosting remain separate gates. Milestones below retain the longer product roadmap rather than claiming those future outcomes are achieved.

## 1. Delivery sequence

| Milestone | Outcome | Exit gate |
| --- | --- | --- |
| M0: feasibility | One real local model call through Bifrost and one bounded Tavily query | Actual connectivity, structured-output capability, quota, and runtime measured |
| M1: first useful comparison | Two existing agents execute one identical task through adapters | Valid outputs, event/usage provenance, actual comparison, fresh run state |
| M2: reliability prototype | Five tasks, repeated trials, three faults, controlled evidence, dashboard | Mandatory hackathon behaviors demonstrated and documented |
| M3: developer beta | Supported SDK/CLI, task/scenario versions, baseline comparison, robust recovery | Independent developer integration and repeat usage |
| M4: self-hosted teams | Shared projects, permissions, isolated workers, scheduling, retention | Authorization, isolation, load, backup, and recovery checks pass |
| M5: additional task packs | RAG/support/coding/workflow evaluation | Domain-specific references and action boundaries validated |
| M6: managed offering | Optional hosted operation and support | Pilot demand, operating economics, privacy, and service reliability validated |

Do not add a managed service merely to make the product appear complete. The local developer tool is a complete useful product once its own acceptance gates pass.

## 2. Prototype target: 7-15 November 2026

| Target dates | Work |
| --- | --- |
| 7-8 Nov | Finalize contracts; perform M0; select a capable local model; create one referenced task and two adapter integrations |
| 9-10 Nov | Persistent run engine, model/tool observations, limits, ordered traces, and first real comparison |
| 11-12 Nov | Five-task pack, three bounded faults, evidence-corpus mode, graders, repeat accounting, and minimal comparison UI |
| 13 Nov | Complete representative real trials; debug malformed outputs, cancellation, interrupted jobs, and instrumentation gaps |
| 14 Nov | Required code/dependency/security/browser checks, report evidence, README, architecture explanation, pitch deck, and demo recording |
| 15 Nov | Final regression smoke check, public-repository preparation, submission before the published deadline |

This is an ambitious target for a developer already familiar with the stack. Measure M0/M1 quickly; if capacity is lower, reduce decorative UI, adapter breadth, scheduling, and report formats while preserving the chosen challenge's mandatory behavior. Do not present missing functionality as complete.

The full illustrative test matrix is 120 attempts. Start with smoke trials to debug the system before spending the complete time/credit budget. Three live searches per attempt would be 360 basic search credits; actual upper bounds, retries, additional testing, and available quota govern admission.

## 3. Developer beta priorities

Recommended order after the prototype:

1. Integration quality: public adapter contracts, compatibility matrix, doctor command, two documented integration paths, and honest unsupported-capability reporting.
2. Persistence quality: migrations, job leases, interruption accounting, cancellation reconciliation, retention, backups, and recovery tests.
3. Evaluation quality: representative referenced task packs, semantic-grader calibration, versioned manifests, meaningful failure cases, and uncertainty.
4. Developer workflow: CLI, Python SDK, JSON/CSV/JUnit export, baseline comparison, and headless regression policies.
5. Usability: polished trace navigation, accessible comparison views, responsive layouts, documentation, and actionable setup/errors.

Plan beta milestones by acceptance rather than a fixed promised launch date. A working local comparison is preferable to broad unsupported framework claims.

## 4. Pilot validation

Recruit a small willing group only after a concrete usable build exists and outreach is authorized. Ask participants to bring their own recurring research/RAG tasks and one real failure to reproduce.

Proposed targets to validate, not achieved metrics:

- first valid comparison within 30 minutes after prerequisites/model download;
- at least three independent developers successfully integrate an existing agent;
- pilots rerun after a change and identify whether a measured outcome improved;
- at least three useful reproduced failures with an evidence-backed diagnosis;
- honest known limits and predictable data retention/export behavior.

Record which features users actually repeat. Expand integration breadth and task packs based on observed demand.

## 5. Team and hosted prerequisites

Before team hosting: project-level permissions, authenticated workers, isolated execution, explicit network policies, per-project quotas, PostgreSQL migration, backup/restore, retention/deletion, audit events, and tested worker recovery.

Managed operation additionally needs an operating-cost model, billing controls if introduced, service observability, abuse/resource protection, privacy terms, support, and capacity planning. No hosting provider, paid integration, billing account, or external publication is selected/enabled by this plan.

## 6. Future task packs

| Pack | Problems addressed | New work required |
| --- | --- | --- |
| RAG/document | Unsupported claims, stale evidence, inconsistent retrieval | Source/reference maintenance, permission-aware corpora, citation/support graders |
| Customer support | Incorrect policies, false promises, inappropriate actions | Simulated customer/policy systems, action authorization, task references |
| Coding | Functional regressions, wasted requests, unsafe operations | Isolated repositories, functional tests, tool/action policy, OS isolation |
| Business workflow | Duplicate writes, partial completion, bad recovery | Simulated services, idempotency assertions, action/outcome accounting |

Reuse the core experiment, event, scenario, and evaluation contracts. Each action-capable pack gets a new trust-boundary review. Production transactions are not replayed as test actions.

## 7. Future improvement engine

After stable task packs and baseline comparison, test developer-approved changes to retries, prompts, model selection, retrieval, or memory. Report quality, cost, and runtime trade-offs with comparable evidence.

A suggested explanation must be trace-backed, and a claimed improvement must be verified by experiments. Do not automatically rewrite or deploy a production agent.

### Focused recovery direction

The current UI now provides a twelve-attempt entry example, a condition-by-agent success table, a guide to the supported workflow, and a focused retest action. It does not infer a root cause or repair the agent automatically.

Three next ideas to validate with developers:

- **Saved failure library:** collect a useful failed task/fault pair, deduplicate examples, and organize a recurring regression suite. Retest currently prepares a form; a saved reusable suite is additional work.
- **Recovery trade-off policies:** compare retry strategies against success, latency and usage budgets. The existing gate checks task-success regression; richer thresholds need explicit configuration and evidence.
- **Claim coverage:** show which individual answer claims are verified, unsupported, contradictory or unassessed, including a calibrated live-research path. The current structured reference grader does not verify arbitrary summary claims.

Prioritize a repeatable user problem over adding more dashboard metrics. Live Tavily acceptance and independent developer feedback come before expanding the supported surface.

## 8. Release checklist

For each release, document supported adapters, actual model/tool integration results, suite/scenario/rubric versions, metric provenance, dependency/license checks, security boundaries, restart/cancellation limitations, accessibility/browser results, and setup/deployment commands.

Only run commands and checks supported by the implemented project. Do not claim a build, SDK, benchmark accuracy, customer adoption, or production readiness from planning artifacts.
