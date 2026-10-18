# Build progress

## MoITT Command Center v2 — current delivery

### Phase 0 — Fix and stabilise (Linux CI verification pending)

- [x] Remove the Windows-only Rolldown package from direct development dependencies and regenerate the npm lockfile with platform-specific optional packages preserved.
- [x] Bind Vite development and preview servers to `127.0.0.1` by default.
- [x] Repair the mojibake middle-dot text in frontend source; a repository scan found no U+00C2 or U+00C3 characters.
- [x] Add `scripts/doctor.py` with version, private backend configuration, key-presence-only, model-catalogue, migration, seed, speech, and npm lockfile checks.
- [x] Move backend settings to the ignored `backend/.env`; make model-catalogue verification use the public endpoint without sending a credential.
- [x] Windows clean install and production build passed in an isolated copy: `npm ci` (0 vulnerabilities), `npm run build`.
- [x] Backend suite passed: 56 tests. Doctor passed: 11/11 checks. Frontend production build passed in the workspace.
- [x] Run the app and capture a login screenshot: [`docs/screenshots/phase-0/login.png`](screenshots/phase-0/login.png). A fresh Vite process served HTTP 200 on `127.0.0.1:5174`; its listener was loopback-only.
- [ ] Linux `npm ci` and `npm run build` — CI workflow added; awaiting the first GitHub Actions run.

Phase 0 remains open until the Linux workflow passes. Do not begin Phase 1 before then.

## Phase 0 — Foundation (accepted)

- [x] Initial repository structure and source architecture copy.
- [x] Central configuration, SQLAlchemy session, initial Alembic migration.
- [x] Synthetic role personas, password hashing, short-lived JWT login, role dependency, append-only audit model/service.
- [x] Health routes and frontend shell/login foundation.
- [x] Apply the initial migration and run backend authentication/RBAC/health tests: 14 passed, including all role logins, role denial, shared error envelopes, and audit creation.
- [x] Install frontend dependencies and verify the original production shell build.
- [x] Refresh vulnerable frontend packages; the production build passes on the upgraded stack and the latest audit reports zero vulnerabilities.

Acceptance passed: the health API is operational, all eight role personas can log in, protected profile access works, and the command shell builds on the audited frontend stack.

## Phase 1 — Decision & Action Register (accepted)

- [x] Register schema and migration, financial-year serial allocator, validation/status services, approved-only pagination and filters, overdue grouping, CSV export, and audit-history API.
- [x] Deterministic synthetic Register seed: 60 approved entries plus 6 unnumbered proposals; six approved items are overdue across three officers.
- [x] Backend acceptance coverage for fiscal-year serials, deadline checks, approved-only counts, transition validation, reassignment reasons, and overdue rules (21 backend tests pass so far).
- [x] Register table and detail drawer UI, status/priority/officer/origin/transaction/date/overdue filters, saved filters, status actions, CSV download, and visible audit timeline.
- [x] Apply migrations, seed 60 approved entries plus 6 proposals, verify six overdue items across three officers, and run the backend suite: 23 passed.
- [x] Verify the strict TypeScript/Vite production build and dependency audit: build passed; zero vulnerabilities.

Acceptance passed: financial-year serial allocation, deadline checks, approved-only default results, audit trail, filters, state transitions, and CSV export are implemented and covered.

## Phase 2 — Transactions and Dashboard (accepted)

- [x] Implement transaction portfolio, milestone/health edits with a required reason, event history, linked approved Register items, minister decisions, and engagements with synthetic seed data.
- [x] Add aggregate dashboard KPIs, stage distribution, milestone/decision/action/engagement summaries, and exact-record drill-down endpoints.
- [x] Build the Friday dashboard with week selector, source record drawer, transaction create/list/detail/edit/event views, decision tracking, engagement calendar, and print styles.
- [x] Verify the synthetic portfolio has 17 transactions in the specified 2/3/3/3/2/2/2 stage distribution; 4 decisions, 6 engagements, and 6 overdue approved Register actions are seeded.
- [x] Backend suite passes: 27 tests. Dashboard KPI drill-down totals reconcile to the exact underlying records; transaction stage totals sum to 17.
- [x] Strict TypeScript/Vite production build passes; npm audit reports zero vulnerabilities.

Acceptance passed: the Friday dashboard displays the specified portfolio distribution, every KPI opens a drill-down with matching record totals, overdue actions come only from approved Register entries, and the transaction/decision/engagement data can be reviewed and maintained in the UI.

## Phase 3 — AI Gateway and Assurance core (accepted)

- [x] Implement OpenAI-compatible provider interface, OpenRouter and config-only local providers, configurable provider/model routing by AI role, fallback models, bounded retry, structured JSON validation/repair, and metadata-only `ai_runs` logging.
- [x] Enforce classification and synthetic-data policy before provider calls; fail closed if tool switches are missing or suspended.
- [x] Add CoS/Director kill-switch controls with mandatory reason, audit event, same-day closed Register-style log, affected-screen banners, decision log filters, and CSV export.
- [x] Build the role-restricted Review Queue; approvals receive serials and update the linked `ai_runs` reviewer and timestamp.
- [x] Verify confidential/cloud and suspended calls are blocked and logged; synthetic cloud exception is explicit; provider-zone config can switch without code changes; structured output repairs once and configured fallback works.
- [x] Backend suite passes: 36 tests. Strict TypeScript/Vite production build passes; npm audit reports zero vulnerabilities.
- [x] Add an OpenRouter live-catalogue verification script. No model identifiers are currently configured in this synthetic workspace, so the script reported a skip rather than checking specific IDs.

Acceptance passed: policy violations and suspended tools fail closed, attempted AI calls are logged, assurance controls are auditable, and cloud/local routing is configuration driven. Live provider operation awaits credentials and configured model identifiers.

## Phase 4 — Minutes Assistant (accepted)

- [x] Add synthetic meeting/audio records, a faster-whisper transcription provider interface, and a LangGraph minutes extraction pipeline.
- [x] Run minutes processing with FastAPI background tasks; persist queued/running/succeeded/failed state and stage progress in `jobs`; expose role-checked status and SSE endpoints.
- [x] Build the review workspace with transcript evidence, proposed actions, approve/reject controls, 24h/48h SLA timers, and an issue gate until every action is resolved.
- [x] Export issued minutes as `.docx`; verify seeded English sample minutes and timestamped evidence, then confirm approved actions receive Register serials.
- [x] Backend suite passes: 39 tests, including meeting processing, action resolution and issue gating, export, STT path, suspension logging, and confidential visibility.
- [x] Strict TypeScript/Vite production build passes.

Acceptance passed: the synthetic English meeting produces a draft and evidence-linked actions; job status reaches completion and streams progress; issue remains blocked while any action is unresolved; issued minutes export to `.docx`; approved actions enter the numbered Register and feed its existing dashboard aggregates. Live transcription of uploaded audio requires faster-whisper's model download; live drafting requires a configured AI provider.

## Phase 5 — Records Search (accepted)

- [x] Add document metadata and SQL-backed chunks with page/section/character locations; apply migration `0006_records_search`.
- [x] Ingest PDF, DOCX, TXT, and MD sources; retain originals under ignored runtime data; split text with overlap; persist vectors in Chroma and chunks in SQL.
- [x] Implement clearance-filtered vector + BM25 reciprocal-rank retrieval, optional configured multilingual sentence-transformers or gateway embeddings, deterministic no-download fallback, document type/transaction/date filters, cited answers, and explicit no-evidence declines.
- [x] Index approved Register entries and issued minutes; add role-restricted document library, source viewer, search filters, and coordinator upload UI.
- [x] Verify citation/source mapping, unanswerable declines, and confidential document/source denial for a user without clearance.
- [x] Backend suite passes: 40 tests. Migration check reports no drift. Strict frontend production build passes; npm audit reports zero vulnerabilities.

Acceptance passed: available evidence returns numbered citations with document title, page/section, excerpt, and a source link; unsupported queries are declined; clearance filtering applies before vector retrieval and source delivery. Local multilingual Sentence Transformers can be enabled with `EMBEDDING_MODEL`; configured gateway embeddings continue to follow AI policy. A deterministic feature-hash fallback keeps clean demos usable without downloading an ML model.

## Phase 6 — Jarvis (accepted)

- [x] Add per-user persistent chat sessions/messages, LangGraph tool routing, rule-based grounded tools for dashboard, overdue Register, transaction status, upcoming engagements, issued minutes, and Records Search.
- [x] Stream tool/progress, citation, proposal-card, token, and completion events over SSE; cite every returned record and decline unsupported factual requests.
- [x] Add daily brief quick prompt, page context, browser speech output, push-to-talk STT using the configured transcription provider, and the assurance suspension refusal.
- [x] Convert explicit action requests into unnumbered `proposed` Register entries only; link the AI run and audit event; reviewer cards support edit, approve, and dismiss.
- [x] Verify session ownership, grounded TX-A answer and citation, no serial on proposal, suspension log/refusal, and voice endpoint through the injected STT provider.
- [x] Backend suite passes: 43 tests. Migration check reports no drift. Strict TypeScript/Vite production build passes; npm audit reports zero vulnerabilities.

Acceptance passed for the scripted transaction question, proposal-only action flow, and graceful suspended-tool refusal. Jarvis uses deterministic local tool routing to keep answers grounded without provider credentials; optional voice transcription still requires the configured faster-whisper model on first use.

## Phase 7 — Compliance, Engagements, Spot-checks, Admin polish (accepted)

- [x] Add the compliance calendar and fortnight-ahead view with audited create/update actions and seeded synthetic deadlines.
- [x] Add monthly random AI-run sampling, saved source reconciliation findings, and audit events.
- [x] Add admin user listing/creation/updates, last-admin protection, and an admin-only system readiness page/API.
- [x] Add phase routes and navigation, and include the compliance calendar in Jarvis grounded answers.
- [x] Verify the full backend suite: 47 passed. Apply migration `0008_compliance_spotchecks`; Alembic reports no drift.
- [x] Verify the strict TypeScript/Vite production build and frontend dependency audit.

Acceptance passed: the compliance page returns the next 14 days of open items, spot-checks persist and can be reconciled, and admins can manage demo users while preserving an active admin account.

## Phase 8 - Demo hardening (accepted)

- [x] Add an opt-in, transcript-fingerprint-checked cache for the last successful minutes extraction of synthetic meetings; cloud-policy and kill-switch blocks cannot use the cache. Cache use writes a distinct `minutes-cache-v1` assurance run. Default is off.
- [x] Add exact local setup commands for Windows and macOS/Linux, a 15-minute run-of-show, recovery guidance, and a rehearsal checklist. Update the run scripts to use the project's local virtual environment.
- [x] Improve `/health/ai` readiness reporting without exposing keys or initializing dependencies; add retry/error states to admin and compliance pages.
- [x] Add JSON request logs with response request IDs and in-process rate limits for login and AI-heavy routes.
- [x] Add persisted meeting job progress/status, authenticated status and SSE APIs, frontend progress display, and migration `0009_jobs`.
- [x] Replace the disabled header search placeholder with a keyboard-openable, role-aware workspace command palette; replace the wildcard placeholder with a page-not-found state.
- [x] Add i18next English/Urdu resources, persistent language selection, and document language/direction updates. Translate the shell, dashboard, Register, Transactions, Decisions, Engagements, Compliance, AI Assurance, Administration, Records Search, Jarvis, Review Queue, and Meetings screens in both languages, including forms, controls, dates, and known statuses. Visual RTL, keyboard entry points, and visible control names have been reviewed; screen-reader and remaining state coverage are documented as open.
- [x] Render the login UI in headless Edge against the local Vite server and confirm the English labels and Urdu toggle render; verify the served Urdu text is correctly UTF-8 encoded. Sampled local API responses were 86 ms for the seeded dashboard (17 transactions) and 26 ms for the Register endpoint (60 rows). A separate full browser measurement for 1,000 rows is recorded below.
- [x] Add a repeatable isolated 1,000-row synthetic Register handler benchmark. The handler plus model and JSON serialization measured p50 72.09 ms and p95 120.67 ms; this excludes HTTP transport and browser rendering.
- [x] Improve Register table keyboard access with labelled native entry buttons, arrow/Home/End row navigation, explicit sort state, and visible focus indicators for interactive controls. Add page sizes through 1,000 and virtualized rows for the large view.
- [x] Measure the complete Register page in headless Edge against an isolated 1,000-row synthetic database at 1440 by 1000. Three page-size changes took 309, 239, and 238 ms (median 239 ms, maximum 309 ms); the virtualized table mounted 40 rows, kept keyboard End navigation to row 1,000, and raised no browser exceptions in the production build. A sampled Urdu run used RTL direction with no viewport overflow. This is a local demo measurement, not a production-host guarantee.
- [x] Run a rendered-text contrast scan on 12 authenticated production views and darken failing secondary text; add a translated accessible chart label/table name and keyboard activation for dashboard stage rows. The scan found no below-threshold visible text in the seeded states.
- [x] Verify saved Urdu direction after reload across 11 CoS routes at desktop and mobile widths, and Administration at mobile width; check Noto Nastaliq Urdu, document overflow, chart-row keyboard focus, and drill-down activation. Scope and limits are recorded in `docs/ACCESSIBILITY_REVIEW.md`; screen-reader and all-state review remains open.
- [x] Configure OpenRouter for extraction, verify the no-cost NVIDIA model against the live catalogue, and successfully extract the seeded synthetic meeting during live browser rehearsals. The initial paid DeepSeek request returned HTTP 402; it was replaced before rehearsals.
- [x] Verify a fresh isolated Python environment and `npm ci`; apply migrations, seed, and run the backend suite. The observed setup completed under 20 minutes in this environment, with package caches available; the latest full suite passes 56 tests after the meeting-action audit regression was added.
- [x] Parse-check all PowerShell and Bash run/seed scripts.
- [x] Run the backend demo path three times with fresh test data: minutes review/issue/DOCX, source-cited search, Jarvis citation/proposal approval, compliance, spot-check reconciliation, and admin readiness.
- [x] Run the frontend production build and dependency audit after `npm ci`; build passes and npm audit reports zero vulnerabilities.
- [x] Run three fresh end-to-end Edge browser rehearsals with live OpenRouter extraction; each included all four dashboard KPI drill-downs, overdue Register audit history, minutes review and DOCX, cited Records Search, Jarvis citation/proposal approval, compliance, saved spot-check findings, and admin readiness. Results: 68.32 s, 71.35 s, and 53.75 s; each had 17 transactions, four reconciled KPI totals, five search citations, two meeting actions, and zero page errors. Details are in `docs/DEMO_SCRIPT.md`.

- [x] Review keyboard and Urdu RTL behavior in Edge on all 12 CoS routes at mobile width; no document overflow, unnamed visible controls, or page errors. Verify Ctrl+K palette access and keyboard navigation to TX-A; results and limits are in `docs/ACCESSIBILITY_REVIEW.md`.

Acceptance passed: the setup steps, demo safeguards, performance checks, browser accessibility/RTL review, and three fresh end-to-end live-extraction rehearsals passed. Remaining screen-reader and exhaustive empty/error-state checks are documented as follow-up limits in `docs/ACCESSIBILITY_REVIEW.md`.
