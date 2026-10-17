# Accessibility and RTL review

Review date: 2026-10-17

## Automated browser review

The production build was reviewed in headless Microsoft Edge with seeded synthetic data.

- A rendered-text contrast scan covered 12 authenticated views in English: Command Center, Register, Review Queue, Meetings, Transactions, TX-A detail, Decisions, Engagements, Compliance, AI Assurance, Records Search, and Administration. After darkening the muted text palette, the scan found no visible text below 4.5:1 for normal text or 3:1 for large text in those states.
- Urdu remained selected after a full page reload. The same 11 CoS views remained `dir="rtl"` at 1440 x 1000 and 390 x 844 with no document-level horizontal overflow. Administration also had no document-level overflow at 390 x 844. Wide data tables stay inside their own scroll containers.
- Noto Nastaliq Urdu loaded in the browser. A post-fix scan across all 12 CoS views found no unnamed visible controls, no exposed Recharts application node, and no uncaught page errors. The Admin view was checked separately as an admin at mobile width; it had no unnamed controls or document overflow. The dashboard stage chart has a translated image label and a translated data-table name; its internal Recharts SVG is hidden from the accessibility tree so it does not create an unlabeled application node. Its stage rows open the corresponding drill-down with Enter and show a 3 px keyboard focus outline.
- A review found and fixed mobile overflow on Compliance, secondary-text contrast failures, the chart's English-only accessible name, and keyboard-inert chart rows.
- A focused keyboard and Urdu pass visited all 12 CoS routes at 390 x 844 after selecting Urdu in the UI. Every route remained RTL without document-level horizontal overflow; visible controls had accessible names and the browser raised no page errors. The command palette opened with Ctrl+K, and the TX-A list entry opened by keyboard using its labelled action button.
- A production layout issue let the Meetings review panes extend beneath Jarvis at desktop width. A container-width rule now keeps approval actions inside the meeting column. The transaction list also has a named keyboard-operable open action, with translated accessible names for its filters and update form.

## Limits and remaining review

The contrast scan evaluates visible text and computed background colors for the seeded screen states. Browser checks do not certify WCAG conformance or cover every assistive-technology combination. Screen-reader testing and a full review of every dialog, empty/error state, and keyboard sequence remain open.

Three fresh, end-to-end browser rehearsals with live extraction passed on 2026-10-17. Each completed the full scripted path in under 72 seconds with 17 transactions, reconciled dashboard drill-downs, two reviewed minutes actions, cited Records Search and Jarvis, assurance, compliance, and admin readiness. Durations and per-run results are recorded in `DEMO_SCRIPT.md`. The initial paid-model attempt returned HTTP 402; subsequent live extraction and all three rehearsals used the configured no-cost NVIDIA route.
