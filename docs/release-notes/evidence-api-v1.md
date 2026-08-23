# Evidence API v1

Fecha: `2026-08-19`

Estado: `publicado y verificado live`

## Qué cambia

Se publica una API estática de solo lectura para integradores y proyectos aliados:

- puntero current pequeño y release inmutable content-addressed;
- colecciones paginadas de entidades, evidence chains, salud de fuentes y
  resultados de preguntas;
- cursores seek opacos y páginas enlazadas por hashes;
- provenance por objeto hasta el export fuente y el snapshot scale firmado;
- `partial`, `blocked`, `unanswerable`, `unknown` y `no_signal` explícitos;
- nombres e identificadores oficiales públicos conservados sin redacción.

Release API: `feb61b39de9daddbcf53f5e1453cd9900c7272d6f1ee676ff9e3b8505729a300`.

## Evidencia

- `docs/etl/sprints/EVIDENCE-API-20260819/evidence/evidence-api-v1-export.json`;
- `docs/etl/sprints/EVIDENCE-API-20260819/evidence/evidence-api-v1-validation.json`;
- `docs/etl/sprints/EVIDENCE-API-20260819/evidence/live-evidence-api-v1-verification.json`;
- `docs/api/evidence-api-v1.schema.json`;
- `tests/test_evidence_api_v1_contract.py`.

El corte contiene `5,830` objetos reales en `26` páginas: `1,147` entidades,
`1,105` evidence chains, `48` estados de fuente y `3,530` resultados. La página más
grande mide `1,080,866` bytes. `1,147/1,147` labels se conservan exactos.

## Límite honesto

Esta release no convierte todas las `5,414,326` filas del origin en conclusiones.
Expone únicamente respuestas que el pipeline analítico actual puede sostener. Las
dimensiones no cubiertas siguen visibles como gaps.
