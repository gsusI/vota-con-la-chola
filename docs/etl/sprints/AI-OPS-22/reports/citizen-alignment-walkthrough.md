# AI-OPS-22 Citizen Walkthrough (Alignment View)

Date: 2026-02-17  
Sprint: `AI-OPS-22`

## Goal
Demonstrate the new citizen flow:
- set local preferences on concrete topics
- see transparent match/mismatch/unknown per party (with coverage)
- audit via explorer links

## Build + Serve (Local)
Build GH Pages output:
```bash
just explorer-gh-pages-build
```

Serve:
```bash
cd docs/gh-pages
python3 -m http.server 8000
```

Open:
- `http://localhost:8000/citizen/?view=alignment`

## Quick Start (Using Sample Prefs)
Use the deterministic sample:
- `docs/etl/sprints/AI-OPS-22/exports/prefs_sample_v1.json`

Option A (Import JSON)
1. Open alignment view.
2. Click `Importar JSON`.
3. Select `docs/etl/sprints/AI-OPS-22/exports/prefs_sample_v1.json`.
4. Confirm you now see:
   - `prefs=5` in the header
   - party cards with `match / mismatch / unknown / coverage`

Option B (Fragment Share Link)
Open this URL (prefs in fragment):
- `http://localhost:8000/citizen/?view=alignment#prefs=v1:1=s,2=o,4=s,5=o,6=s`

## Setting a Preference (Manual)
1. Choose a concern (col 1), then click a topic (col 2).
2. In col 3 ("Tema seleccionado"), click:
   - `Yo: a favor` or `Yo: en contra`
3. Confirm the preference chip updates and the party summary updates.

## Auditing (Evidence Drill-Down)
From any party card:
- Click `Auditar mismatch` (if present) to open `Temas` for a concrete topic.
- Click `Auditar match` (if present) to open `Temas` for a concrete topic.

From the focused-party drill-down list:
- Click `Temas` or `SQL` for a specific topic to inspect the underlying rows.

## Privacy Notes
- Preferences are stored locally in your browser (`localStorage`) by default.
- Preferences are not written into URL query params automatically.
- Share links include preferences only in the URL fragment (`#prefs=...`).

