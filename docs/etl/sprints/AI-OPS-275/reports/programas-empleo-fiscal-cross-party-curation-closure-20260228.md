# AI-OPS-275 - Curacion transversal de snippets fiscales en Empleo

## Objetivo
Cerrar la fila TODO de curacion transversal detectada en AI-OPS-274 para `programas_partidos` en `concern:v1:empleo` (casos de `support` con lexico fiscal y sin ancla laboral).

## Cambio aplicado
- `etl/parlamentario_es/declared_stance.py`:
  - `backfill_declared_stance_from_topic_evidence` ahora carga `topic_key` (`topics.canonical_key`).
  - Nuevo guardrail topic-aware para `programas_partidos`:
    - si `topic_key='concern:v1:empleo'`
    - y la inferencia viene de `programa_policy_proposal`
    - pero el excerpt no contiene ancla laboral,
    - se bloquea la asignacion `support` (se trata como `no_signal`, permitiendo reconciliacion a `unclear`).
  - Nuevos anchors laborales: `empleo|emprego|ocupaci*|trabaj*|traballo|laboral*|paro|salari*|treball*`.
- `tests/test_parl_declared_stance.py`:
  - Regresion negativa: fiscalidad sin ancla laboral en tema Empleo se reconcilia a `unclear`.
  - Regresion positiva: con ancla laboral en tema Empleo mantiene `support`.
- `justfile`:
  - `PROGRAMAS_EMPLEO_FISCAL_AUDIT_PARTIES` pasa a default cross-party: `BNG,CCa,Compromis,EAJ-PNV,VOX`.
  - outputs por defecto del lane mueven a AI-OPS-275.

## Ejecucion
1. Recompute de stance y posiciones:

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db etl/data/staging/politicos-es.db --source-id programas_partidos --min-auto-confidence 0.62 --reconcile-no-signal
python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db etl/data/staging/politicos-es.db --source-id programas_partidos --as-of-date 2026-02-28
python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db etl/data/staging/politicos-es.db --as-of-date 2026-02-28
```

2. Auditoria cross-party strict:

```bash
just parl-check-programas-empleo-fiscal-snippets-audit
```

## Resultado de cierre
- Auditoria cross-party: `status=ok`.
- `suspicious_support_rows`: `4 -> 0`.
- Delta Compromis (`concern:v1:empleo` + `fiscalitat`): `support 4 -> 0`, `unclear 0 -> 4`.
- Gate declarado sigue verde: `declared.gate.passed=true`, `review_pending=0`.
- Tracker gate verde: `mismatches=0`, `done_zero_real=0`.

## Evidencia
- `docs/etl/sprints/AI-OPS-275/evidence/programas_backfill_declared_stance_reconcile_empleo_fiscal_cross_party_latest.json`
- `docs/etl/sprints/AI-OPS-275/evidence/programas_backfill_declared_positions_empleo_fiscal_cross_party_latest.json`
- `docs/etl/sprints/AI-OPS-275/evidence/programas_backfill_combined_positions_empleo_fiscal_cross_party_latest.json`
- `docs/etl/sprints/AI-OPS-275/evidence/programas_empleo_fiscal_snippets_audit_cross_party_latest.json`
- `docs/etl/sprints/AI-OPS-275/exports/programas_empleo_fiscal_snippets_audit_cross_party_latest.csv`
- `docs/etl/sprints/AI-OPS-275/evidence/programas_empleo_fiscal_snippets_audit_cross_party_delta_vs_ai_ops_274_latest.json`
- `docs/etl/sprints/AI-OPS-275/exports/programas_empleo_fiscal_compromis_candidates_post_fix_latest.csv`
- `docs/etl/sprints/AI-OPS-275/evidence/programas_declared_status_post_empleo_fiscal_cross_party_fix_latest.json`
- `docs/etl/sprints/AI-OPS-275/evidence/quality_declared_programas_post_empleo_fiscal_cross_party_fix_latest.json`
- `docs/etl/sprints/AI-OPS-275/evidence/tracker_status_post_latest.log`
- `docs/etl/sprints/AI-OPS-275/evidence/unittest_parl_declared_stance_empleo_anchor_fix_latest.txt`
- `docs/etl/sprints/AI-OPS-275/evidence/unittest_programas_empleo_fiscal_snippets_audit_latest.txt`
