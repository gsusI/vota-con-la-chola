# Gobernanza

Gobernanza para equipo pequeño: rápida, clara y sin proceso extra.

## Reglas
1. Cualquier cambio entra por PR.
2. Merge requiere:
   - checks en verde, y
   - 1 aprobación de codeowner (`.github/CODEOWNERS`).
3. Cambios sensibles (legal, seguridad, o esquema de datos publicados) requieren 2 aprobaciones del equipo core.
4. Si una PR queda bloqueada > 5 días, se escala al equipo core.
5. Nuevas fuentes usan issue `Data Source`, `just add-source`, y pasan `etl-contributor-gates` antes de merge.
6. Rotación: el codeowner que aprueba una nueva fuente queda como steward de esa fuente hasta el siguiente release publicado.

## Límites
- No RFC por defecto.
- No comités permanentes.
- No procesos adicionales sin bloqueo real demostrado.
