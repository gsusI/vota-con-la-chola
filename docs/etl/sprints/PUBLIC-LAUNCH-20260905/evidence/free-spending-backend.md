# Backend gratuito de adjudicaciones — 2026-09-07

Ahora: Workers Free + D1 creados; 47.397 filas normalizadas, 18.662 órganos/proveedores y búsqueda indexada. Destino: `/spending/` pide páginas de 12 resultados y opciones acotadas; mantiene fuentes y CSV voluntarios. Estado: publicado y verificado. Siguiente: incorporar nuevas capturas con importaciones acotadas y mantener paridad y límites gratuitos.

## Decisión

Cloudflare reutiliza cuenta existente con plan **Free $0 Current plan**, verificado en panel. Límites duros, sin plan Paid ni productos con sobrecostes. Supabase [Free](https://supabase.com/pricing) se consideró: también evita cargos en Free, pero añade otra cuenta y su política de pausa por inactividad; no aporta ventaja para esta consulta pública de SQLite. No se promete disponibilidad o crecimiento ilimitados. Detalle operativo y fuentes: [backend](../../../../../infra/cloudflare/spending-api/README.md).

El Vínculo anuncia más de 50 millones de contratos y actualización diaria en su [web](https://el-vinculo.com/), consultada el 2026-09-07. Es una afirmación del proveedor, no una auditoría de cobertura. El backend nuevo resuelve la consulta; no incrementa ni actualiza por sí solo nuestro corpus, cuyo último día de adjudicación sigue siendo 2025-06-30.

## Verificación previa

- SQLite completo: 47.397 resultados, 4.865.774.429.683 céntimos, 11 correcciones de fecha.
- API recorrida localmente por cursor: ninguna fila duplicada ni perdida, importes iguales.
- Galasa 1999–2027: 8 resultados, 550.596.594 céntimos. Enero 2025: 1 resultado, 754.648 céntimos.
- Validación de fechas, límites, versión, ruta/método y error por indisponibilidad pasa.
- CSV paginado conserva cabecera única y fecha original; fallo impide entregar archivo parcial.
- Primera página: unos 15 KB de JSON, frente a 61 MB del JSON completo previo (comparación de datos sin compresión; no mide la descarga total de JS/CSS).
- Base importada inicialmente: 66.075 escrituras, 95,94 MB. Índices adicionales: 13.120 escrituras; total real importado 79.195, base remota 146,21 MB.
- Compilación Next y privacidad pasan. Interfaz publicada y navegador público verificado.

La autorización OAuth inicial fue rechazada por el control automático al incluir permisos de cuenta/DNS. Se redujo a los permisos de scripts Workers y D1, junto a lectura de usuario y acceso en segundo plano requeridos por OAuth; limitada a la cuenta del proyecto. No se modificaron DNS ni planes de pago.

API pública verificada: primera página 15.222 bytes y 0,33 s en esta medición; Galasa, enero, corrección 0023 y CSV remoto pasan. Worker `0caa67af-c0de-4ccd-be93-24ac724f7668`. [Mediciones](free-spending-api-verification.json).

## Reparación de alojamiento detectada en verificación pública

JavaScript del dominio devolvía HTTP 429 (`cf-cache-status: HIT`, `via: varnish`, cuerpo de limitación de GitHub). El Worker real usaba `raw.githubusercontent.com/.../gh-pages`, mientras la configuración local aún mencionaba Pages. Se descargó el Worker con autenticación nativa de Wrangler, preservando su comportamiento y rutas. Se añadieron 286 assets públicos (4,27 MB, privacidad sin hallazgos) con prioridad estática; los errores del proxy ya no se cachean. La versión activada al 100% es `3d9b5ec1-323f-43f0-95b6-f8ab72c52c6a`; no se modificaron DNS ni planes. Los archivos fuente originales conservan su distribución anterior.

## Cierre público

- Fuente inicial `4f78fb7721`; gh-pages `0756695001`; API `0caa67af-c0de-4ccd-be93-24ac724f7668`; router `3d9b5ec1-323f-43f0-95b6-f8ab72c52c6a`.
- Navegador en `https://votaconlachola.org/spending/`, caché desactivada para esta prueba: 19 respuestas de sitio/API observadas, ninguna con error, ninguna petición de `awards.json`, `awards.csv` o ZIP. Peticiones iniciales API: dos autocompletados y una página de 12 resultados, todas HTTP 200.
- Encabezado: 47.397 resultados; Galasa 1999–2027: 8 y 5.505.965,94 EUR. Paginación, búsqueda de expediente, fecha corregida y ancho móvil comprobados en interfaz; CSV remoto parseado: ocho filas e importes correctos.
- Recursos antes bloqueados ahora HTTP 200 desde Workers Static Assets. Rutas y dominios existentes conservados. La base remota queda con 47.397 filas y 4.865.774.429.683 céntimos; tabla de prueba temporal retirada.
- No se activó ningún plan de pago. Se mantiene el límite de disponibilidad impuesto por cuotas gratuitas compartidas; no constituye promesa de cobertura completa ni de tráfico ilimitado.
