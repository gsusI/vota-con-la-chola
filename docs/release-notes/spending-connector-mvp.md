# Spending connector MVP

Fecha: 2026-08-19

Estado: publicado y verificado live

## Resultado

Primer recorrido canónico desde actores publicados por PLACSP hasta una adjudicación,
su importe exacto y la evidencia oficial. Usa la adquisición bulk real H1 2025 ya
preservada por el proyecto.

Corpus fuente:

- `6` ZIP oficiales / `667` miembros ATOM/CODICE;
- `330.577` versiones de registros de contratación;
- `262.558` versiones de resultados de adjudicación;
- `3.190.620` referencias documentales;
- archive de la muestra: `146.382.691` bytes, SHA-256
  `bda70aa0a7437d031e5d3f6114e5a637920ea1a460e1aba67d200209ae5eab7f`.

Release de datos:
`7abe9ac62d4af254aa41a2ffb2a7b4b9cf3e1ae607c6082329da17330a86a7a6`.

SHA-256 del JSON público:
`b09990e1c05be599d728156f1e98030a8d1f5eb08ea90139467fd471cc40df34`.

Muestra pública determinista:

- `20` adjudicaciones reales y `20` órganos distintos;
- `40` participaciones actor: órgano + proveedor;
- `38` anclas de evidencia: `20` source records capturados y `18` documentos
  oficiales enlazados;
- `10` proveedores persona jurídica, `5` posibles personas físicas y `5` sin tipo
  resuelto;
- nombres e identificadores oficiales retenidos exactamente, incluidos valores que
  el propio origen publique enmascarados;
- suma Decimal del importe adjudicado sin impuestos: `4.835.494,71 EUR`;
- suma Decimal del importe pagadero publicado: `5.845.384,70 EUR`.

## Qué cambia

- Nuevo contrato `docs/data-model/spending-spec-v1.md`.
- Cuatro tablas aditivas: `spending_items`, `spending_item_actors`,
  `spending_item_evidence` y `spending_item_links`.
- `14` event kinds separan presupuesto, notice, award, contrato, modificación,
  obligación, factura, pago, entrega, subvención y reintegro.
- Materializador bounded de latest versions PLACSP con IDs deterministas.
- DB pequeña reproducible con source records y filas source exactas del sample.
- Validator independiente de source counts, latest-version selection, actor/item/
  evidence joins, importes Decimal, FK, integridad, archive bytes/hash y retención de
  identidad.
- Consulta reproducible:
  `docs/examples/placsp-actor-spending-evidence.sql`.
- Página estática `/spending/` y feed
  `/spending/data/placsp-sample.json`.
- No se usa ningún dato synthetic, mock, generado o placeholder.

## Contrato de verdad

Todas las filas son `spending_kind=procurement_award` y
`amount_semantics=award_amount`. `paid_on` y `delivered_on` permanecen `NULL`.

La release no afirma:

- que se firmó el contrato;
- que se presentó o aceptó una factura;
- que se pagó el importe;
- que se entregó el bien o servicio;
- que la muestra es representativa;
- que una adjudicación es irregular, ilegal, poco ética o corrupta.

## Escala

El corpus PLACSP analítico existente ya publica `263.302` facts reales en `50`
particiones Parquet. Este MVP prueba el contrato de navegación canónica y UI; no
duplica ese corpus completo dentro del JSON.

Siguiente crecimiento:

1. materializar el corpus PLACSP completo por source/kind/year/bucket;
2. preservar segunda observación e historia de versions/tombstones;
3. capturar documentos con queues y cohortes `100 -> 1k -> 10k -> 100k`;
4. añadir contratos, facturas, pagos y entregas solo desde fuentes que prueben cada
   fase;
5. enlazar presupuestos y ejecución sin sumar semánticas incompatibles;
6. resolver actores con identificadores/revisión, nunca por nombre solo.

## Verificación

```bash
just placsp-spending-check
sqlite3 -header -column etl/data/staging/spending-placsp-mvp.db \
  < docs/examples/placsp-actor-spending-evidence.sql
just privacy-check-public-artifacts
just site-build
just placsp-spending-live-verify
```

Evidencia:

- `docs/etl/sprints/SPENDING-20260819/evidence/placsp-spending-materialization.json`
- `docs/etl/sprints/SPENDING-20260819/evidence/placsp-spending-validation.json`
- `tests/test_placsp_spending_real_pipeline.py`
- `tests/test_placsp_spending_ui_contract.js`

La publicación live devuelve HTTP `200` para `/spending/`, el JSON exacto de
`95.189` bytes y tres expedientes PLACSP de los estratos legal entity, potential
natural person y unclassified. El JSON live conserva SHA-256 `b09990e1...` y release
`7abe9ac6...`.

Evidencia live:

- `docs/etl/sprints/SPENDING-20260819/evidence/live-placsp-spending-verification.json`

## Siguiente

Ampliar a corpus completo y abrir el primer enlace real award -> contrato/pago/
entrega donde exista evidencia oficial suficiente.
