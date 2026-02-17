# AI-OPS-22 Privacy Audit (Citizen Preferences)

Date: 2026-02-17  
Sprint: `AI-OPS-22`

## Contract (What Must Be True)
- Preferences are local-first by default (stored in `localStorage`).
- Preferences are never written into URL query params automatically.
- If a share link is generated, it is explicit opt-in and uses the URL fragment (`#...`), not query (`?...`).

Reference:
- `AGENTS.md` (Privacy exception under Citizen-First rules)
- Implementation: `ui/citizen/index.html`

## Checks
1) Local-first storage key exists
- Key: `vclc_citizen_prefs_v1`
- Evidence: `docs/etl/sprints/AI-OPS-22/evidence/alignment-privacy-grep.txt`

2) URL writer does not include prefs in query params
- Evidence snippet: `docs/etl/sprints/AI-OPS-22/evidence/writeUrlState-snippet.txt`

3) Share link generation uses fragment only
- Expected format: `#prefs=v1:<payload>`
- Evidence: `docs/etl/sprints/AI-OPS-22/evidence/alignment-privacy-grep.txt`

## Verdict
Verdict: PASS (by code inspection + grep evidence; no server-side preference collection exists in this repo).

