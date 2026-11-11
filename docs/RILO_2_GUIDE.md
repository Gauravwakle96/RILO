# Use RILO

Open http://127.0.0.1:8018. RILO defaults to a private local website with a Python
service and worker. Administrators can instead enable the authenticated single-instance
hosted mode documented in [HOSTED_DEPLOYMENT.md](HOSTED_DEPLOYMENT.md).

1. Choose Chat, Repository (GitHub/ZIP), Documents (PDF/DOCX/TXT/Markdown), Website,
   or Search (Tavily or supplied source text).
2. Select two compatible agents. Scout is the baseline. Relay has cautious evidence
   instructions and bounded malformed-output or missing-citation recovery. Analyst profiles focus the same
   underlying execution system on websites, repositories or documents.
3. Write a focused task and attach context. Both agents receive the same captured input.
4. Inspect answers, citations, status, usage and traces. Execution is sequential on
   the laptop. Cancel active work or retry one failed response; originals remain saved.
5. Check evidence before trusting conclusions. A valid quotation does not prove a
   vulnerability or make a source true. Independent semantic review is advisory.
6. Export PDF/Markdown/JSON/CSV, save a benchmark, or retest. Regression Lab highlights
   changed conditions, findings, latency and tokens.

## Optional services

**Tavily:** leave Web search off to use no credits. Enable it for fresh search results
after configuring `TAVILY_API_KEY` privately and restarting API/worker. A newly captured
workspace input makes one shared basic request. Local credit reservation is not the
provider balance. Direct GitHub, URL and document analysis do not need Tavily. Search
off with no supplied sources returns an honest error.

**GitHub:** public retrieval uses metadata/tree lookup and up to the configured 200
commit-pinned text files / 12 MB by default, with a bounded archive fallback when anonymous lookup is unavailable. Private access
requires authorized `GITHUB_TOKEN`, which is never given to agents. Private live
acceptance has not been performed without a token.

**OSV:** opt-in dependency checking sends package names/exact versions, not repository
source. Supports pinned requirements.txt and package-lock.json. Advisory matching does
not establish exploitability. Outdated-package checking is not implemented.

**Repository tests:** require Docker and a preinstalled digest in `RILO_SANDBOX_IMAGE`.
Initial UI supports Python unittest discovery on captured files. No dependency
installation, host mount or container networking. Runner failure is recorded.

## Limits

- Repository retrieval and selected passages are bounded, not exhaustive auditing.
- Default input cap is 6,000 serialized bytes. Excessive history fails clearly; increase
  only after validating model context. Prior messages are never silently removed.
- PDFs retain true page numbers. Empty scanned pages use bounded local Tesseract OCR
  when installed; recognition errors are identified by extraction metadata. DOCX/TXT/Markdown use line citations.
- Website pages containing only metadata or scripts fail source capture before agent
  execution. Use a directly readable URL or paste source text in Chat.
- Failed source capture can be retried as a new paired evaluation. Original attempts
  remain saved; an individual response retry requires a captured snapshot.
- No objective accuracy or winner without suitable labels. Exact-quote metrics have
  narrow scope; ordinary chat and semantic security claims are not objectively graded.
- Standard PDF fonts have limited non-Latin coverage; JSON/Markdown preserve Unicode.
- Hosted mode provides persistent accounts and per-user resource ownership behind
  HTTPS, but remains a single Rilo instance over SQLite. Horizontal scaling, self-service
  account recovery and retention management are future work.

Core local inference requires no paid API. Existing hardware, model downloads,
electricity, internet and any future hosting still have their own costs.
