# Promise/action comparison MVP

Fecha: 2026-08-20

Estado: validado localmente; publicación live pendiente

## Resultado

Primer corte conservador que compara claims explícitas de un programa oficial con
acciones parlamentarias posteriores. Solo emite relaciones revisadas contra
evidencia primaria; una coincidencia de tema o palabra no puede convertirse por
sí sola en alineamiento o conflicto.

Release:
`vclc:comparison-release:ea65f3b8104dd678cb7ebce724b78f86`.

SHA-256 semántico:
`7b37c75c836a0a85c0aab70b7165a5ce005cef320c22c49e34ec650969691b19`.

SHA-256 del JSON público:
`24b6edd02329158040b50dc80a9191df3efea8ec07e10bbcb7adaaed280e0ca6`.

SHA-256 del SQLite materializado en esta ejecución:
`3cb4e0d5150c1e25a73950bb949786097461c5c2a9b8a2a80503a81bfc34e5df`.

Ese hash físico identifica el contenedor staging de esta ejecución, no la
identidad lógica de la release. Una evolución aditiva del schema global puede
cambiarlo sin alterar las filas semánticas; la identidad durable se demuestra
con la release, el SHA semántico y el JSON público.

Cobertura C1 validada:

- `5` assessments revisados sobre registros oficiales reales;
- `4` pares claim-acción y `1` búsqueda de acción acotada;
- `4` claims únicas;
- `18` evidencias;
- `3` estados `ambiguous_mapping`;
- `1` estado `insufficient_evidence`;
- `1` estado `not_comparable`;
- `0` estados `aligned`, `conflicted` o `changed_framing`;
- `0` comparaciones fuertes y ranking público oculto.

La búsqueda acotada de AP-9/AP-53 revisa `97` eventos y `97` filas nominales
entre `2023-07-05` y `2026-02-12`, con `0` coincidencias literales. Ese resultado
solo describe el corpus y alcance declarados: no demuestra inacción ni
incumplimiento.

## Qué cambia

- Contrato metodológico `docs/method/comparison-engine-v1.md`.
- Cuatro tablas SQLite aditivas para releases, revisiones, assessments y
  evidencia.
- Materializador determinista desde la base de promesas, votaciones y actor
  graph reales.
- La identidad de release incluye el corte de acciones, la release exacta del
  actor graph, los cuatro pares claim-acción y la proyección ordenada exacta de
  las `97` filas oficiales observadas por la búsqueda acotada. El lineage
  público conserva hashes semánticos; los hashes físicos de los contenedores
  SQLite quedan solo en los reports de ejecución.
- IDs estables para el objeto lógico comparado e IDs de revisión ligados al
  contenido canónico revisado.
- `changed_framing` queda rechazado en C1/v1 hasta incorporar evidencia
  actor-authored del mismo actor/capacidad y un gate dedicado.
- Evidencia primaria separada para claim, acción, identidad/afiliación y review.
- Estado explícito de capacidad del actor; un voto personal no se presenta como
  posición colectiva completa de su partido.
- Información personal publicada oficialmente conservada con identidad y
  provenance. No hay datos synthetic, mock, placeholder ni anonimización.
- Artefacto JSON acotado preparado para `/comparisons/` y
  `/comparisons/data/comparisons.json`.

## Contrato de verdad

Este corte permite afirmar que cinco relaciones o búsquedas concretas fueron
revisadas bajo el método v1 y que la evidencia disponible no autoriza ninguna
conclusión fuerte.

No permite afirmar:

- cumplimiento o incumplimiento general del programa;
- que la ausencia en el corpus sea ausencia de acción;
- que un voto de toma en consideración equivalga a aprobación sustantiva;
- que una iniciativa de tercero pruebe un cambio deliberado de framing;
- una posición colectiva completa desde el voto de una sola persona;
- cobertura exhaustiva de votos, decisiones, gasto, implementación u outcomes;
- causalidad, conducta antiética o corrupción.

La frescura es `stale`: el corpus de acciones termina el `2026-02-12`, aunque la
release local esté fechada el `2026-08-20`.

## Escala y atomicidad

El productor usa selección bulk indexada y escrituras `executemany` por lotes de
`10.000`. Las ejecuciones C1 observadas se mantienen alrededor de `51 MiB` de
pico RSS.

Esto no prueba una ejecución física de un millón de comparaciones. El gate
`million_row_physical_run_proven` permanece `false`.

Cada fichero se reemplaza atómicamente, pero DB, JSON publicado y copia pública
se promueven secuencialmente. `per_file_atomic_replacement=true` y
`artifact_set_atomic=false`; un proceso interrumpido exige validación antes de
publicar.

## Verificación local

```bash
just comparison-engine-export
python3 scripts/validate_promise_action_comparisons.py
UV_CACHE_DIR=/tmp/vclc-uv-cache \
  UV_PROJECT_ENVIRONMENT=/tmp/vclc-comparison-env \
  uv run --with pytest python -m pytest -q \
  tests/test_promise_action_comparison_real_pipeline.py
node --test tests/test_promise_action_comparison_ui_contract.js
just privacy-check-public-artifacts
just cloudflare-pages-build
```

El materializador, validator independiente, replay real y contrato UI pasan en
local. El JSON publicado y la copia pública son byte-idénticos. Una copia real
del SQLite fuente con solo `PRAGMA user_version` distinto produce exactamente la
misma release, hash semántico, JSON y DB derivados; el hash físico distinto queda
registrado únicamente en el report. No se ha declarado publicación live ni audit
remoto.

Evidencia:

- `docs/method/comparison-engine-v1.md`;
- `docs/etl/sprints/COMPARISON-ENGINE-20260820/evidence/comparison-materialization.json`;
- `docs/etl/sprints/COMPARISON-ENGINE-20260820/evidence/promise-action-comparisons-validation.json`;
- `scripts/verify_live_promise_action_comparisons.py`;
- `tests/test_promise_action_comparison_real_pipeline.py`;
- `tests/test_verify_live_promise_action_comparisons.py`;
- `tests/test_promise_action_comparison_ui_contract.js`.

## Siguiente

1. Publicar `/comparisons/` y el JSON exacto.
2. Verificar ruta, asset, bytes y SHA-256 live; guardar audit inmutable.
3. Mantener `TODO 29` abierto hasta completar ese gate.
4. Ampliar el corpus solo mediante mappings explícitos revisados y medir calidad
   estratificada antes de cualquier ranking.
5. Probar replay físico a escala, origin durable, restore y promoción
   transaccional del conjunto antes de alegar capacidad de millones.
