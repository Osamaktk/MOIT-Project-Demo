# CODEX BUILD PROMPT v2: MoITT Minister's Command Center

You are continuing work on the repository `Osamaktk/MOIT-Project-Demo` (FastAPI backend, React + Vite frontend, SQLite, no Docker). The first build followed `ARCHITECTURE.md` (a Privatisation Commission design). It passes its own tests but does not meet the real need. This prompt supersedes `ARCHITECTURE.md` wherever they conflict. Update `ARCHITECTURE.md` to v2 in Phase 1 so the repo has one source of truth.

Read this whole prompt before writing code. Work phase by phase (Section 12). After every phase: run all tests, run the app, take screenshots, update `docs/PROGRESS.md`, and stop only when the phase's acceptance checks pass.

---

## 1. What is actually needed

The system is for the **Federal Minister for IT & Telecommunication (MoITT)** and his office. Its only job is to make the Minister's work easier and less confusing:

1. Staff or the Minister **upload meeting minutes and other office documents**. The system reads them, finds every action, owner, deadline and commitment, and after one human confirmation **updates the dashboard automatically**.
2. The Minister opens one calm page that shows what needs his attention today, how each project is doing, what is overdue, and what has been promised to him.
3. The Minister can **talk to a live AI assistant (Jarvis)** the way people talk to ChatGPT voice: natural conversation, interruptions allowed, spoken answers, grounded in the office's own records.
4. An Admin can create users, assign roles, and control exactly what each person can see and do.

Design for a busy senior reader. If a screen needs explaining, it is wrong. Fewer items, plain words, no jargon.

### Verified problems in the current build (tested 18 Oct 2026)

| # | Problem | Evidence |
|---|---|---|
| 1 | **Jarvis is not an AI.** It is a regex/keyword router (`backend/app/services/jarvis_graph.py`, model name `deterministic-agent-v1`). "Hello Jarvis, how are you?" returns "I found these matching records." Every open question falls through to a raw document search. | `choose_tool()` and `_execute()` |
| 2 | **No live or voice conversation.** There is only a tiny push-to-talk button that fills a text box. No streaming voice, no spoken replies by default, no animation, no interruption. | `JarvisDock.tsx` |
| 3 | **Upload is hidden and powerless.** It exists only inside Records Search and only for `cos` and `data_coordinator`. The Minister, Director and Liaison get HTTP 403. Uploading two real MoITT minutes created no actions, changed no KPIs, and left the Register at 60 rows. | API test |
| 4 | **Search returns raw text dumps**, not answers. | `/api/v1/records/search` |
| 5 | **Wrong domain model.** Everything is "17 privatisation transactions". Real minutes are about projects (IT Park Islamabad, Pakistan Asaan Khidmat Centres) and assign actions to **organisations** (PSEB, CDA, AJK Government) as well as people. The data model forces "one user, never a unit". | Sample minutes |
| 6 | **Admin is too weak.** Fixed 8 roles, no per-user permissions, no password reset, no role presets. | `api/v1/admin.py` |
| 7 | **UI overlaps and clutter.** KPI captions collide with "Open records" links; the Records search bar is squeezed to "Ask a ques" and its Search button is cut off by the Jarvis dock; the breadcrumb always says "Command Center"; mojibake `·` appears on the Meetings page (source files `MeetingsPage.tsx` and `RegisterPage.tsx` contain mis-encoded middle dots); the Jarvis dock permanently takes 300px; internal jargon everywhere (Register, Zone, AI tools online, Core foundation ready, SYN-2026-0050). | Screenshots |
| 8 | **Frontend does not install on macOS/Linux.** `package.json` pins `@rolldown/binding-win32-x64-msvc` as a devDependency, so `npm ci` fails with EBADPLATFORM. | `npm ci` |
| 9 | Vite dev server binds `0.0.0.0` (exposed to the LAN). | `package.json` scripts |
| 10 | Duplicate uploads are not detected; the library fills with copies. | Library page |
| 11 | No quick way to test every role. | Login page |

Things that work and must be kept: backend test suite (56 tests), migrations, audit trail, kill switch, two-zone policy gateway, clearance filtering, Register serial logic, minutes pipeline, health checks.

---

## 2. Hard rules

1. **Never print, log, commit or return an API key.** Keys live only in `backend/.env` (gitignored). `.env.example` has empty values. Health endpoints may report `configured: true/false` only.
2. Everything must run on **Windows, macOS and Linux**. Fix Problem 8, regenerate `package-lock.json`, and verify `npm ci` and `npm run build` on Linux.
3. Bind dev servers to `127.0.0.1` by default.
4. Keep AI proposals unofficial until a named human confirms (the product's core safety idea). The Minister's own confirmation counts as approval.
5. Real ministry documents may be used as local test fixtures only. Put them in `backend/samples/ministry/` (gitignored). Tests that need them must skip cleanly when absent, and you must provide synthetic look-alike fixtures so CI always has coverage. Do not commit real names or documents.
6. Free cloud models may retain prompts. Keep the existing two-zone policy: documents classified `confidential` never go to a cloud provider unless the admin explicitly allows it per document. Show a clear, calm notice in the UI when a cloud model is active.
7. Do not add features that are not in this prompt. If something is ambiguous, choose the simplest option and record it in `docs/DECISIONS.md`.
8. No placeholders, no TODO stubs, complete typed code, tests for everything you add.

---

## 3. Domain model changes (Phase 1)

Rename the product to **MoITT Command Center** (configurable name). Replace "transactions" with **projects** everywhere (tables, API, UI, seed). Keep the generic stage list in one config file.

New and changed entities:

- `organisations`: `name`, `short_name` (PSEB, CDA, NITB, AJK Govt, GB Govt, MoITT...), `type` (ministry, attached_dept, authority, provincial, external), `aliases` (JSON).
- `projects` (was transactions): `code`, `name`, `aliases` (JSON, used for matching), `sector`, `stage`, `health` (`on_track | at_risk | delayed`), `health_reason` (text, always shown), `lead_org_id`, `summary`.
- `actions` (the Register, same serial/FY rules): replace `officer_id` with **`owner_org_id` (required) + `owner_person_name` (optional) + `owner_user_id` (optional)**. An action is valid when it has an owner organisation or a named person. Add `deadline_text` (original words, e.g. "Immediate"), `deadline_precision` (`day | week | month | relative`), `status_source` (`open | done_at_upload`), `source_document_id`, `source_quote`, `source_page`.
- `commitments`: `project_id`, `statement`, `committed_by_org_id`, `committed_by_text`, `due_date`, `due_text`, `precision`, `status` (`pending | met | missed`), `source_document_id`, `source_quote`. These come from sections such as "Key Completion Commitments" and from proceedings ("contractor mobilization 13 September 2026, completion within 180 days").
- `meetings`: add `chair`, `venue`, `participants` (JSON list of `{text, org_id?}`), `source_document_id`.
- `intake_jobs`: see Section 4.

Health is rule-based and explainable, never a black box:
- `delayed`: a commitment's due date passed unmet, or a project-critical action is more than 14 days overdue.
- `at_risk`: any overdue action, or a commitment due within 30 days with no progress action.
- otherwise `on_track`.
Always store and display the reason ("2 actions overdue; CDA delay report outstanding").

Deadline normalisation (store the original words next to the resolved date, and let the reviewer change it):
- "Immediate" = meeting date + 2 working days. "Today" = meeting date. "Next Meeting" = next scheduled meeting for that agenda if known, else flag as needs input.
- Explicit dates are parsed. "First week of March 2027" resolves to 7 March 2027 with precision `week`. "180 days from contractor mobilization" becomes a relative commitment anchored to the mobilization date.

---

## 4. Document intake pipeline (Phase 2): the heart of the product

### 4.1 One obvious way to upload
- A prominent **Add minutes / Add document** button in the top bar of every screen, plus drag-and-drop anywhere on the Today view. Accepts PDF, DOCX, TXT, MD, and image or scanned PDF.
- Allowed for any role with the `documents.upload` permission (default on for Minister, Secretary, Chief of Staff, Project Lead, Legal, Data Coordinator). Each user's upload goes to a review screen that **they** confirm (or hand to the Chief of Staff with one click).
- Duplicate detection by SHA-256. If the file exists, say so and link to it instead of re-ingesting.
- Scanned PDFs: try text extraction; if no text, try OCR (pytesseract if installed); if neither works, say clearly what is missing and how to fix it. Never silently produce empty results.

### 4.2 Extraction (LLM, structured JSON)
Classify the document first (`minutes | letter | brief | note | other`). For **minutes**, extract:

```json
{
  "meeting": {"subject": "", "date": "", "time": "", "venue": "", "chair": "",
              "participants": [{"text": "", "org_hint": ""}]},
  "actions": [{"description": "", "owner_text": "", "owner_org_hint": "", "owner_person_hint": "",
               "deadline_text": "", "deadline_date": null, "priority_suggestion": "A|B|C",
               "project_hint": "", "source_quote": "", "source_page": 1, "confidence": 0.0}],
  "commitments": [{"statement": "", "committed_by_text": "", "due_text": "", "due_date": null,
                   "project_hint": "", "source_quote": "", "source_page": 1, "confidence": 0.0}],
  "decisions": [{"text": "", "source_quote": "", "source_page": 1}],
  "summary": "three plain sentences for a minister"
}
```
Rules: the model must copy `source_quote` verbatim from the document; the backend verifies each quote exists in the extracted text (fuzzy match) and drops or flags items whose quote cannot be found. Validate with Pydantic, retry once with a repair prompt, then fail with a clear message. Tables in PDFs (S#, Action, Responsibility, Timeline) must be parsed correctly, including rows whose text wraps across lines. Use `pdfplumber` or equivalent table extraction in addition to `pypdf`, and test against the two sample minutes (Section 11).

### 4.3 Entity resolution
Match `owner_org_hint` to `organisations` (aliases, case-insensitive, "CEO & CIDO, PSEB" means org PSEB with role text "CEO & CIDO"). Match `project_hint` to `projects` by name and aliases; if no match, propose **creating a new project** in the review screen. Unmatched owner organisations may be created from the review screen in one click.

### 4.4 Review and confirm screen (see mockup "3 · Upload minutes and confirm")
Two panes: original document on the left (page view, highlighting the quote for the selected item), extracted meeting, actions and commitments on the right. Every action row has: description, owner organisation (dropdown), optional person, deadline (shows original words and resolved date), and an **Open / Already done** toggle (essential when uploading older minutes). Rows needing input are highlighted and block confirmation. A summary box states exactly what will change ("+3 actions, IT Park Islamabad timeline updated, 1 action still needs an owner"). Buttons: **Discard** and **Confirm and add to Register**.

### 4.5 After confirmation
In one transaction: create the meeting, approved actions (with serial numbers), commitments, project links; recompute project health; write `audit_events`; write the `ai_runs` row with outcome `approved` or `edited` and a diff summary; re-index the document and the new records for Jarvis and search. The Today dashboard must reflect the change on next load (invalidate caches). Add an automated test: upload sample minutes, confirm, assert KPI counts and project health changed.

### 4.6 Other document types
Letters, briefs and notes: store, classify, summarise in three sentences, link to a project, and extract any actions or commitments through the same review screen. If none are found, say so and still index the document for search and Jarvis.

---

## 5. Jarvis as a real AI assistant (Phase 3)

Replace the regex router with an **LLM tool-calling agent** (LangGraph is fine) behind the existing AI Gateway (policy, kill switch, `ai_runs` logging all stay).

- **Provider chain via config**, not code: `MODEL_CHAT` plus `MODEL_CHAT_FALLBACK_1..N`. Default to OpenRouter using the user's key from `.env`. At startup, and via `python scripts/verify_openrouter_models.py`, query the live OpenRouter catalogue and choose models that are `:free`, support tool calling (`supported_parameters` includes `tools`) and streaming, and handle English and Urdu well. Record the chosen chain and the evidence in `docs/DECISIONS.md`. On 429/5xx/timeouts, fall through the chain automatically and tell the user calmly if all fail.
- **Optional Groq provider** (OpenAI-compatible, base URL `https://api.groq.com/openai/v1`, key `GROQ_API_KEY`) selectable per role in `.env` and in Admin AI settings. Verify Groq model IDs against its model list before use; do not hard-code unverified names.
- **Conversation**: Jarvis answers greetings, follow-ups and general questions naturally, remembers the session, and asks a short clarifying question when needed. It uses tools to read office data. Facts about the office must come from tools and carry citations. General knowledge (for example "what is a REIT?") is allowed, labelled "General knowledge, not from office records", and must never be presented as an office fact or decision.
- **Tools** (each enforces the caller's role and clearance): `get_dashboard_summary`, `list_projects`, `get_project`, `query_actions`, `list_overdue(owner?)`, `get_commitments(project?)`, `get_upcoming_meetings`, `get_meeting_minutes`, `search_documents` (hybrid RAG, returns passages with citations), `get_compliance_due`, `propose_action` (creates a **proposed** action only, never official), `prepare_brief(project|meeting)`.
- **Answer style**: short, executive, plain English (or Urdu when the user speaks Urdu). Lead with the answer, then one line of why, then citation chips. Offer detail on request.
- **Streaming**: SSE with `token`, `tool_start`, `tool_result`, `citation`, `proposal_card`, `done`, `error`. Show a quiet activity line ("Checking the actions list…").
- **Offline mode**: if no key or all models fail, show a visible, calm banner "AI is offline. Showing simple record lookups" and use the old deterministic router as a fallback. Never silently fake intelligence.
- **Records Search** should now return a synthesised answer with citations (same agent, `search_documents` tool) instead of raw chunks, with the source viewer kept.
- Add tests with a recorded/mocked model: greeting, open-ended question, tool use, citation present, proposal creates no serial, kill switch refusal, fallback chain on 429.

---

## 6. Jarvis Live: voice conversation like ChatGPT voice (Phase 4)

Goal: the Minister taps **Talk to Jarvis**, a full-screen calm overlay opens (see mockup "2 · Jarvis Live"), and he can simply talk. Jarvis answers aloud, he can interrupt at any time, and the transcript and source chips appear as captions.

### 6.1 States and behaviour
`idle` → `listening` → `thinking` → `speaking` → back to `listening`. The conversation stays open until he ends it. **Barge-in**: when the user starts speaking while Jarvis is talking, stop audio immediately and listen. Show captions for both sides. Citation chips and proposed-action cards appear under the caption. Escape or the red button ends the session and saves the transcript to the chat history.

### 6.2 Pipeline (build with fallbacks, pick the best available at runtime)
1. **Speech in**: (a) Browser `SpeechRecognition` (Chrome/Edge) with interim results and `ur-PK` / `en-US`/`en-GB` plus auto-detect; (b) fallback: record with `MediaRecorder` and voice-activity detection, send the utterance to `/api/v1/jarvis/stt`, which uses Groq `whisper-large-v3-turbo` (verify the ID) if `GROQ_API_KEY` is set, else local `faster-whisper`. Implement end-of-speech detection (about 700 ms of silence, tunable).
2. **Thinking**: the Section 5 agent, streaming tokens.
3. **Speech out**: start speaking as soon as the first full sentence arrives (sentence-chunked streaming TTS). (a) Browser `speechSynthesis` with a voice picker and rate control (default); (b) optional server TTS provider behind a `TTSProvider` interface if a key and model are configured. Choose the best installed voice per language (Urdu voice if present, else English with a notice).
4. Target latency: first audible word within about 3 seconds of the user finishing speaking on a normal connection. Measure and log it in `ai_runs.latency_ms`.

### 6.3 Animation (restrained, premium, not sci-fi)
A centered orb with a soft radial gradient and two expanding rings. Driven by real audio level: use the Web Audio `AnalyserNode` on the mic stream while listening, and on the TTS audio element when speaking. For `speechSynthesis` (no audio tap), drive the orb from `boundary` events plus a smoothed noise envelope. State colours: listening = teal, thinking = slow shimmer, speaking = bright pulse. Respect `prefers-reduced-motion` (static orb with a text status). Use Framer Motion or CSS only; keep 60 fps.

### 6.4 Robustness
Handle microphone permission denial with a clear message and a typing fallback. Handle no speech detected. Handle the browser lacking `SpeechRecognition` (use the recording path). Never auto-record without the overlay open and a visible "listening" indicator. Mute button always visible. The kill switch for `jarvis` disables Live mode with a clear message.

Be honest in the UI and docs: true end-to-end speech-to-speech realtime models are not assumed. This is a low-latency streaming pipeline that feels live.

---

## 7. UI/UX redesign (Phase 5)

Match the four mockups in the design canvas "MoITT Command Center Designs" (screens: Minister's Today view, Jarvis Live, Upload and confirm, Admin users and access). Treat them as the visual target, not pixel law. The goal is a calm, premium, uncluttered government product.

### 7.1 Design system
- Font: Plus Jakarta Sans (UI), JetBrains Mono (dates and IDs only), Noto Nastaliq Urdu for Urdu content. Tabular numbers for figures.
- Colours: ink navy `#0F1B2D` sidebar, canvas `#F5F4EF`, surface `#FFFFFF`, border `#E5E2D9`, text `#14213A`, muted `#5B6678`, primary teal `#0F766E`, brand gold `#B7882C` (logo only), danger `#B42318`, warning `#B54708`, success `#067647`, AI marker violet `#4A2FB8` (only on AI-generated content). Radius 14px cards, 10px controls, 8px grid.
- Implement tokens once (`tokens.css` + Tailwind theme). Remove ad-hoc per-feature colours. Use Tailwind + a small shared component library (Button, Card, Chip, Table, Drawer, Dialog, Toast, EmptyState, Skeleton). Adopt shadcn/ui primitives if practical.
- Every text style, spacing and colour comes from tokens. Min body text 14px, touch targets 44px, WCAG AA contrast.

### 7.2 Layout and navigation
- Sidebar by role. **Minister sees only: Today, Projects, Actions, Meetings, Documents.** Staff see more (Review inbox, Compliance, AI oversight). Admin sees Administration. No "Core foundation ready", no version text, no "Zone"/"AI tools online" pills in the top bar. Show an AI-status indicator only when something is wrong, and put the data-zone notice in a small info popover plus the Jarvis footer.
- Real breadcrumb/page title on every page.
- Jarvis is **not** a permanent column. It is a bottom command bar ("Ask Jarvis…", Ctrl/Cmd+J) with a **Talk to Jarvis** button that opens Live mode, and an expandable side panel for text chat. Content must never be squeezed by it.
- Rename jargon: Register → **Actions**; Records Search → **Documents**; AI Assurance → **AI oversight** (staff only); Transactions → **Projects**; remove "SYN-…" references from visible text.

### 7.3 Screens
1. **Login**: calm card, plus a clearly marked **Demo users** panel listing every demo account as a clickable card (name, role, one-line description). One click signs in. Hide this panel when `APP_ENV` is not `demo`.
2. **Today** (Minister's home): header with greeting and date, KPI strip (Active projects, Awaiting your decision, Overdue actions, Meetings this week), **Needs your attention** (3 AI-prepared items, labelled AI summary), Projects list with progress, status chip and next date, an upload drop zone, Actions to follow up, Commitments made to you. Every number opens the exact underlying records.
3. **Projects** and project detail: stage, health with reason, timeline of commitments, linked actions, documents, meetings.
4. **Actions**: simple list with filters (status, owner organisation, project, due), side drawer for detail and history. Advanced filters collapsed by default. No raw "Transaction ID" text box.
5. **Meetings**: list; open a meeting to see summary, decisions, actions and the source document.
6. **Documents**: upload, library (no duplicates), search with synthesised answers and a source viewer.
7. **Review inbox** (Chief of Staff and Project Lead): everything awaiting confirmation (uploads, AI proposals) in one list.
8. **Jarvis Live** overlay and side panel.
9. **Administration** (Section 8).
10. **AI oversight**: decision log, kill switches, spot checks, kept but simplified and visually consistent.

### 7.4 Quality bar (automated)
- Fix every overlap listed in Section 1. Add a Playwright test that loads each screen at 1280, 1440, 1920 and 390 pixel widths and asserts: no horizontal page scroll, no element bounding boxes overlapping text siblings in KPI tiles, tables, toolbars and search bars, no console errors, no text containing ``. Save screenshots to `docs/screenshots/<phase>/` and reference them in `PROGRESS.md`.
- Fix the mojibake at the source (re-save the TSX files as UTF-8 and replace stray `·`).
- Urdu: full RTL, tested on Today, Actions and Jarvis Live.
- Loading skeletons, empty states with one clear next step, friendly error states with Retry on every screen.
- Subtle motion only (Framer Motion): page transitions, drawer slide, orb. No decorative gradients elsewhere.

---

## 8. Roles, permissions and Administration (Phase 6)

Replace the fixed role list with **role presets + per-user overrides**.

### 8.1 Permission model
Areas: `dashboard`, `projects`, `actions`, `meetings`, `documents`, `review`, `jarvis`, `jarvis_voice`, `compliance`, `ai_oversight`, `admin`. Capabilities per area: `view`, `edit`, `approve` (and `upload` for documents). Plus **document clearance** (`public | internal | confidential`) and optional **organisation scope** (a user from PSEB sees and updates only actions owned by PSEB).

Store as `roles` (presets) and `user_permissions` (overrides). Every endpoint declares required `area.capability`; deny by default; enforce on the server, never only in the UI. The UI hides what a user cannot use.

### 8.2 Role presets and demo users
Create these presets and seed one demo user each. Shared demo password: `Demo-Only-Change-Me-2026!` (shown only in demo mode).

| Preset | Demo user (email) | Sees and can do |
|---|---|---|
| `minister` | Federal Minister (`minister@moitt.demo`) | Today, Projects, Actions, Meetings, Documents all view; approve own uploads; confirm proposed actions; Jarvis text and voice; confidential clearance |
| `secretary` | Federal Secretary IT (`secretary@moitt.demo`) | Everything the Minister sees plus edit actions and projects; upload; approve; Jarvis; confidential |
| `cos` | Private Secretary / Chief of Staff (`ps@moitt.demo`) | Full actions ownership, review inbox, approve minutes and AI proposals, upload, AI oversight and kill switch, Jarvis; confidential |
| `project_lead` | Joint Secretary (Dev) (`js.dev@moitt.demo`) | Edit projects and actions for his projects, upload, review inbox for those projects, Jarvis; internal |
| `legal` | Legal Adviser (`legal@moitt.demo`) | Compliance, documents view and vetting, actions view, Jarvis; internal |
| `analyst` | Dashboard Analyst (`analyst@moitt.demo`) | Dashboards and reports view, spot checks, AI oversight view; internal |
| `data_coordinator` | Records Coordinator (`records@moitt.demo`) | Documents upload and classification, data quality, search; internal |
| `external_org` | PSEB Liaison (`pseb.liaison@moitt.demo`) | Only actions owned by PSEB: view and update status; no dashboard; public |
| `admin` | System Administrator (`admin@moitt.demo`) | Administration only (users, roles, AI settings, health, activity log); cannot read confidential documents unless granted |

### 8.3 Administration screen (see mockup "4 · Admin: users and access")
- User list with search, role filter, status (Active, Invited, Deactivated), last sign-in.
- **Create user**: name, email, designation, organisation, role preset, temporary password (generated, shown once) with a forced change on first sign-in.
- Side panel for the selected user: role preset dropdown, the permission grid (View / Edit / Approve per area), document clearance, organisation scope, Save, **Reset password**, **Deactivate**.
- Protections: the last active admin cannot be demoted or deactivated; users cannot edit their own permissions; every change writes an audit event with before and after.
- **Organisations** tab (CRUD), **AI settings** tab (current model chain, provider status, test button; keys are never displayed), **Activity log** tab (searchable, exportable CSV), **System health** tab.
- API tests for every permission boundary: a role without `documents.upload` gets 403; a PSEB liaison cannot read another organisation's actions; an admin cannot read confidential documents by default.

---

## 9. Configuration

`backend/.env` (never committed):

```
APP_ENV=demo
SECRET_KEY=<random, at least 32 characters>
OPENROUTER_API_KEY=<the user's key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
GROQ_API_KEY=            # optional; user may add later
GROQ_BASE_URL=https://api.groq.com/openai/v1
MODEL_CHAT=              # chosen by verify script (free, tool-calling, streaming)
MODEL_CHAT_FALLBACK_1=
MODEL_CHAT_FALLBACK_2=
MODEL_EXTRACTION=        # strong JSON-output model, with fallbacks
MODEL_EXTRACTION_FALLBACK_1=
STT_PROVIDER=auto        # auto | browser | groq | faster_whisper
TTS_PROVIDER=browser     # browser | server (optional)
ALLOW_CLOUD_FOR_SYNTHETIC_DEMO=true
```

Add a first-run **setup check** (`python scripts/doctor.py`) that prints PASS/FAIL for: Python and Node versions, `.env` present, key configured (true/false only), database migrated, seed present, model chain verified, STT/TTS availability, and `npm ci` consistency. The README must give one command per OS to run everything.

---

## 10. Testing and acceptance

Keep all existing tests green and add:
- Intake: upload each sample minutes PDF (and a synthetic look-alike), assert the expected actions, owners (organisations), deadline normalisation, commitments and project links; assert quote verification drops hallucinated items; assert duplicate upload is detected; assert confirm updates KPIs and project health.
- Permissions: a matrix test over all presets and all endpoints (expected 200/403).
- Jarvis: mocked-model tests (Section 5) plus one optional live smoke test that is skipped without a key.
- Voice: unit tests for VAD end-of-speech logic, sentence chunking, and state machine transitions; a Playwright test that opens Live mode with a fake audio device and checks states and the absence of console errors.
- UI: Playwright overlap/overflow/console/encoding checks (Section 7.4) and screenshots.
- Clean machine: fresh clone, one-command setup, then the full demo path runs without manual database edits.

### Demo path that must work end to end
1. Sign in from the Demo users panel as the Chief of Staff, upload the IT Park minutes, review, mark items already done where appropriate, confirm.
2. Sign in as the Minister; the Today page shows the new actions, the updated IT Park project health with its reason, and the new commitments.
3. Upload the Asaan Khidmat Centres minutes as the Minister; confirm; the dashboard updates.
4. Ask Jarvis by text: "How are you?", "What is overdue and who owns it?", "What did CDA commit to?", "What is a REIT?" (labelled general knowledge), "Create an action for the Chief of Staff to follow up on the tender by Friday" (proposal only).
5. Open Jarvis Live, ask the same questions by voice, interrupt a long answer, switch to Urdu.
6. Sign in as Admin; create a new user with custom permissions; sign in as that user and confirm only the granted areas are visible; try a forbidden URL and see a friendly 403 page.

---

## 11. Sample documents (supplied by the user, not in the repo)

The user will place two real MoITT minutes in `backend/samples/ministry/`:
- `Minutes_of_the_Meeting_-_IT_Park_Islamabad_Operationalization_-_24-08-2026.pdf`
- `Minutes_of_Meeting_-_Update_on_Pak_Asaan_Khidmat_Centres_-_19-08-2026-1.pdf`

Their structure, which the extractor must handle:
- **Header block**: Agenda, Date, Time (sometimes), Venue, Chair (Federal Minister for IT & Telecom), Participants (bulleted).
- **Action table** with columns S#/S. No, Action, Responsibility, Timeline. Rows wrap across lines. Responsibility is sometimes an organisation or office-holder ("CEO & CIDO, PSEB", "Chairman CDA and Team", "AJK Government", "Secretary IT - GB") and sometimes a person ("Fateh Malik", "Ali Khan"). Timeline is usually a phrase: "Immediate", "Today", "Next Meeting".
- **Key Completion Commitments** (numbered, with dates such as 23 March 2027 and "first week of March 2027").
- **Proceedings**: numbered sections containing dates, figures (PKR 42,000 per sq. ft. revised to about PKR 25,000–26,000; 80 digital services across 20 departments; 180 days from mobilization; mobilization target 13 September 2026), decisions, and directions that are not in the action table but imply actions. Extract these as decisions or commitments, flagged "from proceedings".
- In the first sample the table is partly mis-ordered (the first action appears before serial 1). Handle messy tables gracefully and put uncertain rows in the review screen with low confidence.

Seed data for the demo: create 6 to 9 projects (IT Park Islamabad, PAKC Islamabad, PAKC Gilgit, PAKC Skardu, PAKC Muzaffarabad (AJK), plus 3 to 4 generic MoITT projects), the organisations above, and around 25 synthetic actions and commitments with a mix of statuses so the dashboard is never empty. Keep seeded people fictional. Run the two sample minutes through the real pipeline in the demo script rather than pre-seeding them.

---

## 12. Phases (do not start a phase until the previous phase's acceptance passes)

**Phase 0: Fix and stabilise.** Fix Problems 8, 9 and the mojibake (7). Regenerate lockfile and verify `npm ci` on Linux. Add `scripts/doctor.py`. All 56 tests still pass.
*Accept:* clean install on Windows and Linux; no `` anywhere; build passes.

**Phase 1: Domain model and permissions foundation.** Section 3 and the permission model of Section 8.1 (backend only), migrations, updated seed, updated `ARCHITECTURE.md` and README.
*Accept:* tests for new entities, health rules, deadline normalisation, permission matrix.

**Phase 2: Document intake.** Section 4 end to end including the review screen and automatic dashboard update.
*Accept:* both sample minutes (and synthetic look-alikes) ingest correctly; Section 10 intake tests pass; Minister's dashboard changes after confirm.

**Phase 3: Jarvis agent.** Section 5.
*Accept:* greeting and open questions answered naturally; grounded answers carry citations; fallback chain works; offline banner works.

**Phase 4: Jarvis Live.** Section 6.
*Accept:* demo-path step 5 works in Chrome and Edge; barge-in works; orb reacts to audio; Urdu path works or degrades with a clear notice.

**Phase 5: UI/UX redesign.** Section 7 for all screens.
*Accept:* Playwright quality checks pass at four widths; screenshots committed; manual review against the four mockups.

**Phase 6: Administration.** Section 8.
*Accept:* demo-path step 6 works; permission boundary tests pass.

**Phase 7: Hardening and handover.** Full demo path three times in a row on a clean machine; updated `DEMO_SCRIPT.md` (15 minutes); README with exact steps; final screenshots.

### Reporting
At the end of each phase, reply with: what changed, test counts, the screenshot paths, anything you could not do and why, and the exact command to run the app. Do not claim a feature works unless you ran it. If a live AI call fails because of the key, models or rate limits, say so plainly and show what the fallback did.
