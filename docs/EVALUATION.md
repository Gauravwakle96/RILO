# Rilo evaluation design

Updated 9 November 2026. The local reference grader, failure scenarios, metric accounting and exploratory comparison gate are implemented. [BENCHMARK.md](BENCHMARK.md) records actual fixture and Bifrost model results. Semantic-grader calibration, confidence analysis and independent user references remain future work. The grader checks quoted fact passages and explicitly declared conflict/uncertainty behavior; arbitrary factual statements in free-text summaries remain unassessed.

## 1. What a result means

Rilo assesses an agent version on a versioned task pack under recorded conditions. An experiment does not establish a universal agent ranking or guarantee future behavior.

Execution, task quality, instrumentation coverage, and resource usage are separate dimensions. A completed experiment can contain failed agents. An unavailable evaluator can make a quality result inconclusive without erasing its execution trace.

No hackathon score, model confidence, or pass probability is invented from an appealing interface.

## 2. Initial task pack

| Task | Expected behavior | Primary evidence/check |
| --- | --- | --- |
| Recent company briefing | Identify relevant facts in the 30 days before a fixed meeting/reference time | Expected fact set, dates, source passages, structured briefing |
| Entity disambiguation | Select the correct similarly named organization | Entity identifiers and matching source evidence |
| Conflicting sources | Explain an unresolved conflict or use justified authoritative evidence | Explicit conflict/reference rubric and cited passages |
| Insufficient evidence | State uncertainty and avoid unsupported claims | Deliberately incomplete corpus, output contract, factual assertions |
| Bounded multi-step research | Complete required research or explain limitations while respecting limits | Completion evidence, tool sequence, request counts, final output |

Publish task definitions and synthetic/openly licensed fixtures. Privately stored real source snapshots require source and Tavily terms review. Each task contains a fixed reference time, corpus version, grading rubric, and expected behavior.

Reference answers and grading policies are not exposed as agent instructions. The agent receives legitimate task inputs and permitted evidence, while graders receive the reference material separately.

## 3. Failure scenarios

| Scenario | Controlled trigger | Evidence of exposure and recovery |
| --- | --- | --- |
| Search timeout | Fail the first eligible search invocation | Injected event, bounded retry/fallback, final supported output or appropriate limitation |
| Model unavailable | Reject one eligible model dispatch with a documented test response | Injected event, actual subsequent model behavior, limits, final result |
| Misleading retrieved instruction | Include synthetic adversarial instructions in an eligible retrieved document | Delivery event, observed tool/actions/output, legitimate task compliance |

Normal operation is a separate condition. Effects are bounded and never create real external provider outages. Later scenarios may include malformed tool output, quota exhaustion, delayed responses, stale documents, and partial artifacts.

Record whether the scenario activated. An unactivated scenario is not counted as a successful recovery test. A safety policy preventing a prohibited tool action is distinguished from the agent itself declining it.

## 4. Fair comparison protocol

1. Pin task, evidence, scenario, evaluator, agent configuration, and adapter versions.
2. Begin with the same primary model, tools, per-run limits, and evidence availability for the agents being compared.
3. Record actual fallback models and cache behavior; intentional differences are experiment variables.
4. Create fresh agent state for each attempt. Define warm-up and provider-cache policy explicitly.
5. Randomize or balance run order. Use concurrency one on the initial local machine to limit resource contention.
6. Run at least three trials per agent/task/condition for exploratory comparisons.
7. Check instrumentation coverage and fault activation before making a strict comparison.
8. Retain every scheduled/attempted outcome, including errors, cancellations, and limits.
9. Compare task-quality changes separately from runtime/resource changes.

Five tasks with three repetitions are an initial demonstration suite, not broad statistical coverage. More trials and representative tasks are needed before consequential release decisions.

Live mode measures current behavior but changing search evidence can confound comparisons. Controlled mode uses the same searchable evidence corpus and supports different agent queries. Exact tool fixtures with uncovered calls produce fixture-gap outcomes.

## 5. Grader design

### Deterministic checks

Validate structured output, required fields, entity identity, permitted dates, expected normalized facts, valid source references, quoted evidence, tool/action limits, and forbidden actions where the task makes them objectively testable.

A reachable URL or a matching keyword alone does not prove a factual claim is supported. References must connect claims to permitted evidence. Design canonical expected facts and acceptable representations for the initial task pack.

### Semantic checks

Use semantic evaluation when a deterministic reference cannot resolve meaning. Provide source passages and a versioned rubric. Validate grader outputs and require explanations tied to evidence. Keep evaluator model/prompt versions fixed and blind agent identity where possible.

Calibrate against manually reviewed examples, examine disagreements, and label uncalibrated grades experimental. Do not make an unvalidated model judge the sole basis for a release gate. Review uncertain cases or leave them inconclusive.

### Overall task assessment

Pass requires the task's declared hard conditions and adequately supported quality conditions. Fail records an evidenced violation. Missing coverage, ambiguous reference evidence, or failed grading yields inconclusive.

Task-pack authors define applicability and policy. Rilo records the rubric rather than silently changing success definitions between runs.

## 6. Metrics and provenance

| Measure | Definition/handling |
| --- | --- |
| Task success | Passed assessments / valid assessable attempts, with numerator and denominator |
| Execution coverage | Assessable attempts, total scheduled/started attempts, and each infrastructure/unknown category |
| Failure recovery | Task outcomes among attempts actually exposed to the scenario; exposure and activation counts shown |
| Consistency | Distribution across repeated trials and tasks; small samples labeled |
| Observable steps | Recorded events according to the adapter's declared instrumentation; unavailable is unknown |
| Model/tool calls | Attempts and retries observed at supported boundaries; missing observation cannot be zero |
| Tokens | Provider/local-server reported counts, tokenizer estimates, or unknown; provenance visible |
| Runtime | Per-attempt execution includes observed workflow/writes; experiment timestamps provide elapsed time; separate queue/grader timing remains future work |
| API fees | Observed usage plus versioned price basis where supported; estimates labeled |
| Tavily usage | Actual credits/requests where reported, with shared quota accounting and reservations |
| Local compute | Runtime and hardware profile; zero inference API fee does not imply free compute |
| Cost per successful task | Defined only with adequate cost and success evidence; undefined when no task passes |
| Regression | Compatible per-agent success differences with repetition count and inconclusive coverage; statistical paired analysis remains future work |

Agent inference and evaluator inference usage are separated. Token or monetary accounting excludes injected calls that never reached a provider, while preserving those events as attempts. In-flight usage not yet reconciled remains provisional/unknown.

Use confidence intervals or paired/bootstrap analysis only when their assumptions and grouping are documented. Show raw distributions and task-level outcomes first. Repeated trials on a few tasks do not represent independent evidence across every possible workload.

## 7. Diagnosis and improvements

Initial diagnoses use observed patterns: repeated identical calls, retry limit exhaustion, invalid tool output handling, missing source support, and incorrect recovery transitions. Every finding links to the relevant trace events.

Optional model-generated explanations are labeled interpretations. A trace correlation is not proof of causation. To verify an improvement, change one declared factor and rerun comparable conditions with enough repetitions.

Rilo proposes experiments; developers decide which agent changes to make. Automatic production modification is outside the product scope.

## 8. Regression gates

A policy specifies minimum valid attempts/coverage, critical violations, task-specific quality thresholds, and tolerated resource changes. Thresholds are product-owner choices, not universal defaults.

Return:

- pass: adequate evidence meets the configured policy;
- fail: adequate evidence establishes a policy violation;
- inconclusive: missing/incompatible/insufficient evidence prevents the decision.

An inconclusive result must not silently pass a release check. The consuming CI workflow decides its documented handling, with a conservative default for critical gates.

## 9. Validation before claims

Validate the platform using agents with known behaviors: compliant completion, bounded recovery, retry loop, unsupported citation, malformed output, limit violation, and missing instrumentation. Expected outcomes must be independently defined.

Required checks include scenario activation, exact event/usage accounting, fresh state, source/corpus coverage, fair manifest comparison, grader calibration, infrastructure-error separation, restart interruption, and redacted exports.

Run real Bifrost/local-model and Tavily integrations in addition to contract tests. Report what was executed, what failed, and what remains unverified. Public reports contain the manifest, versions, counts, evaluation evidence, and limitations.

## 10. Hackathon mapping

| Mandatory platform requirement | Planned proof |
| --- | --- |
| Framework independence | Existing plain Python and LangGraph agents connected through documented adapters |
| Identical tasks and measured outcomes | Pinned suite/manifests and metric tables with provenance |
| Repeated runs | At least three trials per task/agent/condition in the demonstration |
| Controlled failures | Three recorded scenarios with exposure and recovery evidence |
| Comparison and detailed inspection | Dashboard, event timeline, assessment evidence, and export |

Bifrost and Tavily contribute through real model routing and research collection. A scenario fixture or contract mock is identified explicitly; it is not presented as a live integration run.
