# AI-OPS-28 - HF remote quality verifier (2026-02-22)

## Objetivo

Eliminar verificación manual post-publish del contrato `quality_report` en Hugging Face y reemplazarla por un gate reproducible con exit code.

## Entrega

- Nuevo script: `scripts/verify_hf_snapshot_quality.py`
  - Resuelve repo HF desde `--dataset-repo`/`.env` (`HF_DATASET_REPO_ID`, `HF_USERNAME`).
  - Descarga y valida:
    - `latest.json`
    - `snapshots/<snapshot_date>/manifest.json`
    - `README.md` (salvo `--skip-readme-check`)
  - Checks:
    - presencia de `quality_report` en `latest` y `manifest`
    - consistencia de `quality_report` entre ambos artefactos
    - `snapshot_date` consistente
    - sección de calidad en README (`Resumen de calidad del snapshot`, `Vote gate`, referencia a `published/<quality_file>`)
  - Devuelve:
    - `exit=0` si pasa
    - `exit=1` en mismatch de contrato
    - `exit=2` en error operativo/red/parsing
- Nuevo target:
  - `just etl-verify-hf-quality`
  - `just etl-publish-hf-verify` (publish + verify encadenado)
  - variables:
    - `HF_VERIFY_TIMEOUT` (default `20`)
    - `HF_VERIFY_OUT` (opcional, para persistir JSON)
- Tests:
  - `tests/test_verify_hf_snapshot_quality.py`
- CI:
  - `.github/workflows/etl-tracker-gate.yml` agrega job `hf-quality-contract` (push a `main`) que ejecuta:
    - `python3 -m unittest tests.test_publicar_hf_snapshot tests.test_verify_hf_snapshot_quality -q`
    - `python3 scripts/verify_hf_snapshot_quality.py --dataset-repo JesusIC/vota-con-la-chola-data --timeout 25 --json-out hf_remote_quality_verify_ci.json`
  - el job publica `hf_remote_quality_verify_ci.json` como artifact.

## Verificación

- Unit:
  - `python3 -m unittest tests.test_verify_hf_snapshot_quality -q`
- End-to-end remoto:
  - `HF_VERIFY_OUT=docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_20260222T185350Z.json SNAPSHOT_DATE=2026-02-12 just etl-verify-hf-quality`
  - esperado: `OK: contrato de quality_report verificado`.
- Validación local del comando CI:
  - `python3 scripts/verify_hf_snapshot_quality.py --dataset-repo JesusIC/vota-con-la-chola-data --timeout 25 --json-out docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_ci_local_20260222T190143Z.json`
  - resultado: `OK: contrato de quality_report verificado`.

## Evidencia

- `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_20260222T185350Z.json`
- `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_20260222T185350Z.txt`
- `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_ci_local_20260222T190143Z.json`
- `docs/etl/sprints/AI-OPS-28/evidence/hf_remote_quality_verify_ci_local_20260222T190143Z.txt`
