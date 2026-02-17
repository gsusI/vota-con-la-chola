# AI-OPS-17 Citizen Walkthrough (Manual QA Steps)

Date: 2026-02-17  
Sprint: `AI-OPS-17`

## Pre-req (Build)
Generate the GH Pages static site locally:
```bash
just explorer-gh-pages-build
```

Open the citizen app:
- `docs/gh-pages/citizen/index.html` (local file), or
- publish to GH Pages and open `/citizen/`.

## J1 Quick Answer (Concern -> Party Summary)
1. Open `/citizen`.
2. In panel (1) "Preocupacion", click a concern (example: `Vivienda`).
3. Confirm panel (3) shows a **party summary list** (no `topic_id` selected):
   - chips show method label (e.g. "Posicion (combinada)" or "Hechos (votos)")
   - each party card shows coverage + confidence bars and stance chip
   - each card includes an "Auditar top item" link (or explicitly shows "sin audit link" if absent)

## J2 Drill Down (Party -> Top Items)
1. In panel (3), click "Ver top items" on a party card.
2. Confirm:
   - focus chip appears in panel (2) controls ("foco ...")
   - each item row in panel (2) shows a mini stance chip for the focused party
3. Click "Salir foco partido" (panel 2) or "Salir foco" (panel 3) to clear focus.

## J3 Audit (Evidence, No Black Box)
1. In summary mode (no topic selected), click "Auditar top item".
2. Confirm it opens `../explorer-temas/` for a concrete topic.
3. In panel (2), click "Ver en Temas" and "Posiciones (SQL)" on an item row.
4. Confirm both targets exist and load (static pages; queries are encoded in the URL).

## Regression Check (Existing Compare Mode)
1. Click any item in panel (2).
2. Confirm panel (3) switches to per-topic compare mode (party cards + KPI grid).

## Navigation Check (Back/Forward)
1. Select a topic (so URL includes `topic_id=...`).
2. Click "Ver top items" (party focus clears topic selection).
3. Press browser Back and confirm it returns to the prior topic view.

