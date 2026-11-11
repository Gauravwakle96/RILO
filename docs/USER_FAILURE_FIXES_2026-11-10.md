# Recorded user failures: diagnosis, fixes and verification

Rilo at `http://127.0.0.1:8018`, Windows, 10 November 2026.
Existing credentials, model configuration, data and original evaluations are preserved.

## Source-free capability chat

Original evaluation: `exp_7716a10d16ca4be0`, “what are ur specialities”.
The model had no Rilo profile identity and returned generic capability findings;
the evidence grader marked those source-free observations unsupported.

Generation now includes actual profile behavior, conversation-memory limits and
search state. With no supplied evidence it explicitly requests an ordinary answer
and an empty findings list. Source-free chat is not evidence-graded. Any additional
model observations remain in persisted output and response notes, without being
presented as verified facts. Historical notes remain inspectable.

Live retest `exp_45a8e0837f4b498f`: Scout and Relay both completed, named themselves
correctly and returned empty findings. No objective accuracy score was invented.

## Literal checks and title-only websites

Original evaluation: `exp_d8e812dccc5e46e5`. Both answers failed the declared
case-insensitive substring `global ai hakathon`. This is a literal requirement;
even “Global AI Hackathon” does not match its spelling and word order.

The check and original outcomes remain unchanged. Workspace summaries say
“All checks passed” / “Checks not met”, scoped to declared checks. When both
agents fail their requirements the comparison says “Neither met the checks”.
Old persisted tie artifacts are not rewritten; their UI explains the actual
failed outcomes. Checks are not measures of overall factual accuracy.

A fresh HTTP capture of `https://hack4hack.com/hackathons` yielded only page
metadata and scripts. The static parser now excludes head/title text from page
body evidence and refuses empty captures before inference. Its message explains
JavaScript/access limitations and offers readable URLs, pasted source text or
optional configured Tavily search. JavaScript rendering was not implemented or
claimed to work. Tavily remains optional and was not live-validated without a key.

## KYRO capture, overview context and retries

Original failed evaluation: `exp_9a20f248d37c4662`. The public GitHub path downloaded
the complete ZIP under an 8 MB/25-second response bound. Shared ingestion failed
before either model ran. Individual response retry required an absent snapshot.

Public GitHub capture now uses metadata, commit SHA and tree APIs followed by up
to 40 commit-pinned text-file downloads with four concurrent requests. Binary,
oversized, dependency-directory and symbolic-link entries are excluded. Private
tokens remain confined to the fixed API host. Archive fallback and its bounds
remain available if anonymous metadata retrieval is unavailable. Existing DNS,
redirect, URL, upload and sandbox boundaries remain in place.

Size and elapsed-download failures have separate explanations. A failed input
can be retried as a new paired evaluation, preserving inputs and historical
records. Its UI says “Source capture failed” and “Agent not started”, and offers
“Retry source capture” instead of unusable individual response retries. The
Experiments rerun action also uses the workspace retest endpoint.

Live capture fetched 40 KYRO files at commit
`a03f97ded1f5da474cf16eefe08afec1b5133e07`, snapshot `snap_c0d31363059c486d`.
An initial successful capture exposed poor overview context selection. Overview
questions now prioritize README introductions, and long 20-line blocks split
at actual line boundaries instead of being discarded wholesale. Repository
profiles follow the requested scope rather than suggesting security issues in
every overview. Selected passages remain bounded and shared between agents.

Final live evaluation: `exp_a26e263257194f93`, conversation
`conv_5119660d222f48e5`. Both Repo Analyst and Relay completed with real descriptions
of KYRO. All emitted citations matched the captured README. Repo Analyst's first
response omitted citations; a single bounded repair attempt added them. The
original response, warning and recovery remain in its trace. Unsupported claims
still remain unsupported if the bounded repair does not supply evidence. Scout
keeps its one-attempt baseline behavior.

The configured Docker unittest runner executed on the captured subset, discovered
zero tests and returned exit code 5. This is recorded as failed, not a successful
repository test suite. Source capture and model execution are separate outcomes.
The final overview uses one README passage due to the existing input budget;
this is not an exhaustive code audit. Valid citations do not prove conclusions.

PDF, Markdown, JSON and CSV were exported from that persisted evaluation to
`docs/ui-evidence/kyro-recovery-2026-11-10.*`. PDF text extraction confirmed its
evaluation ID, commit, agent identities and README references across eight pages.

## Verification

- Final Python suite: 198 passed, 84.04% coverage, 171.02 seconds.
- Seven new focused regressions cover source-free chat, immutable input retry,
  literal typo failure, title-only pages, bounded public repository capture,
  README line selection and bounded citation repair.
- Two opt-in browser checks passed against the user's actual historical records.
- Ruff and mypy (35 modules) passed; frontend lint, TypeScript and production
  build passed; Python source and wheel builds passed.
- Frontend full dependency audit, Promptfoo runtime audit and locked Python
  pip-audit reported no known vulnerabilities. Source-pattern review found no
  potential credential matches in 54 application/test source files.
- The running production UI displayed both completed KYRO responses with no
  horizontal overflow. ECC browser screenshot export was unavailable in its
  configured workspace; no screenshot verification is claimed for that attempt.

One initial Promptfoo test timed out while model inference and build checks were
running concurrently; focused and final full tests passed subsequently. A browser
check initially selected the prior greeting in a multi-turn conversation; it now
checks the actual capability turn. These failures were investigated, not removed.

Full standard browser suite result is recorded in RILO_2_VERIFICATION.md.
