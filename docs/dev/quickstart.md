# Quickstart: desarrollo local rapido

Objetivo: poder arrancar un entorno local util en un solo comando usando un dataset minimo de pruebas.

## Prerequisitos

- Docker y just funcionando.
- `python3` disponible para el smoke de arranque del explorer.

## Un comando de entrada

```bash
just dev
```

Este comando ejecuta:

- build del contenedor ETL segun haga falta,
- inicializacion de una base de fixture local (`{{DEV_FIXTURE_DB_PATH}}`, por defecto `etl/data/staging/politicos-es.dev.db`) a partir de muestras pequenas,
- smoke interno de tablas minimas (`scripts/etl_smoke_e2e.py`),
- start del explorer en primer plano y verificacion de `GET /api/health`.

Si todo esta bien, el servidor queda listo en:

- `http://127.0.0.1:9010/explorer`

Ctrl+C lo cierra.

## Cambios rapidos recomendados

- Cambiar la ruta de DB local:

```bash
export DEV_FIXTURE_DB_PATH=etl/data/staging/politicos-es.dev.fast.db
just dev
```

- Probar que arranca sin dejar proceso vivo:

```bash
just dev-smoke
```

- Regenerar solo fixture sin dejar server levantado:

```bash
just dev-fixture
```

- Limpiar DB de fixture:

```bash
just dev-clean
```

## Nota de fixture

La fixture usa muestras existentes en `etl/data/raw/samples/` (`congreso_diputados_sample.json` y `congreso_votaciones_sample.json`) y evita llamadas de red para que la reproducibilidad sea consistente.
