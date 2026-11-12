# Rilo design contract

## Local workspace refinement — 12 November 2026

Blue identifies primary execution actions, violet saved tests/history, and teal
connection/source controls. Status still includes text and icons; color alone does
not communicate success. Both themes use contrast-checked semantic tokens.
Secondary controls retain stable backgrounds during theme changes to avoid
transient low contrast. Per-side configuration lives in a collapsible advanced
section. Source inspection loads on demand and distinguishes captured material from
the bounded selection passed to agents. History search, privacy settings and empty
states use the existing responsive panels; motion respects reduced-motion settings.

The product surface is a developer's local reliability workspace. The user's job is to configure repeatable tests, compare agent behavior, inspect a failure, and rerun after a change. The primary action is **New experiment**.

The selected awesome-design-md Linear analysis informs restrained surface steps, hairline dividers, compact type hierarchy, and product-first presentation. It is third-party design analysis, not an official specification. Rilo uses its own graphite/blue palette, semantic statuses, and local licensed Inter/JetBrains Mono fonts. The implementation starts with the application, not marketing content.

## Checkable constraints

- First viewport: persistent navigation, experiment title, primary action, actual summary values, and experiment list or actionable empty state.
- Every number derives from the API. Synthetic-engine runs are explicitly identified as demonstrations; unavailable usage is unknown/not applicable.
- Results show attempts, passes, failures, inconclusive assessments, and infrastructure problems separately.
- Inspectable output, graders, trace events, and configuration are linked to an actual run.
- Modal forms use native dialogs and labeled controls, escape dismissal, focus containment, and validation.
- Keyboard focus is visible; statuses use text in addition to color; responsive layouts support long labels and trace content.
- Motion is limited to state changes and removed for reduced-motion users.
- Mobile navigation collapses into a labeled drawer. Wide tables scroll within their region rather than overflowing the viewport.
- Theme choice can persist in localStorage; session and CSRF credentials cannot.

## Tokens

Dark canvas #111318, sidebar #14161c, surface #191c23, raised surface #20242d; main text #f0f2f7, secondary text #aeb5c4. Blue action #4772ec; semantic green, amber, and red use contrasting foregrounds. Light theme uses warm white/slate surfaces with darker semantic foregrounds. Contrast is verified during rendered QA.

Type uses Inter for interface text and JetBrains Mono for identifiers/trace data. Sizes 12/13/14/16/20/28 px. Spacing follows a 4 px base. Radius 6/8/10 px with sparing pills for compact badges.

## Target viewports

390x844, 768x1024, 1440x900. Verify each viewport using rendered captures and keyboard/reduced-motion checks. Evidence artifacts live under docs/ui-evidence. A successful source/build inspection alone does not satisfy this gate.

## Content states

| State | Trigger | Feedback and next action |
| --- | --- | --- |
| Loading | Catalog, detail, or submission pending | Stable skeleton/explicit progress; running experiments expose cancellation |
| Empty | No experiments or filtered matches | Start an experiment or clear the filter |
| Error | API, validation, or integration failure | Specific error and retry/settings recovery |
| Partial | Some catalog requests fail or experiment is interrupted | Preserve available data and explain missing results |
| Success | Real experiment completion or saved record | Show results, inspect traces, save baseline, export, or rerun |
| Permission | Local session or origin denied | Explain session rejection and allow reconnect on the approved local origin |

All applicable states require actual browser verification before being marked passed in the ECC evidence record.

## Recovery workflow refinement — 9 November 2026

The workspace keeps its graphite/blue identity and local fonts. The experiment landing view explains the failure-recovery job with a reviewable twelve-attempt fixture example and an API-derived comparison from the latest eligible completed real-model experiment. Recorded results are never hardcoded or described as universal reliability.

A **Start here** guide remains in the lower-left sidebar and mobile navigation. It explains the four-step test/inspect/retest/compare workflow, distinct demonstration/model/live prerequisites, available functions and grading/metric limits. It is a route, not a forced tour or blocking dialog. Its section links keep the application route intact and move keyboard focus to the requested section.

Experiment details expose a table of condition-by-agent outcomes with inspect actions. The run inspector's **Retest this case** prepares a focused experiment for user review, preserving model and budgets while selecting the recorded task, fault and at least three repetitions. The user performs the actual agent change. Existing execution, grading and provider configuration remain authoritative.

Headings carry their own hierarchy. New help uses concise prose, rows and a meaningful ordered workflow. Selection, caret, scrollbar and numeric styles use the existing palette; motion is limited to interaction feedback and respects reduced motion.
