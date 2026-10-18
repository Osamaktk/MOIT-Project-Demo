# MoITT Command Center: Phase 2 intake rehearsal

This run validates document intake from upload through the Minister's dashboard. Live OpenRouter extraction is required; mocked tests do not count as a rehearsal.

## Start locally

Open two PowerShell terminals in the repository root.

Backend terminal:

```powershell
$env:MOITT_PYTHON = 'C:\Users\osama\Envs\agent\Scripts\python.exe'
.\scripts\run_backend.ps1
```

Frontend terminal:

```powershell
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173`. The backend launcher runs migrations and seeds the local synthetic data before showing API logs. Keep both terminals visible while rehearsing. Never paste an API key into chat or a terminal transcript; keep it only in the ignored `backend/.env` file.

Before starting, check that `OPENROUTER_API_KEY` and the extraction model are configured, then run the provider check from the backend terminal:

```powershell
& $env:MOITT_PYTHON backend/scripts/verify_openrouter_models.py
```

Use the local sample files in `backend/samples/ministry/`. They are ignored by Git and must not be committed. Select `internal` classification for these ministry minutes unless their handling rules require a stricter classification. Confidential documents must remain local until an administrator grants per-document cloud permission.

## Run of show

| Time | Screen and action | Acceptance cue |
|---|---|---|
| 0:00-1:00 | Sign in as Chief of Staff and open Today. | The page has a clear Add document path and shows MoITT projects and actions. |
| 1:00-2:00 | Upload the IT Park Islamabad minutes. | Duplicate detection and source preview work; extraction returns a useful error if the provider is unavailable. |
| 2:00-5:00 | Review meeting details, participants, decisions, summary, actions, commitments, owners, projects and deadlines against the source. | Quotes are verifiable; uncertain rows are flagged; unknown project or organisation can be created; source page is shown. |
| 5:00-6:00 | Confirm the review. Open Today and the IT Park project. | New actions and commitments appear with their source, serials and updated project health reason. The document is linked and searchable. |
| 6:00-7:00 | Sign out and sign in as Minister. Upload the Asaan Khidmat Centres minutes. | The Minister can upload and review their own document. No administrator approval is needed for internal-classified content. |
| 7:00-10:00 | Review and confirm the second minutes file. | Table rows, named people and organisations, original timelines, commitments and project links are reviewable. Unresolved evidence blocks confirmation. |
| 10:00-12:00 | Return to Today and the linked project. Open the confirmed meeting record. | Dashboard counts and health update; the meeting shows its summary, decisions, linked actions and source document. |
| 12:00-15:00 | Upload the synthetic look-alike, confirm it, then upload the same file again. | Confirmation updates the dashboard; duplicate upload links to the existing review instead of adding a second copy. |

## Acceptance record

Do not mark a check passed unless it was observed in the live UI and backend logs.

| Check | Result | Notes |
|---|---|---|
| OpenRouter model verification succeeds without exposing a key | Not run | |
| IT Park sample extracts and confirms through the UI | Not run | |
| Asaan Khidmat sample extracts and confirms through the UI | Not run | |
| Synthetic look-alike extracts and confirms through the UI | Not run | |
| Confirmed records update dashboard and project health | Not run | |
| Confirmed meeting exposes decisions, linked actions and source | Not run | |
| Duplicate upload points to the existing review | Not run | |
| No browser console errors or unhandled backend errors | Not run | |

**Phase 2 status:** acceptance remains in progress until every check above passes. Record the date, operator and elapsed time here after a real rehearsal.

| Date/time | Operator | Duration | Outcome / follow-up |
|---|---|---|---|
| Not run | | | |

## Recovery

- If provider setup fails, keep the document in review and capture the backend error. Do not describe mocked extraction as live AI.
- If OCR reports a missing Tesseract executable, install Tesseract and ensure it is available on `PATH`, then retry the upload.
- Do not bypass quote verification, reviewer flags, classification rules or the AI kill switch to force confirmation.
- Keep synthetic demo data separate from the real sample PDFs. Do not commit uploads, generated output, logs or local credentials.
