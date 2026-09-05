# Ejecución PLACSP L0–L5 — 2026-09-05

Ahora: corte local verificado, consultas y demo implementadas. Destino: alfa técnica pública reproducible. Siguiente: build aislado, navegador, publicación y comprobación anónima remota. Revisión externa y adopción siguen pendientes.

## Evidencia L0/L1

- GET anónimo a `scale/latest.json` HF fija release `5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd` (consultar hash exacto en `audit.json`; no usar abreviaturas como pin).
- Descarga: 54 archivos PLACSP/controles, 21062691 bytes, 15,550 segundos; todos los tamaños y SHA-256 coinciden. Sin credenciales.
- Manifest corpus SHA-256 `b225f167d1fad027a0f8d3bac336ec96f9a5e06770f32db8c2f2af53810dda4b`: 263302 filas = 121555 anuncios + 141747 resultados. Etiqueta 2025-03-31; filas con capturas 2025-03-31 y 2025-06-30. La web anterior era otro universo; sus contadores no se trasladan al corte.
- Corte: 120 resultados, 76 entradas XML; 6 ZIP originales y 37 miembros rehasheados. Decisiones 2025-01-01 a 2025-01-03; suma 604519346 céntimos EUR sin impuestos. Selección ordenada, explícitamente parcial, solo código 8 y última versión no ambigua dentro del corpus congelado. No equivale a contratos únicos, pagos o cobertura completa.
- Replay original: mismos campos y resultados al parsear entradas XML con hash de ingesta. Textos literales de nombres se conservan junto a etiquetas normalizadas por espacios.
- Defecto detectado: un identificador de proveedor cambia minúscula a mayúscula en Parquet frente a su fuente. Las filas con discrepancias no entran en el corte. El corpus original no se corrige ni se certifica íntegramente en este lanzamiento. Seguimiento requerido sobre `publicdata_publish/money_partitions.py` y productor de identificadores; no reescribir release inmutable.
- Consultas calculadas también mediante agrupación Python independiente; SQLite reproduce proveedor, mes y detalle. Runtime consumidor: Python estándar. Primera ejecución local 0,029 segundos; prueba posterior del paquete incluye validación de texto literal.
- Tests del corte: 4 pasan, incluyendo comparación directa con elementos XML, paridad de ficheros, filtros, resultados vacíos y rechazo de ZIP alterado.

## Cambios previstos para publicación

Publicar únicamente código/exportadores del lanzamiento, consultas/guías/tareas, página spending, entrada de portada y bundle content-addressed. Checkout aislado desde HEAD; conservar modificaciones previas de escala fuera del commit. Antes de mutar remoto: build, privacidad/datos reales y pruebas del recorrido. Después: comprobar URL, descarga, SHA-256 y resultados.

No se envían convocatorias ni mensajes a terceros. Pruebas comunitarias 0/3 y reproducciones externas 0/2. Publicación como alfa técnica permitida por L4 con esos gates abiertos. L5 no equivale a adopción.

## Verificación de build y recorrido

- Build inicial sobre HEAD local: 1435 páginas. Se detectaron 30 commits locales fuera de main remoto, por lo que se descartó publicar esa base.
- Base de release: main remoto `2f3fa5305b33d39beee3f7e78775225b924265f9`; solo cambios del lanzamiento. Build de esa base: 1427 páginas. El despliegue conserva las rutas previas que no son portada o spending.
- Overlay: 166 archivos de lanzamiento/assets; 15110 archivos publicados ajenos conservados por hash, cero eliminaciones. Privacidad del sitio combinado: 15274 archivos, cero hallazgos.
- Tests: 5 pasan. Paridad entre bundle y cada archivo de descarga web; XML, céntimos, consultas/filtros y descarga alterada.
- Navegador real: TRAGSA 1 resultado/186000 céntimos; enlace recargado conserva resultado. CSV descargado contiene la misma fila/suma. Móvil 390 px sin overflow. Estado vacío y reduced-motion probados. Capturas visuales revisadas.
- Release del paquete `909fc46b5e065196b3b770344401229d5617b1639c002996bf49e6eca5811313`; ZIP 399945 bytes, SHA-256 `9d322d80c13247e835991d9187b75d5ad4c32d59bb440c1ca564672f242f7c9b`.
- Siguiente acción autorizada: commit aislado a main, overlay a gh-pages, verificación de hosting canónico, prerelease GitHub con bundle/runner/vídeo. No se publica el resto del trabajo local.

## Cierre técnico publicado

- Source commit `0d028cade343029a217d7706c64a64196acd7eca` publicado en main; sitio `8d146beff0afedc6587a8ae2dd1d69106ac99d09` en gh-pages. Los 30 commits locales previos no se publicaron.
- Dominio canónico verificado con navegador: 88/88 assets con SHA-256 y tamaño exactos, manifest fijado, filtros, enlace recargado y móvil sin overflow; cero errores JS observados. ZIP descargado desde navegador y curl: 399945 bytes y hash esperado.
- Comando documentado contra GitHub Releases: descarga anónima, directorio temporal vacío, tres consultas y 120 resultados, 604519346 céntimos; 1,057 segundos. Descarga directa con Python urllib al dominio devuelve HTTP 403; navegador/curl y ruta documentada GitHub funcionan. No se oculta esa limitación.
- Prerelease `v0.1.0-placsp-alpha.1`: ZIP, runner, vídeo H.264 de 64,4 segundos y SRT. Vídeo 800×450, yuv420p; decode completo sin errores, storyboard revisado.
- Integridad Git: se añadió atributo -text para impedir normalización CRLF en artefactos content-addressed. Se verificaron los bytes de 88 archivos más manifest/ZIP desde Git antes de push; el publicador vuelve a comprobar el index antes del commit.
- Gates externos abiertos: 0/3 personas ajenas prueban recorrido; 0/2 reproducen consulta. No hay aportaciones externas ni difusión directa registradas. Convocatoria preparada y no enviada. Siguiente: observar adopción a 14 días de la release y aceptar correcciones con crédito real.
- Evidencia estructurada: [live-verification.json](live-verification.json). El estado global de escala conserva sus bloqueos previos.

Revisión de adopción programada para el 19 de septiembre de 2026, 13:30 Europe/Madrid, una sola ejecución de lectura y evaluación. No autoriza envío de mensajes.

## CI global y gate propio

GitHub Pages build/deployment del commit de sitio finaliza `success`. El workflow ETL global no está verde: `million-scale-control-plane-contract` falla por capturas BDNS/votos y roots de corpora ausentes en el checkout de CI (mismo job fallaba antes de la alfa); `andalucia-water-receipt-contract` falla porque el recibo 2026-08-07 tiene 29 días frente al máximo de 8. El job de conectores strict-network sigue independiente. Ninguno se rebaja ni se presenta como cerrado.

Se añade `PLACSP Launch Gate`: en checkout limpio y Python 3.12 verifica bytes Git, las cinco pruebas del paquete y privacidad de artefactos/guía. No descarga bases privadas ni omite controles globales. Workflow: `.github/workflows/placsp-launch-gate.yml`.
