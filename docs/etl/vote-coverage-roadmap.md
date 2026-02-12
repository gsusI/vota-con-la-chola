# Vote Coverage Roadmap

Fecha de referencia: **2026-02-12**

Objetivo: cobertura util y trazable de "tema + votacion + voto por politico" en todos los niveles posibles, con pipeline reproducible.

## Estado actual (medido)

- `congreso_votaciones` (run parcial ampliado a legislaturas `15,14`): `120` eventos, `42000` votos nominales, fechas `2025-11-13` a `2026-02-12`.
- `congreso_iniciativas`: `428` iniciativas.
- `senado_iniciativas` (legislaturas `15,14`): `602` iniciativas.
- `senado_votaciones` (backfill historico): `5534` eventos y `1378583` votos nominales cargados para legislaturas con datos disponibles (`15,14,12,11,10`).
- `linking` Congreso (probe de control `max_files=10`, `max_votes=250`): `114/250` eventos enlazados (`109` por `title_norm_exact_unique`, `5` por `title_norm_prefix_unique`).

Nota: el endpoint Senado sigue siendo sensible a disponibilidad/red por entorno, pero ya existe corrida historica reproducible en este proyecto.

## Fase 1 (Nacional) - En curso

Meta: completar cobertura nacional reproducible (Congreso + Senado) con linking estable a temas.

1. Congreso votaciones historicas (hecho en codigo)
- Crawler multi-legislatura y multi-dia usando `targetLegislatura` + `diasVotaciones`.
- Flags de control: `--congreso-legs`, `--max-votes`, `--since-date`, `--until-date`.

2. Senado iniciativas historicas (hecho en codigo)
- Carga por legislaturas (`tipoFich=9`) con `--senado-legs`.
- IDs estables `senado:leg<leg>:exp:<tipo>/<num>`.

3. Senado votaciones historicas (hecho operativo)
- El conector ya soporta multi-legislatura.
- Corrida historica completada para legislaturas con datos expuestos por fuente (`15,14,12,11,10`).

4. Linking nacional (parcial)
- Senado: linking determinista `(legislature, expediente)` ya implementado.
- Congreso: linking por regex de expediente + matching de titulo normalizado (exacto y prefijo unico) ya implementado; queda medir KPIs globales y cerrar gaps.

## Fase 2 (Calidad de linking y publish) - Siguiente

Meta: artefacto publicable y consumible por UI/API.

1. Publicacion canónica de votaciones (hecho en codigo)
- Script: `scripts/publicar_votaciones_es.py` (snapshot `etl/data/published/votaciones-es-<snapshot>.json`).
- Genera artefacto con:
  - evento de voto
  - iniciativa/tema enlazado
  - voto por persona
  - trazabilidad de `source_id`, `source_url`, `source_record_pk`.
- Pendiente operativo: corrida completa y versionado regular del snapshot publicado.

2. KPIs de calidad y gaps
- `% eventos con tema`
- `% eventos con totales`
- `% eventos con voto nominal`
- `% votos nominales enlazados a person_id`
- `% eventos con enlace a tema` (por fuente y total)
- `% votos sin person_id (desglose por razón)` desde `quality-report --include-unmatched --unmatched-sample-limit N`

3. Progreso reciente
- Se añadió `events_with_initiative_link` y `events_with_initiative_link_pct` a `compute_vote_quality_kpis` y reportes de calidad para medir cobertura de topics por evento.

3. Endurecer resiliencia de red
- Retry/backoff por catalogo y fetches de detalle.
- Modo no estricto para "mejor esfuerzo" documentado, manteniendo `--strict-network` como gate duro.

## Fase 3 (Cobertura multinivel) - Siguiente ola

Meta: extender a CCAA, UE y municipal cuando exista fuente oficial de voto nominal.

1. Priorizar fuentes con datos estructurados
- Parlamentos autonomicos con XML/JSON/CSV de votaciones.
- Fuentes UE con voto nominal por MEP (si disponibles por API/feed estable).

2. Mantener contrato de idempotencia
- `source_record_id` estable por evento y por voto nominal.
- muestras reproducibles en `etl/data/raw/samples/`.

3. Mantener UX del Explorer
- FKs explicitas para navegacion tema -> votacion -> voto -> persona.

## Criterios de done para "all votes" (pragmatico)

Se considera "cobertura completa operativa" cuando:

1. Nacional
- Congreso + Senado con corridas `--strict-network` exitosas y `records_loaded > 0`.
- Backfill historico de legislaturas objetivo definido y reproducible.

2. Calidad minima
- `>= 95%` de eventos con fecha.
- `>= 95%` de eventos con tema enlazado.
- `>= 95%` de eventos con totales.
- `>= 90%` de votos nominales con `person_id` resuelto (donde exista censo de miembros).

3. Publish
- Snapshot versionado de votaciones disponible en `etl/data/published/`.
