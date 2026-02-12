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
- CLI ingesta politicos: `scripts/ingestar_politicos_es.py`.
- CLI ingesta Infoelectoral (descargas): `scripts/ingestar_infoelectoral_es.py`.
- CLI parlamentario (votaciones, iniciativas): `scripts/ingestar_parlamentario_es.py`.
- Plan de extraccion fuente por fuente: `docs/etl/extraccion-politicos-plan.md`.
- Tracker E2E scrape/load (TODO operativo): `docs/etl/e2e-scrape-load-tracker.md`.
- Roadmap de cobertura de votaciones: `docs/etl/vote-coverage-roadmap.md`.

Nota para votaciones:
- Flujo recomendado: `ingest -> backfill-member-ids -> link-votes -> quality-report -> publish`.
- Ejecuta `python3 scripts/ingestar_parlamentario_es.py link-votes --db <db>` antes de publicar si quieres maximizar `evento -> tema`.
- Ejecuta `python3 scripts/ingestar_parlamentario_es.py backfill-member-ids --db <db>` después de la ingesta de `congreso_votaciones,senado_votaciones` para resolver `person_id` en votos nominales.
- Sugerencia operativa: añade `--unmatched-sample-limit 50` para capturar casos sin emparejar y priorizar corrección manual por razón (`no_candidates`, `skipped_no_name`, `ambiguous`, ...).
- Revisa KPIs/gate con `python3 scripts/ingestar_parlamentario_es.py quality-report --db <db> --source-ids congreso_votaciones,senado_votaciones` y usa `--enforce-gate` para fallar en CI cuando no se cumpla el minimo.
- Para incluir diagnóstico de emparejado de persona en seco, usa `--include-unmatched --unmatched-sample-limit <n>`.
- Exporta KPIs por fecha con `python3 scripts/ingestar_parlamentario_es.py quality-report --db <db> --json-out etl/data/published/votaciones-kpis-es-<snapshot>.json`.
- El JSON de votaciones puede ser muy grande en corridas completas; para smoke/debug usa `--max-events` y/o `--max-member-votes-per-event`.

## Política de snapshots publicables

- Los artefactos publicados en `etl/data/published/` llevan la fecha de snapshot en el nombre (`...-<fecha>.json`).
- El snapshot se produce con `SNAPSHOT_DATE` y es reproducible para una fecha concreta.
- Política de refresco: re-generar `representantes` y `votaciones` cuando cambie la composición o tras mejoras de parsing/linking de fuente, documentando la fecha en commit y tracker.
- Mantener al menos un snapshot publicado por nivel operativo tras cambios de formato relevantes.

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
just parl-samples
just parl-link-votes
just parl-quality-report
just etl-stats
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

Nota de rendimiento:
- La ingesta normal (`ingest`) mantiene el camino rapido y no ejecuta backfills pesados.
- El backfill de tablas/columnas normalizadas se ejecuta solo bajo demanda con `backfill-normalized`.

## Consultas SQL utiles

```bash
sqlite3 etl/data/staging/politicos-es.db "SELECT COUNT(*) FROM persons;"
sqlite3 etl/data/staging/politicos-es.db "SELECT source_id, COUNT(*) FROM mandates WHERE is_active=1 GROUP BY source_id;"
sqlite3 etl/data/staging/politicos-es.db "SELECT run_id, source_id, status, records_loaded FROM ingestion_runs ORDER BY run_id DESC LIMIT 5;"
```
