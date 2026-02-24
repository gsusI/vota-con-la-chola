# Preguntas metodologicas: preocupaciones, dice-vs-hace y cambios de postura

Estado de este documento:
- Basado en el codigo y esquema actuales del repo.
- Basado en el snapshot ciudadano con `as_of_date=2026-02-23`.
- Conteos contrastados en `etl/data/staging/politicos-es.db` el `2026-02-24`.

## 1) ¿Como definimos lo que constituye una preocupacion?

Hoy, en la superficie `/citizen`, una preocupacion se define como:
- Una etiqueta de navegacion (`concern`) con keywords deterministicas.
- Match lexical sobre el `label` del tema (`topic.label`), no sobre el texto completo de la ley.

Implementacion actual:
- Definiciones: `ui/citizen/concerns_v1.json`.
- Nota explicita del archivo: "Navigation-only concern tags (deterministic keywords). Not a substantive classifier."
- Asignacion: `scripts/export_citizen_snapshot.py` en `compute_topic_concern_ids(label, concerns)`.

Implicacion:
- Hoy "preocupacion" es una capa UX de navegacion y agrupacion.
- No es todavia un clasificador semantico profundo del contenido normativo.

## 2) ¿Como sabemos si partidos contribuyen en una direccion u otra, mas alla del titular y por articulos?

### Lo que si hacemos hoy (direccion por voto/tema)

La direccion se infiere asi:
- Voto nominal (`topic_evidence.evidence_type='revealed:vote'`) en `etl/parlamentario_es/topic_analytics.py`.
- Mapeo directo de voto:
- `SI -> support (+1)`
- `NO -> oppose (-1)`
- `ABSTENCION -> unclear (0)`
- Agregacion persona->topic en `topic_positions` (`computed_method='votes'`).
- Agregacion persona->partido en export citizen con guardrail de cobertura (si cobertura baja, degrada a `unclear`).

### Lo que no hacemos aun (articulado de cada ley en citizen)

No estamos evaluando de forma sistematica el articulado de cada norma para la capa citizen de "dice vs hace":
- El tagging de concern se hace sobre `topic.label`.
- El `topic` parlamentario suele venir de `initiative_id`/titulo o fallback a `vote_event`.

### Capacidad parcial ya existente (pero no integrada al flujo citizen principal)

El esquema ya tiene base para granularidad por articulo/fragmento:
- `legal_norms`
- `legal_norm_fragments`
- `legal_fragment_responsibilities`

En el estado actual del DB consultado:
- `legal_norms=12`
- `legal_norm_fragments=8`
- `legal_fragment_responsibilities=15`

Conclusión operativa:
- Hoy podemos afirmar direccion por voto en tema.
- Aun no podemos afirmar direccion por articulo de ley de forma generalizada en la vista ciudadana.

## 3) ¿Que tipo de evidencias primarias tenemos listadas?

Marco metodologico:
- `docs/fuentes-datos.md` define "accion politica" como evento con actor, instrumento, objeto, fechas, resultado y evidencia primaria trazable.
- Regla de doble entrada: comunicacion se valida contra fuente con efectos (ej.: nota -> BOE/PLACSP/BDNS).

Familias de evidencia primaria contempladas:
- Votaciones e iniciativas parlamentarias.
- Normativa oficial (BOE y equivalentes).
- Contratacion publica.
- Subvenciones.
- Presupuestos/ejecucion y otros registros con efectos.

Evidencia realmente cargada hoy para stance por tema (conteo en DB):
- `revealed:vote`: 431036 filas.
- `declared:intervention`: 635 filas.
- `declared:programa`: 11 filas.

Origen principal actual de esas filas:
- `congreso_votaciones` (revealed).
- `senado_votaciones` (revealed).
- `congreso_intervenciones` (declared).
- `programas_partidos` (declared).

## 4) ¿Que tipo de hipotesis tenemos? ¿Como las ranqueamos?

La pagina `ui/citizen/leaderboards.html` implementa 10 hipotesis (H1-H10):
- H1 brecha declarado vs votado.
- H2 coherencia por partido.
- H3 concentracion de incoherencia por tema.
- H4 alineacion con bloque de gobierno (heuristico).
- H5 regionalistas vs estatales en agenda territorial.
- H6 disciplina interna (proxy).
- H7 incertidumbre en high-stakes.
- H8 evidencia vs confianza.
- H9 robustez con filtro de alta confianza.
- H10 recencia vs no_signal.

Reglas de ranking relevantes:
- H1 usa solo comparables claros (`support/oppose` en ambos metodos).
- H1 aplica shrinkage hacia la tasa global:
- `gap_robusta = (mismatch + prior*gap_global) / (overlap + prior)`.
- Parametros actuales:
- `H1_MIN_COMPARABLES = 5`
- `H1_PRIOR_WEIGHT = 5`
- `H1_WARN_TOTAL_COMPARABLES = 40`
- Si un partido no llega a comparables minimos, no rankea como "elegible".

Diagnostico del estado actual (por eso los rankings se ven flojos):
- Comparables globales H1 hoy: `6`.
- Mismatch globales: `2`.
- Partidos con comparables: `UPN=3`, `BNG=2`, `CCa=1`.
- Ninguno alcanza `n>=5`, por eso el leaderboard queda poco interpretable.

## 5) ¿De donde sacamos lo que dicen los politicos versus lo que hacen?

### "Dicen" (declared)

Fuentes:
- Intervenciones (ej. Diario de Sesiones) y programas.

Extraccion:
- `etl/parlamentario_es/declared_stance.py` (`DECLARED_REGEX_VERSION='declared:regex_v3'`).
- Si no hay señal clara o hay conflicto, entra en cola de revision:
- `topic_evidence_reviews` con razones (`missing_text`, `no_signal`, `low_confidence`, `conflicting_signal`).

Agregacion:
- `etl/parlamentario_es/declared_positions.py` -> `topic_positions` con `computed_method='declared'`.

### "Hacen" (revealed)

Fuentes:
- Voto nominal de Congreso/Senado.

Extraccion y agregacion:
- `etl/parlamentario_es/topic_analytics.py` produce `topic_evidence` de tipo `revealed:vote` y luego `topic_positions` con `computed_method='votes'`.

### Union "combined"

Regla actual (`etl/parlamentario_es/combined_positions.py`):
- Si existe `votes`, usa `votes`.
- Si no, usa `declared`.
- Es selector, no mezcla ponderada.

## 6) ¿De verdad, como lo estamos sabiendo?

Porque el flujo es trazable y reproducible:
- Cada postura exportada en citizen viene de `topic_positions`.
- Cada `topic_position` viene de `topic_evidence` con `source_id`, `source_url`, `source_record_pk`, `raw_payload`.
- Citizen enlaza a drill-down de Explorer (`topic_positions`, `topic_evidence`, `explorer-temas`) para auditoria.
- La incertidumbre no se oculta (`unclear` y `no_signal` se mantienen explicitos).

Conteo actual de posiciones (`as_of_date=2026-02-23`):
- `votes`: 68528
- `declared`: 134
- `combined`: 68535

Interpretacion:
- El metodo combinado hoy esta dominado por votos revelados.
- La capa declarada existe, pero aun con cobertura baja para comparacion robusta.

## 7) ¿Cuando decimos "dice vs hace", por tema/scope, que granularidad tenemos?

Granularidad actual:
- Scope por `topic_set` con anclas: `institution_id`, `admin_level_id`, `territory_id`, `legislature`, ventana temporal.
- Unidad comparada principal: `topic` (normalmente iniciativa/evento), no articulo normativo.
- Resultado final en citizen: posicion agregada por partido y tema.

Granularidad no cubierta aun en citizen principal:
- Articulo/fragmento de norma como unidad sistematica de comparacion "dice vs hace".

## 8) ¿Como detectamos cambios de postura? ¿Basta votar a favor o en contra?

Respuesta corta: no, no basta.

Lo que podemos detectar hoy:
- Choque declarado-votado en el mismo `topic` (mismatch de signo).
- Diferencias entre snapshots (`as_of_date`) para una persona/partido en un topic.

Limitacion clave:
- `support/oppose` siempre es relativo a la proposicion votada.
- Si cambia el contenido (enmienda, texto sustitutivo, paquete mixto), el mismo voto no implica automaticamente el mismo significado politico de fondo.

Por eso, "cambio de postura" robusto requiere:
- Normalizar la direccion sustantiva de la medida (no solo el sentido del voto).
- Descomponer por fragmentos/articulos cuando sea relevante.
- Mantener hipotesis de direccion como hipotesis auditables, no como verdad cerrada (`docs/intervention_template_es.md`: `expected_direction` es hipotesis).

## 9) TODOs urgentes para cerrar huecos metodologicos

- [URGENT] Subir cobertura `declared` para que H1/H2 tengan muestra util (objetivo minimo operativo: comparables globales > 40 y varios partidos con `n>=5`).
- [URGENT] Integrar articulado/fragmentos (`legal_norm_fragments`) al mapping de concerns y al calculo de direccion.
- [URGENT] Introducir "direccion de politica" estable por concern (ontologia de impacto) separada del mero `si/no` de votacion.
- [URGENT] Diferenciar tipos de voto/proposicion (texto final, enmienda, toma en consideracion, convalidacion, etc.) antes de etiquetar "cambio de postura".
- [URGENT] Publicar un panel de trazabilidad de cobertura: por concern, por partido, por metodo (`votes/declared/combined`) y por nivel de evidencia.

## 10) SQL de auditoria recomendada (reproducible)

```sql
-- Evidencia por tipo
SELECT evidence_type, COUNT(*) FROM topic_evidence GROUP BY evidence_type;

-- Posiciones por metodo y fecha
SELECT computed_method, COUNT(*)
FROM topic_positions
WHERE as_of_date = '2026-02-23'
GROUP BY computed_method;

-- Cola de revision declarada
SELECT review_reason, status, COUNT(*)
FROM topic_evidence_reviews
GROUP BY review_reason, status;
```

