# Comparison engine v1

Estado: contrato normativo para `TODO 29`

Fecha: `2026-08-20`

## 1. Objetivo

Comparar una promesa explicita o una posicion declarada con una accion posterior
sin convertir una coincidencia tematica en un veredicto. Cada resultado debe
responder una pregunta acotada:

> Dada esta afirmacion, este actor, esta capacidad, este marco semantico y este
> intervalo, que relacion documentada tiene esta accion posterior con lo dicho?

El motor produce observaciones auditables, no juicios sobre sinceridad, intencion,
culpa, legalidad, merito, causalidad, cumplimiento total ni corrupcion.

El contrato soporta millones de pares mediante candidatos particionados,
evaluacion por lotes y publicacion Parquet. La escala no relaja los gates de
identidad, tiempo, mapping o evidencia.

## 2. Estado actual y limite de autoridad

El proyecto ya tiene tres piezas utiles, pero ninguna basta por si sola para una
comparacion fuerte:

- `claims` y `promises` conservan el texto oficial, actor, pagina, hash, review y
  criterios observables;
- `topic_evidence` y `topic_positions` separan `declared`, `votes` y `combined`;
- el actor graph conserva identidades source-scoped, capacidades y relaciones
  temporales sin fusion por nombre.

La coherencia actual de `topic_positions` es una lectura exploratoria. Empareja
posturas agregadas por topic, persona y fecha. No demuestra que una accion
implemente, contradiga o cumpla una proposicion concreta. En particular:

- compartir topic no significa compartir medida, instrumento ni direccion;
- `SÍ` no significa apoyo a una promesa hasta interpretar el texto exacto
  sometido a votacion;
- `NO` no significa oposicion hasta saber si se votaba aprobar, derogar,
  sustituir, enmendar o tramitar;
- `combined` selecciona `votes` y, si faltan, `declared`; no mezcla ambos y no
  puede usarse como lado de accion en este motor;
- una posicion agregada no sustituye el ballot, acto, norma, contrato, gasto o
  acuerdo atomico que aporta evidencia.

Por ello, este contrato no reetiqueta la metrica historica de coherencia. Define
una capa nueva, versionada y fail-closed.

## 3. Principios no negociables

1. Solo se procesan afirmaciones, actores, acciones y evidencias de fuentes
   publicas reales. No hay datos synthetic, mock, placeholder ni filas generadas
   para completar cobertura o probar escala.
2. La afirmacion y la accion permanecen inmutables. La comparacion es una
   assertion derivada y corregible.
3. La unidad autoritativa es el par afirmacion-accion cuando existe una accion
   concreta. Una busqueda acotada que no encuentra accion puede producir una
   assessment de cobertura assertion-scope con
   `action_kind='bounded_action_search'`,
   `action_search_state='no_reviewed_action_found'` y `action_id=NULL`; no
   inventa una accion. Varias acciones sobre una promesa
   siguen siendo varios resultados y no se esconden en un score unico.
4. Un topic compartido genera como maximo un candidato de mapping.
5. Un nombre compartido nunca resuelve un actor.
6. La accion debe ser posterior a la afirmacion y atribuible a la capacidad
   valida del actor en la fecha de la accion.
7. Una accion procedimental no produce `aligned` o `conflicted` salvo que el
   propio objeto de la afirmacion sea exactamente ese procedimiento y exista
   mapping confirmado.
8. Ausencia de accion observada no significa incumplimiento. Produce
   `insufficient_evidence` con cobertura y blockers visibles.
9. Confianza alta no compensa mapping no revisado, identidad ambigua, evidencia
   incompleta o cobertura desconocida.
10. Cada resultado llega a evidencia exacta de ambos lados, al mapping, a la
    identidad/capacidad y a las posibles contraevidencias.
11. Toda identidad personal u organizativa publicada oficialmente se conserva
    completa y exacta. Solo se excluyen secretos, sesiones privadas, rutas de
    workstation y material no publico.
12. Ningun resultado autoriza afirmar intencion, engaño, hipocresia, delito,
    corrupcion, influencia, responsabilidad causal, exito o fracaso social.

## 4. Unidad de comparacion

### 4.1 Lado declarado

Una **assertion source** es una version exacta de:

- `promise`: una claim `explicit_promise` o `coalition_commitment`;
- `declared_claim`: una `issue_position`, `soft_commitment` o `preference`;
- `declared_position`: una postura clara derivada de evidencia textual, con
  metodo y evidencia atomica visibles.

La comparacion conserva `claim_id`, `promise_id` cuando exista, version
documental, texto exacto, actor atribuido, capacidad, fechas, condiciones,
territorio, deadline, topics y evidencia primaria.

### 4.2 Lado de accion

Una **action source** es un hecho oficial atomico y versionado:

- ballot nominal o agregado explicitamente como tal;
- iniciativa, enmienda, etapa legislativa, norma o acto administrativo;
- contrato, adjudicacion, obligacion, pago, subvencion o entrega, sin mezclar su
  semantica monetaria;
- acuerdo formal y sus cambios de estado;
- accion geopolitica o institucional;
- otro evento oficial cuyo efecto pueda describirse sin inferir causalidad.

Una nota de prensa, discurso o nueva promesa es otra assertion, no una accion.
Asistir a una reunion no prueba apoyo, influencia, acuerdo ni implementacion. Una
adjudicacion no prueba pago o entrega. Firmar un acuerdo no prueba ejecucion.

Indicators y outcomes quedan fuera de este contrato. Su enlace descriptivo
pertenece a `TODO 30`.

### 4.3 Comparacion autoritativa

Un `promise_action_comparison` contiene siempre una version declarada. Despues
adopta una de dos formas:

- **par**: une una accion versionada real; o
- **assessment de cobertura**: usa `action_kind='bounded_action_search'`,
  `action_search_state='no_reviewed_action_found'`, `action_id=NULL` y documenta
  en `action_search_scope_json` el universo oficial, fuentes, filtros, ventana,
  corte y blockers que se buscaron sin localizar una accion revisada elegible.

En ambos casos conserva:

- un actor o relacion de responsabilidad temporal;
- un marco semantico versionado;
- una decision de mapping;
- una fecha de corte;
- evidencia y contraevidencia.

Un par no es una evaluacion completa de toda la promesa. Una assessment
`bounded_action_search` tampoco prueba inaccion: solo describe el resultado de
una busqueda acotada y produce `insufficient_evidence`.

## 5. Elegibilidad de la assertion

### 5.1 Elegible para mapping

Una assertion entra en candidate generation solo si:

- tiene identificador estable y version de contenido;
- tiene actor directo o firmantes explicitos;
- conserva evidencia primaria, URL, localizador y SHA-256;
- no esta `rejected` ni `needs_context`;
- su texto no esta truncado;
- tiene fecha de publicacion o un intervalo temporal explicitamente desconocido;
- el metodo de extraccion y su version estan registrados.

`rule_confirmed` permite generar candidatos. No convierte un mapping posterior en
confirmado.

### 5.2 Elegible para comparacion fuerte

Ademas de lo anterior:

- `claim_kind` debe ser `explicit_promise`, `coalition_commitment` o una posicion
  declarada clara con direccion `support`/`oppose`;
- la proposicion debe delimitar al menos objeto y direccion;
- las condiciones y el territorio expresos deben conservarse;
- `claim_status` debe ser `active`, o la accion debe caer dentro del intervalo
  historico anterior a una correccion/supersession;
- una promesa condicional solo se compara como fuerte cuando el estado de la
  condicion es conocido y evidenciado;
- `mixed`, `unclear`, `no_signal`, slogan, contexto y preferencia sin direccion
  operativa no producen `aligned` o `conflicted`.

Una assertion inelegible se conserva con `not_comparable`; no se elimina para
mejorar artificialmente la tasa de comparables.

## 6. Elegibilidad de la accion

Una accion entra en candidate generation si tiene:

- identificador y version estables;
- fecha del hecho con precision explicita;
- actor directo o participacion/capacidad enlazada al actor graph;
- tipo de accion y objeto exactos;
- fuente oficial, source record, URL y evidencia;
- estado de revision de su efecto semantico.

Para producir un estado fuerte necesita ademas:

- evidencia primaria exacta y, cuando aplique, la version de texto vigente;
- efecto material sobre el frame comparado;
- direccion confirmada respecto al frame;
- capacidad valida del actor en `occurred_at`;
- mapping confirmado;
- accion posterior a la assertion.

### 6.1 Votos

Un ballot solo adquiere direccion sustantiva mediante esta cadena:

`ballot -> vote event -> objeto/texto exacto votado -> efecto de SÍ/NO -> frame`

Reglas:

- el ballot conserva `yes`, `no`, `abstain`, `absent`, `not_voting`, `paired` o
  `unknown` sin colapsarlos;
- `abstain`, `absent`, `not_voting`, `paired` y `unknown` nunca generan por si
  solos un estado fuerte;
- una mocion procedimental, toma en consideracion, enmienda, veto o votacion
  parcial conserva su clase; no se presenta como aprobacion/rechazo de toda la
  politica;
- si no esta disponible el texto/version exacto o el efecto de la opcion de voto,
  el resultado es `insufficient_evidence`;
- una regla por palabras del titulo o topic produce solo `rule_candidate`.

### 6.2 Dinero, acuerdos y ejecucion

- presupuesto, licitacion, adjudicacion, obligacion, pago y entrega son acciones
  distintas;
- anuncio, firma, entrada en vigor e implementacion de un acuerdo son estados
  distintos;
- una accion parcial puede ser evidencia `aligned` con un criterio concreto, pero
  nunca se etiqueta automaticamente como promesa `fulfilled`;
- una retirada, anulacion o correccion posterior se conserva como nueva accion y
  contraevidencia, no borra el resultado anterior.

## 7. Marco semantico

El **comparison frame** define la proposicion que ambos lados deben poder
contestar. Topic es solo una dimension de discovery.

Campos logicos minimos:

| Dimension | Contenido |
| --- | --- |
| `policy_object` | objeto concreto de la medida |
| `desired_direction` | crear, ampliar, reducir, mantener, impedir, derogar, financiar, regular, implementar u otra direccion controlada |
| `instrument_kind` | ley, presupuesto, contrato, programa, acuerdo, acto administrativo, ballot u otro instrumento |
| `target_population` | poblacion o contraparte nombrada, si existe |
| `territory_id` | jurisdiccion/territorio aplicable |
| `responsible_capacity` | partido, grupo, cargo, gobierno, firmante, miembro u otra capacidad |
| `conditions` | condiciones literales relevantes |
| `deadline` | fecha o intervalo expresado, no inferido |
| `quantity_or_threshold` | cifra, unidad y comparador cuando se expresan |
| `topic_ids` | topics versionados usados para discovery, nunca como prueba suficiente |

Un cambio material en objeto, direccion, instrumento, territorio, poblacion,
condicion o umbral impide un match binario. `changed_framing` exige una nueva
assertion o accion comparable atribuible al mismo actor/capacidad que haga
explicito ese cambio. Apoyar una iniciativa de un tercero con alcance adyacente no
prueba que el actor haya reformulado su posicion: queda `ambiguous_mapping` o
`not_comparable`. Si dos objetos solo comparten familia politica pero contestan
preguntas diferentes, son `not_comparable`.

## 8. Identidad, atribucion y capacidad

El actor graph manda sobre la etiqueta textual.

Gates:

1. Resolver la occurrence de la assertion y de la accion dentro de su fuente.
2. Exigir el mismo `actor_id` resuelto o una decision de relacion revisada.
3. Comprobar la capacidad valida en la fecha de la accion.
4. Conservar la label oficial exacta de cada fuente aunque difieran.
5. Si hay dos identidades plausibles, devolver `ambiguous_mapping`.

Reglas de atribucion:

- una promesa de partido no se atribuye automaticamente a cada afiliado;
- un voto individual no se convierte silenciosamente en accion del partido;
- un rollup de delegacion se etiqueta como agregado, publica numerador,
  denominador, ausencias, disidencia y fecha de afiliacion;
- partido, grupo parlamentario, coalicion, institucion y gobierno siguen siendo
  actores distintos;
- una promesa de coalicion solo se atribuye a firmantes explicitos;
- una accion gubernamental solo se relaciona con una promesa partidaria mediante
  una regla de responsabilidad/capacidad revisada y temporal;
- proveedor, beneficiario, autoridad de contratacion y firmante son roles
  contextuales, no identidades intercambiables.

El primer actor graph es source-scoped. Ningun cruce de fuentes por nombre puede
producir un estado fuerte antes de una decision de identidad admitida por su
contrato.

## 9. Tiempo y ventanas

Se mantienen separados:

- `asserted_at`: cuando se hizo/publico la assertion;
- `action_occurred_at`: cuando ocurrio la accion;
- `source_published_at`: cuando la publico el origen;
- `observed_at`: cuando se capturo;
- `as_of_date`: corte del resultado;
- `valid_from/to`: vigencia de actor, capacidad, frame o relacion;
- `system_created_at`: materializacion local.

Reglas:

1. `action_occurred_at <= asserted_at` produce `not_comparable`; una accion
   admisible como posterior exige estrictamente `action_occurred_at > asserted_at`.
2. Una accion posterior a `as_of_date` no entra en esa version.
3. Falta de fecha del hecho produce `insufficient_evidence`; nunca se usa
   `fetched_at` como sustituto silencioso.
4. Si existe deadline, el resultado declara si la accion cae antes, durante o
   despues; no aplica un grace period no expresado sin versionarlo en config.
5. Sin deadline, el motor describe acciones observadas hasta el corte. No declara
   incumplimiento por inaccion.
6. Condiciones, competencias, mayoria, mandato y participacion de coalicion se
   evaluan en la fecha relevante, no en el snapshot actual.
7. Una correccion o cambio de posicion crea otro intervalo; no reescribe el
   anterior.

## 10. Mapping: candidatos frente a decisiones confirmadas

### 10.1 Estados de mapping

| Estado | Significado | Puede producir estado fuerte |
| --- | --- | --- |
| `rule_candidate` | heuristica determinista, keyword, topic, expediente aproximado o regla no promovida | no |
| `model_candidate` | similitud/clasificador sobre texto real | no |
| `confirmed_structural` | enlace estructural exacto generado por una regla promovida y versionada | si |
| `human_confirmed` | reviewer confirma mismo frame, direccion y capacidad con evidencia | si |
| `human_rejected` | reviewer confirma que no corresponde | no |
| `ambiguous` | dos o mas interpretaciones siguen siendo plausibles | no |
| `needs_context` | falta texto, version, identidad, tiempo o efecto | no |
| `superseded` | existe decision posterior | no para nuevas releases |

`rule_confirmed` en una claim y `confirmed_structural` en un mapping son cosas
distintas. La primera valida la clasificacion de la frase; la segunda valida el
enlace entre esa frase y una accion concreta.

### 10.2 Candidate generation

El pipeline puede proponer pares por:

- referencia oficial exacta a iniciativa, norma, expediente o acuerdo;
- actor/capacidad temporal compatible;
- frame versionado y campos estructurados compatibles;
- topic, keyword o similitud como recall aid;
- ventana temporal y jurisdiccion.

La busqueda aplica primero actor, tiempo, jurisdiccion y frame bucket. Queda
prohibido el producto cartesiano global entre claims y acciones.

Cada candidato registra metodo, version, config hash, features observables,
candidate rank y razones. Un score de similitud no es evidencia de comparabilidad.

### 10.3 Review

Cada worker card de review contiene:

- texto y evidencia exacta de assertion y accion;
- labels e IDs publicos de actores;
- capacidad y fechas;
- frame dimension por dimension;
- efecto propuesto de la accion;
- evidencia favorable, contraria y contexto;
- source blockers y cobertura;
- decision anterior, si la hay.

Decisiones admitidas:

- confirmar mismo frame y direccion;
- confirmar mismo frame y direccion opuesta;
- marcar cambio material de framing;
- rechazar como no comparable;
- marcar ambiguedad;
- pedir contexto.

No se rellenan decisiones vacias. Dos reviewers no pueden compartir ciegamente la
respuesta inicial. Toda discrepancia se arbitra y conserva.

### 10.4 Promocion de reglas

Una regla deja de ser candidata solo cuando:

- se evalua sobre gold set estratificado de pares oficiales reales;
- existe dual review y adjudicacion;
- publica matriz de confusion por fuente, action kind y patron de mapping;
- alcanza precision `>= 0.98` y limite inferior Wilson 95% `>= 0.95` en el
  estrato promovido;
- no tiene errores criticos conocidos de actor, direccion o texto/version;
- su recall, unresolved rate y coverage se publican aunque sean bajos;
- un cambio de codigo, parametros, taxonomia o fuente crea nueva version y exige
  revalidacion.

La promocion es por estrato. Nunca se generaliza de votos legislativos a gasto,
acuerdos o geopolitica.

## 11. Estados de resultado

Solo existen estos seis estados publicos:

| Estado | Regla normativa | Lo que no significa |
| --- | --- | --- |
| `aligned` | mapping confirmado, actor/capacidad/tiempo compatibles y la accion material posterior avanza la misma proposicion | promesa cumplida, eficacia, merito o causalidad |
| `conflicted` | mapping confirmado y la accion material posterior se opone o dificulta la misma proposicion; tambien puede coexistir con acciones alineadas que deben mostrarse | mentira, hipocresia, incumplimiento total, ilegalidad o corrupcion |
| `insufficient_evidence` | la pregunta es plausible, pero falta texto, efecto, fecha, cobertura, fuente o evidencia suficiente | que no hubo accion o que la promesa se incumplio |
| `ambiguous_mapping` | identidad, capacidad, frame, referencia o direccion tiene mas de una lectura plausible no resuelta | conflicto sustantivo |
| `changed_framing` | una assertion/accion posterior comparable y atribuible al mismo actor/capacidad explicita un cambio material de objeto, instrumento, alcance, territorio, poblacion, condicion o umbral | alineacion parcial, apoyo a iniciativa ajena o cambio inferido por similitud |
| `not_comparable` | hay evidencia suficiente para concluir que los objetos contestan preguntas incompatibles o pertenecen a capacidades/tiempos no comparables | falta de datos; el motivo exacto debe publicarse |

`aligned` y `conflicted` son **estados fuertes**. Los otros cuatro son estados de
incertidumbre o incompatibilidad y cuentan como no comparables en rankings.

En la implementacion fisica C1/v1, `changed_framing` esta deshabilitado: productor
y validator DEBEN rechazar cualquier fila con ese estado hasta que el review input
y el schema conserven evidencia explicita de una nueva assertion/accion posterior
cuya autoria corresponda al actor en la misma capacidad, y el validator compruebe
ese gate. La
presencia del valor en el enum no autoriza una fila publicada.

### 11.1 Orden fail-closed de decision

El evaluador aplica los gates en este orden:

1. Assertion rechazada, no accionable o fuera de vigencia -> `not_comparable`.
2. Actor/capacidad con multiples mappings -> `ambiguous_mapping`.
3. Accion anterior o capacidad temporal incompatible conocida ->
   `not_comparable`.
4. Candidate mapping sin confirmacion -> `ambiguous_mapping`.
5. Falta de texto/version/fecha/efecto/coverage requerido ->
   `insufficient_evidence`.
6. Accion puramente procedimental -> `not_comparable`; si ni siquiera puede
   establecerse su efecto procedimental -> `insufficient_evidence`.
7. Nueva assertion/accion del mismo actor/capacidad confirma cambio material ->
   `changed_framing`; alcance adyacente de un tercero permanece ambiguo/no
   comparable.
8. Mapping confirmado y efecto material en la misma direccion -> `aligned`.
9. Mapping confirmado y efecto material en direccion opuesta -> `conflicted`.

Si dos gates no fuertes aplican, se conserva el detalle de todos en
`reason_codes`; el estado principal usa el primero de este orden. Ningun fallback
convierte un fallo en `aligned` o `conflicted`.

### 11.2 Casos frontera

- Mismo topic, medidas distintas -> `ambiguous_mapping` como candidato; tras
  review, normalmente `not_comparable`.
- Voto `SÍ` sin texto exacto -> `insufficient_evidence`.
- Voto sobre tramite, no fondo -> `not_comparable`.
- Promesa condicional con condicion desconocida -> `insufficient_evidence`.
- Actor homonimo -> `ambiguous_mapping`.
- Accion antes del programa -> `not_comparable`.
- Medida propia posterior con menor presupuesto, distinto territorio o distinta
  poblacion expresos -> `changed_framing`; una medida adyacente de tercero no.
- Ninguna accion localizada en una fuente incompleta ->
  `insufficient_evidence`, nunca `conflicted`.
- Acciones posteriores en ambas direcciones -> se publican pares `aligned` y
  `conflicted` separados, con timeline y contraevidencia; no se promedian.

## 12. Agregacion, cobertura y rankings

Los agregados publican conteos, no un veredicto unico:

- `comparisons_total`;
- `action_pairs_total`;
- `bounded_action_search_assessments_total`;
- conteo por los seis estados;
- `strong_pairs_total = aligned + conflicted`;
- `comparable_ratio = strong_pairs_total / comparisons_total`;
- assertions con/sin candidato;
- acciones descubiertas/evaluadas/rechazadas;
- coverage por source, actor, periodo, action kind y frame;
- blockers, unknowns y freshness;
- denominadores y version de metodo.

No se calcula un porcentaje de “promesas cumplidas” desde estos estados.
`aligned / strong_pairs_total` solo describe los pares comparables observados y
debe etiquetarse asi.

`bounded_action_search_assessments_total` siempre permanece en el denominador de
cobertura y fuera de `strong_pairs_total`. Debe acompañarse del universo buscado;
sin ese scope, la assessment falla validacion.

Se heredan los gates de `docs/method/truth-contract.md`:

- ranking oculto si `strong_pairs_total < 5`;
- lectura exploratoria/grisada si `5 <= strong_pairs_total < 40`;
- ranking normal solo desde `40`, sin ocultar unknowns;
- freshness `future` o `unknown` bloquea ranking;
- los cuatro estados no fuertes nunca entran en numerador aligned/conflicted.

Comparar actores exige ademas el mismo metodo, frame family, ventana, action-kind
coverage y unidad de atribucion. Si estas distribuciones difieren, el ranking es
`not_comparable` aunque cada actor tenga resultados individuales validos.

## 13. Confianza

`confidence` mide calidad de la lectura, no probabilidad de verdad.

Componentes obligatorios:

- `assertion_quality`;
- `identity_quality`;
- `mapping_quality`;
- `action_effect_quality`;
- `evidence_quality`;
- `coverage_quality`;
- `temporal_quality`.

Cada componente usa `[0,1]`, metodo y version. Si se publica un valor agregado,
v1 usa el minimo de los componentes requeridos. Un promedio no puede esconder un
eslabon debil.

Etiquetas publicas:

- alta: `>= 0.66`;
- media: `>= 0.33` y `< 0.66`;
- baja: `> 0` y `< 0.33`;
- sin confianza util: `0`.

Reglas:

- mapping candidato fuerza `mapping_quality = 0` para estados fuertes;
- evidencia o coverage desconocidos impiden confianza alta;
- `aligned`/`conflicted` requieren todos los gates categoricos, aunque el valor
  numerico sea alto;
- `insufficient_evidence` puede explicar que componente falta, pero no recibe una
  apariencia visual de veredicto;
- los valores y thresholds se versionan en cada release.

## 14. Procedencia

Cada par resuelve estas cadenas independientes:

`assertion source -> document version -> exact quote -> claim/promise`

`action source -> source record/document version -> exact locator -> action`

`actor occurrence -> resolution/capacity evidence -> actor used in comparison`

`mapping candidate -> review decision -> result version -> release`

Roles de evidencia:

- `assertion_primary`;
- `assertion_context`;
- `action_primary`;
- `action_text_version`;
- `mapping_support`;
- `mapping_counterevidence`;
- `actor_identity`;
- `actor_capacity`;
- `temporal_context`;
- `correction`;
- `superseding`;
- `source_blocker`.

Cada enlace incluye `source_id`, source record, URL publica, document/content
SHA-256, localizador, quote exacta cuando exista, observed/fetched time, evidence
tier y quality flags. `source_default` sigue visible como evidencia mas debil.

La busqueda de contraevidencia tiene estado propio:

- `searched_complete_scope`;
- `searched_bounded_scope`;
- `not_searched`;
- `blocked`;
- `unknown`.

`not_searched`, `blocked` o `unknown` impiden presentar el resultado como una
evaluacion exhaustiva.

## 15. Esquema fisico v1

La primera implementacion usa cuatro tablas aditivas. Las tablas fuente siguen
siendo autoridad; estas filas son assertions derivadas.

### 15.1 `comparison_releases`

Una release inmutable por conjunto de inputs y review. Campos fisicos v1:

- identidad/metodo: `comparison_release_id`, `schema_version`, `method_version`,
  `mapping_review_version`;
- tiempo: `snapshot_date`, `generated_at`, `created_at`;
- inputs: `promises_source_scope_sha256`, `actions_source_scope_sha256`,
  `actor_source_scope_sha256`, `actor_graph_release_id`,
  `reviewed_mappings_sha256`;
- output: `semantic_sha256`, `comparison_count`, `evidence_count`,
  `status_counts_json`;
- lineage: `source_manifest_json`.

`source_manifest_json` conserva solo lineage semantico canonico: IDs seleccionados,
hashes SHA-256 del scope seleccionado, release del actor graph, hash canonico de
reviews, corte temporal de acciones, alcance de busqueda y politica real-only.
Rutas, bytes y SHA-256 del fichero completo son hechos fisicos de ejecucion: viven
solo en los reports del productor/validator y no participan en la DB derivada, la
release ni el JSON publico. El artefacto publico declara ademas
`real_data_only=true`, `synthetic_or_mock=false` y
`public_domain_information_policy` con valor
`retain_official_public_identity_exclude_only_secrets_private_session_state_and_workstation_traces`;
no se finge que son columnas del schema. Ese valor exige conservar identidad
oficial publica y solo excluye secretos, estado de sesion privado y trazas de
workstation.

`source_manifest_json.input_releases` y el `input_releases` publico son el mismo
objeto exacto:

```json
{
  "promises": {"selected_scope_sha256": "<sha256>"},
  "actions": {
    "selected_scope_sha256": "<sha256>",
    "coverage_cutoff": "2026-02-12"
  },
  "actor_graph": {
    "release_id": "<release-id>",
    "selected_scope_sha256": "<sha256>"
  },
  "reviewed_mappings": {"canonical_sha256": "<sha256>"}
}
```

El validator rechaza keys extra o lineage fisico en ambos objetos.

El `selected_scope_sha256` de `actions` es el SHA-256 del JSON canonico exacto:

```json
{
  "action_pairs": ["<filas oficiales seleccionadas, ordenadas por clave>"],
  "bounded_action_searches": ["<scopes reales reconstruidos, ordenados por clave>"]
}
```

Cada scope de busqueda incluye configuracion y resultado observado: miembros,
intervalo, terminos, politica, tablas fuente, filas/eventos escaneados,
`candidate_rows_sha256`, `matching_event_ids` y `result_state`.
`candidate_rows_sha256` cubre el array ordenado por `(vote_event_id, member_name)`
con esta proyeccion exacta por fila: `vote_event_id`, `vote_date`, `title`,
`expediente_text`, `source_id`, `source_url`, `member_name`, `vote_choice`. No es
necesario publicar las filas completas. Asi, un cambio real en titulo, texto,
voto, fecha o fuente dentro del universo buscado cambia el action scope hash y la
release aunque counts, matches y action pairs seleccionados sigan iguales.

### 15.2 `comparison_mapping_reviews`

Decision explicita sobre un candidato assertion-accion o sobre una busqueda
acotada sin accion. Campos fisicos v1:

- identidad: `mapping_review_id`, `comparison_release_id`, `claim_id`,
  `promise_id`;
- accion/busqueda: `action_kind`, `action_id`, `action_search_state`,
  `action_search_scope_json`;
- actor/capacidad: `claim_actor_id`, `action_actor_id`,
  `action_registry_actor_id`, `action_party_actor_id`,
  `affiliation_relationship_id`, `actor_link_state`;
- decision: `review_outcome`, `claim_direction`, `action_direction`,
  `action_substance_state`, `mapping_basis`, `directional_countable`;
- auditoria: `review_method`, `review_version`, `review_rationale`,
  `reviewed_at`, `created_at`.

Vocabulario fisico v1:

- `action_kind`: `roll_call_vote`, `bounded_action_search`;
- `action_search_state`: `not_applicable`, `no_reviewed_action_found`;
- `actor_link_state`: `reviewed_official_identity_and_affiliation`,
  `claim_actor_only_no_action`;
- `action_substance_state`: `substantive`, `procedural`, `unknown`,
  `not_applicable`;
- `mapping_basis`: `exact_measure`, `reviewed_related_measure`,
  `broad_topic_only`, `procedural_near_match`,
  `bounded_search_no_reviewed_action`;
- `review_method`: exactamente `explicit_evidence_review`;
- `review_outcome`: los seis estados de la seccion 11.

Esta tabla contiene **reviews**, no candidates. `rule_candidate` y
`model_candidate` se quedan en el run manifest/queue y no entran aqui hasta una
review explicita. Una futura tabla de candidatos sera aditiva.

Constraints semanticos adicionales del validator:

- `bounded_action_search` exige `action_id=NULL`, action
  actors/affiliation nulos,
  `actor_link_state='claim_actor_only_no_action'`,
  `action_search_state='no_reviewed_action_found'`, scope JSON no vacio,
  `action_direction='not_applicable'`,
  `action_substance_state='not_applicable'`,
  `mapping_basis='bounded_search_no_reviewed_action'`,
  `review_outcome='insufficient_evidence'` y `directional_countable=0`;
- `roll_call_vote` exige `action_search_state='not_applicable'` y scope JSON
  vacio;
- `broad_topic_only`, `procedural_near_match`,
  `bounded_search_no_reviewed_action`, accion
  `procedural/unknown/not_applicable` o direccion `unclear/not_applicable` fuerzan
  `directional_countable=0`;
- v1 solo permite `directional_countable=1` para `aligned/conflicted`, accion
  `roll_call_vote` sustantiva, actor link revisado, `mapping_basis='exact_measure'`
  y direcciones claras;
- `reviewed_related_measure` puede justificar ambiguity, cambio de framing o no
  comparabilidad, pero no un estado fuerte v1.

### 15.3 `promise_action_comparisons`

Resultado publico de un par o assessment `bounded_action_search`. Campos fisicos
v1:

- identidad/lineage: `comparison_id`, `comparison_release_id`,
  `mapping_review_id`;
- assertion: `claim_id`, `promise_id`, `claim_kind`, `claim_actor_label`,
  `claim_actor_id`, `claim_text`, `claim_page_start`, `claim_page_end`,
  `claim_published_date`, `claim_review_status`;
- accion: `action_kind`, `action_id`, `action_search_state`,
  `action_search_scope_json`, `action_date`, `action_title`,
  `action_member_name`, `action_vote_choice`, `action_actor_id`,
  `action_party_actor_id`, `action_source_id`, `action_source_url`;
- salida: `comparison_status`, `directional_countable`, `public_summary`,
  `caveat`, `decided_at`, `created_at`.

`mapping_review_id` es uno-a-uno. La natural key v1 es
`(comparison_release_id, claim_id, action_kind, action_id)`. Como SQLite trata
NULLs como distintos en `UNIQUE`, el validator exige adicionalmente como maximo
un `bounded_action_search` por claim/release en v1.

Para `action_kind='bounded_action_search'`, los campos que describirian una accion
concreta son NULL. `action_search_state` y `action_search_scope_json` si son
obligatorios. Es una assessment de coverage, no un action record fabricado. El
scope incluye como minimo actores/miembros buscados, source tables/contracts,
intervalo, search terms, matching policy, expected/reviewed matching-event count
y blockers si existen; evidence metadata conserva la procedencia row-level,
`source_manifest_json` conserva lineage semantico y el report conserva los hechos
fisicos de cada fichero ejecutado.

Los componentes de frame, confidence, coverage, freshness, reason codes y
counterevidence son requisitos del artefacto/API; el schema piloto los deriva de
la review, evidencia, manifest y release. Si pasan a columnas, la migracion es
aditiva.

### 15.4 `comparison_evidence`

Relacion N:M entre resultado y evidencia. Campos fisicos v1:

- `comparison_evidence_id`, `comparison_id`;
- `evidence_side`: `claim`, `action`, `actor_link`, `mapping_review`;
- `evidence_role`: `primary`, `context`, `identity`, `review`;
- `source_id`, `source_record_id`, `source_url`, `content_sha256`,
  `exact_quote`, `observed_at`, `metadata_json`, `created_at`.

Mapeo desde los roles logicos de la seccion 14:

- `assertion_primary` -> `claim/primary`;
- `assertion_context` -> `claim/context`;
- `action_primary` y text version -> `action/primary|context`;
- identidad/capacidad -> `actor_link/identity|context`;
- mapping/review/counterevidence/correccion ->
  `mapping_review/review|context`, con tipo detallado en `metadata_json`.

La publicacion falla si un estado fuerte no tiene como minimo `claim/primary`,
`action/primary`, `actor_link/identity` y `mapping_review/review`. La metadata debe
conservar localizador, evidence tier, supports/contradicts/context/corrects,
quality flags y estado de busqueda de contraevidencia cuando no existen columnas
dedicadas.

### 15.5 Extensiones aditivas

A escala pueden separarse `comparison_frames`, candidate features, queues y
componentes de coverage en tablas propias. Esta normalizacion no cambia los IDs,
estados ni semantica de las cuatro tablas v1.

## 16. IDs, idempotencia y versionado

V1 calcula IDs como:

```text
vclc:<kind>:<first-32-hex(sha256(NUL-joined UTF-8 parts))>
```

`NULL` se serializa como cadena vacia dentro del tuple; `kind` y `action_kind`
evitan colisiones semanticas. Todos los valores fuente y hashes completos se
conservan fuera del ID.

Tuples exactos v1:

- release: `comparison-release`, schema version, method version, review version,
  snapshot date, promises scope SHA-256, actions scope SHA-256, action coverage
  cutoff, actors scope SHA-256, actor graph release ID, reviewed mappings SHA-256;
- mapping review: `comparison-mapping-review`, review version, claim ID, action
  kind, action ID nullable, SHA-256 completo del review JSON canonico;
- comparison: `promise-action-comparison`, claim ID, promise ID, action kind,
  action ID nullable, claim actor ID, action actor ID, action party actor ID y
  search-scope SHA-256 para `bounded_action_search` (cadena vacia para un action
  pair). Es la identidad logica del par/assessment y no incluye review version ni
  resultado;
- claim evidence: `comparison-evidence`, comparison ID, `claim`, claim evidence
  ID;
- action evidence: `comparison-evidence`, comparison ID, `action`, vote event ID,
  member-vote ID;
- actor link evidence: `comparison-evidence`, comparison ID, `actor-link`, actor
  relationship ID;
- review evidence: `comparison-evidence`, comparison ID, `mapping-review`, hash
  SHA-256 completo del review JSON canonico.

El `semantic_sha256` de la release se calcula aparte sobre reviews, comparisons y
evidence ordenados y serializados como JSON canonico. No se trunca.

Reprocesar los mismos inputs/config produce los mismos IDs, status counts y hash
logico. Timestamps de ejecucion no participan en identidad semantica.

Un cambio de source scope seleccionado, corte de coverage, actor graph release,
actor resolution, mapping canonico o metodo crea otra release. Un cambio solo en
ruta, bytes fisicos no seleccionados, layout SQLite o SHA-256 del fichero completo
no crea otra release. `comparison_id` permanece estable mientras assertion, action,
actores/capacidad y, para una busqueda, scope no cambien. Una decision corregida
cambia el review digest y `mapping_review_id`, incluso si `review_version` se
mantiene por error; el validator debe exigir ademas version bump para una
correccion intencional. Ampliar un bounded search cambia el scope digest y crea
otro comparison ID, preservando la assessment anterior. V1 materializa una DB
por release. Enlaces de supersession pueden añadirse despues sin cambiar IDs
publicados.

## 17. Correcciones y supersession

1. Raw bytes y evidencias son inmutables.
2. Una correccion oficial crea nueva version fuente y enlace `corrects` o
   `supersedes`.
3. V1 no tiene FK row-level de supersession. Una review corregida crea nuevo
   review input version y release; `source_manifest_json` enlaza la anterior.
4. Una release inmutable nunca cambia en sitio.
5. `latest` solo avanza tras validacion completa y compare-and-swap.
6. Rollback cambia el pointer, no borra releases.
7. La URL publica de una observacion usa `comparison_id` y release. Un futuro
   shell logico puede agrupar versiones sin reescribir URLs anteriores.
8. Un takedown del origen queda como tombstone observado; no elimina evidencia
   historica ya publica y licitamente capturada.

Toda correccion publica muestra antes/despues, motivo, fuente, fecha y efecto sobre
el status. No se reescribe una serie historica para hacer desaparecer un error.

## 18. Arquitectura para millones

### 18.1 Control plane y data plane

- SQLite: releases, IDs, reviews, queues, estados, indices y sample navegable;
- CAS/object storage: documentos, payloads y texto completo por SHA-256;
- Parquet Zstandard: candidatos, comparaciones y evidence edges completos;
- JSON bounded: manifests, conteos, filtros y samples publicos;
- Evidence API: keyset/cursor pagination y drill-down.

### 18.2 Particiones

No se particiona por nombre ni texto libre. Layout recomendado:

- candidatos: `assertion_source / action_kind / action_year / frame_bucket`;
- reviews: `mapping_state / source_pair_bucket / task_id_prefix`;
- resultados: `release / status / action_kind / action_year / comparison_id_prefix`;
- evidence: `release / evidence_role / source_id_bucket / comparison_id_prefix`.

Objetivo: row groups cercanos a `25k` y ficheros de hasta `100k` filas, medidos con
corpus reales. Un manifest publica filas, bytes, min/max keys y SHA-256 por fichero.

### 18.3 Ejecucion

- adapters producen referencias tipadas; no copian blobs;
- indices invertidos por actor/frame/tiempo evitan joins cartesianos;
- batches de `5k..25k` y un writer por shard;
- leases con expiracion, retries acotados y dead-letter;
- checkpoint por particion y run manifest append-only;
- candidate generation y review/application son fases separadas;
- scans por keyset, no deep offset;
- unchanged partitions se reutilizan solo tras verificar hash;
- sibling temp + rename atomico protege cada fichero; C1 aun no sustituye el
  conjunto DB+JSON transaccionalmente, por lo que valida release/hash parity
  despues de promocion;
- cada run reconcilia discovered, eligible, candidates, reviewed, compared,
  rejected, ambiguous, blocked y dead.

No se crean filas falsas para benchmarks. La promocion de capacidad usa universos
oficiales reales, memoria/RSS, throughput, error rate y restore medidos.

## 19. Contrato de publicacion

### 19.1 Artefactos

El piloto `C1` produce:

- `etl/data/staging/promise-action-comparisons-v1.db`;
- `etl/data/published/promise-action-comparisons-v1.json`;
- copia byte-identica en
  `ui/gh-pages-next/public/comparisons/data/comparisons.json`;
- validation report con reconciliacion, IDs, hashes y gates;
- este contrato y release note enlazados.

El nivel `C4 million-scale` añade manifest/release inmutable, Parquet
particionado de las cuatro entidades, pointer `latest` hasheado, durable origin y
clean-room restore. El piloto pequeño no afirma tener esos gates.

El JSON publico nunca supera `5 MB` y no contiene el corpus completo. Estructura
minima v1:

```text
schema_version
release_id
snapshot_date
as_of_date
generated_at
real_data_only
synthetic_or_mock
public_domain_information_policy
semantic_sha256
hash_contract
methodology
input_releases
counts
status_counts
coverage
freshness
scale_contract
items[]
caveats[]
```

Cada item v1 publica:

```text
comparison_id
mapping_review_id
comparison_status
directional_countable
public_summary
caveat
claim { IDs, actor ID/label, exact text, pages, date, review status }
action { IDs, kind, date, title, member, vote, actors, source } | null
action_search { state, scope }
actor_capacity { assertion/action capacity, attribution unit, actor-link state,
                 collective/global-merge flags }
frame { source texts, normalization state, exact-frame flag,
        material differences }
mapping_review { ID, state, method/version/time, actor link, basis, directions,
                 substance state, reason codes, differences, rationale }
reason_codes[]
confidence { method, minimum aggregate, label, seven components }
coverage { state, exhaustive, action-search scope }
freshness { tier, cutoff, as-of, warning, ranking eligibility, reason }
counterevidence { search state, exhaustive, items }
evidence[] { ID, side, role, source record/URL/hash, quote, observed, metadata }
evidence_links[]
```

`action=null` solo es valido con la assessment `bounded_action_search` descrita
en la seccion 15. `real_data_only` debe ser true y `synthetic_or_mock` false. El
pilot publica confidence numerica fail-closed incluso para estados no fuertes;
los componentes bloqueados valen cero y no se maquillan con un promedio.

### 19.2 API

Rutas logicas v1:

- `GET /v1/comparisons` con cursor, limit, status, actor, frame, action kind y
  as-of;
- `GET /v1/comparisons/{comparison_id}`;
- `GET /v1/comparisons/{comparison_id}/versions`;
- `GET /v1/comparisons/{comparison_id}/evidence`;
- `GET /v1/comparison-releases/{release_id}`;
- `GET /v1/comparison-frames/{frame_id}` cuando se normalicen frames.

Cursor opaco y seek-based. El API devuelve release ID/hash, next cursor, bounded
limit, coverage/freshness y deprecation metadata. Nunca hace offset profundo ni
devuelve millones de filas en una respuesta.

### 19.3 UI

La superficie publica debe mostrar, en este orden:

1. texto exacto/acotado de lo declarado, actor oficial, capacidad, fecha y fuente;
2. accion exacta, actor/capacidad, fecha, action kind y fuente;
3. status y definicion no acusatoria;
4. por que se considero o no comparable, dimension por dimension;
5. mapping state y si es candidato o confirmado;
6. coverage, freshness, confianza y contraevidencia;
7. timeline y todas las acciones relacionadas, sin colapsarlas;
8. links a evidencia, objeto fuente, actor graph y release/hash;
9. caveats y camino de correccion/review.

Copy obligatorio:

- `Alineado en este par: la accion observada avanza la misma proposicion. No es una evaluacion de cumplimiento total.`
- `En conflicto en este par: la accion observada va en direccion opuesta bajo un mapping confirmado. No prueba intencion, culpa ni corrupcion.`
- `Evidencia insuficiente: no podemos determinar la relacion sin inventar datos ni tratar ausencia como incumplimiento.`
- `Mapping ambiguo: existe mas de una relacion plausible entre lo declarado y la accion.`
- `Cambio de enfoque: ambos objetos estan relacionados, pero cambia una dimension material.`
- `No comparable: los objetos no responden la misma pregunta bajo este metodo.`

Prohibido:

- badge rojo/verde sin evidencia y caveat visible;
- ranking sobre candidatos no revisados;
- headline “promesa rota/cumplida” derivado de `conflicted/aligned`;
- ocultar identities, unknowns, blockers o acciones contrarias;
- tratar confianza como probabilidad de honestidad;
- inferir outcomes o corrupcion desde un path del grafo.

La URL comparte `comparison_id` y, opcionalmente, release ID en fragment/query
explicito. Cambiar filtros, abrir evidencia o cargar mas filas debe preservar
estado y accesibilidad sin layout shifts abruptos.

## 20. Quality gates

Una release falla cerrada ante cualquiera de estos casos:

### 20.1 Datos y procedencia

- dato synthetic/mock/placeholder/fallback en inputs, tests de escala o outputs;
- input release/hash distinto del manifest;
- source record, URL, hash o locator ausente en evidencia obligatoria;
- texto fuente truncado usado como assertion/action completa;
- identidad oficial publica eliminada o alterada;
- secreto, cookie, token, sesion privada o path local en output publico.

### 20.2 Semantica

- status fuera de los seis permitidos;
- `aligned/conflicted` con mapping candidato, ambiguo o superseded;
- `aligned/conflicted` basado solo en topic/keyword/similitud;
- `aligned/conflicted` sobre accion procedimental no equivalente al objeto de la
  assertion;
- `aligned/conflicted` sin direccion de efecto confirmada;
- ausencia de accion convertida en conflicto/incumplimiento;
- award tratado como pago, firma como implementacion o attendance como influencia;
- outcome o cambio de indicador presentado como efecto causal.

### 20.3 Identidad y tiempo

- merge de actor por nombre;
- actor/capacidad sin evidencia o fuera de vigencia;
- label actual back-projected a un hecho historico;
- accion anterior a assertion con estado fuerte;
- fecha de fetch usada como fecha de accion;
- intervalo conocido invalido.

### 20.4 Integridad y escala

- duplicate natural key o ID no determinista;
- FK/orphan/supersession roto;
- conteos source -> eligible -> candidates -> reviews -> comparisons no
  reconciliados;
- evidencia obligatoria sin enlace;
- rerun con cambios de IDs, status counts o logical hash;
- artefacto publico no bounded;
- fichero Parquet sobre limite sin excepcion documentada;
- manifest/file hash mismatch;
- clean restore o full-row validation fallido en niveles promovidos;
- peak RSS o error rate sobre presupuesto declarado.

## 21. Gates de promocion

| Nivel | Requisito |
| --- | --- |
| `C0 contract` | este metodo, schema y tests de contrato |
| `C1 reviewed pilot` | pares oficiales reales revisados, evidencia completa, replay, FK, UI con estados no fuertes honestos; cero estados fuertes es valido |
| `C2 candidate scale` | candidatos reales particionados, reconciliation, queue y bounded export; siguen sin veredictos fuertes automaticos |
| `C3 promoted mapping` | gold set real estratificado, dual review, metricas por estrato y regla promovida que pasa seccion 10.4 |
| `C4 million-scale` | `1M+` pares/edges reales, partitions, durable origin, clean restore, correction replay, RSS/throughput y API bounded medidos |
| `C5 accountability production` | segunda observacion temporal, supersession real, correction SLO, ownership de dos personas y reproduccion externa |

Ningun nivel se infiere por el numero total de filas del proyecto. El manifest de
la propia lane debe probarlo.

### 21.1 Corte de referencia C1

El corte de `2026-08-20` usa solo promesas oficiales BNG 2023, roll calls
oficiales de Congreso/Senado, afiliaciones oficiales proyectadas por el actor
graph y cinco mappings sometidos a `explicit_evidence_review`:

- release `vclc:comparison-release:ea65f3b8104dd678cb7ebce724b78f86`;
- semantic SHA-256
  `7b37c75c836a0a85c0aab70b7165a5ce005cef320c22c49e34ec650969691b19`;
- actions selected-scope SHA-256
  `e7535d6a4c186c79ff8ba7b56cbe96c886aa2c49ebe5adef4d83d2bd6db933e1`;
- bounded-search candidate rows SHA-256
  `1b8e4e8e982edf2985a5e184395331d3271ae7a0d055eb9d6a9f3d509dbadb0a`;
- `5` comparisons y `18` evidence links;
- `3` `ambiguous_mapping`;
- `1` `insufficient_evidence` mediante `bounded_action_search`;
- `1` `not_comparable` por accion procedimental/objeto distinto;
- `0` `aligned`, `0` `conflicted`, `0` `changed_framing`;
- `0` filas `directional_countable`.

La ausencia de estados fuertes es un resultado correcto. El enum soporta los seis
estados, pero no se crea una fila para demostrar un codigo. Este corte prueba C1,
no C3 ni C4. Escribe en batches y reemplaza cada fichero de forma atomica, pero el
conjunto DB+JSON aun requiere validacion contra releases mezcladas. Cinco reviews
no prueban ejecucion fisica de un millon de comparaciones, representatividad,
durable origin ni clean restore.

## 22. Definition of Done v1

- schema aditivo con las cuatro tablas y FKs validas;
- IDs y replay deterministas;
- assertion/action atomicas de fuentes oficiales reales;
- actor, capacidad, tiempo y frame comprobados por separado;
- mappings candidatos separados de decisiones confirmadas;
- seis estados exactos y algoritmo fail-closed;
- acciones procedimentales y topic-overlap no generan estados fuertes;
- evidencia, contraevidencia, coverage, freshness y confianza visibles;
- correcciones/supersession append-only;
- export bounded + partitions/API preparados para millones;
- identidad oficial publica conservada;
- cero causalidad, legalidad, intencion, culpa o corrupcion inferida;
- validator independiente, UI auditable y release note con limites reales.
