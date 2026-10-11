# Adquisición PLACSP — ejecución del 26 de septiembre de 2026

Estado operativo y secuencia: [tracker](../../e2e-scrape-load-tracker.md#dn-02--2026-09-26--adquisición-y-cobertura-primero).
Este documento contiene resultados y comandos de reproducción, no otro roadmap.

## Resultado comprobado

| Familia | Archivo fuente | Versiones procesadas | IDs de expediente dentro de la cohorte |
| --- | --- | ---: | ---: |
| main | 202608 | 51,998 | 34,901 |
| minor | 202608 | 28,091 | 27,758 |
| aggregated | 202608 | 18,323 | 12,806 |
| minor | 2018 | 164,000 | 160,305 |
| minor | 2019 | 298,107 | 293,982 |

Cinco archivos oficiales completos, normalizados y exportados. Los conteos por periodo pueden solaparse; no representan contratos únicos nacionales. Las particiones Parquet separan avisos y resultados. Nunca sumar sus importes como gasto ejecutado ni presentar adjudicación/formalización como pago.

- [Resumen de ejecución](evidence/execution-summary.json): cuentas, validadores y límites.
- [Inventario](evidence/acquisition-inventory.json): 59 contenedores publicados en los tres catálogos (23 principal, 17 menores, 19 agregación), capturas locales y transiciones de almacenamiento.
- [Benchmark de agosto](evidence/benchmark-summary.json): descarga, normalización, exportación, RSS y almacenamiento por familia. Agosto es estacional, no una estimación de toda España.
- [Bloqueo de publicación](evidence/publication-blocker.json): el dry-run HF falla por generaciones incoherentes de extracción/validación documental. No se publicó ninguna de estas cohortes; la API pública comprobada sigue en 47.397 resultados.

## Reanudar o adquirir otro periodo

El runner exige una base dedicada y un catálogo oficial capturado. Una ejecución procesa exactamente un contenedor: encola de forma idempotente, descarga con TLS verificado, reanuda miembros, verifica SQLite/FKs, exporta y valida todos los Parquet. Mantiene recibo y bloqueo por base. No activa una release pública.

Ejemplo para el siguiente año de menores; añadir `--plan-only` muestra los comandos sin adquirir datos:

```sh
uv run --no-project --python 3.12 --with 'pyarrow>=18,<21' \
  python scripts/run_placsp_acquisition_batch.py \
  --catalog docs/etl/sprints/DINERO-NACIONAL-20260926/evidence/catalog-minor.json \
  --period 2020 --snapshot-date 2026-09-26 \
  --db etl/data/staging/placsp-minor-2020-20260926.db \
  --pipeline-id placsp-minor-2020-20260926 \
  --output-root etl/data/published/placsp-minor-2020-acquisition \
  --report-root docs/etl/sprints/DINERO-NACIONAL-20260926/evidence/minor-2020-run
```

El Python aislado necesitó el almacén CA ya verificado del runtime nativo para descargar. En ese entorno, anteponer `SSL_CERT_FILE="$(python3 -c 'import ssl; print(ssl.get_default_verify_paths().cafile)')"` al comando. No se desactiva TLS.

La reserva de **15 GiB se comprueba durante adquisición/normalización**. El exporter necesita espacio adicional: usar las mediciones del lote y revisar disco antes de empezar otra cohorte. Los límites de archivo de 512 MiB/2.000 miembros siguen siendo explícitos; no equivalen a soporte comprobado de todos los archivos anuales.

En 2019, el guard pausó tras 415 de 597 miembros. Después de compactar una cohorte terminada, se reanudaron los 182 pendientes y se cerró exportación/validación. Evidencia original: [pausa por almacenamiento](evidence/minor-2019-run/normalize-storage-stop.json) y [recibo de reanudación](evidence/minor-2019-run/run.json).

## Retención y restauración

Los SQLite expandidos nuevos de principal/agosto, menores/2018 y menores/2019 se compactaron con zstd. Antes de retirar cada copia expandida se comprobaron hashes, longitud descomprimida y recuperación byte a byte; en los anuales se consolidó WAL y comprobó SQLite. Se retienen ZIP oficiales, SQLite comprimidos y Parquet. La base histórica anterior y producción se preservaron.

Cada recibo de almacenamiento contiene `restore_command`, tamaño y SHA-256 esperado: [principal/agosto](evidence/cohort-compression.json), [menores/2018](evidence/minor-2018-run/storage-archive.json), [menores/2019](evidence/minor-2019-run/storage-archive.json). Reservar espacio para la expansión, restaurar y verificar el hash antes de reanudar un recibo archivado. El runner rechaza una base ausente para no recrearla silenciosamente y perder checkpoints.

## Verificación

19 tests de catálogo, ingestión, presupuesto de disco y aislamiento del runner pasan. Los cinco validadores Parquet independientes pasan; colas terminales, integridad y FKs pasan. Privacidad global pasó; publicación HF quedó bloqueada antes del empaquetado por el contrato documental existente. Capturas de catálogos y fuentes: [Hacienda](https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/Paginas/licitaciones_plataforma_contratacion.aspx).
