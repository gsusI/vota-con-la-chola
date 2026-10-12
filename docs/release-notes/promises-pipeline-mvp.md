# Promises pipeline MVP

Fecha: 2026-08-19

Estado: publicado y verificado live

## Resultado

Primer flujo canónico y reproducible desde un programa electoral oficial hasta
claims, promesas, topics, evidencia exacta y una superficie ciudadana estática.

Fuente real: programa del BNG para las Eleccións Xerais 2023, publicado en la web
oficial del partido.

- URL: `https://www.bng.gal/media/bnggaliza/files/2023/07/05/23_bng_xerais_programa.pdf`
- SHA-256: `b8994deec0bbc45cdcbef5d7c5395cabf30b0509706303c3d8e76058c48eebfd`
- `396.842` bytes y `68` páginas.
- `266` segmentos reales y `266` anclas de evidencia.
- `97` candidatos de acción explícita; `91` promesas completas cargadas.
- `6` fragmentos de final de página quedan `needs_context` y no se publican.
- `26` compromisos blandos permanecen claims pendientes, no promesas confirmadas.
- `323` enlaces topic versionados.
- `20` promesas rule-confirmed en la muestra pública.

Release de datos:
`a3864cf278115becd5428afd0559985063a5c8b7e2bd459b244a6f07f1b81590`.

SHA-256 del JSON público:
`08a35fc3ff4f626331bd3e95a993f683163a6695dabfddfceb9e8dc6495eff52`.

## Qué cambia

- Nuevo contrato `docs/data-model/promises-spec-v1.md`.
- Seis tablas aditivas y navegables: documentos, runs, claims, evidencia,
  promesas y topics.
- Actor partido directo. No se crea una persona proxy para representar al BNG.
- Segmentación page-aware con IDs deterministas y replay idempotente.
- Cita exacta, offsets, página, URL, hash de cita y hash documental por claim.
- Topic tagging multilabel con método, versión y confianza.
- Página estática `/promises/` y feed `/promises/data/bng-2023.json`.
- La identidad y el texto públicos se conservan. No hay datos sintéticos, mock ni
  placeholders en el pipeline o la muestra.

## Límites explícitos

- Es una primera fuente y un solo partido. No permite comparación representativa.
- `rule_confirmed` describe la regla estructural aplicada; no afirma revisión
  humana independiente.
- La taxonomía por keywords es interpretable, pero necesita medición humana antes
  de promociones comparativas.
- `not_assessed` significa que no se evaluó cumplimiento. Esta release no afirma
  promesa cumplida o incumplida.
- Los claims ambiguos y fragmentos incompletos quedan fuera del sample público.

## Verificación

```bash
just manifesto-promises-check
just privacy-check-public-artifacts
just site-build
just manifesto-promises-live-verify
```

Evidencia:

- `docs/etl/sprints/PROMISES-20260819/evidence/promises-bng-2023-ingest.json`
- `docs/etl/sprints/PROMISES-20260819/evidence/promises-bng-2023-validation.json`
- `docs/etl/sprints/PROMISES-20260819/evidence/live-promises-bng-2023-verification.json`
- `tests/test_manifesto_promises_real_pipeline.py`
- `tests/test_manifesto_promises_ui_contract.js`

## Siguiente

Segundo manifiesto oficial ideológicamente distinto, muestra estratificada de
revisión humana y enlaces promesa -> decisión -> presupuesto -> ejecución sin
modificar la claim original.
