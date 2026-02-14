# Calidad de dato (lean)

## Objetivo
Procesar texto y datos estructurados con trazabilidad, priorizacion clara y controles minimos de calidad.

## Pipeline minimo para fuentes de texto

1. **Ingesta raw**
- Guardar archivo original sin modificar en `etl/data/raw/`.
- Registrar metadatos minimos: `source_id`, `source_url`, `fetched_at`, `content_hash`, `content_type`.

2. **Normalizacion**
- Convertir a UTF-8 y texto plano (manteniendo referencia al original).
- Segmentar en bloques (`documento`, `seccion`, `parrafo`).
- Detectar idioma.

3. **Extraccion de evidencia**
- Extraer candidatos de evidencia con esquema fijo:
  - `actor_id`
  - `tema_id`
  - `tesis_id`
  - `tipo` (`dicho` o `hecho`)
  - `fragmento`
  - `source_url`
  - `source_hash`
  - `fecha_evento`
  - `confianza` (0-1)

4. **Validacion**
- Rechazar registros sin fuente o sin actor/tema.
- Rechazar duplicados exactos (`source_hash` + `fragmento_hash`).
- Marcar para revision humana si `confianza < umbral`.

5. **Publicacion**
- Solo publicar en `etl/data/published/` registros validos.
- Todo dato publicado debe poder trazarse al raw original.

## Priorizacion de datos a obtener

## Regla simple (score)
`prioridad = (impacto * fiabilidad_fuente) / esfuerzo`

- `impacto`: 1-5 (cuanto mejora la decision del usuario)
- `fiabilidad_fuente`: 0-5 (grado de oficialidad/verificabilidad)
- `esfuerzo`: 1-5 (coste tecnico/editorial)

## Escala practica de `fiabilidad_fuente` (0-5)

- `5/5` primaria con efectos: boletin/registro obligatorio con responsabilidad legal (ej: BOE, BDNS, PLACSP, EUR-Lex)
- `4/5` oficial estructurado: open data/datasets exportables con metadatos consistentes (ej: Congreso/Senado OpenData)
- `3/5` oficial comunicacional: notas, "referencias", agendas, RSS (hecho de comunicacion, no efecto juridico)
- `2/5` reutilizador fiable: ONG/academia que deriva de 4-5 (util, pero verificar contra original)
- `1/5` senal: prensa/redes/rumores (sirve para alertas, no evidencia)
- `0/5` sin trazabilidad: afirmacion sin fuente verificable

## Orden recomendado
1. **P0 (primero)**: convocatorias, resultados oficiales, votaciones Congreso/Senado, BOE.
2. **P1**: iniciativas e intervenciones oficiales.
3. **P2**: programas y contenido de partidos (texto no estructurado).

## Criterio de corte lean
- Si una fuente no llega a produccion en 2 semanas o no aporta mejora visible, se pausa.

## Controles de calidad minimos (no negociables)

1. **Completitud**
- `% registros con source_url y source_hash` debe ser 100% en published.

2. **Validez de esquema**
- 100% de registros deben cumplir tipos y campos obligatorios.

3. **Unicidad**
- Duplicados exactos < 1% por lote.

4. **Trazabilidad**
- 100% de registros published referencian un raw existente.

5. **Actualidad**
- SLA por fuente P0: actualizacion <= 24h en periodo activo.

6. **Revision humana minima**
- Regla de dos ojos solo para contenido sensible o baja confianza.

## Indicadores operativos semanales

- `published_total`
- `published_without_source` (objetivo: 0)
- `duplicates_rate`
- `low_confidence_rate`
- `p0_freshness_hours`
- `rejected_records_total`

## Definicion de listo (DoD) por conector

1. Descarga raw reproducible.
2. Normalizacion estable (sin errores criticos 3 ejecuciones seguidas).
3. Validaciones minimas en verde.
4. Al menos un snapshot en `etl/data/published/` consumible por la app.
5. Documento corto de limites conocidos del conector.

## Anti-burocracia

- No introducir nuevos estados/editoriales salvo bloqueo real.
- No crear mas de un dashboard de calidad al inicio.
- No añadir metricas que no disparen una accion concreta.
