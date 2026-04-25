# AI-OPS-263 - Contrato de diversidad efectiva por disponibilidad (`programas_partidos`)

## Objetivo
Evitar falsos fallos del guardrail de muestra dedupe cuando un partido no alcanza el objetivo nominal de diversidad por limite real de evidencia disponible.

## Cambios implementados
- `scripts/export_programas_support_precision_sample.py`
  - El resumen ahora expone disponibilidad real por partido: `available_unique_by_party`.
  - Se añade contrato efectivo por partido:
    - `effective_min_unique_per_party_by_party = min(min_unique_per_party, available_unique_by_party[party])`
    - check nuevo `min_unique_per_party_effective_met`.
  - Se añaden campos operativos:
    - `parties_below_effective_min_unique`
    - `parties_capped_by_available_unique`
  - En `--strict`, el fail se decide por cobertura requerida + contrato efectivo (no por umbral nominal imposible).
- `tests/test_export_programas_support_precision_sample.py`
  - Cobertura de disponibilidad por partido y comportamiento cap-aware (`VOX` capped).

## Corridas reales (staging)
DB: `etl/data/staging/politicos-es.db`

1) Guardrail estricto con objetivo nominal alto
- Comando: `python3 scripts/export_programas_support_precision_sample.py ... --dedupe-key excerpt_norm+source_url --min-unique-per-party 10 --strict`
- Resultado: `status=ok`, `strict rc=0`
- Métricas clave:
  - `unique_by_party.VOX=5`
  - `available_unique_by_party.VOX=5`
  - `min_unique_per_party=10`
  - `effective_min_unique_per_party_by_party.VOX=5`
  - `parties_capped_by_available_unique=[VOX]`
  - `checks.min_unique_per_party_met=false`
  - `checks.min_unique_per_party_effective_met=true`

2) Validación de lane `just` en mismo modo
- Comando: `DB_PATH=etl/data/staging/politicos-es.db PROGRAMAS_PRECISION_SAMPLE_DEDUPE_KEY=excerpt_norm+source_url PROGRAMAS_PRECISION_SAMPLE_MIN_UNIQUE_PER_PARTY=10 just parl-check-programas-support-precision-sample`
- Resultado: `status=ok`, `strict rc=0`.

## Evidencia adicional de gap real VOX
- `support_rows_total=16`, `unique_excerpt_norm_320_total=5`, `unique_excerpt_norm_full_total=6`.
- Toda la señal `support` de VOX está concentrada en una única URL programática.

## Evidencia
- `docs/etl/sprints/AI-OPS-263/evidence/programas_support_precision_sample_dedup_min10_cap_summary_latest.json`
- `docs/etl/sprints/AI-OPS-263/evidence/programas_support_precision_sample_dedup_min10_cap_just_summary_latest.json`
- `docs/etl/sprints/AI-OPS-263/evidence/programas_support_precision_sample_dedup_min10_cap_stdout_latest.txt`
- `docs/etl/sprints/AI-OPS-263/evidence/just_parl_check_programas_support_precision_sample_min10_overrides_20260228_latest.txt`
- `docs/etl/sprints/AI-OPS-263/evidence/unittest_programas_precision_sample_cap_20260228.txt`
- `docs/etl/sprints/AI-OPS-263/evidence/programas_vox_support_unique_overview_20260228.csv`
- `docs/etl/sprints/AI-OPS-263/evidence/tracker_status_post_ai_ops_263_latest.log`
- `docs/etl/sprints/AI-OPS-263/exports/programas_vox_support_unique_by_url_20260228.csv`
- `docs/etl/sprints/AI-OPS-263/exports/programas_support_precision_sample_dedup_min10_cap_latest.csv`
- `docs/etl/sprints/AI-OPS-263/exports/programas_support_precision_sample_dedup_min10_cap_just_latest.csv`
