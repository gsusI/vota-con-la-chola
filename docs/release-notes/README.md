# Release-note flow

Estado: `operativo`
Fecha: `2026-08-19`

Este directorio registra cambios públicos reales. `releases.json` es el índice máquina; cada entrada apunta a una nota Markdown y a evidencia existente.

## Flujo mínimo

1. Implementar y verificar el cambio con datos reales.
2. Crear `docs/release-notes/<slug>.md` con fecha, estado, rutas, cambio, límites, comandos y evidencia.
3. Añadir la entrada correspondiente a `docs/release-notes/releases.json`, en orden descendente.
4. Ejecutar `just transparency-dashboard-export`; el exporter falla si falta la nota, una evidencia, una ruta pública o si el título no coincide con el H1.
5. Ejecutar los tests del slice y `just cloudflare-pages-build`.
6. Publicar el frontend mediante `just site-publish`.
7. Ejecutar `node scripts/audit_public_routes.js --base-url https://votaconlachola.org`.
8. Si el audit live falla, no declarar el cambio terminado. Corregir, regenerar, republicar y conservar evidencia del fallo y la reparación.

## Campos obligatorios del registro

- `id`: estable y único;
- `date`: fecha ISO real;
- `status`: estado factual;
- `title`: debe coincidir con el H1 de la nota;
- `summary`: una frase de impacto público, sin claims no verificados;
- `public_routes`: rutas realmente implementadas;
- `note_path`: Markdown existente;
- `evidence_paths`: uno o más ficheros existentes.

## Prohibiciones

- releases sintéticas, mock, placeholder o futuras;
- cifras sin enlace a fuente;
- estado `published_live_verified` sin audit live;
- esconder warnings, gaps, `unknown`, metadata drift o promociones pendientes;
- borrar una release histórica para mejorar la apariencia del dashboard.

## Política de identidad

Las notas y artefactos conservan información personal publicada oficialmente cuando sea necesaria para accountability. El gate de publicación elimina solo secretos, material de sesión privada, trazas del workstation y datos no públicos.
