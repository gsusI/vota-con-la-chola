# Vote explainer MVP

Estado: `mvp`
Fecha: `2026-04-04`

## Que se envio

Se publica el primer **vote explainer** estatico bajo:

- `/vote-explainer/`
- `/vote-explainer/<public_vote_id>/`

La ruta canonica por voto ya responde, usando solo el snapshot publico de votaciones:

- que se voto
- que paso en esa votacion concreta
- como votaron los grupos visibles en el snapshot
- donde estan las fuentes oficiales
- que caveats metodologicos aplican

## Contrato implementado

El MVP sigue `docs/product/vote-explainer-spec.md` y `docs/method/truth-contract.md` con estas decisiones:

- `public_vote_id` determinista: `<source_id>--<yyyymmdd>--<short_hash>`
- JSON estatico por voto en `vote-explainer/data/<public_vote_id>.json`
- metadata social pre-renderizada por voto
- caveats visibles para:
  - resultado derivado
  - iniciativa no enlazada
  - falta de URL oficial directa del evento
  - sub-votacion o lectura parcial del expediente
  - desglose parcial de grupos
  - frescura del snapshot cuando aplique

## Nota de demo

La demo publica actual sale del `manifest.json` exportado junto al resto de artefactos de `vote-explainer/data/`.

Flujo recomendado:

1. abrir `/vote-explainer/`
2. entrar en la primera votacion disponible del indice
3. contrastar la pagina con:
   - el enlace oficial principal
   - el enlace a `/explorer-votaciones/`
   - los caveats visibles al final de la pagina

## Limites conocidos del MVP

- usa solo el snapshot publico actual de votaciones
- no depende de `declared`
- no depende de `reviewed_implications`
- el bloque de grupos es un resumen parcial del snapshot publico, no un roll-call nominal completo
- la pagina no intenta explicar todo el expediente cuando la votacion es una parte concreta

## Verificacion minima

- test del contrato JSON y del routing canonico: `tests/test_export_vote_explainer_snapshot.py`
- build source para la ruta estatica:
  - `scripts/export_vote_explainer_snapshot.py`
  - `ui/gh-pages-next/app/vote-explainer/[publicVoteId]/page.js`
