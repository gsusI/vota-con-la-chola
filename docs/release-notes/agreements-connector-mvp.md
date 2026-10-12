# Agreements and meetings connector MVP

Fecha: 2026-08-19

Estado: publicado y verificado live

## Resultado

Primer recorrido canónico desde una sesión del Consejo de Ministros hasta un
acuerdo, sus actores institucionales, clasificación temática y evidencia oficial.
Usa una captura real de páginas de referencias de La Moncloa.

Captura fuente:

- `20` referencias reales de `moncloa_referencias`;
- `11` registros cuyo resumen oficial contiene explícitamente `acuerdo`;
- JSON capturado de `21.234` bytes;
- SHA-256
  `ab08b7dc09a46c890f055e95fdeac5e7d716a5023f8792f19ce440a239271ddf`;
- cada fila conserva URL oficial, source record, hash individual, fecha y excerpt.

Release de datos:
`6f75ec32a5c085fbf71109919de785e48a5d7b2dcdf8ea13b2aaddfcffdf3753`.

SHA-256 del JSON público:
`8d8ce21967ac1c63a869dd2b5661877e789bb32fcc7e36f9626f9c2678fea678`.

Muestra pública determinista:

- `11` sesiones y `11` acuerdos ejecutivos adoptados;
- `22` relaciones meeting-actor: órgano convocante y organismo publicador, sin
  presentarlos como asistentes;
- `37` relaciones agreement-party: `11` adoptantes, `11` publicadores, `10`
  organismos afectados y `5` contrapartes explícitamente mencionadas;
- `20` asignaciones de tema rule-derived, visibles como `unreviewed`;
- `11` evidencias de reunión y `11` evidencias de acuerdo con excerpt y hash;
- `0` claims de asistencia personal;
- `0` influence assertions.

## Qué cambia

- Nuevo contrato `docs/data-model/agreements-influence-spec-v1.md`.
- Once tablas aditivas para meetings, participants, agenda, agreements, parties,
  evidence, topics, links e influence assertions.
- Materializador bounded sobre una captura oficial checksum-pinned.
- Validator independiente de source excerpt, fecha, URL, captura, actor mention,
  topic method, FK, integridad, idempotencia y publicación real-only.
- Consulta reproducible:
  `docs/examples/moncloa-actor-agreement-evidence.sql`.
- Página estática `/agreements/` y feed
  `/agreements/data/moncloa-sample.json`.
- No se usa dato synthetic, mock, generado o placeholder.
- Toda información personal pública que aparezca en futuras fuentes queda retenida;
  este corte concreto contiene actores institucionales, no una lista de personas.

## Contrato de verdad

La captura permite afirmar que La Moncloa publicó el resumen y que el Consejo de
Ministros adoptó el acuerdo descrito en la fecha indicada.

La release no afirma:

- que la captura contenga la lista completa de asistentes;
- que los organismos mencionados asistieran a la sesión;
- que el acuerdo esté firmado, vigente, ejecutado o cumplido;
- que exista una negociación, presión, quid pro quo o influencia;
- que exista conducta irregular, poco ética, ilegal o corrupta;
- que los topics derivados sean una clasificación humana confirmada.

## Escala

El modelo evita reescrituras al crecer a millones:

1. adquisición particionada por fuente, jurisdicción, periodo y cursor;
2. object storage content-addressed para HTML/PDF y SQLite solo para metadatos;
3. batches set-based, IDs deterministas e idempotencia por source record/ordinal;
4. keyset pagination e índices por actor, fecha, kind, topic y review state;
5. hechos y assertions separados físicamente;
6. snapshots, correcciones y supersession append-only;
7. publicación bounded con manifiestos completos y evidencia individual.

La promoción `R2` exige un millón de filas reales, segunda captura y diff, origin
durable/restore, `>=99,9%` con hash fuente, `0` FK failures y revisión de toda
inferencia publicable.

## Verificación

```bash
just moncloa-agreements-check
sqlite3 -header -column etl/data/staging/agreements-moncloa-mvp.db \
  < docs/examples/moncloa-actor-agreement-evidence.sql
just privacy-check-public-artifacts
just site-build
just moncloa-agreements-live-verify
```

Evidencia:

- `docs/etl/sprints/AGREEMENTS-20260819/evidence/moncloa-agreements-materialization.json`
- `docs/etl/sprints/AGREEMENTS-20260819/evidence/moncloa-agreements-validation.json`
- `tests/test_moncloa_agreements_real_pipeline.py`
- `tests/test_moncloa_agreements_ui_contract.js`

La publicación live devuelve HTTP `200` para `/agreements/`, el JSON exacto de
`108.229` bytes y tres referencias oficiales La Moncloa. El JSON live conserva
SHA-256 `8d8ce219...` y release `6f75ec32...`. La QA de navegador renderiza `11`
cards / `11` excerpts / `37` actor labels en desktop y viewport estrecho, sin
overflow, controles cortados ni errores de consola.

Evidencia live:

- `docs/etl/sprints/AGREEMENTS-20260819/evidence/live-moncloa-agreements-verification.json`

## Siguiente

Añadir una fuente oficial de agendas o lobbying con participantes personales
publicados; preservar nombres/cargos íntegros; capturar una segunda observación;
vincular agreement -> implementación solo cuando otra fuente la pruebe.
