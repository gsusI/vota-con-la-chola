# Geopolitics connector MVP

Fecha: 2026-08-20

Estado: publicado y verificado live

## Resultado

Primer recorrido canónico de política exterior: fuente oficial -> acción -> actores
-> etapa jurídica -> evidencia. Usa la captura real y checksum-pinned de referencias
del Consejo de Ministros ya validada por la vertical de acuerdos.

Captura fuente:

- `20` referencias oficiales de La Moncloa;
- JSON capturado de `21.234` bytes;
- SHA-256
  `ab08b7dc09a46c890f055e95fdeac5e7d716a5023f8792f19ce440a239271ddf`;
- `2` registros califican mediante reglas deterministas sobre texto oficial;
- cada acción conserva URL, source record, hash, fecha y cita completa.

Release de datos:
`6683fd44eece98198ab3040e264c584b878cb33aa43be719ae19b99f58246204`.

SHA-256 del JSON público:
`ea8c3eb11ff2e31e0a6585ee3f965b7d6dd5d662b2953952f4eb440a988c880e`.

Muestra determinista:

- `2` acciones `treaty_process`;
- `11` relaciones actor-acción con identidad oficial intacta;
- `2` evidencias exactas y `2` links al acuerdo fuente;
- `4` topics derivados, visibles como `unreviewed`;
- `0` posiciones geopolíticas inferidas;
- `0` observaciones posteriores;
- `0` claims de entrada en vigor, implementación, influencia o resultado.

Acciones observadas:

1. `2026-01-13`: remisión/autorización relativa al acuerdo UE/Euratom/España
   sobre el Centro Común de Investigación de la Comisión Europea en Sevilla;
2. `2026-01-27`: remisión/autorización relativa al acuerdo España/Omán sobre
   exención recíproca de visados para pasaportes diplomáticos, especiales y de
   servicio.

## Qué cambia

- Contrato `docs/data-model/geopolitics-spec-v1.md`.
- Ocho tablas aditivas para acciones, actores, evidencia, topics, posiciones,
  evidencia de posición, links y observaciones posteriores.
- Materializador reproducible sobre la proyección de acuerdos y captura oficial.
- Validator independiente de bytes/hash, source record, excerpt, actores, etapa,
  estados desconocidos, FK, integridad, replay e identidad pública.
- Consulta:
  `docs/examples/moncloa-geopolitical-action-evidence.sql`.
- Página estática `/geopolitics/` y feed
  `/geopolitics/data/moncloa-sample.json`.
- Ningún dato synthetic, mock, generado, anonimizado o placeholder.

## Contrato de verdad

La fuente permite afirmar que el Consejo de Ministros aprobó la remisión a las
Cortes Generales y autorizó manifestar el consentimiento de España en los términos
del resumen oficial.

La release no afirma:

- firma, ratificación, publicación jurídica o entrada en vigor;
- aplicación, uso, cumplimiento o resultado;
- alineamiento, alianza, hostilidad o calidad de la relación diplomática;
- asistencia, negociación previa, lobbying, influencia o motivo;
- legalidad, irregularidad, conducta poco ética, corrupción, mérito o culpa;
- que las clasificaciones de scope/topic tengan revisión humana.

## Escala

El contrato físico prepara `10M` acciones, `100M` edges/evidencias y `1M`
documentos sin cambiar la ontología:

1. captura inmutable content-addressed y manifest-first;
2. colas bounded con checkpoint, deduplicación URL/hash y host-aware concurrency;
3. upserts lógicos exactly-once sobre workers at-least-once;
4. particiones Parquet por fuente, tipo y año/mes;
5. JSON público siempre bounded, cursor estable y release inmutable;
6. correcciones y estados posteriores append-only;
7. origin durable, restore, reconciliación, FK, real-only e higiene antes de `R2`.

## Verificación

```bash
just moncloa-geopolitics-check
sqlite3 -header -column etl/data/staging/geopolitics-moncloa-mvp.db \
  < docs/examples/moncloa-geopolitical-action-evidence.sql
just privacy-check-public-artifacts
just cloudflare-pages-build
just moncloa-geopolitics-live-verify
```

Evidencia local:

- `docs/etl/sprints/GEOPOLITICS-20260819/evidence/moncloa-geopolitics-materialization.json`
- `docs/etl/sprints/GEOPOLITICS-20260819/evidence/moncloa-geopolitics-validation.json`
- `tests/test_moncloa_geopolitics_real_pipeline.py`
- `tests/test_moncloa_geopolitics_ui_contract.js`

La publicación live devuelve HTTP `200` para `/geopolitics/`, el JSON exacto de
`13.937` bytes y las dos referencias oficiales La Moncloa. El JSON live conserva
SHA-256 `ea8c3eb1...` y release `6683fd44...`. La QA de navegador renderiza `2`
cards / `11` actor labels / `2` citas exactas / `8` estados `no evaluado` en
desktop y `390x844`, sin overflow, controles cortados ni errores de consola. El
audit global pasa `43` rutas / `47` assets / `119` evidencias, sin fallos.

Evidencia live:

- `docs/etl/sprints/GEOPOLITICS-20260819/evidence/live-moncloa-geopolitics-verification.json`

## Siguiente

Añadir una fuente BOE que pruebe publicación jurídica o entrada en vigor; después,
una fuente oficial de votaciones internacionales o sanciones. El link entre fuentes
solo puede cerrarse con identificador oficial o evidencia revisada, nunca por título
parecido.
