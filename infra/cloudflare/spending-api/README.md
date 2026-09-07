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

Node con `node:sqlite` (22.13+), Wrangler 4 y corpus público congelado disponibles:

```sh
node scripts/build_spending_backend.mjs /tmp/spending-build
node tests/test_spending_backend.mjs /tmp/spending-build/verify.db
just privacy-check-public-artifacts
wrangler deploy --dry-run --config infra/cloudflare/spending-api/wrangler.jsonc
```

El generador emite SQL, SQLite de verificación, metadatos y reporte. No incluye XML/binarios en D1: siguen en el paquete estático verificable.

Para un snapshot nuevo, crear otra base dentro del límite de almacenamiento y cuota diaria, actualizar la vinculación y cargar el SQL en la base vacía. No reimportar sobre la base activa ni promover datos sin comprobar filas, céntimos, fechas y consultas de referencia. Conservar versión anterior para rollback; retirar copias antiguas solo cuando se haya verificado su sustitución.

```sh
wrangler d1 execute vclc-spending --remote --config infra/cloudflare/spending-api/wrangler.jsonc --file /tmp/spending-build/import.sql --yes
wrangler deploy --config infra/cloudflare/spending-api/wrangler.jsonc
```

Después de verificar la API: publicar frontend mediante `PLACSP_LAUNCH_SCOPED_PUBLISH=1 PLACSP_PUBLISH_SITE=<checkout-gh-pages> just explorer-gh-pages-publish`. Comprobar navegador, Galasa, CSV, evidencia y ausencia de carga automática de `awards.json`.

Rollback: desplegar la versión anterior de Worker con su base compatible; para volver temporalmente a la interfaz anterior, publicar el commit previo del componente. No modificar paquetes originales.
