# AI-OPS-125 — Distribución pública del Atlas y continuidad de release

## Objetivo
Cerrar el pendiente `Derechos/Atlas público` conectando el contrato del Atlas (snapshot+parquet+diff+changelog) con distribución pública reproducible y chequeo estricto de continuidad entre releases.

## Cambios entregados
- `scripts/publish_liberty_atlas_artifacts.py`
  - Publica el bundle del Atlas en `etl/data/published` con versionado por `snapshot_date`:
    - `liberty-restrictions-atlas-<date>.json`
    - `liberty-restrictions-irlc-by-fragment-<date>.parquet`
    - `liberty-restrictions-accountability-edges-<date>.parquet`
    - `liberty-restrictions-diff-<date>.json`
    - `liberty-restrictions-changelog-entry-<date>.json`
    - `liberty-restrictions-changelog-history-<date>.jsonl`
  - Emite release metadata:
    - `liberty-restrictions-atlas-release-<date>.json`
    - `liberty-restrictions-atlas-release-latest.json`
  - Espejo opcional a GH Pages (`--gh-pages-out`) y salida operativa (`--out`).
- `scripts/report_liberty_atlas_changelog_continuity.py`
  - Valida continuidad de changelog en modo estricto:
    - historial no vacío,
    - líneas malformadas,
    - unicidad de `entry_id`,
    - monotonía de `run_at`,
    - cadena `previous_snapshot_date`.
  - Cross-check opcional contra release JSON.
  - Ajuste aplicado en este sprint: acepta reruns idempotentes (`previous_snapshot_date == snapshot_date`) como caso válido y los reporta en `self_referential_previous_snapshot_entries`.
- `justfile`
  - Nuevas variables `LIBERTY_ATLAS_*`.
  - Nuevos lanes:
    - `just parl-publish-liberty-atlas-artifacts`
    - `just parl-report-liberty-atlas-changelog-continuity`
    - `just parl-check-liberty-atlas-changelog-continuity`
  - Integración en `just parl-liberty-restrictions-pipeline` tras el export.
  - `just parl-test-liberty-restrictions` incluye tests del nuevo contrato.
- Tests nuevos:
  - `tests/test_publish_liberty_atlas_artifacts.py`
  - `tests/test_report_liberty_atlas_changelog_continuity.py`

## Ejecución y resultados
- `python3 -m unittest tests/test_publish_liberty_atlas_artifacts.py tests/test_report_liberty_atlas_changelog_continuity.py -q`
  - PASS (`4` tests).
- `just parl-test-liberty-restrictions`
  - PASS (`41` tests; `1` skip local por dependencia parquet).
- `SNAPSHOT_DATE=2026-02-23 LIBERTY_RESTRICTIONS_SNAPSHOT_PREV=... just parl-export-liberty-restrictions-snapshot`
  - PASS (`snapshot_date=2026-02-23`, diff `unchanged`).
- `SNAPSHOT_DATE=2026-02-23 just parl-publish-liberty-atlas-artifacts`
  - PASS (`status=ok`), release latest publicado en `etl/data/published`.
- `SNAPSHOT_DATE=2026-02-23 just parl-check-liberty-atlas-changelog-continuity`
  - PASS (`status=ok`, `entries_total=4`, `previous_snapshot_chain_ok=true`).
- `SNAPSHOT_DATE=2026-02-23 just etl-publish-hf-dry-run`
  - PASS dry-run; el bundle del Atlas entra en el snapshot público (resumen: `Published files=10`, `Parquet tables=68`, `Parquet files=126`).
- `SNAPSHOT_DATE=2026-02-23 just etl-publish-hf`
  - PASS publicación real en `https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data`.
- `SNAPSHOT_DATE=2026-02-23 just etl-verify-hf-quality`
  - PASS (`quality_report` encontrado en manifest + latest para el snapshot publicado).
- `SNAPSHOT_DATE=2026-02-23 just parl-liberty-restrictions-pipeline`
  - PASS end-to-end incluyendo export + publicación + continuidad del Atlas en el mismo lane reproducible.

## Evidencia
- `docs/etl/sprints/AI-OPS-125/evidence/unittest_liberty_atlas_distribution_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/evidence/just_parl_test_liberty_restrictions_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/evidence/just_parl_export_liberty_restrictions_snapshot_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/evidence/liberty_atlas_publish_20260223T192412Z.json`
- `docs/etl/sprints/AI-OPS-125/evidence/just_parl_publish_liberty_atlas_artifacts_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/evidence/liberty_atlas_changelog_continuity_20260223T192412Z.json`
- `docs/etl/sprints/AI-OPS-125/evidence/just_parl_check_liberty_atlas_changelog_continuity_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/evidence/just_etl_publish_hf_dry_run_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/evidence/just_etl_publish_hf_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/evidence/hf_verify_quality_20260223T192412Z.json`
- `docs/etl/sprints/AI-OPS-125/evidence/just_etl_verify_hf_quality_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/evidence/just_parl_liberty_restrictions_pipeline_20260223T192412Z.txt`
- `docs/etl/sprints/AI-OPS-125/exports/liberty-atlas-release_20260223T192412Z.json`

## Estado DoD
- Distribución pública reproducible (`published` + mirror GH Pages): `OK`.
- Retención/versionado explícito por `snapshot_date`: `OK`.
- Continuidad de changelog/release con gate estricto: `OK`.
- Publicación y verificación de snapshot HF: `OK`.
