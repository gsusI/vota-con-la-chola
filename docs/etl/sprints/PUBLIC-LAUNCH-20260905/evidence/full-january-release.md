# Release PLACSP de enero completo

Fecha: 2026-09-05

## Estado actual

La release anterior imponía un límite literal de 120 resultados y solo alcanzaba decisiones del 1 al 3 de enero de 2025. Ese límite no describía la disponibilidad del corpus.

La nueva generación elimina el tope en producción y valida toda la cohorte elegible de enero dentro del corpus congelado. Resultado: 2.632 filas, 47.744.719.885 céntimos EUR sin impuestos, decisiones del 1 al 31 de enero, 1.960 entradas XML, seis archivos oficiales y 350 miembros rehasheados.

Release inmutable: `aa4d608264906c78630786a2b6a2a6b58f38d0243ebee0c64810a82b3ed7d49f`. ZIP: 9.625.726 bytes; SHA-256 `ffa5cd49ff239d629394539df877c52366eb1938fb05b5f91524679ae14a2e1f`.

## Selección y normalización

El corpus contiene 141.747 hechos de resultado de adjudicación y produjo 10.394 candidatos de enero antes de validar el estado y la semántica fuente. La selección final excluye 7.720 anuncios sin adjudicación vigente o tombstones, 1.611 filas sin identidad o importe EUR exacto y 42 discrepancias entre Parquet y fuente; 129.742 hechos quedan fuera de enero.

Los nombres pasan por decodificación HTML, NFKC, espacios y puntuación. Un identificador publicado agrupa variantes aunque cambie la etiqueta de su esquema; sin identificador se usa una clave conservadora de nombre, mayúsculas y puntuación terminal. Cada fila conserva `authority_source_text` y `supplier_source_text` literales. El artefacto `name-aliases.json` registra nombre canónico, variantes y frecuencias.

Resultado: 521 órganos canónicos, 21 grupos con varias grafías y 125 filas reasignadas; 1.457 proveedores canónicos, 111 grupos con varias grafías y 202 filas reasignadas. El NIF `A61797536` aparece una sola vez en el selector como `GAS NATURAL COMERCIALIZADORA S.A.` y reúne nueve filas con cuatro grafías fuente y dos etiquetas de esquema.

## Verificación

- `python3 -m unittest tests.test_placsp_launch -v`: seis pruebas pasan; comprueban manifest, JSON/CSV, XML, tres consultas, rechazo de manipulación y normalización.
- `CLOUDFLARE_PAGES_FROZEN_INPUTS=1 just cloudflare-pages-build`: 1.427 rutas estáticas; límites de fichero, datos reales, payloads y privacidad pasan.
- Playwright local: 2.632 filas y 477.447.198,85 EUR; Select2 de Gas Natural ofrece una opción y devuelve nueve filas conservando grafías fuente; editar solo Desde mantiene Hasta; calendario 10–20 de enero actualiza ambos campos tras dos clics y devuelve 926 filas; viewport 390 × 844 conserva controles y resultados.
- El HTML no serializa las 2.632 filas. El cliente descarga `awards.json`, comprueba filas e importe contra `latest.json` y habilita los filtros solo cuando coincide.

## Publicación, dirección y siguiente acción

Publicación verificada: fuente `1925016eee3e1e643e16b17e0ad715fbc782cac5`; sitio `1b2b62588a`; release GitHub `v0.2.0-placsp-january-2025`. El dominio canónico sirve el puntero `aa4d6082…`, 2.632 filas y 477.447.198,85 EUR; el ZIP descargado anónimamente desde GitHub mide 9.625.726 bytes y coincide con SHA-256 `ffa5cd49…`. Playwright confirma en producción la carga completa y una sola opción para Gas Natural. La release de 120 filas permanece como historial inmutable.

Dirección: mantener releases mensuales fechadas, acotadas y reproducibles. Siguiente: recoger tres pruebas externas y dos reproducciones; ampliar meses solo mediante otra release con los mismos gates.
