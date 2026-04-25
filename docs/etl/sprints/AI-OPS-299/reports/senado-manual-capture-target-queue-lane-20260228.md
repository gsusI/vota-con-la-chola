# AI-OPS-299: Cola reproducible de captura manual para desbloqueo Senado

## Objetivo
Convertir el `TODO` de captura manual de cookie Senado en una lane operativa y acotada: lista priorizada de objetivos de captura (`URL + comando sugerido`) derivada de la cola WAF por cohortes.

## Cambios entregados
- Nuevo script: `scripts/export_senado_manual_capture_targets.py`.
- Nuevas recetas `just`:
  - `parl-export-senado-manual-capture-targets`
  - `parl-check-senado-manual-capture-targets`
- Cobertura de tests:
  - `tests/test_export_senado_manual_capture_targets.py`
  - regresión conjunta con lanes de validez/cookie/runtime (`11 tests`, `OK`).

## Comandos ejecutados

```bash
just parl-check-senado-manual-capture-targets
python3 scripts/report_senado_manual_capture_validity.py \
  --captures-glob 'etl/data/raw/manual/senado*_ai_ops_235_*.meta.json' \
  --cookie-domain-contains senado.es \
  --min-captures 1 \
  --out docs/etl/sprints/AI-OPS-299/evidence/senado_manual_capture_validity_latest.json
python3 scripts/report_senado_cookie_lever_status.py \
  --cookie-file etl/data/raw/manual/senado_iniciativas_cookie_seed_refresh_20260218T201301Z.cookies.json \
  --domain-contains senado.es \
  --max-age-hours 24 \
  --min-domain-cookies 1 \
  --min-unexpired-persistent-cookies 1 \
  --out docs/etl/sprints/AI-OPS-299/evidence/senado_cookie_lever_status_latest.json
```

## Resultado medible
- Lane de targets: `status=ok`.
  - `packet_rows_total=110`
  - `selected_targets_total=8`
  - `selected_cohorts_total=5`
  - `seed_targets_total=1`
  - `targets_from_zero_doc_total=5`
  - `targets_with_403_total=7`
- Validez de capturas existentes: `status=degraded`.
  - `captures_total=2`
  - `usable_captures_total=0`
  - `access_denied_captures_total=2`
  - strict `rc=4`
- Lever de cookie actual: `status=degraded` por stale (`cookie_file_stale`).
  - `has_domain_cookies=true`
  - `has_unexpired_persistent_cookies=true`
  - `file_age_within_threshold=false`
  - strict `rc=4`

## Conclusión operativa
Se cierra una brecha controlable del flujo manual: la captura ya no depende de selección ad-hoc de URLs y pasa a ejecutarse con cola priorizada reproducible. El desbloqueo de red sigue pendiente de interacción humana real (resolver challenge y generar cookie fresco/utilizable).

## Artefactos
- `docs/etl/sprints/AI-OPS-299/evidence/senado_manual_capture_targets_latest.json`
- `docs/etl/sprints/AI-OPS-299/exports/senado_manual_capture_targets_latest.csv`
- `docs/etl/sprints/AI-OPS-299/evidence/senado_manual_capture_validity_latest.json`
- `docs/etl/sprints/AI-OPS-299/evidence/senado_manual_capture_validity_strict_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-299/evidence/senado_cookie_lever_status_latest.json`
- `docs/etl/sprints/AI-OPS-299/evidence/senado_cookie_lever_status_strict_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-299/evidence/unittest_senado_manual_capture_targets_lane_latest.txt`
