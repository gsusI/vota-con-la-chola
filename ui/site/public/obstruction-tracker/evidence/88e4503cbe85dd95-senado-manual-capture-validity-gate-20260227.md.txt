# AI-OPS-236: Gate canónico de validez de captura manual Senado

## Objetivo
Cerrar una brecha controlable: convertir la "captura manual" en un contrato machine-readable que separe "captura ejecutada" de "captura utilizable" antes de lanzar retries de red.

## Cambios de código
- `scripts/report_senado_manual_capture_validity.py`
  - nuevo reporte canónico para evaluar capturas `*.meta.json` + sidecars `.html` / `.cookies.json`,
  - detecta bloqueo `Access Denied` y contabiliza cookies de dominio objetivo,
  - define `usable_capture` y soporte `--strict` (exit `4` si status no `ok`).
- `tests/test_report_senado_manual_capture_validity.py`
  - cobertura de casos `ok`/`degraded`,
  - cobertura de sidecars y chequeo de exit code estricto.
- `justfile`
  - nuevos lanes `parl-report-senado-manual-capture-validity` y `parl-check-senado-manual-capture-validity`.

## Validación técnica

```bash
python3 -m unittest \
  tests/test_report_senado_manual_capture_validity.py \
  tests/test_manual_capture_playwright.py \
  tests/test_report_senado_cookie_lever_status.py \
  tests/test_report_senado_waf_block_profile.py
```

Resultado: `Ran 10 tests`, `OK`.

## Ejecución real sobre capturas AI-OPS-235

```bash
python3 scripts/report_senado_manual_capture_validity.py \
  --captures-glob 'etl/data/raw/manual/senado*_ai_ops_235_*.meta.json' \
  --cookie-domain-contains senado.es \
  --min-captures 1 \
  --strict \
  --out docs/etl/sprints/AI-OPS-236/evidence/senado_manual_capture_validity_strict_latest.json
```

Resultado:
- `status=degraded`
- `captures_total=2`
- `usable_captures_total=0`
- `access_denied_captures_total=2`
- `cookies_domain_total=0`
- `strict_fail_reasons=["no_usable_capture"]`
- `strict_rc=4`

Chequeo lane `just`:
- `just parl-check-senado-manual-capture-validity` -> `rc=4` (esperado, contrato estricto activo).

## Decisión operativa
- Queda cerrada la deuda controlable de observabilidad del lever manual: ya existe gate explícito y reproducible para evitar retries sin sesión utilizable.
- El bloqueo externo persiste: las capturas actuales siguen en `Access Denied` sin cookies de `senado.es`.
- Próximo paso se mantiene: captura interactiva real (resolver challenge) hasta lograr `status=ok` en este gate.
