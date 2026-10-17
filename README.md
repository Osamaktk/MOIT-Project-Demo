# PC Command Center

Demo foundation for the Privatisation Commission Chairman's office, built phase by phase from [`ARCHITECTURE.md`](ARCHITECTURE.md). All seeded people, records, and transaction names are fictional.

## Current status

Phases 0-8 are accepted: Foundation, Decision & Action Register, Transactions and Dashboard, AI Gateway and Assurance, Minutes Assistant, Records Search, Jarvis, Compliance, Spot-checks, and Admin. The repository includes central configuration, database migrations, eight synthetic role personas, authentication/RBAC, audit records, an audited Register workflow, a 17-transaction portfolio, a Friday dashboard with source-record drill-downs, provider/policy/assurance controls, evidence-linked minutes, clearance-filtered search, a grounded records assistant with proposal-only actions, a fortnight compliance calendar, monthly spot-check reconciliation, and user administration. Three full live-extraction browser rehearsals passed in 68.32 s, 71.35 s, and 53.75 s; detailed checks are in `docs/DEMO_SCRIPT.md`. Live audio transcription downloads the configured faster-whisper model on first use.

## Requirements

- Python 3.11 or later
- Node.js 20.19+ or 22.12+ (Vite runtime requirement)
- PowerShell on Windows or Bash on macOS/Linux

## Run locally

1. Install Python 3.11+ and Node.js 20.19+ or 22.12+. Confirm `python --version` and `node --version` work in a new terminal.
2. From the repository root, copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell; `cp .env.example .env` in Bash). Replace `SECRET_KEY` with a private random value of at least 32 characters. The example selects OpenRouter and `nvidia/nemotron-3-super-120b-a12b:free` for extraction; add your key to `OPENROUTER_API_KEY` to draft meeting minutes live. The selected free route advertised JSON/structured-output support and zero token pricing in the OpenRouter catalogue on 2026-10-17. Verify the model ID from `backend/` with `python scripts/verify_openrouter_models.py`. Keep credentials in `.env` only.
3. Create and initialize the backend from the repository root:

   ```powershell
   cd backend
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # macOS/Linux, use: source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   alembic upgrade head
   python -m app.db.seed
   uvicorn app.main:app --reload
   ```

4. In a second terminal, install and start the frontend:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

The API is at <http://localhost:8000>, OpenAPI docs at <http://localhost:8000/docs>, and the UI at <http://localhost:5173>.

On Windows, `scripts/run_backend.ps1` applies migrations and starts the API, `scripts/run_frontend.ps1` starts Vite, and `scripts/seed.ps1` creates missing demo records. On macOS/Linux, use the matching `.sh` scripts. The seed command is idempotent for an existing demo database; it does not reset or delete records. A clean setup downloads Python packages and npm packages, so allow network access during installation. The documented setup sequence is designed to complete in under 20 minutes on a supported machine with those runtimes installed.

If PowerShell blocks local activation scripts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate `.venv` again. On macOS/Linux, replace the Windows activation command with the Bash command in the code comment.

All eight fictional roles use the demo-only password `Demo-Only-Change-Me-2026!`. Their emails are `minister@demo.example`, `cos@demo.example`, `director.td@demo.example`, `liaison@demo.example`, `legal@demo.example`, `analyst@demo.example`, `data.coordinator@demo.example`, and `admin@demo.example`. Never reuse these credentials outside a local synthetic demo.

## Scripts

- `scripts/run_backend.ps1` / `scripts/run_backend.sh`: apply migrations and run FastAPI.
- `scripts/run_frontend.ps1` / `scripts/run_frontend.sh`: run Vite.
- `scripts/seed.ps1` / `scripts/seed.sh`: seed the demo personas.
- `backend/scripts/benchmark_register_1000.py`: benchmark the Register handler and serialization against an isolated synthetic SQLite dataset (up to 1,000 rows); this excludes HTTP and browser rendering.

## Configuration and data

Settings come from `.env`; see `.env.example`. Runtime data is written under `data/` and is ignored by Git. Do not place confidential or real office data in this demo.

The API attaches an `X-Request-ID` to each response and emits a JSON request log with the method, path, status, and duration; request bodies, query strings, passwords, and provider keys are not logged. Login requests are limited to 60 per client per minute and AI-heavy routes to 30 per client per minute. These in-memory limits suit the documented single-process local demo; use a shared limiter before multi-worker deployment.

Use the language control on the login page or app header to switch English/Urdu. The choice is saved in the browser and updates the document language and text direction. Shared navigation, login, dashboard, Decision & Action Register, Transactions, Decisions, Engagements, Compliance, AI Assurance, Administration, Records Search, Jarvis, Review Queue, and Meetings UI copy are translated in English and Urdu. The Register supports page sizes through 1,000 with virtualized rendering; an isolated production-build headless Edge run measured a 239 ms median (309 ms max) at 1,000 rows. The automated browser contrast and RTL review is recorded in [docs/ACCESSIBILITY_REVIEW.md](docs/ACCESSIBILITY_REVIEW.md); manual screen-reader and all-state review remains open.

AI provider and model-role mappings are environment settings (`AI_PROVIDER_*`, `MODEL_*`) and are never hard-coded. Before using OpenRouter, set the required model roles and verify them against its live catalogue from `backend/` with `python scripts/verify_openrouter_models.py`. The upstream catalogue is documented at <https://openrouter.ai/docs/api/api-reference/models/get-models>. `AI_ZONE_MODE=local` selects the configured OpenAI-compatible local endpoint without code changes. Confidential prompts are blocked from cloud providers except for explicitly enabled synthetic demo records; each attempt is recorded in `ai_runs`.

Meeting audio uploads are limited to 25 MB. The first faster-whisper transcription downloads the configured model (`STT_MODEL_SIZE`, default `small`) and runs on CPU; PyAV decodes supported audio formats, so ffmpeg is optional. The repository's included English sample is synthetic and can be reviewed without downloading a speech model.

Meeting processing runs as a FastAPI background task. The API returns a job ID; clients can poll `GET /api/v1/jobs/{id}` or read progress events from `GET /api/v1/jobs/{id}/events`. Job access follows meeting visibility, and the meeting workspace displays progress until the draft is ready. These in-process tasks match the single-process demo deployment and do not survive a server restart.

`DEMO_MODE_CACHE=false` is the default. When enabled, the Minutes Assistant saves the most recent successful structured extraction for a synthetic meeting under `data/demo_cache/`, tied to a SHA-256 fingerprint of its transcript. If a later provider request fails, an exact transcript match can reuse that saved result. Policy blocks and suspended tools remain fail-closed. Cache-backed results receive a distinct assurance-log row (`minutes-cache-v1`); the cache is a presentation safeguard, not a substitute for review or approval.

Records Search stores document chunks in SQL and vectors in a persistent local Chroma database under `data/chroma/`. For multilingual local semantic search, install `backend/requirements-embeddings.txt`, set `EMBEDDING_MODEL` to a Sentence Transformers model that supports Urdu and English (for example, `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`), then reingest documents so they use the configured vector space. The model downloads on first use. Without that optional model, the offline demo uses stable local feature-hash vectors so the clean setup does not download a large ML runtime. To use hosted embeddings instead, configure `MODEL_EMBEDDING` and the embedding provider in `.env`; indexing and search route through the AI Gateway and its classification rules. The runtime Chroma directory is ignored by Git and can be recreated by reseeding/reingesting source documents.

## Phase verification

The timed 15-minute run-of-show and rehearsal checklist are in [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md). Acceptance checks and implementation notes for completed phases are tracked in [`docs/PROGRESS.md`](docs/PROGRESS.md). Run backend checks from `backend/` with `python -m pytest` and the frontend production build from `frontend/` with `npm run build` when dependencies are installed.
