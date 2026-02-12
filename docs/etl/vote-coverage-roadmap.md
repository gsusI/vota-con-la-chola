# Vote Coverage Roadmap

Fecha de referencia: **2026-02-12**

Objetivo: cobertura util y trazable de "tema + votacion + voto por politico" en todos los niveles posibles, con pipeline reproducible.

## Estado actual (medido)

- `congreso_votaciones` (run parcial ampliado a legislaturas `15,14`): `120` eventos, `42000` votos nominales, fechas `2025-11-13` a `2026-02-12`.
- `congreso_iniciativas`: `428` iniciativas.
- `senado_iniciativas` (legislaturas `15,14`): `602` iniciativas.
- `senado_votaciones`: bloqueado en este entorno por fallo de red en catalogo (`RemoteDisconnected`), sin carga en esta corrida.

Nota: en corridas previas del mismo proyecto, `senado_votaciones` si cargo eventos y votos nominales; el bloqueo actual es de disponibilidad/conectividad del endpoint en este entorno.

## Fase 1 (Nacional) - En curso

Meta: completar cobertura nacional reproducible (Congreso + Senado) con linking estable a temas.

1. Congreso votaciones historicas (hecho en codigo)
- Crawler multi-legislatura y multi-dia usando `targetLegislatura` + `diasVotaciones`.
- Flags de control: `--congreso-legs`, `--max-votes`, `--since-date`, `--until-date`.

2. Senado iniciativas historicas (hecho en codigo)
- Carga por legislaturas (`tipoFich=9`) con `--senado-legs`.
- IDs estables `senado:leg<leg>:exp:<tipo>/<num>`.

3. Senado votaciones historicas (pendiente operativo)
- El conector ya soporta multi-legislatura.
- Falta corrida estable por disponibilidad de red del catalogo en este entorno.

4. Linking nacional (parcial)
- Senado: linking determinista `(legislature, expediente)` ya implementado.
- Congreso: linking por regex de expediente (best-effort), mejorar recall en fase 2.

## Fase 2 (Calidad de linking y publish) - Siguiente

Meta: artefacto publicable y consumible por UI/API.

1. Publicacion canónica de votaciones
- Generar snapshot en `etl/data/published/` con:
  - evento de voto
  - iniciativa/tema enlazado
  - voto por persona
  - trazabilidad de `source_id`, `source_url`, `source_record_pk`.

2. KPIs de calidad y gaps
- `% eventos con tema`
- `% eventos con totales`
- `% eventos con voto nominal`
- `% votos nominales enlazados a person_id`

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
