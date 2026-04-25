# AI-OPS-332 - Cierre de toolchain `retry_packet_only_dedup` + retry acotado `status=403/404`

## Objetivo
Cerrar la deuda de producto de `836` (pasar de dedupe ad-hoc a toolchain reproducible con `strict/fail-fast`) y ejecutar una iteración acotada en Senado para avanzar la cola accionable.

## Ejecución
1. Se añadió `scripts/export_senado_retry_packet_only_dedup.py` + cobertura unitaria (`tests/test_export_senado_retry_packet_only_dedup.py`) y wiring operativo en `Justfile` (`parl-export-senado-retry-packet-only-dedup`, `parl-check-senado-retry-packet-only-dedup`).
2. Baseline de estado (`initiative_doc_status` + `senado_waf_block_profile`) sobre `etl/data/staging/politicos-es.db`.
3. Export de pools accionables:
- `status=403`: `pool_rows_total=169`.
- `status=404`: `pool_rows_total=793`.
4. Packetización canónica con dedupe `packet-only`:
- `status=403`: `used_packet_files_total=12`, `used_urls_total=613`, `excluded_used_urls_total=160`, `fresh_rows_total=9`.
- `status=404`: `used_packet_files_total=13`, `used_urls_total=622`, `excluded_used_urls_total=7`, `fresh_rows_total=80`.
- Hallazgo operativo: la lane `status=404` no estaba agotada bajo contrato canónico (a diferencia de la hipótesis previa de agotamiento).
5. Retry acotado de red (un burst por lane):
- `status=403` (9 URLs): `fetched_ok=0`, `archive_hits=0`, `archive_fetched_ok=0`, `text_documents_upserted=0`, `failures_count=9`.
- `status=404` (80 URLs): `fetched_ok=0`, `archive_hits=0`, `archive_fetched_ok=0`, `text_documents_upserted=0`, `failures_count=30`.
6. Post-proceso estructural (`backfill_initiative_doc_extractions --only-missing`, `backfill_initiative_doc_excerpts`): sin nuevos pendientes (`seen=0`, `upserted/updated=0`, `needs_review=0`).

## Delta medido (before -> after final)
- `downloaded_doc_links`: `0` delta (`4414 -> 4414`)
- `missing_doc_links`: `0` delta (`5139 -> 5139`)
- `missing_doc_links_actionable`: `0` delta (`4955 -> 4955`)
- `effective_downloaded_doc_links_pct`: `0` delta (`47.11 -> 47.11`)
- WAF linked-to-votes:
  - `missing_urls`: `0` delta (`1179 -> 1179`)
  - `blocked_403_urls`: `-9` (`169 -> 160`)
  - `blocked_500_urls`: `0` delta (`0 -> 0`)
  - `unknown_status_urls`: `0` delta (`217 -> 217`)

## Conclusión
- Se cierra la deuda técnica de `836`: el contrato `retry_packet_only_dedup` queda productizado, testeado y ejecutable con `strict`.
- La iteración de red no produjo descargas nuevas en esta corrida, pero sí mejoró clasificación de bloqueo (`blocked_403_urls -9`).
- La lane `status=404` queda reclasificada como **activa/no agotada** bajo dedupe canónico (80 filas frescas en este sprint), por lo que requiere continuidad operativa y no cierre prematuro por agotamiento.

## Evidencia
- `docs/etl/sprints/AI-OPS-332/evidence/senado_status403_fresh_packet_summary_20260301T005820Z.json`
- `docs/etl/sprints/AI-OPS-332/evidence/senado_status404_fresh_packet_summary_20260301T005820Z.json`
- `docs/etl/sprints/AI-OPS-332/evidence/senado_retry_status403_fresh_20260301T005820Z.json`
- `docs/etl/sprints/AI-OPS-332/evidence/senado_retry_status404_fresh_20260301T005820Z.json`
- `docs/etl/sprints/AI-OPS-332/evidence/initiative_doc_status_delta_ai_ops_332_20260301T005820Z.json`
- `docs/etl/sprints/AI-OPS-332/evidence/senado_retry_packet_used_refs_20260301T005820Z.txt`
- `docs/etl/sprints/AI-OPS-332/evidence/senado_retry_packet_used_urls_20260301T005820Z.txt`
- `docs/etl/sprints/AI-OPS-332/evidence/initiative_doc_status_after_final_20260301T005820Z.json`
- `docs/etl/sprints/AI-OPS-332/evidence/senado_waf_block_profile_after_final_20260301T005820Z.json`
