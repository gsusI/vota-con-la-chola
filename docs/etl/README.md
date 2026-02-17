# ETL

Estructura minima de `etl/`:

- `etl/extract/`: scripts o jobs de extraccion desde fuentes.
- `etl/transform/`: normalizacion, validacion y enriquecimiento.
- `etl/load/`: publicacion/carga a destino final.
- `etl/data/raw/`: descargas sin transformar.
- `etl/data/staging/`: datos intermedios validados.
- `etl/data/published/`: salidas canonicas consumidas por la app.

Actualmente:
- Snapshot de proximas elecciones: `etl/data/published/proximas-elecciones-espana.json`.
- Snapshot de representantes (JSON, excluye municipal por defecto): `etl/data/published/representantes-es-<snapshot_date>.json` (ver `scripts/publicar_representantes_es.py`).
- Snapshot de votaciones parlamentarias (JSON): `etl/data/published/votaciones-es-<snapshot_date>.json` (ver `scripts/publicar_votaciones_es.py`).
- Snapshot de KPIs de calidad de votaciones: `etl/data/published/votaciones-kpis-es-<snapshot_date>.json`.
- Esquema SQLite ETL: `etl/load/sqlite_schema.sql`.
- Esquema analitico (posiciones por temas): `topics`, `topic_sets`, `topic_set_topics`, `topic_evidence`, `topic_positions` (en el mismo SQLite).
- CLI ingesta politicos: `scripts/ingestar_politicos_es.py`.
- CLI ingesta Infoelectoral (descargas): `scripts/ingestar_infoelectoral_es.py`.
- CLI parlamentario (votaciones, iniciativas): `scripts/ingestar_parlamentario_es.py`.
- Tracker E2E scrape/load (TODO operativo): `docs/etl/e2e-scrape-load-tracker.md`.
- El backlog de conectores y calidad vive solo en el tracker (y el dashboard `/explorer-sources`).
- Artefactos de sprint (canónicos): `docs/etl/sprints/`.
- Índice de sprints: `docs/etl/sprints/README.md`.
- Puntero al prompt pack de sprint activo: `docs/etl/sprint-ai-agents.md`.

Nota para votaciones:
- Flujo recomendado: `ingest -> backfill-member-ids -> link-votes -> backfill-topic-analytics -> quality-report -> publish`.
- Ejecuta `python3 scripts/ingestar_parlamentario_es.py link-votes --db <db>` antes de publicar si quieres maximizar `evento -> iniciativa` (y por extensión el tagging a topics en `backfill-topic-analytics`).
- Ejecuta `python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db <db>` después de la ingesta de `congreso_votaciones,senado_votaciones` para resolver `person_id` en votos nominales.
- Sugerencia operativa: añade `--unmatched-sample-limit 50` para capturar casos sin emparejar y priorizar corrección manual por razón (`no_candidates`, `skipped_no_name`, `ambiguous`, ...).
- Para publicar y auditar unmatched en un pass sin escribir cambios, usa:
  - `python3 scripts/publicar_votaciones_es.py --db <db> --snapshot-date <fecha> --include-unmatched --unmatched-sample-limit 100`
- Para publicar y materializar el emparejado de `person_id` al vuelo (sin paso separado), usa:
  - `python3 scripts/publicar_votaciones_es.py --db <db> --snapshot-date <fecha> --backfill-member-ids`
- Revisa KPIs/gate con `python3 scripts/ingestar_parlamentario_es.py quality-report --db <db> --source-ids congreso_votaciones,senado_votaciones` y usa `--enforce-gate` para fallar en CI cuando no se cumpla el minimo.
- Para incluir diagnóstico de emparejado de persona en seco, usa `--include-unmatched --unmatched-sample-limit <n>`.
- Exporta KPIs por fecha con `python3 scripts/ingestar_parlamentario_es.py quality-report --db <db> --json-out etl/data/published/votaciones-kpis-es-<snapshot>.json`.
- El JSON de votaciones puede ser muy grande en corridas completas; para smoke/debug usa `--max-events` y/o `--max-member-votes-per-event`.

Nota para posiciones por temas:
- La representacion “politico x scope x tema” se construye desde evidencia atómica trazable (`topic_evidence`) y se agrega en snapshots recomputables (`topic_positions`).
- El roadmap operativo y de calidad vive en `docs/etl/e2e-scrape-load-tracker.md` (filas “Analitica”).
- Para poblar un MVP desde **votaciones** (hecho, reproducible), ejecuta:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-topic-analytics --db <db> --as-of-date <YYYY-MM-DD>`
  - Esto materializa `topic_sets`, `topics`, `topic_set_topics`, `topic_evidence`, `topic_positions` y desbloquea `/explorer-temas`.
- Seed/versionado del set (parámetros + curación opcional): `etl/data/seeds/topic_taxonomy_es.json`.
- Para capturar evidencia **textual** (metadata + excerpt) para evidencia declarada (p.ej. intervenciones Congreso):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-text-documents --db <db> --source-id congreso_intervenciones --only-missing`
  - Esto materializa `text_documents` y además copia un snippet a `topic_evidence.excerpt` para auditoría en `/explorer-temas`.
- Para inferir un **stance mínimo** en evidencia declarada (regex v2 conservador sobre excerpts ya capturados):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-declared-stance --db <db> --source-id congreso_intervenciones --min-auto-confidence 0.62`
  - (o `just parl-backfill-declared-stance`)
  - El comando auto-escribe solo casos de confianza alta y alimenta `topic_evidence_reviews` para casos ambiguos (`missing_text`, `no_signal`, `low_confidence`, `conflicting_signal`).
- Para inspeccionar la cola de revisión:
  - `python3 scripts/ingestar_parlamentario_es.py review-queue --db <db> --source-id congreso_intervenciones --status pending --limit 50`
  - (o `just parl-review-queue`)
- Si se delega revisión a crowd (MTurk), usar el runbook:
  - `docs/etl/mechanical-turk-review-instructions.md`
- Para aplicar decisión manual sobre evidencia pendiente (y opcionalmente recomputar posiciones):
  - `python3 scripts/ingestar_parlamentario_es.py review-decision --db <db> --source-id congreso_intervenciones --evidence-ids 123,124 --status resolved --final-stance support --recompute --as-of-date <YYYY-MM-DD>`
  - `python3 scripts/ingestar_parlamentario_es.py review-decision --db <db> --source-id congreso_intervenciones --evidence-ids 130 --status ignored --note \"sin señal accionable\"`
  - Atajo: `just parl-review-resolve <evidence_id> <stance>`
- Para materializar **posiciones (says)** desde esa evidencia declarada (en `topic_positions`, `computed_method=declared`):
  - `python3 scripts/ingestar_parlamentario_es.py backfill-declared-positions --db <db> --source-id congreso_intervenciones --as-of-date <YYYY-MM-DD>`
  - (o `just parl-backfill-declared-positions`)
- Para materializar una **posición combinada** (KISS: `votes` si existe; si no, `declared`) en `topic_positions`, `computed_method=combined`:
  - `python3 scripts/ingestar_parlamentario_es.py backfill-combined-positions --db <db> --as-of-date <YYYY-MM-DD>`
  - (o `just parl-backfill-combined-positions`)

## Política de snapshots publicables

- Los artefactos publicados en `etl/data/published/` llevan la fecha de snapshot en el nombre (`...-<fecha>.json`).
- El snapshot se produce con `SNAPSHOT_DATE` y es reproducible para una fecha concreta.
- Política de refresco: re-generar `representantes` y `votaciones` cuando cambie la composición o tras mejoras de parsing/linking de fuente, documentando la fecha en commit y tracker.
- Mantener al menos un snapshot publicado por nivel operativo tras cambios de formato relevantes.

## Publicación abierta en Hugging Face

- Decisión: el espejo público de snapshots vive en un dataset de Hugging Face.
- Credenciales en `.env`:
  - `HF_TOKEN`
  - `HF_USERNAME`
  - `HF_DATASET_REPO_ID` (opcional, por defecto `<HF_USERNAME>/vota-con-la-chola-data`)
- Comandos:
  - `just etl-publish-hf-dry-run` para validar paquete local sin subir.
  - `just etl-publish-hf` para subir snapshot real.
- Estructura remota por snapshot:
  - `snapshots/<snapshot_date>/politicos-es.sqlite.gz` (solo si `HF_INCLUDE_SQLITE_GZ=1`; no recomendado en público)
  - `snapshots/<snapshot_date>/published/*`
  - `snapshots/<snapshot_date>/ingestion_runs.csv`
  - `snapshots/<snapshot_date>/source_records_by_source.csv`
  - `snapshots/<snapshot_date>/manifest.json`
  - `snapshots/<snapshot_date>/checksums.sha256`
  - `latest.json` en la raíz del dataset.
- Guardas de privacidad por defecto:
  - `HF_PARQUET_EXCLUDE_TABLES=raw_fetches,run_fetches,source_records,lost_and_found`
  - `HF_ALLOW_SENSITIVE_PARQUET=0` (activar solo en datasets privados)
  - `HF_INCLUDE_SQLITE_GZ=0` (activar solo en datasets privados)
- Regla operativa: después de publicar artefactos locales por snapshot, ejecutar `just etl-publish-hf` o registrar bloqueo con evidencia en tracker.

## Entorno reproducible con Docker

Prerequisitos:
- Docker Desktop o Docker Engine + Compose.
- `just` instalado (`brew install just` en macOS).

## Opcion recomendada: just (sin Python local)

```bash
just etl-build
just etl-init
just etl-samples
just parl-backfill-member-ids
just parl-quality-pipeline
just parl-publish-votaciones
just parl-congreso-votaciones-pipeline
just parl-samples
just parl-link-votes
just parl-quality-report
just etl-stats
just etl-backfill-territories
just etl-backfill-normalized
just etl-e2e
just etl-publish-representantes
just etl-publish-votaciones
just parl-quality-report-json
just etl-smoke-e2e
just etl-smoke-votes
```

UI de navegacion de grafo (Docker):

```bash
just graph-ui
```

Gate local del tracker:

```bash
just etl-tracker-status
just etl-tracker-gate
```

## Opcion alternativa: docker compose (sin just)

Todos los comandos Python se ejecutan dentro del contenedor `etl`, asi que no necesitas instalar Python en el host.

### Build de imagen

```bash
docker compose build etl
```

### Inicializar SQLite

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py init-db --db etl/data/staging/politicos-es.db"
```

### Ingesta live (cuando haya red)

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py ingest \
    --db etl/data/staging/politicos-es.db \
    --source all \
    --snapshot-date 2026-02-12 \
    --strict-network"
```

Extraccion live fuente por fuente (sin `just`):

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py ingest \
    --db etl/data/staging/politicos-es.db \
    --source congreso_diputados \
    --snapshot-date 2026-02-12 \
    --strict-network"
```

Gate local del tracker (falla si una fuente marcada `DONE` tiene `0` carga real):

```bash
docker compose run --rm etl \
  "python3 scripts/e2e_tracker_status.py --db etl/data/staging/politicos-es.db --tracker docs/etl/e2e-scrape-load-tracker.md --fail-on-done-zero-real"
```

UI de navegacion de grafo (Docker):

```bash
DB_PATH=etl/data/staging/politicos-es.db docker compose up --build graph-ui
```

Esto publica la UI en `http://localhost:8080` (usa `DB_PATH` para elegir otra SQLite).

Modo background:

```bash
DB_PATH=etl/data/staging/politicos-es.db docker compose up --build -d graph-ui
docker compose stop graph-ui
docker compose rm -f graph-ui
```

Override de variables:

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py ingest --db etl/data/staging/politicos-es.e2e9.db --source all --snapshot-date 2026-02-12 --strict-network"
DB_PATH=etl/data/staging/politicos-es.e2e9.db docker compose up --build graph-ui
```

Backfill opcional de normalizacion (una vez, para historico):

```bash
docker compose run --rm etl \
  "python3 scripts/ingestar_politicos_es.py backfill-normalized --db etl/data/staging/politicos-es.db"
```

Con `just`:

```bash
just etl-backfill-normalized
```

Backfill opcional de **referencias territoriales** (enriquece `territories.name/level/parent`):

```bash
just etl-backfill-territories
```

Nota de rendimiento:
- La ingesta normal (`ingest`) mantiene el camino rapido y no ejecuta backfills pesados.
- El backfill de tablas/columnas normalizadas se ejecuta solo bajo demanda con `backfill-normalized`.

## Consultas SQL utiles

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM persons;"
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) FROM mandates WHERE is_active=1 GROUP BY source_id;"
sqlite3 etl/data/staging/politicos-es.db "SELECT run_id, source_id, status, records_loaded FROM ingestion_runs ORDER BY run_id DESC LIMIT 5;"
```
