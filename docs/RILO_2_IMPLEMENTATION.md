# RILO 2.0 implementation journal

The user's 30-section blueprint is the acceptance specification. Build in the
requested phase order; preserve existing behavior and record concrete limitations.

## Architecture decisions

- Keep React/Vite/TypeScript, FastAPI, SQLite WAL, Bifrost/Ollama and the single worker.
- Reuse experiments/runs/events for all task execution. Add modular workspace
  contracts, ingestion, evidence, verification and reports around that pipeline.
- Default Tavily off. Selecting Tavily requires a configured key and bounded credit
  allowance; no silent fallback or live-validation claim without actual retrieval.
- Pin a shared source snapshot before either agent runs. Execute sequentially on
  this laptop; isolate histories and run the evaluator after generation.
- Keep single-user local deployment explicit. External providers optional.
- Unknown accuracy without ground truth stays unknown; semantic judgments advisory.

## Phases and delivered behavior

Updated through 10 November 2026. Existing provider, model, historical records and benchmark
features are preserved. Migration 3 adds workspaces, sources and artifacts;
migration 4 adds immutable response retry relationships. A private SQLite backup
was taken before migration.

| Phase | Implemented | Practical limits |
| --- | --- | --- |
| 0 Audit | Whole-project inventory, fresh 127 Python/13 browser baseline | Earlier verification kept separate |
| 1 Foundation | Typed task contracts, shared model boundary, migrations, private snapshots, provenance | Existing single-server SQLite deployment |
| 2 Chat | Persistent paired turns, isolated histories, context, cancellation, bounded response retries, traces, exports | Conservative local context budget; no cross-agent critique mode |
| 3 Repository | Public GitHub commit-pinned file capture with archive fallback, authorized private API path, ZIP, Python AST/static checks, optional OSV/Docker | Bounded sources; no exhaustive vulnerability proof or dependency installation |
| 4 Evidence | Quotes, line/page checks, consistent code-indentation matching, independent advisory review, potential disagreements | Semantic correctness remains uncertain |
| 5 Search | Optional Tavily basic search, shared retrieval, source validation/deduplication, preserved Scout/Relay research | Live Tavily unvalidated without credentials |
| 6 Documents | Text PDFs with actual pages, DOCX/TXT/Markdown with lines, resource-limited parser | No OCR or reliable rendered DOCX pages |
| 7 Website | Robots-aware bounded capture, public IP/DNS/redirect checks, no scripts | No authenticated/script-rendered sites |
| 8 Benchmarks | Immutable suite versions, repeated trials, pinned conditions, optional exact-quote labels | Quote metrics are not vulnerability accuracy |
| 9 Regression | Retest, compatibility checks, findings/latency/tokens, labeled quote-F1 deltas, Wilson intervals | No unsupported winner; implementation changes flagged |
| 10 Reports | Persisted JSON/CSV/Markdown/PDF; invariant PDF generation | Standard PDF font has limited non-Latin coverage |
| 11 Reliability | Security boundaries, UI, tests, audits, package/build, local documentation | Public/team hosting and independent security assessment remain future work |

## Validation

- Fresh pre-expansion baseline: 127 Python tests; 13 browser tests in 2.8 minutes.
- Expanded Python suite: 173 passed, 83.35% coverage; minimum remains 80%.
- Final standard browser suite: 16 passed in 3.4 minutes; five opt-in live tests
  skipped in the normal run and executed separately.
- Live model checks cover chat, advisory review, shared follow-up, GitHub, text PDF,
  website, source-only research and an isolated Docker unittest.
- Five explicit live browser scenarios passed across focused runs, including the
  corrected regression refresh and recorded failed-response retry.
- A real Scout malformed-output failure during ZIP analysis remains recorded.
  Relay completed the same task; retrying creates an explicit additional attempt.
- Final results and exact records: [RILO_2_VERIFICATION.md](RILO_2_VERIFICATION.md).

## Operational decisions

Sequential execution fits the current laptop. Identical source selection occurs
before generation. A conservative 6,000-byte serialized input cap rejects excessive
history without silently discarding it. The observed Ollama runner advertised a
4,096-token context; the byte cap is not a tokenizer count. Provider/model choices
remain unchanged.

Source objects and uploads remain private. Their combined default quota is 512 MB,
with serialized admission. Uploads are limited to 8 MB, ZIP expansion to 30 MB/2,000
entries, snapshots to 8 MB/500 sources. No automatic deletion is enabled.

Optional Docker tests use a pinned image, no network/host mounts, read-only root,
nonroot user, dropped capabilities, and CPU/memory/PID/time/output limits. Cleanup
results are recorded. PDF parsing has process resource limits, but not full
filesystem isolation. The local service is not a security certification.

The optional Docker image was pulled and its digest configured. No plugin trust,
sandbox policy, unrelated project, credential or model choice was changed. No paid
API was required; hardware, electricity and internet remain prerequisites.

## Remaining acceptance gaps

Update: the [Promptfoo integration](PROMPTFOO_INTEGRATION.md) adds explicit task
checks, a per-agent results matrix, scoped leader/tie decisions, saved regression
suites and dependency preflight using actual upstream code. This addresses the
missing comparison flow for declared requirements. General semantic accuracy and
security-coverage claims remain unsupported without independent measurements.

1. Live Tavily and private GitHub validation need appropriate credentials.
2. Calibrated semantic accuracy/security scoring requires independent truth labels.
   Repository rubric weights exist; no invented aggregate score is emitted.
3. Disagreement matching is conservative and semantic model review is advisory.
4. Deterministic architecture/static inventory is strongest for Python; other
   captured languages use model analysis without equivalent AST checks.
5. Outdated-package detection, cross-agent critique, multilingual PDF fonts, OCR,
   team authentication/ownership, public deployment and retention UI are not built.

RILO is a working local evaluation workspace. A 92+/100 product rating or hackathon
result has not been independently established.
