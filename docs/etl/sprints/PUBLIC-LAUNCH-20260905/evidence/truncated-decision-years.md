# Corrección de años truncados — 2026-09-07

Ahora: 11 adjudicaciones contienen años truncados en la fecha fuente. Dirección: normalizar la fecha usada por calendario, ordenación y CSV, conservando la fuente literal y los paquetes históricos inmutables. Estado: publicado; navegador público verifica calendario 01/01/2004–30/06/2025 y 47.397 resultados. Siguiente: conservar estas comprobaciones al incorporar nuevas capturas.

Regla: años de dos cifras se completan al año más reciente no posterior a la captura; 0023 corresponde a 2023 y 0099 a 1999. Los cinco resultados con 0204/0205 tienen correcciones específicas ligadas a sus expedientes (SDA 02/2023-1290 y 82/24-C), hacia 2024/2025. No se aplica esa corrección a otros expedientes.

Verificación: 11 correcciones, 47.397 filas e importes idénticos, transformación idempotente; rango corregido 2004-01-01 a 2025-06-30. El CSV añade decision_date_source y el paquete fuente permanece verificable por sus hashes originales.

Publicación: fuente `5ffd1c1195`; sitio `a6dee879b4`. Pruebas del corpus completo y compilación pasan. Verificación visual pública completada; botón CSV ejecutado, sin inspección independiente del archivo descargado en esta comprobación.
