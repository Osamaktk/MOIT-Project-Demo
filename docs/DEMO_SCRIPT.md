# PC Command Center: 15-minute demonstration

## Before the meeting

- Complete the [README setup](../README.md#run-locally), seed a fresh synthetic database, and start the API and frontend.
- Add an OpenRouter API key to `.env` as `OPENROUTER_API_KEY`, then verify the configured extraction model from `backend/` with `python scripts/verify_openrouter_models.py`. The configured extraction model is `nvidia/nemotron-3-super-120b-a12b:free`; a live structured extraction of the synthetic sample succeeded during rehearsal preparation. Verify the model ID before presenting. `DEMO_MODE_CACHE` is optional, defaults off, and only helps after a successful synthetic sample extraction has been cached.
- Confirm the seeded TX-A documents, sample meeting/audio/transcript, compliance items, and all eight role accounts are visible.
- Sign in as `cos@demo.example`. The password is the demo-only value documented in the README.
- Keep the browser at a readable presentation size. Avoid presenting the API docs or developer tools.

## Run of show

| Time | Screen and action | Narration and acceptance cue |
|---|---|---|
| 0:00–1:00 | Sign in and open **Command Center**. | Explain that all people, records, and transaction names are synthetic. Point to the active AI zone badge and the one-page Friday view. |
| 1:00–3:00 | Review the portfolio tiles, stage distribution, milestones, decisions, overdue actions, and engagements. Open a KPI and a TX-A milestone. | The portfolio contains 17 records across the configured stages. Open a drill-down to show the exact underlying rows and the source timestamp. |
| 3:00–4:00 | Open **Register**, filter to overdue actions, open one row, and show its owner, deadline, and audit history. | Only approved entries feed the totals. A named officer and calendar deadline are visible on the record. |
| 4:00–8:00 | Open **Meetings & Minutes** and select **Synthetic TX-A transaction review**. Play the sample clip, select an action to jump to transcript evidence, and process the sample if no draft exists. Review both proposed actions, approve them, then issue the minutes and open the DOCX export. | Each proposed action has a transcript quote and timestamp. The actions have no Register serial until approved; minutes cannot be issued until all actions are resolved. A cache-backed result is identified in the assurance log. |
| 8:00–10:00 | Open **Records Search** and ask: “When is the next TX-A diligence milestone?” Open a citation and then its source. | The answer is tied to a visible indexed document and excerpt. Search declines questions when permitted records provide no evidence. |
| 10:00–12:00 | Ask Jarvis: “What is the status of TX-A?” Then ask: “Create an action for the Liaison to confirm the next TX-A milestone by 2026-10-30.” Review the unnumbered proposal and approve it from its card. | The status answer cites transaction data. The action is only a proposal until a reviewer approves it; approval assigns its Register serial. |
| 12:00–13:00 | Open **Compliance** and review the next-fortnight panel. | Show the due date, owner, status, and reference. Legal or CoS can update an item, and the change is audited. |
| 13:00–14:00 | Open **AI Assurance**, review the run log, generate the current monthly sample if one does not exist, and reconcile it with a short source finding. | Show tool, model, zone, outcome, reviewer, and the saved spot-check finding. Point out that suspended tools fail closed. |
| 14:00–15:00 | Sign out and sign in as `admin@demo.example`; open **Administration** and show system readiness and role controls. Close on the Command Center. | User management is restricted to admin. The health view reports configuration/readiness without exposing secret values. |

## Rehearsal checklist

Run the complete sequence three times in a row before presenting. For each rehearsal, record elapsed time and mark each item:

| Check | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| API and UI are ready; login works for the selected roles | [x] | [x] | [x] |
| Dashboard shows 17 synthetic transactions; all four KPI drill-down totals match | [x] | [x] | [x] |
| Overdue Register row opens with audit history | [x] | [x] | [x] |
| Sample meeting produces a live draft with evidence; actions resolve; minutes issue and DOCX opens | [x] | [x] | [x] |
| Records Search returns citations and opens a cited source excerpt | [x] | [x] | [x] |
| Jarvis cites TX-A and creates an unnumbered proposal that can be reviewed | [x] | [x] | [x] |
| Fortnight compliance items and saved spot-check findings are visible | [x] | [x] | [x] |
| Admin readiness and user-management screens load for admin | [x] | [x] | [x] |
| No uncaught browser errors or real data appear | [x] | [x] | [x] |
| Total time is 15 minutes or less | [x] | [x] | [x] |

Record date, operator, total time, and any failure below. Fix the issue and repeat all three runs after a failed check; do not mark an unperformed rehearsal complete.

| Run | Date/time | Operator | Duration | Issues / follow-up |
|---|---|---|---|---|
| 1 | 2026-10-17 | Automated browser (Edge) | 68.32 s | Passed: 17 transactions; 4 KPI totals reconciled; 5 citations; 2 minutes actions; 0 page errors. |
| 2 | 2026-10-17 | Automated browser (Edge) | 71.35 s | Passed: 17 transactions; 4 KPI totals reconciled; 5 citations; 2 minutes actions; 0 page errors. |
| 3 | 2026-10-17 | Automated browser (Edge) | 53.75 s | Passed: 17 transactions; 4 KPI totals reconciled; 5 citations; 2 minutes actions; 0 page errors. |

## Recovery during a presentation

- If an API request fails, use the visible retry control or reload the page after checking the two local processes.
- If live minutes drafting cannot reach its provider, retry once. With `DEMO_MODE_CACHE=true`, a prior successful result for the same synthetic transcript may be reused and is visibly distinguished in the AI run log. If no matching cache exists, explain the provider setup dependency and continue with the source transcript and existing records.
- Do not disable the assurance kill switch or classification policy to get past a failure. A suspended or policy-blocked request must remain blocked.
- If the seeded database is no longer in the expected presentation state, stop and restore a known synthetic demo snapshot using the operator's normal file backup procedure; never edit rows directly during the presentation.
