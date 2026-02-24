# AI-OPS-163 — Responsabilidad por fragmento: evidencia de voto (`congreso_vote`/`senado_vote`)

Fecha: 2026-02-24 (UTC)

## Objetivo del slice

Extender la cadena de evidencia parlamentaria de `Responsabilidad por fragmento normativo` desde diarios (`congreso_diario`/`senado_diario`) hacia actos de voto (`congreso_vote`/`senado_vote`) sin abrir dependencias externas nuevas.

## Implementación

- Nuevo backfill reproducible: `scripts/backfill_sanction_norms_vote_evidence.py`.
- Matching conservador (evitar sobreatribución):
  - prioridad 1: `BOE-A-*` explícito en título de voto/iniciativa;
  - prioridad 2: reglas de referencia legal+frase para normas sancionadoras (p. ej. `Ley 58/2003 + General Tributaria`, `LO 4/2015 + seguridad ciudadana`, `RDL 6/2015 + tráfico/seguridad vial`).
- Materialización idempotente en `legal_fragment_responsibility_evidence` con tipos:
  - `congreso_vote`
  - `senado_vote`
- Trazabilidad por fila en `raw_payload` (`match_method`, `match_confidence`, `matched_terms`, `vote_event_id`, `initiative_id`).
- Observabilidad extendida en `scripts/report_sanction_norms_seed_status.py`:
  - `responsibility_evidence_items_parliamentary_vote_total`
  - `responsibilities_with_parliamentary_vote_evidence_total`
  - `responsibilities_missing_parliamentary_vote_evidence`
  - `responsibility_evidence_item_parliamentary_vote_share_pct`
  - `responsibility_parliamentary_vote_coverage_pct`
  - check `responsibility_evidence_vote_chain_started`
- Just lane nuevo:
  - `just parl-backfill-sanction-norms-vote-evidence`

## Corrida de cierre (DB real)

Comando ejecutado:

```bash
DB_PATH=etl/data/staging/politicos-es.db \
SANCTION_NORMS_VOTE_EVIDENCE_OUT=docs/etl/sprints/AI-OPS-163/evidence/sanction_norms_vote_evidence_backfill_20260224T011452Z.json \
just parl-backfill-sanction-norms-vote-evidence
```

Resultado (`20260224T011452Z`):

- `vote_link_rows_scanned_total=8358`
- `vote_events_scanned_total=8357`
- `vote_rows_with_candidate_total=26`
- `candidate_matches_total=26`
- `evidence_inserted=20`
- `evidence_updated=32`
- `by_evidence_type`:
  - `congreso_vote=14`
  - `senado_vote=38`
- `by_boe_id`:
  - `BOE-A-2003-23514=19`
  - `BOE-A-2015-11724=5`
  - `BOE-A-2015-11722=2`

Replay idempotente (`20260224T012020Z`):

- `candidate_matches_total=26`
- `evidence_inserted=0`
- `evidence_updated=52`
- Sin drift de métricas agregadas en status.

## Estado del lane tras backfill

`report_sanction_norms_seed_status.py` (`20260224T011452Z`):

- `status=ok`
- `responsibility_evidence_items_total=37` (antes: 17)
- `responsibility_evidence_items_parliamentary_total=22` (antes: 2)
- `responsibility_evidence_items_parliamentary_vote_total=20`
- `responsibilities_with_parliamentary_evidence_total=8/15` (`53.33%`)
- `responsibilities_with_parliamentary_vote_evidence_total=6/15` (`40.00%`)
- `responsibility_evidence_item_parliamentary_share_pct=0.594595`
- `responsibility_evidence_item_parliamentary_vote_share_pct=0.540541`
- `responsibility_evidence_item_non_seed_source_record_coverage_pct=1.0`
- `responsibility_evidence_vote_chain_started=true`

## Integridad y pruebas

- `PRAGMA foreign_key_check`: `0` violaciones.
- `just parl-test-sanction-norms-seed`: `Ran 19`, `OK`.
- `just parl-test-liberty-restrictions`: `Ran 100`, `OK (skipped=1)`.
- Cola `seed -> non-seed` permanece cerrada:
  - `queue_rows_total=0`.

## Artefactos

- Backfill voto:
  - `docs/etl/sprints/AI-OPS-163/evidence/sanction_norms_vote_evidence_backfill_20260224T011452Z.json`
  - `docs/etl/sprints/AI-OPS-163/evidence/sanction_norms_vote_evidence_backfill_20260224T012020Z.json`
  - `docs/etl/sprints/AI-OPS-163/evidence/just_parl_backfill_sanction_norms_vote_evidence_20260224T011452Z.txt`
- Status lane:
  - `docs/etl/sprints/AI-OPS-163/evidence/sanction_norms_seed_status_20260224T011452Z.json`
  - `docs/etl/sprints/AI-OPS-163/evidence/just_parl_report_sanction_norms_seed_status_20260224T011452Z.txt`
- Queue post-apply:
  - `docs/etl/sprints/AI-OPS-163/evidence/sanction_norms_seed_source_record_upgrade_queue_20260224T011452Z.json`
  - `docs/etl/sprints/AI-OPS-163/exports/sanction_norms_seed_source_record_upgrade_queue_20260224T011452Z.csv`
- Integridad/tests:
  - `docs/etl/sprints/AI-OPS-163/evidence/sqlite_fk_check_20260224T011452Z.txt`
  - `docs/etl/sprints/AI-OPS-163/evidence/just_parl_test_sanction_norms_seed_20260224T011452Z.txt`
  - `docs/etl/sprints/AI-OPS-163/evidence/just_parl_test_liberty_restrictions_20260224T011452Z.txt`
