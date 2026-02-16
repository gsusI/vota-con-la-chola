# Protocolo de anotación (doble entrada)

Version: `v1`

Objetivo: mantener la parte “humana” (inevitable) **reproducible** y **auditable**, evitando que la automatización convierta ambigüedad en certeza.

Aplica a:
- codificación de `policy_events` -> ejes del `codebook` (acción revelada),
- y evidencia textual -> `topic_evidence` (posiciones declaradas).

## Roles mínimos

- `annotator_a`: primera codificación.
- `annotator_b`: segunda codificación independiente.
- `arbiter`: resuelve discrepancias y actualiza el codebook (si procede).

Regla: quien arbitra no debe ser quien implementó el conector o el modelo que produjo la propuesta.

## Unidad de anotación

1. **Evento con efectos** (`policy_event`):
  - input: evidencia primaria (BOE, BDNS, PLACSP, etc.) + metadatos.
  - output: `policy_event_axis_scores` (eje -> direction/intensity/confidence/method/notes).
2. **Texto declarativo** (speech/intervención/programa):
  - input: fragmento + source_url + actor + contexto.
  - output: `topic_evidence` (topic_id, stance, confidence, excerpt, evidence_date).

## Formato de salida (KISS)

Para cada unidad, producir un registro con:
- `unit_id` (estable; ideal: el `policy_event_id` o `source_record_id`)
- `codebook_version`
- `labels` (por eje o por stance)
- `confidence`
- `notes`
- `annotator_id`
- `created_at`

La persistencia puede ser:
- CSV/JSON versionado en el repo (solo si es pequeño),
- o carga directa al SQLite (con `method=human:v1` y trazabilidad a `source_record_pk`).

## Flujo de trabajo

1. **Calibración**
  - elegir un set pequeño y representativo (alto impacto + casos ambiguos).
  - discutir en grupo hasta fijar interpretaciones estables del codebook.
  - congelar `docs/codebook_tier1_es.md` como versión `v1` (cambios posteriores = `v1.1`, `v2`, etc.).

2. **Doble anotación ciega**
  - A y B anotan sin ver la salida del otro.
  - se registran tiempos/casos difíciles (para priorizar mejoras del codebook).

3. **Medición de acuerdo**
  - por eje/tema: acuerdo de dirección (`-1/0/+1`) y acuerdo de stance.
  - medir al menos: porcentaje de acuerdo simple y una métrica tipo kappa (si aplica).

4. **Arbitraje**
  - el árbitro decide el label final para cada discrepancia.
  - si la discrepancia es recurrente: actualizar el codebook (nueva versión).

5. **Publicación**
  - toda anotación “final” debe quedar asociada a:
    - `codebook_version`,
    - `method` (`human:v1`, `human:v1.1`, etc.),
    - evidencia primaria (`source_url` / `source_record_pk`).

## Políticas anti-deriva

- Cambios en definiciones: siempre nueva versión del codebook.
- No “arreglar” eventos antiguos silenciosamente: si se re-anota, se registra el método/versionado.
- “No observable” es un resultado válido: mejor `no_signal/unclear` que inventar.

## Checklist de Definition of Done (para un batch humano)

- 100% unidades con `unit_id` estable.
- 100% unidades con `codebook_version`.
- 100% unidades con evidencia primaria linkeada.
- Se puede reproducir qué cambió entre `v1` y `v1.1` (changelog corto en PR/commit).

