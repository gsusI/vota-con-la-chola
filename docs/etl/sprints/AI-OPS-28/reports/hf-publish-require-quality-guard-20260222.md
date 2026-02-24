# AI-OPS-28 - HF publish require-quality guard (2026-02-22)

## Objetivo

Evitar publicaciones HF que omitan metadatos canónicos de calidad (`votaciones-kpis`) por error operativo.

## Entrega

- `scripts/publicar_hf_snapshot.py`:
  - nuevo flag `--require-quality-report`;
  - nuevo guard `ensure_quality_report_for_publish(...)` que falla si:
    - no existe `quality_report` para el snapshot,
    - falta `quality_report.file_name`,
    - el nombre no cumple prefijo esperado `votaciones-kpis-es-`,
    - falta `quality_report.vote_gate_passed`.
- `justfile`:
  - nuevo env var `HF_REQUIRE_QUALITY_REPORT` (default `1`);
  - `just etl-publish-hf` y `just etl-publish-hf-dry-run` ahora pasan `--require-quality-report` por defecto.
- tests:
  - `tests/test_publicar_hf_snapshot.py` añade cobertura del guard.

## Verificación

- `python3 -m unittest tests.test_publicar_hf_snapshot -q` -> OK.
- `python3 -m unittest tests.test_parl_quality tests.test_cli_quality_report tests.test_backfill_initiative_doc_extractions tests.test_export_initdoc_extraction_review_queue tests.test_apply_initdoc_extraction_reviews tests.test_report_initiative_doc_status tests.test_publicar_hf_snapshot tests.test_verify_hf_snapshot_quality -q` -> `Ran 46 tests ... OK`.
- `SNAPSHOT_DATE=2026-02-12 DB_PATH=etl/data/staging/politicos-es.db just etl-publish-hf-dry-run` -> OK con guard activo (`HF_REQUIRE_QUALITY_REPORT=1` por defecto).

## Evidencia

- `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_dryrun_require_quality_20260222T185920Z.txt`
- `docs/etl/sprints/AI-OPS-28/evidence/hf_quality_hardening_tests_20260222T190403Z.txt`
