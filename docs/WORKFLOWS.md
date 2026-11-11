# Rilo workflows

Updated 9 November 2026. Core local flows are implemented: create, execute, inspect, rerun, baseline, compare, cancel and export. The diagrams retain future team/replay improvements where indicated. API clients can use SSE; the current dashboard polls persisted state. Trace inspection displays recorded events, and fixture synthesis is separately labeled as an executable demonstration.

## 1. Developer journey

```mermaid
flowchart TD
    A[Start local Rilo] --> B[Check Bifrost, local model, and Tavily]
    B --> C[Connect agents and inspect capabilities]
    C --> D[Choose versioned tasks and expected behavior]
    D --> E[Select live or controlled evidence]
    E --> F[Choose scenarios, repetitions, and limits]
    F --> G[Preflight compatibility and quota checks]
    G -->|Ready| H[Run experiment and watch progress]
    G -->|Missing requirement| I[Show actionable setup issue]
    I --> C
    H --> J[Compare outcomes and evidence]
    J --> K[Inspect a failed or uncertain run]
    K --> L[Change agent configuration or code]
    L --> M[Rerun the same task and scenario versions]
    M --> N[Compare candidate with baseline]
    N --> O[Save baseline and export report]
    O --> P[Automate future regression checks]
```

The developer chooses the agent changes. Rilo runs and evaluates the configured experiments.

## 2. Execution pipeline

```mermaid
flowchart TD
    A[Dashboard, SDK, or CLI request] --> B[API validates immutable experiment specification]
    B --> C[Reserve limits and persist queued job]
    C --> D[Worker claims job with lease]
    D --> E[Create fresh per-run state and apply scenario]
    E --> F[Invoke existing agent through adapter]
    F --> G[Model boundary and tool boundary]
    G --> H[Bifrost routes model requests]
    G --> I[Tavily live search or controlled evidence search]
    H --> J[Responses and observed usage]
    I --> J
    J --> F
    F -->|Completion, limit, error, or cancellation| K[Persist final run outcome]
    G --> T[Append ordered trace events]
    T --> U[Stream progress to dashboard]
    K --> L[Run versioned graders]
    L --> M[Store assessments and supporting evidence]
    M --> N[Aggregate results with coverage and uncertainty]
    N --> O[Comparison, trace inspection, and report]
```

The model/tool boundary is where supported fault injection and measurement occur. Bifrost model logs alone do not establish every agent step or tool call. Adapters report observation coverage.

## 3. Experiment and attempt states

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Queued: validated and admitted
    Draft --> Rejected: invalid configuration or limits
    Queued --> Running: worker claims lease
    Queued --> Cancelled: cancelled before start
    Running --> Completed: all scheduled attempts accounted for
    Running --> Partial: interrupted with completed evidence
    Running --> Failed: infrastructure prevents usable execution
    Running --> Cancelled: cancellation acknowledged
    Completed --> [*]
    Partial --> [*]
    Failed --> [*]
    Cancelled --> [*]
    Rejected --> [*]
```

Completed means execution accounting is complete; it does not mean the agents passed. Individual attempts separately record completed, timed_out, limit_reached, cancelled, infrastructure_error, or adapter_error. Assessment results separately record pass, fail, or inconclusive.

Worker restart marks an expired in-progress attempt interrupted. Retrying creates a new attempt with a new identifier and fresh state. Replay does not silently resume a partially completed external action.

## 4. Research example

1. The developer selects two agent versions and a company-briefing task with a pinned meeting/reference time.
2. Rilo verifies the agents can use the model and research tool boundaries required by the selected scenarios.
3. In controlled mode, both agents can search the same fixed permitted corpus. They may choose different queries and actions.
4. A normal trial records baseline behavior.
5. A fault trial fails the first eligible search call. The trigger is recorded; a trial in which the trigger never occurs is marked not activated.
6. Rilo observes whether the agent retries within limits, uses another permitted source, reports uncertainty, or fails.
7. Graders check the versioned output contract and expected facts/citations. Unresolved semantic judgments remain inconclusive.
8. Comparison shows outcomes, attempts, coverage, observed requests/tokens, runtime, and grader evidence.
9. The developer changes recovery behavior and repeats the same conditions.

## 5. Replay distinction

```mermaid
flowchart LR
    A[Choose mode] --> B[Live testing]
    A --> C[Controlled evidence testing]
    A --> D[Trace playback]
    B --> E[New model calls and current Tavily results]
    C --> F[New model calls and fixed searchable evidence]
    D --> G[Existing recorded event sequence]
    E --> H[New benchmark attempt]
    F --> H
    G --> I[Inspection only]
```

A source snapshot controls evidence availability, not the model's randomness. A trace viewer reproduces the record of what happened, not a new successful run.

## 6. Developer-beta release check

```mermaid
flowchart TD
    A[Developer changes agent] --> B[CI invokes Rilo CLI or API]
    B --> C[Resolve pinned suite, scenario, and baseline]
    C --> D[Check comparability and execution limits]
    D --> E[Run candidate trials]
    E --> F[Assess results and uncertainty]
    F --> G{Configured gate result}
    G -->|Pass| H[Return passing check with report]
    G -->|Fail| I[Return failing check with evidence]
    G -->|Inconclusive| J[Return incomplete check and reason]
```

CI publication is a later integration. No repository, pull request, deployment, external message, or release is changed by preparing this plan. The default beta behavior is returning a result and report; deployment decisions remain in the developer's existing workflow.

## 7. Error and recovery behavior

| Condition | Intended behavior |
| --- | --- |
| Model or Tavily unavailable during preflight | Do not admit a live experiment; explain which dependency failed |
| Dependency failure deliberately injected during a run | Record trigger and observe the agent's recovery |
| Unexpected outage in the runner or gateway | Record infrastructure error; preserve partial trace; do not pretend the agent was evaluated |
| Output fails schema validation | Record invalid output with bounded text and validation evidence |
| Token/tool/time limit reached | Stop admission of further work; record limit and charged/unknown usage |
| User cancels | Stop scheduling, signal active adapter, preserve evidence, acknowledge actual cancellation state |
| Instrumentation unavailable | Display unknown metrics and unsupported scenarios; block strict comparison where necessary |
| Missing corpus/fixture coverage | Report evaluation infrastructure gap, not an agent failure |
| Semantic evidence insufficient | Inconclusive assessment with explanation |
