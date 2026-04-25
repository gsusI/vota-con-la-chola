# AI-OPS-249 - Recuperación de cobertura partidaria tras higiene

## Objetivo
Recuperar cobertura por partido tras AI-OPS-248 (higiene anti-ruido), evitando regresiones de contrato (`strict-network`, gate declarado, tracker enforce).

## Cambios ejecutados
- Manifest de recuperación por override reproducible:
  - Input: `docs/etl/sprints/AI-OPS-248/exports/programas_manifest_deeplink_hygiene_multicycle_20260228.csv`
  - Override para partidos en cero según cola AI-OPS-248 (`CCa`, `EAJ-PNV`, `EH Bildu`, `Izquierda Unida`, `PSC`, `UPN`) usando `previous_programmatic_url_hint`.
  - Output: `docs/etl/sprints/AI-OPS-249/exports/programas_manifest_deeplink_recovery_override_20260228.csv`.
- Ingest real en staging con red estricta:
  - `run_id=299`, `records_seen=51`, `records_loaded=51`, `status=ok`.
- Higiene operativa de corrida interrumpida:
  - intento previo abortado (`run_id=297`) normalizado a `status=error` para no dejar estado `running` residual en `ingestion_runs`.
- Recompute declarado/combinado + cierre reproducible de cola pendiente (`review-decision --status ignored --recompute`).
- Gate tracker enforce ejecutado con resultado limpio (`mismatches=0`, `done_zero_real=0`).

## Resultado (AI-OPS-248 post-ignore -> AI-OPS-249 post-ignore)
- `party_proxy_count`: `9 -> 10` (`+1`)
- `support`: `88 -> 88` (`0`)
- `unclear`: `204 -> 228` (`+24`)
- `topic_evidence_total`: `292 -> 316` (`+24`)
- `declared_positions_total`: `127 -> 127` (`0`)
- `review_pending`: `0 -> 0` (`0`)
- Gate declarado: `passed=true`.

## Lectura operativa
- Se recupera cobertura en un partido adicional (`EH Bildu`: `0 -> 24` evidencias), cumpliendo avance de la lane de cobertura.
- Tradeoff vigente: la recuperación actual añade evidencia mayoritariamente `unclear` (+24) y no incrementa `support`.
- Persisten partidos con evidencia `0` tras el override (`CCa`, `EAJ-PNV`, `Izquierda Unida`, `PSC`, `UPN`).

## Evidencia
- `docs/etl/sprints/AI-OPS-249/evidence/programas_ingestion_runs_latest_20260228.csv`
- `docs/etl/sprints/AI-OPS-249/evidence/programas_declared_status_post_recovery_override_full_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-249/evidence/quality_declared_programas_post_recovery_override_full_post_ignore_20260228.json`
- `docs/etl/sprints/AI-OPS-249/evidence/tracker_status_post_recovery_override_full_post_ignore_enforce_20260228.log`
- `docs/etl/sprints/AI-OPS-249/exports/programas_status_delta_ai_ops_248_vs_ai_ops_249_post_ignore_20260228.csv`
- `docs/etl/sprints/AI-OPS-249/exports/programas_party_delta_ai_ops_248_vs_ai_ops_249_post_ignore_20260228.csv`
- `docs/etl/sprints/AI-OPS-249/exports/programas_manifest_url_changes_vs_ai_ops_248_recovery_override_20260228.csv`

## Siguiente paso recomendado
- Intento dirigido para convertir cobertura recuperada en señal útil:
  - mantener URLs recuperadas solo donde no empeoran ruido,
  - probar candidato alternativo por partido (`CCa`, `EAJ-PNV`, `IU`, `PSC`, `UPN`) con `max-probe-candidates` acotado,
  - aceptar cambio solo si mejora conjunta: `party_proxy_count` sin subir `unclear/support` ratio.
