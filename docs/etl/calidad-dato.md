# Calidad de dato (KISS)

Fuente de verdad:
- Backlog + DoD + estado por fuente: `docs/etl/e2e-scrape-load-tracker.md`
- Dashboard (estado + KPIs + roadmap): `/explorer-sources`
- Quality report votaciones (KPIs + gate): `python3 scripts/ingestar_parlamentario_es.py quality-report --db <db>`

## No negociables

- **Trazabilidad**: todo lo visible enlaza a evidencia primaria (`source_url` / `source_record_pk`) y tiene hash o raw (`raw_payload` o `raw_path`).
- **Reproducibilidad**: snapshots por `snapshot_date`; usar `--from-file`/muestras cuando haya bloqueos de red.
- **Idempotencia**: ingestas con upserts estables (por defecto: `(source_id, source_record_id)`).
- **Integridad**: `PRAGMA foreign_key_check` no devuelve filas tras ETL/backfills.
- **Publish sanity**: en `etl/data/published/`, 100% de filas publicadas tienen `source_id` + `source_url`/hash (no se publican “resúmenes” sin rastro).

## Modelo “posiciones por tema” (lo mínimo)

Tablas canónicas (mismo SQLite):
- `topics`, `topic_sets`, `topic_set_topics`
- `topic_evidence` (átomos: says/does, trazables)
- `topic_positions` (agregado reproducible desde `topic_evidence`)

Build MVP:
- Votos -> temas/posiciones: `python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db <db> --as-of-date <YYYY-MM-DD>`
- Texto auditable (says): `python3 scripts/ingestar_parlamentario_es.py backfill-text-documents --db <db> --source-id congreso_intervenciones --only-missing`
  - Materializa `text_documents` y copia un snippet a `topic_evidence.excerpt` para auditoría directa en `/explorer-temas`.

## KPIs mínimos (los que miramos)

En `/explorer-sources` (y `status.json`) deben ser accionables:
- `topic_evidence_with_topic_pct`
- `declared_evidence_with_text_excerpt_pct`
- `declared_evidence_with_evidence_date_pct`
- `declared_evidence_with_signal_pct`
- `events_with_initiative_link_pct`, `events_with_official_initiative_link_pct`
- `member_votes_with_person_id_pct`

Regla: si un KPI no dispara una acción concreta, se elimina.

## DoD (resumen) por conector

- Descarga raw reproducible (ideal `--strict-network`; fallback `--from-file` documentado).
- Parse estable (3 ejecuciones seguidas sin errores críticos).
- Upsert idempotente con `source_record_id` estable.
- Integridad SQL en verde (incluye FK check).
- Artefacto consumible (publish o UI) y fila del tracker actualizada con evidencia.
