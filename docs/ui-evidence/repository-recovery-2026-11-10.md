# RILO | Repository recovery case study

An anonymized summary of recorded execution data. This is a selected view, not a complete raw report or a newly executed evaluation.

Reviewed 10 November 2026. Original run timestamp: 2026-11-09T18:39:36.482125+00:00

## What happened

Rilo captured 40 files from a real GitHub repository at a fixed commit. Repo Analyst and Relay received the same selected README passage and executed sequentially with independent histories. Both completed; all six final citations matched the captured passages.

Repo Analyst initially returned three findings without citations. Its recorded citation_warning event was followed by one bounded recovery and a second model response with citations. Relay completed in one model call. The extra call increased Repo Analyst's duration and token usage.

## Recorded conditions

Model: ollama/qwen2.5-coder:7b through Bifrost. Per-agent limits: {"max_model_calls": 2, "max_tool_calls": 2, "timeout_seconds": 180}. Rubric: workspace-evidence-v1. No explicit success checks or ground-truth labels were supplied.

## Relay | completed

Duration: 38.44 seconds (38439.05 ms). Model calls: 1. Agent tool calls: 0. Input tokens: 932; output tokens: 482 (reported).

Findings: 3. Citation validity: 1.0; evidence coverage: 1.0. These are recorded reference metrics, not accuracy scores. All findings remain PARTIALLY VERIFIED because interpretation requires review.

Event order: run_start -> step -> model_request -> model_response -> synthesis -> task_checks -> assessment -> run_end

Finding 1: PARTIALLY VERIFIED; README.md lines 3-5, valid=True. Method: snapshot_reference_and_exact_passage. Source passages and finding text are withheld.

Finding 2: PARTIALLY VERIFIED; README.md lines 9-9, valid=True. Method: snapshot_reference_and_exact_passage. Source passages and finding text are withheld.

Finding 3: PARTIALLY VERIFIED; README.md lines 9-9, valid=True. Method: snapshot_reference_and_exact_passage. Source passages and finding text are withheld.

## Repo Analyst | completed

Duration: 65.35 seconds (65348.24 ms). Model calls: 2. Agent tool calls: 0. Input tokens: 1963; output tokens: 900 (reported).

Findings: 3. Citation validity: 1.0; evidence coverage: 1.0. These are recorded reference metrics, not accuracy scores. All findings remain PARTIALLY VERIFIED because interpretation requires review.

Event order: run_start -> step -> model_request -> model_response -> citation_warning -> recovery -> model_request -> model_response -> synthesis -> task_checks -> assessment -> run_end

Finding 1: PARTIALLY VERIFIED; README.md lines 3-5, valid=True. Method: snapshot_reference_and_exact_passage. Source passages and finding text are withheld.

Finding 2: PARTIALLY VERIFIED; README.md lines 9-9, valid=True. Method: snapshot_reference_and_exact_passage. Source passages and finding text are withheld.

Finding 3: PARTIALLY VERIFIED; README.md lines 13-13, valid=True. Method: snapshot_reference_and_exact_passage. Source passages and finding text are withheld.

## Isolated test result

The configured Docker unittest profile executed with network disabled, discovered zero tests and returned exit code 5. Rilo retained this as failed. Source capture and model completion are separate outcomes; neither changes this test result.

## Comparison

Both completed; no explicit success checks were defined. Compare reference checks, recovery and usage without assigning factual accuracy.

## Publication and verification boundaries

This is an anonymized summary derived from a real recorded evaluation, not a full raw report or a new run.

Original reports, original answers, captured sources and their license remain private.

Source text is withheld, so readers cannot independently repeat these reference checks from this summary.

Citation validity measures reference integrity, not the factual accuracy of every interpretation.

No ground-truth labels or explicit success checks were supplied; accuracy and a quality winner are undefined.

The overview used one selected README passage from a bounded capture; it was not a complete repository audit.

Agent tool-call counts exclude shared source capture. Local API fee estimates exclude hardware and energy.

The isolated unittest profile discovered zero tests and failed; this was not a passing repository test suite.

## Reproduce the workflow

Use Rilo's Repository workspace with your own accessible repository and select Repo Analyst and Relay. Inspect file references, trace events and the exported full report. A model may already supply citations or produce a different response; a repair event is not guaranteed.

For public raw source evidence and a repeatable controlled comparison, use the research benchmark linked from the Rilo README. This anonymized case does not provide the original source snapshot.

[Recorded metrics JSON](repository-recovery-2026-11-10.json) | [CSV](repository-recovery-2026-11-10.csv) | [PDF](repository-recovery-2026-11-10.pdf) | [Public research benchmark](../BENCHMARK.md)
