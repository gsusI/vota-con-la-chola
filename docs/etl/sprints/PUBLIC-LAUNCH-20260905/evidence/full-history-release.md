# Histórico PLACSP completo disponible

Fecha: 2026-09-06

- Ahora: el exportador anterior limitaba a enero de 2025 antes de aplicar el calendario; Galasa mostraba una sola adjudicación incluso con 1999–2027.
- Destino: consultar todas las adjudicaciones elegibles del corpus disponible, sin límite de mes o filas; conservar la última versión no ambigua, importes exactos, identidades y XML.
- Nueva selección: 47.397 resultados, 4.865.774.429.683 céntimos, 32.783 capturas XML revalidadas contra seis archivos oficiales y 666 miembros. No son pagos ni cobertura exhaustiva de fuentes.
- Galasa 1999–2027: 8 resultados y 550.596.594 céntimos; enero de 2025: 1 y 754.648 céntimos. Prueba de regresión automatizada pasa.
- Transporte: gzip reversible para JSON/CSV/XML y partes de ZIP de 20 MiB. El calendario consulta todo el JSON, sin paginación ni recorte de datos en origen. La paginación solo limita tarjetas renderizadas.
- Integridad: siete pruebas de datos pasan; nueve de privacidad pasan. El escáner distingue el login público de Vortal de rutas locales, manteniendo detección de rutas privadas cercanas y de otros hosts. No se modificaron XML para resolver el falso positivo.
- Fechas: se conserva la fecha publicada; algunos registros fuente contienen años atípicos, incluido 0023. El rango inicial abarca todas las fechas disponibles. Las fechas inválidas se registran como exclusión; el sufijo Z de fecha se normaliza sin cambiar día.
- Estado: PUBLICADO y verificado en el dominio canónico. Siguiente: ampliar cobertura solo al incorporar nuevas fuentes o capturas; mantener todo el histórico elegible accesible.

Prueba local de navegador: selección de Galasa y rango 1999–2027 devuelve ocho filas y 550.596.594 céntimos; CSV y XML descargados y cotejados. Se corrigió además la edición rápida de fechas: cambiar Desde ya no restablece un Hasta que se está editando; cada campo envía solo su valor cambiado. Repetición completa pasa: rango amplio, enero, restauración del enlace, CSV, XML y móvil 390×844 sin desbordamiento.

## Publicación verificada

- Código: `731599a6ebeb413e5df4f8e9f3418a67a168c303`; sitio: `5f7e1bbdf6`. Release: `0e55b07120bcb42731b45a78fd682813cd6a51793232faee805ddce46be32a90`.
- Dominio: `https://votaconlachola.org/spending/`. Puntero público: 47.397 resultados y 4.865.774.429.683 céntimos.
- Playwright público: seleccionar Galasa, editar Desde 01/01/1999 y Hasta 31/12/2027 devuelve 8 resultados y 5.505.965,94 EUR; enero vuelve a 1 resultado y 7.546,48 EUR; restaurar enlace vuelve a 8. CSV público descargado contiene ocho filas y suma exacta; XML público descargado coincide con SHA-256. Móvil 390×844 sin desbordamiento.
- El primer acceso de verificación recibió HTML previo en caché; revalidación canónica y navegador con caché desactivada confirmaron la release nueva.
- `just explorer-gh-pages-publish` ejecutó tests, build, límites, privacidad, overlay e integridad Git; se reanudó únicamente su push final después de publicar main para evitar transferencias simultáneas duplicadas. Push de gh-pages final correcto. Se conservaron exactamente 17.290 archivos ajenos al cambio y no se eliminó ninguno.
