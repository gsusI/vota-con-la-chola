# How This Works (Citizen App)

Sprint: `AI-OPS-17`  
Date: `2026-02-17`

## What You’re Looking At
The citizen page (`/citizen`) is a static view over a bounded JSON snapshot (`citizen.json`).
It is meant to answer: for a given concern, what are the most relevant “items” (topics) and what stance does each party show, with audit links.

## Data Used
The snapshot is exported from the project SQLite DB and is scoped to:
- Congreso (`institution_id=7`)
- Topic set: `topic_set_id=1` (Congreso leg 15 taxonomy)
- As-of date: latest available (or a specified `--as-of-date`)

Underlying evidence is stored in the DB in:
- `topic_evidence` (atomic evidence rows)
- `topic_positions` (computed positions per person/topic/scope)

## What Is Computed
For each topic and party, we compute a party stance by aggregating the positions of party members:
- We keep explicit coverage (`members_with_signal / members_total`) and confidence.
- If coverage is too low, we downgrade to `unclear` (shown as “Incierto”).
- If there is no evidence for the party on that topic, we emit `no_signal` (shown as “Sin senal”).

## What We Do NOT Claim
- Concerns are **navigation tags only**: keyword matches on topic labels (not ML, not “understanding”).
- This does not claim intent, causality, or moral alignment.
- Unknown/no-signal is not imputed or “filled in”.

## How To Audit (Drill-down)
Every topic/stance card links to existing explorers:
- Topic view: `/explorer-temas/?topic_set_id=...&topic_id=...`
- Raw rows: `/explorer/?t=topic_positions...` and `/explorer/?t=topic_evidence...`

Use these links to see concrete rows and evidence behind any summary.
