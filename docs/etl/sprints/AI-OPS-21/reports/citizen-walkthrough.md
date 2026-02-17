# AI-OPS-21 Citizen Walkthrough (Coverage + Coherence)

Date: 2026-02-17  
Sprint: `AI-OPS-21`

## Pre-req (Build)
Generate the GH Pages static site locally:
```bash
just explorer-gh-pages-build
```

Run a local static server (recommended; avoid `file://` fetch/CORS issues):
```bash
cd docs/gh-pages
python3 -m http.server 8000
```

Open:
- `http://localhost:8000/citizen/`

## J1 Coverage + Coherence View (Shareable)
1. Open `/citizen/`.
2. In panel (1), click two concerns (example: `Educacion`, `Seguridad y justicia`).
3. In panel (3), switch `Vista: coherencia`.
4. Confirm:
   - URL includes `concerns_ids=...` and `view=coherence`
   - `Metodo` selector is disabled (coherence compares votos vs dichos)
   - `Filtro` (stance) is disabled (not applicable in coherence view)
   - coverage lines show `votos any/clear`, `dichos any/clear`, `combinado any/clear`, plus `comparables` and `mismatch`

## J2 Party Coherence Cards + Audit Links
1. In coherence view, locate a party with `comparables > 0`.
2. Confirm the card shows:
   - comparables ratio bar
   - mismatch ratio bar (of comparables)
   - an audit example section (topic label + votes/dichos chips)
3. Click `Auditar tema` and confirm it opens `../explorer-temas/` with `topic_set_id` + `topic_id`.
4. Click `Votos (SQL)` and `Dichos (SQL)` and confirm links open Explorer SQL with method-specific filters.

## J3 Party Focus (Topic List Chips)
1. Click `Foco partido` on a party card.
2. Confirm:
   - focus chip appears (`foco=...`) and URL includes `party_id=<n>`
   - panel (2) item rows show `v:` and `d:` mini chips (and `mismatch` tag when comparable+different)
3. Clear focus via `Salir foco partido` or `Salir foco` button in panel (3).

## Back/Forward Restore
1. Switch between `Vista: detalle`, `Vista: mi dashboard`, and `Vista: coherencia`.
2. Use browser Back/Forward and confirm the view state restores correctly (including selected concerns and party focus).

