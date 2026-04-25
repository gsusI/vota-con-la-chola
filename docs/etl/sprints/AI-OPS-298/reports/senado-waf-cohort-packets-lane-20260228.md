# AI-OPS-298: Paquetización operativa de cola Senado por cohortes WAF

## Objetivo
Convertir la cola accionable de documentos Senado en paquetes reproducibles por cohorte para ejecutar retries de forma acotada y trazable, sin repetir patrones ciegos en contexto de bloqueo WAF.

## Comandos ejecutados

```bash
just parl-check-senado-waf-cohort-packets
just parl-report-senado-waf-block-profile
```

## Resultado medible
- Check estricto de paquetes (`scripts/export_senado_waf_cohort_packets.py`) en `etl/data/staging/politicos-es.db`: `status=ok`.
- Estado consolidado de cola:
  - `missing_urls=680`
  - `missing_initiatives=345`
  - `blocked_403_urls=607`
  - `blocked_403_rate=0.892647`
- Paquetización operativa:
  - `selected_cohorts_total=4`
  - `packet_rows_total=110`
  - `packet_unique_initiatives_total=92`
  - `zero_doc_priority_total=25`
- Cohortes top priorizadas:
  - `leg10:tipo610`
  - `leg14:tipo621`
  - `leg14:tipo624`
  - `leg14:tipo622`
- Endurecimiento aplicado en la exportación:
  - exclusión de URLs `global_enmiendas_vetos` redundantes cuando existe alternativa descargada por iniciativa,
  - filtro `only_linked_to_votes=true` por defecto,
  - salida dual `JSON + CSV` para ejecución y auditoría.

## Conclusión operativa
La fila no se puede cerrar por bloqueo remoto persistente (WAF/403) y ausencia de palanca nueva de cookie utilizable, pero queda en `PARTIAL` con progreso visible bajo control del repo: cola segmentada, priorizada y lista para ejecución dirigida por cohorte, evitando reintentos indiscriminados.

## Artefactos
- `docs/etl/sprints/AI-OPS-298/evidence/senado_waf_cohort_packets_latest.json`
- `docs/etl/sprints/AI-OPS-298/exports/senado_waf_cohort_packets_latest.csv`
- `docs/etl/sprints/AI-OPS-232/evidence/senado_waf_block_profile_latest.json`
- `docs/etl/sprints/AI-OPS-236/evidence/senado_manual_capture_validity_latest.json`
