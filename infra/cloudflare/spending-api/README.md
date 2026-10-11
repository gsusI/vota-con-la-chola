# Spending API

Backend público de solo lectura para `/spending/`. Workers Free + D1; la interfaz pide 12 resultados y opciones de búsqueda acotadas. La descarga completa solo ocurre por petición explícita.

## Coste y límites

Plan **Workers Free**, confirmado en el panel el 2026-09-07. Sin altas de pago, R2, Workers AI ni otros servicios facturables. Con este plan y las condiciones actuales, agotar las cuotas produce errores, no sobrecostes. No se promete disponibilidad ni capacidad ilimitadas. Las cuotas se comparten con los demás Workers/D1 de la cuenta.

- Workers: 100.000 peticiones/día; 10 ms de CPU por invocación.
- D1: 5.000.000 filas leídas/día, 100.000 escritas/día; 500 MB por base, 5 GB por cuenta.
- Corpus inicial: 47.397 adjudicaciones, 18.662 índices de órganos/proveedores; carga base real 66.075 escrituras y 95,94 MB; índices de búsqueda adicionales, 13.120 escrituras reales. Total importado: 79.195 escrituras; base remota 146,21 MB.
- Respuestas cacheadas una hora en cliente y hasta un día en edge, por versión de datos. La caché reduce lecturas; no elimina necesariamente invocaciones de Worker.
- La API nunca escribe en D1. La carga offline rechaza más de 90.000 escrituras estimadas o 450 MB. Revisar uso acumulado del día antes de importar; el presupuesto del generador no sustituye la cuota compartida de cuenta.
- No cambiar a Workers Paid: elimina los límites gratuitos de D1 y permite facturar excesos. Revalidar el plan antes de cada despliegue/importación.
- Al agotar cuota o fallar D1: HTTP 503, `Retry-After`, aviso visible y enlace a datos fuente. No descargar silenciosamente todo el corpus como fallback.

Fuentes oficiales consultadas el 2026-09-07: [Workers](https://developers.cloudflare.com/workers/platform/pricing/), [D1 precios](https://developers.cloudflare.com/d1/platform/pricing/), [D1 límites](https://developers.cloudflare.com/d1/platform/limits/), [aplicación de límites gratuitos desde septiembre](https://developers.cloudflare.com/changelog/post/2026-09-01-d1-free-tier-limit-enforcement/).

## Modelo

`awards.id` es un ordinal interno del snapshot, ordenado por fecha normalizada y claves originales. `payload` conserva la fila pública completa, incluidos identificadores y fecha fuente. `entities` almacena listas ordenadas de ordinales por órgano/proveedor, bajo clave primaria compuesta. Esto permite resolver ambos filtros mediante búsquedas de clave y `json_each`, sin reescribir varias veces cada adjudicación durante la carga inicial. Los totales globales por fecha salen de acumulados diarios en metadatos.

No usar los ordinales como identidad entre versiones: los enlaces de evidencia conservan sus claves originales. Los cursores CSV se fijan a una versión. La búsqueda de texto y el autocompletado usan un índice invertido de pares de caracteres: eligen la lista menos frecuente y verifican después la coincidencia completa. Las consultas muy comunes todavía pueden recorrer un subconjunto grande; caché y límites gratuitos protegen el coste, no garantizan tráfico ilimitado.

## API

- `GET /v1/status`: versión y cobertura.
- `GET /v1/options?kind=authority&q=galasa`: hasta 30 opciones; `supplier` también válido.
- `GET /v1/awards`: filtros `authority`, `supplier`, `start`, `end`, `q`; `after` y `limit` para cursor, máximo 200. Devuelve filas, número de resultados, céntimos, siguiente cursor y versión.
- `GET /v1/export`: mismos filtros, CSV por bloques, cabecera solo en primer bloque; `X-Next-Cursor` vacío finaliza. `version` fija la descarga al snapshot. Textos con prefijos de fórmula llevan apóstrofo para apertura segura en hojas de cálculo.
- CORS público; sin credenciales ni endpoints de escritura. SQL parametrizado y rutas/parámetros acotados.

## Reproducir y publicar

Desplegar la API desde la raíz del repositorio con `just spending-api-deploy`. Ejecuta primero el control de privacidad y despliega solo el Worker, conservando las variables remotas y la vinculación D1 existente. No importa datos ni consume escrituras D1. Requiere Wrangler 4 autenticado (`wrangler login`); no carga el `.env` del repositorio. Para validar sin publicar: `just spending-api-deploy --dry-run`.

Node con `node:sqlite` (22.13+), Wrangler 4 y corpus público congelado disponibles:

```sh
node scripts/build_spending_backend.mjs /tmp/spending-build
node tests/test_spending_backend.mjs /tmp/spending-build/verify.db
just privacy-check-public-artifacts
wrangler deploy --dry-run --config infra/cloudflare/spending-api/wrangler.jsonc
```

El generador emite SQL, SQLite de verificación, metadatos y reporte. No incluye XML/binarios en D1: siguen en el paquete estático verificable.

Para medir una release candidata sin cambiar `src/release.json` ni emitir SQL de importación, usar `node scripts/build_spending_backend.mjs <directorio-salida-nuevo> --plan-only --public-root=<directorio-launch-candidato>`. Ese directorio debe contener `latest.json` y su release con `awards.json.gz`. El reporte indica tamaño y escrituras estimadas; superar el presupuesto diario exige una importación acotada posterior, nunca ejecutar la carga completa por omitir el guard. Este modo crea solo artefactos locales de planificación y la base de verificación. Usar un directorio nuevo para no confundir archivos de una ejecución anterior.

Para un snapshot nuevo, crear otra base dentro del límite de almacenamiento y cuota diaria, actualizar la vinculación y cargar el SQL en la base vacía. No reimportar sobre la base activa ni promover datos sin comprobar filas, céntimos, fechas y consultas de referencia. Conservar versión anterior para rollback; retirar copias antiguas solo cuando se haya verificado su sustitución.

Cuando la carga exceda un día, generar un plan desde la base local verificada:

```sh
node scripts/plan_spending_import_batches.mjs <verify.db> <directorio-plan-nuevo>
node tests/verify_spending_import_plan.mjs <verify.db> <directorio-plan> <replay.db-nuevo>
```

El plan v2 conserva la versión candidata y checksums, limita cada lote a un presupuesto conservador de 20.000 escrituras y tolera repetir el mismo lote: la prueba lo ejecuta dos veces y compara todas las filas. Una restricción de base impide mezclar versiones. Comprobar cuota restante real de la cuenta y registrar consumo antes de cada ejecución remota; este generador no carga datos ni garantiza disponibilidad de cuota. Usar exclusivamente una base candidata nueva. Regenerar el plan después del sellado definitivo: una identidad provisional de planificación no debe promoverse. La activación del Worker queda al final, tras verificar todos los lotes y su paridad.

Ejecutar un solo lote y conservar su recibo:

```sh
node scripts/run_spending_import_batch.mjs <directorio-plan> <config-candidata-json> <directorio-ledger> <cuota-json> --dry-run
node scripts/run_spending_import_batch.mjs <directorio-plan> <config-candidata-json> <directorio-ledger> <cuota-json> --execute
```

La configuración candidata debe ser JSON estricto, contener una sola base `vclc-spending-national-*` y carecer de configuración de Worker/rutas. El archivo de cuota recoge una observación real del consumo total de la cuenta: `account_id`, `plan: "free"`, `source: "cloudflare-account-usage"`, `observed_at` ISO UTC, `daily_limit: 100000` y `rows_written` entero. No inventar estos valores ni derivarlos de una sola base. Se exige antigüedad máxima de cinco minutos, mismo día UTC, observación posterior al lote anterior y reserva adicional de 2.000 escrituras. La lectura del panel puede tener retraso y otros proyectos comparten cuota: el margen no garantiza ausencia de actividad concurrente.

El ejecutor fija identidad de plan/base, verifica checksum, crea un bloqueo local y registra la intención antes de llamar a Wrangler. Guarda solo consumo, tamaño y bookmark confirmados; no copia errores crudos a evidencia pública. Si falta confirmación, deja `pending` y no reintenta. Si el consumo supera el presupuesto, conserva el recibo y detiene la carga. Reconciliar con Cloudflare antes de resolver manualmente una operación pendiente; nunca borrarla para forzar el siguiente lote. El modo `--dry-run` no crea ledger ni llama a la red.

El generador emite `date-quality.json`. Fechas inválidas o años anteriores a 1900 que sigan sin resolver bloquean el modo normal y la generación de lotes. El ejecutor exige `date_quality_passed: true` en el manifiesto. El modo de medición puede conservarlas para diagnóstico; eso no autoriza publicación. Los cuatro casos detectados en la candidata nacional requieren representación explícita de fecha desconocida o corrección corroborada antes de regenerar el plan.

```sh
wrangler d1 execute vclc-spending --remote --config infra/cloudflare/spending-api/wrangler.jsonc --file /tmp/spending-build/import.sql --yes
just spending-api-deploy
```

Después de verificar la API: publicar frontend mediante `PLACSP_LAUNCH_SCOPED_PUBLISH=1 PLACSP_PUBLISH_SITE=<checkout-gh-pages> just explorer-gh-pages-publish`. Comprobar navegador, Galasa, CSV, evidencia y ausencia de carga automática de `awards.json`.

Rollback: desplegar la versión anterior de Worker con su base compatible; para volver temporalmente a la interfaz anterior, publicar el commit previo del componente. No modificar paquetes originales.

## Alojamiento de la interfaz

El router del dominio conserva las rutas existentes y sirve `/spending/`, portada, favicons y `_next/static` mediante Workers Static Assets. Son 286 archivos (4,27 MB), muy por debajo de los 20.000 del plan Free. Los archivos coincidentes se sirven antes de ejecutar el script; [peticiones estáticas gratuitas](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/). El resto mantiene el proxy previo. Los errores del proxy llevan `no-store`.

Motivo: comprobación pública detectó JavaScript con HTTP 429 de GitHub, cacheado durante 300 segundos. Esto impedía iniciar React aunque D1 respondiese. La publicación acotada actualiza también los assets mediante `scripts/publish_spending_static_assets.py`; activa una versión exacta, sin alterar DNS, dominios ni rutas. Wrangler usa su autenticación nativa. Nunca publicar desde una plantilla generada por C3: descargar e inspeccionar primero el Worker real.
