# AI-OPS-20 Citizen Walkthrough (Manual QA Steps)

Date: 2026-02-17  
Sprint: `AI-OPS-20`

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

## J1 Multi-Concern Selection (Shareable)
1. Open `/citizen/` (no params).
2. In panel (1), click two concerns (example: `Vivienda`, then `Sanidad`).
3. Confirm "Mis preocupaciones (dashboard)" shows removable tags for both.
4. Confirm URL now includes `concerns_ids=vivienda,sanidad`.
5. Open the URL in a new tab and confirm both tags are restored.

## J2 Dashboard View (>=2 concerns)
1. With >=2 concerns selected, switch panel (3) `Vista: mi dashboard`.
2. Confirm:
   - party summary cards render (counts across concerns)
   - each party card includes `Ver top items`
   - audit links exist when available ("Auditar item" / "Evidencia (programa)")

## J3 Party Focus (Shareable)
1. In panel (3), click `Ver top items` on a party card.
2. Confirm:
   - focus chip appears (`foco=...`) and clear button appears
   - panel (2) item rows show a mini stance chip for the focused party
   - URL includes `party_id=<n>`
3. Open the URL in a new tab and confirm party focus is restored.
4. Clear focus via `Salir foco partido` (panel 2) or the clear button in panel (3).

## J4 Method Toggle (Static Multi-Artifact)
1. Switch `Metodo`:
   - `Metodo: hechos (votos)` -> reloads with `computed_method=votes`
   - `Metodo: dichos (intervenciones)` -> reloads with `computed_method=declared`
2. Confirm the status chip `metodo` matches the selected method after reload.

## J5 Backward Compatibility (v2 links)
1. Open a legacy URL like: `/citizen/?concern=vivienda`.
2. Confirm it renders in detail mode and is shareable (URL remains stable).

## J6 Audit Drill-Down (Evidence)
1. In summary mode (no topic selected), click `Auditar item` (or `Auditar top item`).
2. Confirm it opens `../explorer-temas/` with `topic_set_id` and `topic_id` in the URL.
3. Confirm party link in citizen snapshot opens `../explorer-politico/?party_id=<id>` and focuses the party.

