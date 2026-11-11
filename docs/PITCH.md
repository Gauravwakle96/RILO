# Rilo pitch outline

Use six slides. Add only measured benchmark numbers from [BENCHMARK.md](BENCHMARK.md) and actual screenshots from `docs/ui-evidence`.

## 1. A good demo is not a reliability test

“Two agents can use the same model and behave very differently under failure. Developers need to compare the whole workflow and see why a result changed.”

Visual: one research task flowing through two agents, with different retry paths.

## 2. Repeat the work and expose the failure

Rilo pins tasks, source evidence, model, limits, grader and implementation. It runs fresh repeated attempts under normal conditions and three controlled failures.

Visual: two agents × five tasks × four conditions × three repetitions = 120 attempts.

## 3. Follow each result back to its evidence

Show success/coverage, steps, model/tool calls, reported tokens, fee provenance and time. Open a real run’s fault, retry, model response, output and source-backed check.

For the paired workspace, show the declared-check matrix and a real source citation.
Point out that an uncited observation stays unsupported and a valid quote does not
prove every interpretation. The KYRO report includes an actual citation-repair trace.

Visual: actual metrics table alongside a recorded recovery trace.

## 4. Findings change the next experiment

Compare Scout and Relay’s measured recovery. Show the remaining insufficient-evidence failure. Explain the grader false negative found in review and corrected with a versioned rerun, preserving prior evidence.

Visual: actual before/after grader example with an accepted longer supported quote; distinguish a grader correction from an agent improvement.

## 5. Built for developers beyond the hackathon

Connect a local HTTP entry point, register revisions, save baselines, export evidence and use CLI exit codes in automation. Unknown internal metrics remain explicit. The stack runs locally with existing hardware.

Show one paired task saved as a regression suite. The same pipeline accepts chat,
GitHub/ZIP repositories, documents, readable websites and supplied research sources.

Visual: SDK/CLI commands and declared candidate-change comparison.

## 6. Current evidence and next validation

Actual Bifrost/Ollama inference, automated Python/browser checks and measured matrices are complete. Tavily’s live request implementation is present; actual acceptance requires the missing private key. Next product validation is an independent developer bringing a real recurring research task, followed by calibrated live grading.

Close: “Rilo makes a reliability claim inspectable and gives the developer the next repeatable experiment.”
