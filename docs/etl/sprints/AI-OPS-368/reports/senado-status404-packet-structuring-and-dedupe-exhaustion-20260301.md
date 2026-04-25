# AI-OPS-368 — Structuración de cola Senado `status=404` + dedupe canónico

## Objetivo
Crear un paquete operacional actualizado y reproducible para la cola residual Senado, priorizando cohortes con mayor impacto y evitando reprocesar URLs ya usadas en packets previos.

## Comandos ejecutados
```bash
python3 scripts/report_senado_waf_block_profile.py \
  --db etl/data/staging/politicos-es.db \
  --only-linked-to-votes \
  --sample-limit 25 \
  --out docs/etl/sprints/AI-OPS-368/evidence/senado_waf_block_profile_20260301T103942Z.json

python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-actionable-missing \
  --only-linked-to-votes \
  --only-status 404 \
  --format csv \
  --out docs/etl/sprints/AI-OPS-368/exports/senado_status404_actionable_pool_20260301T103942Z.csv

python3 scripts/export_senado_retry_packet_only_dedup.py \
  --pool-csv docs/etl/sprints/AI-OPS-368/exports/senado_status404_actionable_pool_20260301T103942Z.csv \
  --packet-csv-glob 'docs/etl/sprints/AI-OPS-3*/exports/senado_*packet*.csv' \
  --packet-csv-glob 'docs/etl/sprints/AI-OPS-3*/exports/senado_archive_gap_urls_*.csv' \
  --max-rows 80 \
  --strict-min-fresh-rows 0 \
  --out docs/etl/sprints/AI-OPS-368/evidence/senado_status404_fresh_packet_summary_20260301T103942Z.json \
  --csv-out docs/etl/sprints/AI-OPS-368/exports/senado_status404_fresh_packet_20260301T103942Z.csv \
  --used-urls-out docs/etl/sprints/AI-OPS-368/evidence/senado_status404_used_urls_20260301T103942Z.txt \
  --used-packet-refs-out docs/etl/sprints/AI-OPS-368/evidence/senado_status404_used_packet_refs_20260301T103942Z.txt

python3 scripts/export_senado_waf_cohort_packets.py \
  --db etl/data/staging/politicos-es.db \
  --only-linked-to-votes \
  --cohort-top-n 6 \
  --max-urls-per-cohort 20 \
  --max-total-rows 120 \
  --max-zero-doc-rows 20 \
  --out docs/etl/sprints/AI-OPS-368/evidence/senado_waf_cohort_packets_20260301T103942Z.json \
  --csv-out docs/etl/sprints/AI-OPS-368/exports/senado_waf_cohort_packets_20260301T103942Z.csv
```

## Resultado
- Perfil actualizado (`linked_to_votes`): `missing_urls=384`, `status=404=329`, `status=403=32`, `status=0=18`, `status=200=5`.
- Dedupe canónico sobre pool `status=404`:
  - `pool_rows_total=329`
  - `used_urls_total=1389`
  - `fresh_rows_total=0`
  - `excluded_used_urls_total=329`
  - `strict_fail_reasons=[packet_exhausted_by_canonical_dedupe]`
- Packet estructurado por cohortes WAF:
  - `selected_cohorts_total=6`
  - `packet_rows_total=108`
  - `packet_unique_initiatives_total=97`
  - cohorte dominante: `leg10:tipo610` con `271` URLs faltantes.

## Conclusión operativa
Se completa la parte controlable de estructuración/limpieza de cola: el residual `status=404` no tiene URLs frescas bajo dedupe canónico y queda formalmente agotado para retries repetitivos sin palanca nueva. El siguiente paso de red debe limitarse a una única iteración con lever nuevo verificable o a una cohorte no-exhausta.

## Evidencia principal
- `docs/etl/sprints/AI-OPS-368/evidence/senado_waf_block_profile_20260301T103942Z.json`
- `docs/etl/sprints/AI-OPS-368/evidence/senado_status404_fresh_packet_summary_20260301T103942Z.json`
- `docs/etl/sprints/AI-OPS-368/evidence/senado_waf_cohort_packets_20260301T103942Z.json`
- `docs/etl/sprints/AI-OPS-368/exports/senado_status404_actionable_pool_20260301T103942Z.csv`
- `docs/etl/sprints/AI-OPS-368/exports/senado_status404_fresh_packet_20260301T103942Z.csv`
- `docs/etl/sprints/AI-OPS-368/exports/senado_waf_cohort_packets_20260301T103942Z.csv`
