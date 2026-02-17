# Roadmap (producto + datos + impacto)

Este documento es el roadmap "macro" del proyecto.

Fuente de verdad para ejecucion y estado (no duplicar roadmaps en otros docs):
- `docs/roadmap-tecnico.md` (ejecucion de corto plazo).
- `docs/etl/e2e-scrape-load-tracker.md` (backlog operativo de conectores/quality).
- Dashboard local: `/explorer-sources` (progreso vs roadmap).

## Visión y misión

Visión:
- Que cualquier persona en España pueda decidir su voto con la misma exigencia con la que audita una cuenta pública: comparando **lo que se promete, lo que se ejecuta y lo que impacta**, con evidencia verificable en su nivel territorial (Estado, CCAA, municipal, UE).

Misión:
- Construir y operar una infraestructura cívica abierta, reproducible y auditable que transforme datos públicos fragmentados en explicaciones claras y trazables para:
  1. medir alineamiento ciudadano-político,
  2. contrastar "dicen vs hacen",
  3. estimar impacto cuando sea metodológicamente defendible.

## Cómo estimamos esfuerzo (puntos)

Este roadmap no usa fechas. Priorizamos por valor, dependencia y esfuerzo.

Puntos (escala tipo Fibonacci; estiman complejidad, riesgo e incertidumbre, no tiempo):

| Puntos | Guía rápida | Ejemplos típicos |
|---:|---|---|
| 1 | cambio trivial | ajuste de KPI, fix pequeño, índice nuevo |
| 2 | pequeño | endpoint simple, conector con contrato estable, backfill chico |
| 3 | medio | normalizador con edge cases, UI con estado + filtros, QA básico |
| 5 | grande | conector con varias rutas, modelo nuevo en SQLite + publish + KPIs |
| 8 | muy grande | integración multi-fuente con linking y gates; UI "modo auditor" completo |
| 13 | épico | nueva capa de producto o modelo (p.ej. causalidad) con múltiples fuentes |
| 21 | programa | varios épicos coordinados (p.ej. 3 conectores + modelo + gates + publish) |
| 34 | expansión | multipaquete multinivel/infra + QA + operaciones |

Tipos de esfuerzo (para que no se nos esconda el trabajo manual):
- `ENG`: ingeniería (ETL/esquema/publicación/UI/ops).
- `HUM`: trabajo humano inevitable (codebook, anotación, definición de intervenciones, revisión ambigua).

## 0) Qué vamos a medir (salidas del sistema)

Separar explícitamente tres productos distintos y auditables:
- **Alineamiento**: preferencias del usuario vs posiciones públicas agregadas por tema y `scope` (municipal/autonómico/estatal/UE).
- **Acción revelada**: qué hizo un actor/partido descompuesto en un **vector** por ámbitos (y ejes dentro del ámbito), con pesos transparentes y **incertidumbre**.
- **Impacto** (cuando sea defendible): estimaciones con diseño causal (DiD, event study, synthetic control, etc.) y diagnósticos; si no se puede identificar, se etiqueta como asociación y ya.

Regla de producto: por defecto no hay "número mágico". Si se quiere un ranking, debe ser un modo configurable con pesos explícitos y análisis de sensibilidad.

## 1) Principios de diseño (no negociables)

Los principios operativos ya están en `docs/principios-operativos.md` y `AGENTS.md`. En el roadmap, esto se concreta en:
- **Reproducibilidad**: un solo SQLite; snapshots por `snapshot_date`; preferir `--from-file` y/o muestras deterministas.
- **Trazabilidad**: cada fila importante tiene `source_id`, `source_url` o `source_record_pk`, `raw_payload` (o enlace a raw) y hash.
- **Ingesta rápida**: evitar N+1; caches en memoria por corrida; upserts idempotentes.
- **Navegación por esquema**: FKs explícitas; PKs simples; el Explorer debe seguir funcionando aunque crezca el esquema.

## 2) Ámbitos (dominios) a priorizar en España

Tier 1 (MVP de utilidad cotidiana y prosperidad, prioriza conectores y codebook):
- Economía y empleo
- Coste de vida (inflación, energía, cesta básica)
- Sanidad y salud pública
- Educación y capital humano
- Vivienda y urbanismo
- Impuestos, gasto público y sostenibilidad fiscal
- Justicia, seguridad y orden público
- Energía y medio ambiente (por precio/suministro y salud)
- Infraestructura y transporte
- Protección social y pensiones

Tier 2/3 (expandir cuando Tier 1 esté estable):
- Ciencia/innovación/digitalización, competencia, migración, calidad administrativa, agricultura, industria, cultura/medios, exterior/defensa, turismo, consumo, igualdad, juventud, cohesión territorial, medidas simbólicas.

## 3) Taxonomía de fuentes (para escalar sin inventar)

Usar `docs/fuentes-datos.md` como inventario operativo y mantener esta separación en el modelo:
- **Acción institucional primaria**: parlamento (votos/iniciativas), normativa (BOE y boletines), presupuesto (aprobado y ejecución), implementación (contratación y subvenciones), nombramientos y acuerdos.
- **Outcomes**: indicadores oficiales (INE/Eurostat/OCDE/BDE y registros sectoriales).
- **Confusores/contexto**: macro, demografía, shocks energéticos, clima.
- **Fiscalización/control**: AIReF, Tribunal de Cuentas, auditorías (calidad institucional, eficiencia, fraude).
- **Catálogos/metafuentes**: datos.gob.es, data.europa.eu para discovery (no confundir con "los datos").

## 4) Ontología mínima (cómo lo encajamos con el esquema actual)

El esquema actual ya cubre buena parte de lo "mínimo" para el ledger de evidencia:
- Actores y roles: `persons`, `mandates`, `roles`, `parties`, `institutions`, `territories`, `admin_levels`.
- Acción parlamentaria: `parl_vote_events`, `parl_vote_member_votes`, `parl_initiatives`, `parl_vote_event_initiatives`.
- Temas y evidencia trazable: `topics`, `topic_sets`, `topic_evidence`, `topic_positions`.

Lo que falta para el marco "acción revelada + impacto" (plan de evolución aditiva):
- **Dominios y ejes**: `domains`, `policy_axes`, `event_axis_scores` (o equivalente) para pasar de "tema" a vector por ámbito.
- **Eventos de política (más allá del parlamento)**: `policy_events` con FK a `policy_instruments` (ley/decreto/presupuesto/contrato/subvención/etc.) y enlaces a evidencia primaria.
- **Intervenciones**: agrupación reproducible de eventos en paquetes tratables (`interventions`, `intervention_events`).
- **Indicadores**: `indicator_series` + puntos (y metadatos de definición/cambio metodológico).
- **Estimaciones**: `causal_estimates` + diagnósticos y `evidence_links` (hashes/URLs/IDs) para auditoría.

Regla: cada tabla nueva importante debe tener PK simple y FKs declaradas para que el Explorer navegue bien.

## 4.1) Algoritmo (núcleo) y pipeline objetivo en este repo

Esta es la traducción práctica del pseudocódigo a piezas del repo (sin meter "backfills pesados" en `ingest`):
- Definir y versionar taxonomía + codebook: vivir en `docs/` y alimentar clasificadores/reglas (humano en el loop).
- Curar fuentes core: inventario en `docs/fuentes-datos.md` y `sources` en SQLite (con `scope`).
- Ingesta reproducible por `snapshot_date`: CLIs `scripts/ingestar_*.py` hacia `etl/data/staging/*.db`.
- Trazabilidad de raw: `raw_fetches`, `run_fetches`, `source_records` y `raw_payload` por tabla final.
- Normalización y entity resolution: `persons`, `mandates`, `parties`, `institutions`, `territories` (con `person_identifiers` cuando exista).
- Extracción de eventos: hoy `parl_*` + (roadmap) `policy_events` para BOE/dinero público/ejecutivo.
- Clasificación a dominios/ejes: guardar scores y métodos (reglas + anotación) y nunca ocultar "incierto/no observable".
- Agregación reproducible de posiciones por tema: `topic_evidence` -> `topic_positions`.
- Agregación reproducible de acción revelada por dominio/eje: `policy_events`/scores -> snapshots vectoriales por actor/partido y `scope`.
- Publicación de artefactos canónicos: `etl/data/published/*-<snapshot_date>.json` + KPIs por snapshot.
- Distribución pública gratuita de snapshots en Hugging Face Datasets: `snapshots/<snapshot_date>/...` + `latest.json` para colaboración externa y réplica.
- UI/API: `scripts/graph_ui_server.py` + `ui/graph/*` para explorar esquema, evidencia y resultados.

## 4.2) Estado actual (baseline)

En alto nivel, ya existe:
- Núcleo de datos reproducible: SQLite único + trazabilidad de runs/raw + upserts idempotentes.
- Cobertura amplia de representantes/mandatos (nacional, autonómico, municipal) con tracker operativo en Docker.
- Capa parlamentaria funcional (Congreso/Senado) para eventos de voto + votos nominales + iniciativas, con linking y KPIs de calidad en curso.
- Esquema analítico "schema-first" para temas y evidencia (`topics/*`) y UI de exploración genérica por FKs.

Principales huecos para el marco "acción revelada + impacto":
- Codebook y ejes por dominio (Tier 1) versionados y aplicables.
- Modelo canónico de eventos fuera del parlamento (BOE/ejecutivo/dinero público) con evidencia primaria y drill-down.
- Ingesta de outcomes/confusores + capa de intervención/estimación para impacto (solo cuando sea defendible).

Para detalle operativo, usar:
- `docs/roadmap-tecnico.md` (corto plazo, cerrar loop "dicen/hacen" + fiabilidad).
- `docs/etl/e2e-scrape-load-tracker.md` (conectores y DoD).

## 4.3) Ruta crítica (qué desbloquea valor)

Si solo hiciéramos cinco cosas (en orden), serían:
- Hacer "boring y estable" el loop nacional de votaciones: ingest -> linking -> KPIs -> publish (gates en verde).
- Semillar y versionar un `topic_set` Tier 1 por `scope` (al menos nacional) y poblar `topic_evidence` desde votos.
- Agregar posiciones reproducibles (`topic_positions`) y exponer drill-down a evidencia en UI.
- Añadir una primera fuente de acción con efectos fuera del parlamento (BOE o dinero público) como `policy_events` trazables.
- Definir el primer "paquete de intervención" end-to-end (eventos -> indicadores -> diseño -> diagnóstico), aunque sea en un solo dominio.

## 5) Roadmap por fases (por esfuerzo)

### Fase 0: base metodológica y de datos (`ENG: 3`, `HUM: 13`)

Objetivo: nacer "a prueba de auditoría" y evitar un ranking con apariencia científica.

Entregables:
- **Taxonomía v1**: Tier 1 y Tier 2, con definición operacional (qué cuenta como evidencia y qué no). Ver `docs/domain_taxonomy_es.md`.
- **Codebook v1 (Tier 1)**: 6-10 ejes por dominio, con ejemplos y reglas de codificación. Ver `docs/codebook_tier1_es.md`.
- **Protocolo de anotación**: doble anotación, acuerdo inter-anotador, arbitraje, versionado del codebook. Ver `docs/annotation_protocol_es.md`.
- **Contrato de neutralidad operativa**: separar "acción revelada" de "valoración" (pesos configurables y sensibilidad).
- **Definición de intervención** (plantilla): cómo empaquetar normas y ejecución en tratamientos tratables. Ver `docs/intervention_template_es.md`.

Definition of Done:
- El codebook tiene versión, ejemplos, y reglas de "no observable" (no imputar por defecto).
- Existe un checklist de trazabilidad (mínimos por fila) aplicable a todas las fuentes nuevas.

### Fase 1: MVP "acción verificable" a nivel Estado (`ENG: 21`, `HUM: 8`)

Objetivo: producir fichas auditables de "lo que hicieron" (sin causalidad fuerte todavía).

Alcance de fuentes (P0/P1):
- Cortes Generales (Congreso + Senado): votos + iniciativas + linking.
- BOE: normativa publicada (y versiones cuando aplique).
- Presupuesto Estado: aprobado y ejecución cuando sea obtenible.
- Dinero público: contratación (PLACSP/OpenPLACSP) y subvenciones (BDNS/SNPSAP) al menos en agregado reproducible.

Entregables:
- Ledger mínimo de `policy_events` (parlamento + normativa + dinero público) con `EvidenceLink` reproducible.
- Action vectors v1 por actor/partido y dominio (Tier 1) con pesos transparentes.
- Señal de incoherencia v1: contradicciones intra-dominio y "dicho vs hecho" cuando existan ambos, siempre con drill-down a evidencia.
- UI: drill-down desde vector -> eventos -> evidencia primaria (modo auditor).

Gates de calidad:
- `PRAGMA foreign_key_check` sin filas.
- En fuentes marcadas como operativas: `records_loaded > 0` y umbral mínimo por fuente en `--strict-network`.
- Cobertura mínima de linking voto -> iniciativa/tema en nacional (medida en KPIs publicados).

### Fase 2: multinivel (3 CCAA piloto) (`ENG: 21`, `HUM: 8`)

Objetivo: capturar donde está gran parte del impacto real en España (competencias autonómicas).

Selección piloto (criterios técnicos, no políticos):
- Población alta + heterogeneidad + disponibilidad de datos + evitar WAF crónico si es posible.

Entregables:
- Layer de `Jurisdiction` funcionando en modelo y UI (Estado/CCAA, y preparado para municipal).
- Conectores reproducibles para boletines oficiales autonómicos (normativa) y, cuando exista, presupuestos/ejecución y contratación/subvenciones autonómicas.
- Action vectors Tier 1 para 3 CCAA, comparables con Estado.

Riesgo y mitigación:
- Heterogeneidad de formatos: preferir discovery por catálogos y adaptadores por CCAA, no scraping ad hoc infinito.

### Fase 3: producto público v1 (trazabilidad total) (`ENG: 13`, `HUM: 5`)

Objetivo: que el output sea utilizable sin "fe" y sin caja negra.

Entregables:
- Dashboard de usuario: preferencias -> resultados por nivel -> explicación con evidencia.
- Escenarios de pesos (sin ranking único por defecto) + sensibilidad básica.
- UX "modo cita": cada métrica enlaza a evidencia primaria.
- UX "modo réplica": export de dataset procesado + script/consulta reproducible (por snapshot).

### Fase 4: impacto (causalidad) en 1-2 dominios (`ENG: 13`, `HUM: 13`)

Objetivo: incorporar evidencia de impacto solo donde la identificación sea defendible.

Estrategia:
- Elegir 1-2 dominios con buena data y tratamientos relativamente fechables (ejemplos típicos: vivienda y energía; o vivienda y sanidad, según datos disponibles).

Entregables:
- Ingesta reproducible de `IndicatorSeries` (outcomes y confusores) con metadatos y cambios metodológicos.
- 4-6 evaluaciones causales con diagnósticos y etiquetas de credibilidad.
- "Impact cards": efecto estimado + incertidumbre + supuestos + enlaces a datos/modelo.

No escalable (manual, explícito):
- Definir intervención y fecha real de tratamiento.
- Justificar la estrategia de identificación (esto no se automatiza sin perder rigor).

### Fase 5: expansión operativa (10-12 CCAA + municipios grandes) (`ENG: 34`, `HUM: 13`)

Objetivo: cubrir la mayor parte del impacto cotidiano con un enfoque escalable.

Entregables:
- Cobertura multinivel robusta en Tier 1.
- Estrategia de agregación para contratación/subvenciones (CPV/programa/órgano + muestreo) evitando "leerlo todo".
- Conectores de alta frecuencia cuando proceda (energía/clima) con almacenamiento eficiente.
- Modo "catálogo": discovery + curación, para municipal (evitar caer en PDFs como default).

## 5.1) Criterio de éxito (cuando Fases 1-4 estén en verde)

Se considera "éxito" si existe:
- Tier 1 de **acción verificable** para Estado y 3 CCAA piloto, con drill-down a evidencia primaria.
- Dashboard con trazabilidad y cobertura visible (qué temas tienen evidencia suficiente y cuáles no).
- 4-6 evaluaciones de impacto sólidas en 1-2 dominios (aunque el resto quede solo en "acción revelada").

## 6) Dónde no escala (y cómo lo tratamos)

Puntos manuales inevitables (o casi):
- Diseño y mantenimiento del **codebook** por dominio (versionado obligatorio).
- Codificación sustantiva de normas y medidas (auditoría humana en casos dudosos).
- Definición de intervenciones para causalidad.
- Entity resolution cuando faltan IDs estables (beneficiarios/proveedores).

Mitigaciones operativas:
- Active learning: la IA solo pide anotación humana donde duda y siempre deja rastro.
- Muestreo inteligente para dinero público.
- Reglas explícitas de "no observable" y "incierto" en lugar de imputación silenciosa.

## 7) Cómo mantener este roadmap vivo (sin duplicar)

Reglas:
- Todo conector nuevo o cambio relevante se refleja en `docs/etl/e2e-scrape-load-tracker.md` con evidencia de verificación.
- Los KPIs publicados por snapshot son la base para decidir si se avanza de fase.
- `docs/roadmap-tecnico.md` se mantiene como plan de ejecución de corto plazo y debe enlazar a esta visión macro.
- Cada snapshot operativo debe publicarse también en Hugging Face (`just etl-publish-hf`) o registrarse explícitamente como bloqueo en tracker.
