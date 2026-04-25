# AI-OPS-274 - Auditoria de snippets fiscales en Empleo (programas_partidos)

## Objetivo
Cerrar la auditoria preventiva abierta tras AI-OPS-273 para verificar que el fix del falso positivo `1560538` no introdujo nuevos `false_positive` en la cohorte BNG de `concern:v1:empleo` con lexico fiscal.

## Implementacion
- Nuevo reporte reproducible: `scripts/report_programas_empleo_fiscal_snippets_audit.py`.
- Nuevo contrato `just`:
  - `parl-report-programas-empleo-fiscal-snippets-audit`
  - `parl-check-programas-empleo-fiscal-snippets-audit`
- Cobertura dedicada: `tests/test_report_programas_empleo_fiscal_snippets_audit.py`.

## Corrida de cierre (cohorte BNG)
Comando:

```bash
DB_PATH=etl/data/staging/politicos-es.db \
PROGRAMAS_EMPLEO_FISCAL_AUDIT_PARTIES='BNG' \
just parl-check-programas-empleo-fiscal-snippets-audit
```

Resultado (`programas_empleo_fiscal_snippets_audit_bng_latest.json`):
- `rows_total=2`
- `support_rows=1`
- `unclear_rows=1`
- `suspicious_support_rows=0`
- `status=ok`

Validacion clave:
- `evidence_id=1560338` se mantiene como `support` pero con ancla laboral (`traballo`), por lo que no se clasifica como sospechoso.
- `evidence_id=1560538` permanece en `unclear`.

## Hallazgo transversal detectado
En corrida multi-partido de la misma auditoria (`BNG,CCa,Compromis,EAJ-PNV,VOX`) aparece gap nuevo:
- `rows_total=13`
- `suspicious_support_rows=4`
- Concentrado en `Compromis` (`fiscalitat verda` sin ancla laboral en el snippet)
- `status=degraded`, strict `rc=4`

Este gap se mueve a nueva fila TODO de curacion transversal en el tracker.

## Evidencia
- `docs/etl/sprints/AI-OPS-274/evidence/programas_empleo_fiscal_snippets_audit_bng_latest.json`
- `docs/etl/sprints/AI-OPS-274/exports/programas_empleo_fiscal_snippets_audit_bng_latest.csv`
- `docs/etl/sprints/AI-OPS-274/evidence/just_parl_check_programas_empleo_fiscal_snippets_audit_bng_latest.txt`
- `docs/etl/sprints/AI-OPS-274/evidence/programas_empleo_fiscal_snippets_audit_cross_party_latest.json`
- `docs/etl/sprints/AI-OPS-274/exports/programas_empleo_fiscal_snippets_audit_cross_party_latest.csv`
- `docs/etl/sprints/AI-OPS-274/evidence/programas_empleo_fiscal_snippets_audit_cross_party_strict_rc_latest.txt`
- `docs/etl/sprints/AI-OPS-274/evidence/unittest_programas_empleo_fiscal_snippets_audit_latest.txt`
