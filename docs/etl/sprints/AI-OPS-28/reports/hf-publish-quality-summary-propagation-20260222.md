# AI-OPS-28 - HF publish quality summary propagation (2026-02-22)

## Objetivo

Propagar el estado canónico de calidad (`votaciones-kpis-es-<snapshot>.json`) al paquete de publicación HF para que el gate quede visible sin abrir artefactos internos del repo.

## Cambios entregados

- `scripts/publicar_hf_snapshot.py`:
  - se cablea `extract_quality_report_summary(...)` en `main()`;
  - `manifest.json` ahora incluye bloque `quality_report` cuando existe el artefacto KPI;
  - `latest.json` ahora incluye el mismo bloque `quality_report`;
  - `README.md` generado incluye:
    - referencia al archivo KPI usado (`published/votaciones-kpis-es-<snapshot>.json`);
    - resumen de gates/KPIs (vote gate, initiative gate si aplica, cobertura/cierre de extracción si están presentes).
- `tests/test_publicar_hf_snapshot.py`:
  - cobertura de parseo desde JSON y JSON.GZ (`extract_quality_report_summary`);
  - cobertura de render de `build_dataset_readme(..., quality_summary=...)`.

## Verificación

- Unit tests:
  - `python3 -m unittest tests.test_publicar_hf_snapshot -q` -> `Ran 12 tests ... OK`
  - `python3 -m unittest tests.test_parl_quality tests.test_cli_quality_report tests.test_backfill_initiative_doc_extractions tests.test_export_initdoc_extraction_review_queue tests.test_apply_initdoc_extraction_reviews tests.test_report_initiative_doc_status tests.test_publicar_hf_snapshot -q` -> `Ran 37 tests ... OK`
- Dry-run real de publish:
  - `python3 scripts/publicar_hf_snapshot.py --db etl/data/staging/politicos-es.db --snapshot-date 2026-02-12 --published-dir etl/data/published --skip-parquet --skip-sqlite-gz --dry-run --keep-temp`
  - Resultado: `exit=0`.
  - Verificado en bundle generado: `manifest.json` y `latest.json` contienen `quality_report`; README contiene "Resumen de calidad del snapshot".
- Estado remoto actual (solo lectura):
  - `curl -fsSL https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/resolve/main/latest.json`
  - evidencia: `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_latest_20260222T1848Z.json`
  - resultado: `latest.json` remoto aún no contiene `quality_report` (esperado hasta la próxima publicación real).
- Publicación real completada:
  - `SNAPSHOT_DATE=2026-02-12 DB_PATH=etl/data/staging/politicos-es.db just etl-publish-hf`
  - resultado: publicación exitosa en `https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data`
  - verificación remota post-publish:
    - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_latest_post_publish_20260222T184735Z.json` (`latest.json` con `quality_report`)
    - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_manifest_post_publish_20260222T184743Z.json` (`manifest.json` con `quality_report`)
    - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_readme_post_publish_20260222T184749Z.md` (sección "Resumen de calidad del snapshot")

## Evidencia

- Log dry-run:
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_dryrun_quality_summary_20260222T184311Z.txt`
- Resumen de publish real:
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_run_summary_20260222T184712Z.txt`
- Bundle capturado (copiado desde temp para trazabilidad):
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_dryrun_quality_summary_bundle_20260222T184311Z/manifest.json`
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_dryrun_quality_summary_bundle_20260222T184311Z/latest.json`
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_dryrun_quality_summary_bundle_20260222T184311Z/README.md`
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_publish_dryrun_quality_summary_bundle_20260222T184311Z/checksums.sha256`
- Estado remoto pre-publicación:
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_latest_20260222T1848Z.json`
- Estado remoto post-publicación:
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_latest_post_publish_20260222T184735Z.json`
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_manifest_post_publish_20260222T184743Z.json`
  - `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_readme_post_publish_20260222T184749Z.md`

## Siguiente paso operativo

Mantener esta validación en cada publicación (`just etl-publish-hf`): comprobar que `latest.json` remoto conserva `quality_report` y coincide con el snapshot publicado.
