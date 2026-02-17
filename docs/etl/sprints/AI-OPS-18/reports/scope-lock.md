# AI-OPS-18 Scope Lock (Programas Partidos)

Date: 2026-02-17  
Sprint: `AI-OPS-18`

## Objective Boundary
This sprint is scoped to delivering the **first reproducible `programas_partidos` slice** end-to-end enough to move tracker line `74` out of `TODO`, while preserving strict gate/parity invariants.

Primary tracker target:
- `docs/etl/e2e-scrape-load-tracker.md:74` (Posiciones declaradas (programas))

Non-negotiable invariants:
- strict tracker gate stays green (`just etl-tracker-gate`)
- status export parity remains `overall_match=true`

## What Counts As Visible Progress (G3)
Tracker line `74` must move from `TODO` to one of:
- `PARTIAL` with evidence-backed, reproducible pipeline producing non-zero outputs, or
- `DONE` (preferred) if the full slice lands cleanly within sprint capacity.

## Definition: PARTIAL vs DONE (This Sprint)
### PARTIAL (minimum acceptable)
- A deterministic, sample-driven pipeline exists for `source_id=programas_partidos`:
  - ingest reads a manifest from `etl/data/raw/samples/programas_partidos_sample.csv` (no network required)
  - writes traceable `source_records`
  - extracts program text into `text_documents` (or equivalent canonical storage)
  - emits at least some `topic_evidence` rows linked via `source_record_pk`
- Evidence-based metrics show `programas_*` totals are **non-zero** and reproducible from the sample.

### DONE (target)
Everything in PARTIAL, plus:
- declared stance extraction produces non-zero signal (`programas_declared_with_signal > 0`) with explicit reasons/confidence
- positions are materialized into `topic_positions` (declared/combined as appropriate) and are navigable in explorers
- tracker row updated to `DONE` with commands and evidence paths

## Explicit Non-Goals (Anti-scope-creep)
- No new upstream connectors outside `programas_partidos`.
- No non-reproducible browser automation (no headful flows as default).
- No “AI summarization” claims in the product layer; outputs must be evidence-linked.
- No destructive schema migrations.

## Escalation Rules (Anti-Loop)
- If upstream fetching is blocked (WAF/403/contract drift), do **not** burn the sprint:
  - keep the sample-driven from-file pipeline as the controllable lane
  - record a single probe with evidence, then stop unless a new lever exists (credentials/endpoint change/approved bypass)

## Must-Pass Gates (G1-G6)
- `G1 Integrity`: `PRAGMA foreign_key_check` returns zero rows.
- `G2 Queue health`: pending reviews for `programas_partidos` are controlled (`pending_ratio <= 0.35`).
- `G3 Visible progress`: tracker line `74` moves out of `TODO` (evidence-backed).
- `G4 Signal floor`: `programas_declared_with_signal > 0` (even if small) with reason breakdown.
- `G5 Strict gate/parity`: strict gate exit `0` and status parity `overall_match=true`.
- `G6 Workload evidence`: FAST wave artifacts demonstrate deterministic throughput work happened (not just planning).

## Primary Deliverables
- Source contract + sample manifest
- Ingest + text extraction pipeline for `programas_partidos`
- Deterministic tests + idempotence
- Tracker reconciliation for line `74`
