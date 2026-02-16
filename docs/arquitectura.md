# Arquitectura (MVP ultra-lean)

## Principio
Una sola app y un solo flujo de datos hasta validar utilidad real.

## Componentes minimos

1. **Frontend web**
- Cuestionario de prioridades.
- Resultado con explicacion y enlaces a evidencia.

2. **Backend API (monolito simple)**
- Lee datos consolidados.
- Expone endpoints para catalogo y calculo de resultados.

3. **Base de datos SQLite (MVP)**
- Tablas minimas: `sources`, `persons`, `parties`, `institutions`, `mandates`, `ingestion_runs`.
- Archivo unico reproducible para colaboradores y CI local.
- PostgreSQL se evaluara cuando haya necesidad real de concurrencia/escalado.

4. **Job diario de actualizacion**
- Recalcula snapshot publico.
- Registra fecha de generacion y fuentes.

## Flujo unico
1. Se actualizan datos oficiales.
2. Se valida formato minimo.
3. Se publica snapshot.
4. La API sirve resultados y evidencias al frontend.

## Capas futuras (sin romper el MVP)

El MVP ya cubre identidad, mandatos y evidencia parlamentaria + analítica por temas. Para llegar a “acción revelada” e “impacto” sin cambiar de arquitectura:
- Mantener el mismo patrón (ingesta -> normalización -> publicación) en SQLite.
- Usar las tablas ya presentes en `etl/load/sqlite_schema.sql` (scaffolding) para:
  - dominios y ejes (`domains`, `policy_axes`)
  - eventos con efectos (`policy_events`, `policy_instruments`, `policy_event_axis_scores`)
  - intervenciones (paquetes tratables) (`interventions`, `intervention_events`)
  - indicadores/outcomes (`indicator_series`, `indicator_points`)
  - estimaciones y diagnósticos (`causal_estimates`)

Nota KISS: el cuello de botella no es “tener tablas”, es poblarlas con conectores reproducibles + codebook/anotación (ver `docs/roadmap.md`).

## Reglas de simplificacion
- Una fuente de verdad para niveles/fechas: `docs/proximas-elecciones-espana.md` y `etl/data/published/proximas-elecciones-espana.json`.
- Cualquier documento extra debe reducir ambiguedad operativa, no crear proceso.
- Si una decision no desbloquea usuarios en 2 semanas, se pospone.

## Fuera del MVP
- Microservicios.
- Gobernanza editorial pesada.
- Frameworks de compliance avanzados mas alla de minimos legales.
- Infra multi-entorno compleja.

## Minimos no negociables
- Trazabilidad de fuentes.
- Reproducibilidad del snapshot.
- Seguridad basica de API y control de acceso de escritura.
