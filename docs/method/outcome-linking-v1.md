# Outcome linking v1

Estado: contrato normativo preproduccion para `TODO 30`

Fecha contractual: `2026-08-20`

Input real: `etl/data/manual/outcome_links/reviewed_links_v1.json`

## 1. Verdad actual

Esta capa aun no publica outcome links.

| Campo | Valor |
| --- | ---: |
| escala operativa | `C0` |
| pares dentro del universo acotado | 20 |
| candidatos reales auditados por maquina | 1 |
| pares revisados por una persona | 0 |
| links publicados | 0 |
| nivel del candidato | `L1` |
| estado del candidato | `pending_human_review` |

`bounded_scope_complete=true` significa solamente que las queries, filtros y
releases descritos aqui se enumeraron completos. No significa cobertura global:

- `all_possible_actions_searched=false`;
- `all_possible_indicators_searched=false`;
- `all_possible_action_indicator_pairs_searched=false`.

El nombre historico `reviewed_links_v1.json` no convierte su contenido en review.
El fichero contiene un candidato preproduccion. No existe reviewer, timestamp de
review, decision humana ni sign-off. Todos esos campos son `null`.

Copy exacta si el estado aparece en diagnostico:

- label: `Candidato preproducción pendiente de revisión humana`;
- summary: `Este emparejamiento usa una votación real del Senado y observaciones reales de Eurostat. Es un candidato metodológico L1, no un enlace de resultado publicado.`;
- warning: `No usar para afirmar asociación estadística, causalidad o efecto; atribuir resultados; clasificar actores; asignar mérito o culpa; ni evaluar éxito, fracaso, legalidad o corrupción.`

## 2. Prohibiciones

Outcome linking relaciona una accion publica real con observaciones reales que
puedan aportar contexto antes/despues. V1 no demuestra que la accion produjo el
cambio observado.

1. Solo fuentes y filas reales. Cero synthetic, mock, demo, placeholder, URL
   inventada o valor de relleno.
2. Discovery produce candidatos, nunca confirmacion.
3. Tiempo usa intervalos inclusivos; una label anual no es un instante.
4. Semantica y geografia necesitan review humana identificada para `L2`.
5. `L3`, `L4` y `L5` son hard reject en producer y validator v1.
6. Dos puntos permiten aritmetica; no asociacion estadistica.
7. Ningun nivel asigna intencion, legalidad, corrupcion, merito, culpa, exito o
   fracaso a persona, partido o institucion.
8. Nombres y datos personales publicados oficialmente se retienen. No se
   anonimizan, inicializan, pseudonimizan ni sustituyen por agregados.
9. Solo se excluyen secretos, cookies, tokens, credenciales, sesiones privadas y
   trazas locales. Eso no autoriza retirar identidad publica.
10. Todo item conserva drill-down a accion, participante, observacion y evidencia.

Claims actuales:

| Claim | Valor |
| --- | --- |
| `statistical_association_claim` | `none` |
| `causal_claim` | `none` |
| `effect_estimate` | `not_computed` |
| `political_merit_or_blame` | `not_assessed` |
| `success_or_failure_assessment` | `not_assessed` |
| `corruption_assessment` | `not_assessed` |
| `directional_countable` | `false` |
| `ranking_eligible` | `false` |

## 3. Escalera de evidencia L0-L5

La escalera expresa autoridad metodologica, no importancia politica o calidad
moral.

| Nivel | Estado | Gate minimo | Permitido | Prohibido |
| --- | --- | --- | --- | --- |
| `L0` | descubrimiento/pre-candidato | par elegible enumerado pero sin bundle de candidato cerrado y revisado, o falta acción/indicador/evidencia | cobertura, exclusión, blocker y pair planning interno | afirmar relación |
| `L1` | candidato | evidencia real, par machine-audited y gates deterministas reproducibles | cola interna, evidencia y estado pendiente | outcome, asociacion o efecto |
| `L2` | contexto descriptivo revisado | gates L1 mas review humana semantica/geografica, reviewer, decision y copy | hechos, intervalos, valores y aritmetica como contexto | asociacion, efecto, causalidad, merito o culpa |
| `L3` | asociacion descriptiva | multiples puntos, especificacion estadistica, diagnosticos y review | fuera de v1 | v1 lo rechaza |
| `L4` | diseno causal candidato | tratamiento, outcome, poblacion, comparador, DAG y supuestos | fuera de v1 | v1 lo rechaza |
| `L5` | estimacion causal validada | identificacion, falsificaciones, robustez, sensibilidad y review | fuera de v1 | v1 lo rechaza |

Reglas:

- `L1 -> L2` solo mediante review humana real y versionada.
- Cambiar un enum manualmente no sube nivel.
- Confianza de modelo, volumen o proximidad temporal no sustituyen review.
- V1 falla si recibe `L3`, `L4`, `L5` o claims asociados; no degrada en silencio.
- El candidato Senado-Eurostat es exactamente `L1`.

## 4. Escala C0-C5

Arquitectura preparada para millones no significa millones procesados.

| Nivel | Evidencia fisica minima | Estado |
| --- | --- | --- |
| `C0` | contrato, input real y cierre acotado; sin link publicado | cobertura actual del input |
| `C1` | schema, producer y validator; candidate bundle local real, completo y validado, sin release mientras falte review | gate de implementación demostrado localmente: `2.973` checks independientes, cero fallos |
| `C2` | al menos 1.000 pares reales, batches bounded y replay | subgate físico planner demostrado: C2A `33.726` pares / `111` checks; queue/review sigue abierta |
| `C3` | al menos 100.000 pares/refs reales, particiones, restore y fault injection | volumen/partición/fault local excedidos por C2B; Parquet, reuse incremental y rollback durable abiertos |
| `C4` | al menos 1.000.000 pares reales con tiempos, peak RSS, paridad y retention | subgate físico demostrado: C2B `2.865.602` pares / `107` checks; retention/origin remoto y promoción abiertos |
| `C5` | C4 durable, clean restore, rollback, SLO y verificacion externa | no demostrado |

El input de publicación local conserva `scale_stage=C0`; el bundle demuestra la mecánica C1
solo cuando el validator independiente pasa. Los planners C2A/C2B son artefactos
L0 internos separados: prueban procesamiento físico real, no cobertura global,
review, relación, efecto ni promoción. Un millón de candidatos no es un millón de links correctos.
Candidates, reviews, publications, exclusiones y participant refs se cuentan por
separado. Nunca se fabrican filas para alcanzar un umbral.

## 5. Unidades del modelo

### 5.1 Accion

Hecho oficial versionado: votacion, iniciativa, norma, adjudicacion, obligacion,
pago, entrega, firma, entrada en vigor u otro evento verificable. Estados no se
colapsan. Votacion no prueba implementacion; adjudicacion no prueba pago.

### 5.2 Indicador, release, serie y observacion

- Definicion: fuente, dataset, concepto, frecuencia, unidad, metodologia y
  politica de revision.
- Release: captura oficial content-addressed.
- Serie: dimensiones completas, geografia y stable key.
- Observacion: intervalo inclusivo, valor exacto, status, incertidumbre,
  revision y evidencia en bruto.

### 5.3 Link, version, review y membership

`outcome_link_id` identifica relacion logica accion-serie.
`outcome_link_version_id` fija evidencia, seleccion, participantes, assessments,
calculos, claims y wording del candidato. Es independiente de release y review.

Review es decision humana append-only con identidad propia derivada de link
version. Membership liga version + review a release. Resultado de review nunca
entra en la preimage de link version: evita ciclo `version -> review -> version`.

## 6. Canonicalizacion

Todos los hashes normativos usan:

```text
json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
```

UTF-8, sin LF final. Arrays conservan orden contractual. Decimales y upstream IDs
se conservan como texto donde corresponda. NaN e Infinity son invalidos.

Hashes fisicos SQLite no forman parte de closures, IDs de version o release.
Cambios de pagina/header/indice pueden alterar el contenedor sin alterar filas.
Sirven solo como localizadores de ejecucion.

`generated_at` es metadata determinista externa, fuera de identidades. El input
usa `2026-08-20T00:00:00Z` con source
`externally_supplied_deterministic_build_parameter`. Es fecha contractual de la
construccion, no reloj de materializacion, validacion ni publicacion. Ningun
consumidor debe rotularla como `Generado` sin ese matiz. Freshness se calcula y
muestra por separado desde los inputs: action snapshot `2026-02-12`; indicator
release `vclc:indicator-release:408979873b81ba19e8e65169`, source snapshot
`2026-08-11`, upstream update `2026-02-10T11:00:00+0100`, comparison state
`baseline`. El status agregado `policy_outcomes_public_status_v3` usa
`contract_date` para esa metadata y expone esos inputs seleccionados, sus
cutoffs y el estado pendiente; no inventa un timestamp de materializacion o
validacion.

## 7. Cierre exacto del universo de acciones

Alcance: eventos enlazados a la iniciativa opaca
`senado:leg14:exp:621/000005`, source `senado_votaciones`, snapshot
`2026-02-12`. El source/snapshot freeze impide que una captura futura amplie en
silencio el universo historico.

Query, parametros, proyeccion y orden viven literalmente en
`selection_closure.action_scope.preimage.query_contract`. SHA-256 del SQL UTF-8:

`26744880f6ace2751ea0d84dcebf2848d1667ae6ffba38777e98b8f361f5c6ab`

Parametros, en orden:

1. `senado:leg14:exp:621/000005`;
2. `senado_votaciones`;
3. `2026-02-12`.

Proyeccion por fila:

```text
action_id, initiative_id, link_method, link_confidence_decimal,
link_evidence, vote_date, legislature, session_number, vote_number, title,
totals.present, totals.yes, totals.no, totals.abstain, totals.not_voting,
totals.absent_normalized, totals.absent_source_record, source_id,
source_record_id, source_snapshot_date, source_record_content_sha256
```

Orden: `vote_date`, `session_number`, `vote_number`, `action_id`.
`confidence` usa `format(confidence, '.1f')`; `evidence_json` se parsea.

| Medida | Valor |
| --- | --- |
| filas | 20 |
| bytes canonicos | 17.309 |
| SHA-256 universo | `1a9860116209538c5eb0445e78b2ba09e89cab19410ab3215102208c5832a756` |
| predicate | title `exact_utf8_equal` a `Resto del proyecto de ley` |
| seleccionados | 1, voto 142 |
| excluidos | 19, votos 123..141 |
| `bounded_scope_complete` | `true` |
| `all_possible_actions_searched` | `false` |

Closure activa, sin hash fisico DB:

- preimage: 2.362 bytes canonicos;
- SHA-256:
  `76cbc30d6295225b608827cf106fe7e306187802f0d193b8170cd80a72683a0e`.

Liga source hashes seleccionados:

- voto:
  `f889017fcbf3b36d069112eeb4c680ab3da4b4863982b9dbd7f931119a601f81`;
- iniciativa:
  `97e7b6db4361b460a0a8f345558a007a963a1acd87bc34e0393d11fcdef8e98f`.

## 8. Cierre exacto del universo de indicadores

Alcance: release exacto
`vclc:indicator-release:408979873b81ba19e8e65169`. Definitions/releases y
series filtran ese release de forma explicita. Observaciones filtran tanto
series version como release. Un release futuro no altera replay historico.

Las queries/proyecciones completas viven en
`selection_closure.indicator_scope.preimage.query_contract`.

| Query | Parametros | SHA-256 SQL UTF-8 |
| --- | --- | --- |
| definiciones + releases | indicator release ID | `790635d039f4eae732119050ad902a0d540573a0efe05c761f8818f24ff07d48` |
| series | indicator release ID | `91b354196b2636c1b28d762f238f35945102d49d602de53902a966351af54dc3` |
| observaciones + evidencia | series version ID, indicator release ID | `ee9c1a4358185bfa7c5e27e38053c728c39c743a6b3da8462a713e2d2541204c` |

Transforms exactos, tambien embebidos:

- definitions/releases: direct SQLite row mapping, preservando scalar JSON
  types;
- series: parsear `dimensions_json`, eliminar esa key y emitir el valor parseado
  como `dimensions`;
- observations: direct row mapping, conservar `value_decimal` y
  `raw_value_json` como TEXT, y anadir `temporal_role` por reglas inclusivas.

Cada query declara su lista ordenada completa `*_row_projection_fields`. Un
validator no puede hashear dicts SQLite directos cuando el contrato exige rename
o campo derivado.

Resultados:

| Proyeccion | Filas | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| definiciones + releases | 1 | 809 | `e80f36946e6f670722a5cc994afabaf2f0820a4926062bcde90e002cabc38819` |
| series del release | 86 | 42.340 | `dd3a99e71c260a17bb131dcd63e01a10558a52ec77e4d69203d2bcd81bdaa1f4` |
| ES/country elegible | 1 | 483 | `37be1a070d8eaa0a95fcdfbc6c2fa160cba852c1d492e053d606562e0e178411` |
| observaciones con rol | 25 | 20.024 | `9db97ee08e7bafddb3df2ab9ab094dc86a4b4cd40ecb0b85336be46d14676d23` |

Filtro geografico exacto: `geography_code=ES AND geography_level=country`.

Roles del universo:

- 20 `strict_pre_eligible`;
- 1 `overlap_excluded`;
- 4 `strict_post_eligible`.

Seleccion:

- pre: maximo `period_end`, luego `revision_ordinal DESC`, luego ID ASC;
- post: minimo `period_start`, luego `revision_ordinal DESC`, luego ID ASC;
- overlap: todos los intervalos que intersectan fecha de accion.

Closure activa:

- preimage: 5.780 bytes;
- SHA-256:
  `9cf53d68068f938150f646dda99300b9967830eb50ab396a7b98fecba98fbdd3`;
- `bounded_scope_complete=true`;
- `representative_indicator_codebook=false`;
- `all_possible_indicators_searched=false`.

Liga release y bruto Eurostat: 4.763.587 bytes, SHA-256
`8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491`.

## 9. Cierre exacto de actor refs

Participant occurrences salen del action ID seleccionado, ordenadas por
`CAST(seat AS INTEGER), seat, member_name`. Actor query filtra exactamente:

- release
  `e52dd7fac6f29570d23756e927e0b9cfe73d1bf2f7c30fa01de75d4dc3a6f4a5`;
- source `senado_votaciones`.

No usa `latest`. Un segundo actor release no duplica ni cambia refs historicos.
`person_id` se compara como ID opaco mediante igualdad tras coercion a TEXT con
`attributes_json.legacy_person_id`.

La proyeccion actor-ref preserva el tipo JSON parseado de `legacy_person_id`;
en este release real son numeros JSON, requisito del digest `b372...`. Solo el
match coacciona ambos IDs a TEXT. El export downstream emite
`upstream_person_id` como TEXT opaco. No se confunden digest fuente y tipo de
storage publico.

| Query | SHA-256 SQL UTF-8 |
| --- | --- |
| participants voto | `91e4a03d06e5a7daf6fcae745497a7c52828a2658c7e6514da223ad93490848d` |
| actor release + source | `2b6f769421ad86e111c67d919368ed017ee84bb67653c149abb0841b2041a2c1` |

Proyeccion actor-ref:

```text
seat, official_member_name, legacy_person_id, vote_choice,
official_group_code, actor_id, node_version_id, release_id, canonical_label,
identity_state, source_id, source_record_id, source_url,
source_content_sha256, provenance_state
```

Resultado:

- refs: 264;
- bytes canonicos: 220.798;
- SHA-256:
  `b372167366b0d7899b414764e6243d94509dac94dcc982326dcf2fae85e60dd6`;
- closure: 2.431 bytes, SHA-256
  `a2e9c927717b5c86afef2c9ead58f0be3b243e2bb5d7d145f29c0b418ae22d59`.

Dos diferencias reales de labels:

1. seat `99`: `JUAN JOSÉ IMBRODA ORTIZ` frente a
   `Juan José Imbroda Ortiz`;
2. seat `273`: `LUIS ROGELIO RODRÍGUEZ COMENDADOR PÉREZ` frente a
   `LUIS ROGELIO RODRÍGUEZ-COMENDADOR PÉREZ`.

No se corrigen. Label y opcion de ballot oficiales son autoritativas. Actor
graph aporta referencia adicional, no reemplazo.

Gap de provenance actor actual:

- los `264/264` refs preservan actor release, actor/node IDs, source record,
  label y estado source-scoped;
- los `264/264` tienen `actor_source_content_sha256=null`;
- los `264/264` apuntan a la misma URL generica del catalogo Senado para
  legislatura 15, no a una captura actor-specific content-addressed;
- nombre, seat, grupo y voto exactos siguen protegidos por el SHA del
  vote-record normalizado y su raw locator, por lo que no hay perdida de
  identidad;
- la arista actor es, por ahora, derived linkage basado en release + closure,
  no provenance de captura actor-source completa.

C1 conserva este gap de forma explicita. Antes de L2 se exige una captura
actor-source checksum-pinned o estado `derived_link` explicito, junto con origin
durable y restore del actor release requerido. Nunca se elimina un nombre
oficial para ocultar este defecto de provenance.

## 10. Closure combinada activa

| Campo | Valor |
| --- | --- |
| action scope | `76cbc30d6295225b608827cf106fe7e306187802f0d193b8170cd80a72683a0e` |
| indicator scope | `9cf53d68068f938150f646dda99300b9967830eb50ab396a7b98fecba98fbdd3` |
| actor-ref scope | `a2e9c927717b5c86afef2c9ead58f0be3b243e2bb5d7d145f29c0b418ae22d59` |
| pares acotados | 20 |
| candidatos machine-audited | 1 |
| reviews humanos | 0 |
| publicados | 0 |

Preimage: 628 bytes. SHA-256:

`87b10890f2a414c3200f03a0a253910faf2110e467844528c24d4ecd8aee2354`

Incluye `all_possible_action_indicator_pairs_searched=false`, ademas de los flags
separados de acciones e indicadores.

## 11. Correcciones de auditoria

Hashes anteriores quedan solo como evidencia historica preproduccion:

- action closure: 812 bytes,
  `4e7fa86eb51e9f2a8d5b47634395b0b1a7546e5ce43423ac66396ab9140ce466`;
- indicator closure: 1.649 bytes,
  `1eeee6bf6c92fcaac841b3fe5ea6f23eb3e8fe62ecb135d2ca3ba82606b9dbd6`;
- combined: 2.624 bytes,
  `ec03e02f5be32defee320a60692bd3b73eab5d1d41d5b997c71953af7ea7b863`.

No son identidad activa porque incluian hashes fisicos SQLite y combined decia
`reviewed_pairs=1` sin review humano.

Las cuatro proyecciones logicas mantienen hashes exactos aunque el contenedor
fisico pueda cambiar. Hashes/path/bytes de DB pertenecen exclusivamente a future
execution/validator reports, no al manual input ni a este contrato normativo.

Otra correccion: `-40000/287` fue etiquetado erroneamente como porcentaje. Es
cambio en basis points. Porcentaje exacto: `-400/287`.

## 12. Slice real: accion y ballots

Accion seleccionada:

- ID/source record:
  `url:https://www.senado.es/legis14/votaciones/ses_17_142.xml`;
- fecha `2020-10-07`;
- legislatura 14, sesion 17, votacion 142;
- titulo exacto `Resto del proyecto de ley`;
- iniciativa `senado:leg14:exp:621/000005`;
- titulo
  `Proyecto de Ley del Impuesto sobre Determinados Servicios Digitales. (621/000005)`;
- link `leg_expediente_payload_exact`, confidence decimal `1.0`;
- evidence: expediente `621/000005`, field `payload.tipo+numero`, legislature
  `14`.

Source record normalizado voto:

- source `senado_votaciones`, snapshot `2026-02-12`;
- 39.854 bytes;
- SHA-256
  `f889017fcbf3b36d069112eeb4c680ab3da4b4863982b9dbd7f931119a601f81`.

Source record normalizado iniciativa:

- source `senado_iniciativas`;
- 9.301 bytes;
- SHA-256
  `97e7b6db4361b460a0a8f345558a007a963a1acd87bc34e0393d11fcdef8e98f`.

Son hashes del payload normalizado, no bytes XML originales. Captura
vote-specific original: `content_sha256=null`, `bytes=null`, state
`absent_from_current_snapshot`. URLs oficiales existen, pero no copia original
content-addressed. Gap visible; original-byte completeness queda bloqueada.

Labels exactas y autoritativas:

| Label fuente | Filas |
| --- | ---: |
| `SÍ` | 134 |
| `NO` | 101 |
| `ABSTENCIÓN` | 28 |
| `NO VOTAN` | 1 |

Suma 264. `NO VOTAN` no significa absent.

Ausencia conserva dos campos distintos:

- `parl_vote_events.totals_absent`: `NULL`;
- `raw_payload.totals_absent`: `0`.

`NULL` significa no normalizado; no se convierte en cero. El cero fuente se
conserva separado. Ninguno reemplaza `NO VOTAN`.

## 13. Identidad publica

Input contiene 264 registros nominales reales:

- 264 seats, nombres oficiales y upstream person IDs distintos;
- cero nombres ausentes;
- cero ballot choices ausentes.

Proyeccion fuente de ocho campos:

- 75.913 bytes;
- SHA-256
  `74fd8e3efa93dbaafe3c5b305124e65e5690add43fdf47a622cfa53546f87d8e`.

Proyeccion exportada con actor IDs, upstream IDs como TEXT opaco y provenance
exacta de cada occurrence:

- 330.512 bytes;
- SHA-256
  `1d5b71858a3d5367a83f335d6a5ec8d50931666432ed55e8593e27889423c542`.

Cada row liga:

- `vote_source_record_id` al action/source record exacto;
- `vote_source_record_content_sha256` a `f889017f...`;
- `vote_source_locator` como JSON Pointer RFC 6901
  `/member_votes/<original_array_index>`.

El index se deriva emparejando exactamente seat, nombre oficial, grupo oficial y
ballot choice contra el array original. Nunca se usa posicion del export sorted
como sustituto. Los 264 indices originales quedan cubiertos una sola vez.

Reglas:

1. Nombres, seats, grupos, votos y source links quedan drillable cuando exista
   release.
2. Agregado no sustituye participant refs.
3. Upstream IDs son TEXT opaco; no se parsean prefijos, numeros, URL o signos
   para inferir identidad/semantica.
4. Cross-DB actor refs son ID TEXT + release ID + projection digest. No FK fisico
   entre SQLite files.
5. Actor mismatch no altera occurrence oficial.
6. Escala cambia particion/paginacion, no retencion.

## 14. Slice real: indicador

- source `eurostat_sdmx`;
- dataset `nama_10r_3gdp`;
- indicator `vclc:indicator:b9225f1a836937d1e9369b12`;
- code `gdp_current_market_prices_per_inhabitant_pps_eu27_2020`;
- frequency `A`, unit `PPS_EU27_2020_HAB`;
- release `vclc:indicator-release:408979873b81ba19e8e65169`;
- series `vclc:indicator-series-version:3589ebcf91bc85174095f0f1`;
- stable key
  `nama_10r_3gdp|freq=A|unit=PPS_EU27_2020_HAB|geo=ES`;
- geography `ES`, `NUTS`, `country`;
- raw: 4.763.587 bytes, SHA-256
  `8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491`.

| Rol output | Periodo | Intervalo | Valor | Observation ID | Evidence ID | Pointer |
| --- | --- | --- | ---: | --- | --- | --- |
| `pre` | 2019 | `2019-01-01..2019-12-31` | 28700 | `vclc:indicator-observation-version:9a65804d28811168fbd8b41d` | `vclc:indicator-observation-evidence:5b1771a0f21e6a5b0da781fb` | `/value/244044` |
| `overlap_excluded` | 2020 | `2020-01-01..2020-12-31` | 25100 | `vclc:indicator-observation-version:be05c6fbcc661b89fb8b6698` | `vclc:indicator-observation-evidence:ad294082bf5da72f26bacd2b` | `/value/244045` |
| `post` | 2021 | `2021-01-01..2021-12-31` | 28300 | `vclc:indicator-observation-version:ee0bd4e628bf3c0f64a7a6f7` | `vclc:indicator-observation-evidence:970678ddbde169f13e826941` | `/value/244046` |

Las tres: revision ordinal 1, `baseline`, source status `null`, uncertainty
`not_provided`.

## 15. Gate temporal

Accion puntual `d`, intervalos inclusivos:

```text
pre eligible  <=> observation.period_end < d
post eligible <=> observation.period_start > d
overlap       <=> observation.period_start <= d <= observation.period_end
```

Accion `[action_start, action_end]`:

```text
pre.period_end < action_start
post.period_start > action_end
```

Cualquier interseccion queda `overlap_excluded`.

Aplicacion:

- `2019-12-31 < 2020-10-07`: pre;
- 2020 contiene fecha: overlap excluido;
- `2021-01-01 > 2020-10-07`: post.

Roles universo:
`strict_pre_eligible|overlap_excluded|strict_post_eligible`. Roles refs:
`pre|overlap_excluded|post`. No se mezclan enums. Usar 2020 como pre/post falla.

## 16. Gates semantico y geografico

Enum semantico:

```text
target_outcome_confirmed | broad_context_only | incompatible | needs_context
```

Estado:

- `status=pending_human_review`;
- `decision=null`;
- `proposed_decision=broad_context_only`;
- `target_outcome_match=null`, propuesta `false`;
- `mechanism_verified=null`, propuesta `false`.

PIB/habitante es contexto economico amplio. No mide base, recaudacion,
incidencia, compliance, output digital, bienestar o distribucion del impuesto.
Es propuesta machine-audited, no decision humana.

Enum geografico:

```text
exact | national_scope_compatible | nested_not_equal | crosswalk_versioned |
incompatible | needs_context
```

Estado:

- `status=pending_human_review`;
- `decision=null`;
- `proposed_decision=national_scope_compatible`;
- `geography_match=null`, propuesta `true`.

Accion propone `ES` por procedimiento nacional del Senado; vote row no tiene
`territory_id`. Eurostat usa `ES/country`. Necesita confirmacion humana; nunca se
declara `human_confirmed` sin reviewer.

## 17. Aritmetica exacta

Pre `28700`; post `28300`.

| Medida | Numerador | Denominador | Unidad | Display 6 lugares |
| --- | ---: | ---: | --- | ---: |
| diferencia | -400 | 1 | `PPS_EU27_2020_HAB` | `-400` |
| post/pre | 283 | 287 | ratio | `0.986063` |
| cambio relativo | -4 | 287 | ratio | `-0.013937` |
| cambio porcentual | -400 | 287 | percent | `-1.393728` |
| cambio basis points | -40000 | 287 | basis points | `-139.372822` |

Racionales son autoridad. Display usa `ROUND_HALF_EVEN`, seis lugares; no es
autoridad. Binary float queda prohibido para identidad/validation.

`-400` es diferencia aritmetica, no efecto. No se atribuye a voto, ley,
participantes, partidos o instituciones. Intervalo cruza COVID-19 y muchos
cambios no medidos. Excluir 2020 evita overlap; no resuelve confounding.

## 18. IDs y preimages

### Link logico

Preimage exacta:

```text
identity_contract_version, link_kind, action_id, indicator_id,
stable_series_key,
geography_scope {geography_code, geography_level, geography_system}
```

Resultado:

- 406 bytes;
- SHA-256
  `5874c51233074eb67d2807ed9a709708a798eb94ed133773de837321d0f0d6c2`;
- ID `vclc:outcome-link:5874c51233074eb67d2807ed`.

### Link version

Preimage liga todo significado del paquete de evidencia/propuesta:

- contract/method, logical link, candidate evidence state y supersession;
- cuatro closures;
- accion, iniciativa, evidence, fechas/titles y source hashes;
- original-byte gap, ballot labels/counts y absent distinction;
- participant/actor digests y mismatch count;
- indicator/release/series/raw hash/unit/geography/method/revision;
- temporal refs/reglas;
- assessments machine semantico/geografico;
- racionales, rounding, claims, wording, reason codes y limitations;
- `review_contract_version` y regla
  `review_result_included_in_version_identity=false`.

No incluye review result. Review ID depende de version ID; incluirlo aqui crearia
ciclo. Tampoco incluye release, manifest, artifact hash, physical DB hash,
runtime time o audit PK.

Resultado:

- 11.270 bytes;
- SHA-256
  `193c3c8b7e5f442d0373408a28acde31972e19807f21c31c59955e3d770d1abc`;
- ID `vclc:outcome-link-version:193c3c8b7e5f442d0373408a`;
- `supersedes_outcome_link_version_id=null`.

### Review identity

Actual:

```text
review_version_id=null
review_identity_sha256=null
review_identity_preimage=null
reviewer_public_id=null
reviewed_at=null
review_method=null
decision=null
signoff=null
supersedes_review_version_id=null
```

Review futuro preimage:

```text
review_identity_contract_version, outcome_link_version_id,
reviewer_public_id, reviewed_at, review_method, evidence_examined,
semantic_decision, geography_decision, level_decision, claim_policy,
reason_codes, rationale, reader_wording, signoff,
supersedes_review_version_id
```

Human timestamp es hecho y participa. Build `generated_at` no. Rationale y
wording participan para ligar todo significado. Membership liga version + review
despues de existir ambos.

## 19. Schema aditivo implementado

Estas nueve tablas y sus índices viven en `etl/load/sqlite_schema.sql`. Todas
las PK son estables/content-addressed; no usan `AUTOINCREMENT` para entidades
semánticas. Las filas son append-only: triggers de base de datos rechazan
`UPDATE` y `DELETE`, y las FK usan `RESTRICT`.

### `outcome_links`

- PK TEXT `outcome_link_id`;
- `identity_contract_version`, `link_kind`;
- `action_id`, `indicator_id`, `stable_series_key` como TEXT opaco;
- `geography_code`, `geography_level`, `geography_system`;
- `identity_sha256` full 64 hex;
- UNIQUE sobre identity SHA.

### `outcome_link_versions`

- PK TEXT `outcome_link_version_id`;
- FK local `outcome_link_id -> outcome_links`;
- `version_identity_sha256`, `method_version`, `evidence_package_kind`;
- queryable `version_state`, `evidence_level`, `candidate_status` y
  `machine_audit_state`;
- valores actuales `preproduction_candidate`, `L1`, `pending_human_review` y
  `machine_validated`;
- action/source/initiative hashes e IDs;
- action/indicator/actor/combined closure hashes;
- indicator release/series/raw content refs;
- participant source/export/actor-ref digests;
- temporal/semantic/geography/calculation/claim/wording JSON canonico;
- `supersedes_outcome_link_version_id` nullable self-FK;
- no `outcome_link_release_id` y no review ID en identity preimage.

### `outcome_link_reviews`

- PK TEXT `outcome_link_review_version_id`;
- FK local `outcome_link_version_id`;
- full `review_identity_sha256`;
- `reviewer_public_id`, `reviewed_at`, `review_method`;
- semantic/geography/level decision enums;
- evidence examined, reason codes, rationale, claim policy, reader wording;
- sign-off y `supersedes_review_version_id` nullable self-FK;
- no fila placeholder cuando review no existe.

### `outcome_link_releases`

- PK TEXT `outcome_link_release_id`;
- schema/method/config versions + hashes;
- `as_of_date`, source release roots, sorted membership semantic root;
- counts por level/status/source y previous release ID;
- release descriptor SHA;
- no artifact hash, manifest hash ni runtime `generated_at` en preimage.

### `outcome_link_release_memberships`

- PK TEXT content-addressed `outcome_link_release_membership_id`;
- FK local a release y link version;
- FK nullable a review version;
- cuando existe review, FK compuesto liga review + link version + decisiones
  semántica, geográfica y de nivel seleccionadas; no se puede reutilizar un
  review de otra versión ni publicar una decisión distinta de la revisada;
- membership state, selected level, selected decision, selected semantic
  decision, selected geography decision e inclusion reason;
- UNIQUE `(outcome_link_release_id, outcome_link_version_id)`;
- membership ID preimage liga release ID, link version ID, selected review ID o
  `null`, state, level, decision e inclusion reason;
- misma version puede vivir en varios releases con membership IDs distintos.

El input C0 produce cero release rows y cero membership rows. Un materializer C0
puede producir link/version/refs/evidence localmente, pero no debe inventar
release para hacer parecer publicado el candidato.

### `outcome_link_observation_refs`

- PK TEXT `outcome_link_observation_ref_id`;
- FK local a link version;
- role `pre|overlap_excluded|post`;
- observation/evidence/release/series IDs logicos;
- interval, exact value, status, uncertainty, revision;
- raw content hash/path/pointer y exclusion reason;
- UNIQUE `(outcome_link_version_id, role, indicator_observation_version_id)`.

### `outcome_link_participant_refs`

- PK TEXT `outcome_link_participant_ref_id`;
- FK local a link version;
- `action_id` TEXT opaco, requerido por index/drill-down;
- official name, opaque upstream ID, seat, official group y ballot label;
- actor ID, node version, actor release, official/actor labels;
- source ID/URL/snapshot/record ID/content hash, exact raw JSON Pointer y row
  semantic hash;
- index `(action_id, upstream_person_id, outcome_link_participant_ref_id)`;
- index actor `(actor_graph_release_id, actor_id, outcome_link_participant_ref_id)`.

### `outcome_link_evidence`

- PK TEXT `outcome_link_evidence_id`;
- FK local a link version;
- evidence role, logical entity/version ID, official URL;
- content hash, bytes, repo-relative raw path, locator, capture state;
- original-byte absent y normalized-record present se almacenan separados.

### `outcome_link_scope_closures`

- PK TEXT `scope_closure_sha256`;
- kind `action|indicator|actor_reference|combined`;
- contract version, canonical preimage JSON, canonical bytes;
- bounded completeness y all-possible flags;
- UNIQUE full SHA.

### Ref ID preimages y prefixes

Cada tabla guarda full 64-hex semantic SHA y deriva ID con primeros 24 hex. No
se usa rowid como identidad.

Observation ref preimage `outcome_link_observation_ref_identity_v1`:

```text
outcome_link_version_id, role, exclusion_reason,
indicator_id, indicator_release_id, indicator_series_version_id,
indicator_observation_version_id, indicator_observation_evidence_id,
period_label, period_start, period_end, value_decimal, value_text,
source_status_code, uncertainty_state, revision_ordinal, revision_state,
source_content_sha256, raw_path, value_json_pointer, status_json_pointer
```

ID: `vclc:outcome-link-observation-ref:<first-24-hex>`.

Participant ref preimage `outcome_link_participant_ref_identity_v1`:

```text
outcome_link_version_id, action_id, seat, official_member_name,
upstream_person_id_text, official_group_code, official_vote_choice,
vote_source_id, vote_source_url, vote_source_snapshot_date,
vote_source_record_id, vote_source_record_content_sha256,
vote_source_locator, actor_graph_release_id, actor_id,
actor_node_version_id, actor_canonical_label, actor_identity_state,
actor_provenance_state, actor_source_record_id, actor_source_url,
actor_source_content_sha256
```

Full preimage SHA tambien es `participant_row_semantic_sha256`. ID:
`vclc:outcome-link-participant-ref:<first-24-hex>`.

Evidence preimage `outcome_link_evidence_identity_v1`:

```text
outcome_link_version_id, evidence_role, entity_version_id,
source_id, source_record_id, official_url, content_sha256, bytes,
raw_path, locator, capture_state, normalized_record_is_original_bytes
```

Campos ausentes son JSON `null`, nunca placeholder. El gap XML original, con
hash/bytes `null`, obtiene evidence ID reproducible sin fingir bytes. ID:
`vclc:outcome-link-evidence:<first-24-hex>`.

Review ID:
`vclc:outcome-link-review-version:<first-24-hex>` de preimage en seccion 18.
Release ID: `vclc:outcome-link-release:<first-24-hex>` del descriptor en seccion
20. Membership ID:
`vclc:outcome-link-release-membership:<first-24-hex>`.

Orden canonico de arrays:

- observation refs: role rank `pre=0`, `overlap_excluded=1`, `post=2`, luego
  observation ID, evidence ID;
- participant refs: action ID, `CAST(seat AS INTEGER)`, seat, official name,
  opaque upstream ID, participant ref ID;
- evidence: evidence role, entity version ID, content SHA-or-empty,
  locator-or-empty, evidence ID;
- reviews: link version ID, reviewed_at, review ID;
- memberships: link version ID, review ID-or-empty, membership ID.

Cross-DB refs se validan por:

```text
source_id + opaque stable ID + upstream release/content hash + closure digest
```

SQLite FK solo dentro del output DB. Audit integer PKs nunca son identidad.
Lookup actor futuro necesita indice bounded por
`(release_id, source_id, actor_id)` o mapping equivalente; nunca scan global para
cada participant.

## 20. DAG release/manifest sin ciclos

```text
source bytes/releases + method/config
  -> canonical projections
  -> scope closure hashes
  -> logical IDs + release-independent link versions
  -> independent review versions
  -> sorted full membership descriptor semantic root
  -> canonical release descriptor
  -> outcome_link_release_id
  -> SQLite/Parquet/JSON artifacts
  -> artifact hashes
  -> manifest body {release_id, artifacts, hashes, counts}
  -> manifest SHA-256
  -> latest pointer {release_id, manifest_sha256}
```

Reglas anti-ciclo:

- release ID no incluye artifact/manifest hashes;
- artifact puede incluir release ID;
- manifest incluye release ID/artifact hashes, no su propio hash;
- manifest SHA vive en receipt/latest pointer;
- latest no vuelve a release/manifest identity;
- link version no incluye review result;
- review deriva de link version;
- membership deriva despues de ambos;
- `generated_at` metadata nunca es identity root.

Release descriptor preimage exacta incluye:

```text
release_identity_contract_version, schema_version, method_version,
config_sha256, as_of_date, source_release_roots,
scope_closure_root_sha256, membership_semantic_root_sha256,
member_count, review_count_by_state, level_counts,
previous_outcome_link_release_id
```

`scope_closure_root_sha256` hashea array canonico:

```text
[{scope_kind, scope_closure_sha256}, ...]
```

Orden: `scope_kind`, despues SHA. Incluye exactamente action, indicator,
actor_reference y combined.

`source_release_roots` es array canonico con shape unica:

```text
{source_kind, source_id, source_release_or_snapshot_id,
 source_content_root_sha256, scope_closure_sha256}
```

Orden: `source_kind`, `source_id`, `source_release_or_snapshot_id`, content root,
scope SHA. Accion usa snapshot `2026-02-12` y action candidate-universe SHA.
Indicator usa indicator release ID y raw Eurostat SHA. Actor usa actor release ID
y actor-ref projection SHA.

Antes de conocer release ID, `membership_semantic_root_sha256` hashea array de
descriptores completos:

```text
{outcome_link_version_id, review_version_id,
 membership_state, selected_level, selected_decision,
 selected_semantic_decision, selected_geography_decision,
 inclusion_reason, publication_flag}
```

`review_version_id`, `selected_decision`, `selected_semantic_decision` y
`selected_geography_decision` admiten JSON `null`, no empty string dentro del
objeto. Orden: version ID, review ID-or-empty, state, level, decision-or-empty,
semantic decision-or-empty, geography decision-or-empty, inclusion reason,
publication flag. Cambiar cualquiera cambia root y release ID.

Tras derivar release ID, membership ID hashea:

```text
{membership_identity_contract_version, outcome_link_release_id,
 full_membership_descriptor}
```

Artifacts o compression distintos pueden compartir semantic root, pero siempre
tienen hashes/manifest distintos. Membership nueva crea release nuevo; no muta
link version.

## 21. Revision y supersession

Append-only:

1. Cambio action date/title/ballot/participant/source hash crea link version
   nueva.
2. Capturar XML original crea evidence/link version nueva; no rellena hash viejo.
3. Nuevo Eurostat release crea series/observations versionadas y recalcula roles.
4. Nuevo actor release/ref digest crea link version nueva si cambia refs.
5. Review crea review version; correccion usa `supersedes_review_version_id`.
6. Cambio de rationale, wording, decision o sign-off cambia review ID.
7. Retirada upstream conserva historia, registra state y crea release nuevo.
8. Release nuevo selecciona memberships nuevas; anteriores quedan rollbackable.
9. `superseded` nunca equivale a delete.

Todos los `supersedes_*` del candidato actual son `null`.

## 22. Contrato JSON manual/publico

### Input C0

Top-level:

```text
format_version, method_version, generated_at, generated_at_source,
generated_at_identity_authority, scope_truth, policy,
selection_closure, candidates
```

Cada candidato:

```text
IDs/preimages, status/level, review null state, release null state,
action, all participants, indicator, temporal assessment,
semantic/geography pending assessments, exact math, policy,
reason codes, limitations, reader wording
```

Parser rechaza duplicate keys. Exactamente un JSON. Paths repo-relative. No
self-hash dentro del fichero. Execution DB hashes quedan fuera de identidad.

### Release publico futuro

Un release valido contiene:

- `latest.json`: solo release ID, manifest SHA y immutable manifest path;
- `manifest.json`: schema/method, counts, partitions, hashes, min/max IDs,
  limits y provenance roots;
- bounded link index;
- detail shards por link/version;
- participant shards completos y keyset-paginables;
- observation/evidence refs;
- machine-readable limitations/claim flags.

Index item minimo:

```text
release_id, outcome_link_id, outcome_link_version_id, review_version_id,
action/indicator/geography/time summary, reviewed level/decision,
exact arithmetic display, association/causal/merit flags,
participant/evidence counts, detail/participant/evidence paths,
freshness, supersession, limitations
```

No `L1` en superficie ciudadana como outcome. Un status index interno puede
contarlo con copy pendiente. Ningun shard filtra identidad por ser personal
publica.

Budgets iniciales:

- index browser objetivo <= 5 MB;
- detail/participant shard objetivo <= 5 MB;
- keyset cursor, nunca OFFSET sobre millones;
- no millones de rows cargadas al browser.

## 23. Validator independiente

Validator no importa funciones de confianza del producer.

### JSON e identidad

- strict parse + duplicate-key rejection;
- schema/enum/null-state exactos;
- recanonicalizar cuatro closures y link/version preimages;
- validar canonical bytes, full SHA y prefix IDs;
- `review_result_included_in_version_identity=false`;
- `generated_at_identity_authority=false`;
- current review/membership/supersedes siguen null;
- diff byte-identical con mismo input + metadata externa.

### Universo

- ejecutar SQL literal con todos los release/source/snapshot params;
- action `20/17309/1a9860...`;
- definitions `1/809/e80f...`;
- series `86/42340/dd3a...`;
- ES/country `1/483/37be...`;
- observations `25/20024/9db9...`, roles `20/1/4`;
- actor refs `264/220798/b372...`;
- closures activas y combined `87b108...`;
- bounded complete true; all-possible flags false.

### Action/identity parity

- action/initiative/date/titles/link/evidence/source hashes exactos;
- 264 rows/seats/names/IDs;
- `SÍ=134`, `NO=101`, `ABSTENCIÓN=28`, `NO VOTAN=1`;
- nominal sum = present 264;
- normalized absent `null`, source-record absent `0`;
- official labels no reemplazadas;
- dos actor label mismatches preservados;
- source/export/actor digests exactos;
- cada participant locator resuelve el raw `member_votes[index]` exacto y los
  264 indices forman cobertura bijectiva;
- cero identity loss.

### Indicator/time/math parity

- raw Eurostat hash/bytes/pointers exactos;
- obs/evidence IDs, intervals, values, status, revision exactos;
- same series/release;
- 2019 pre, 2020 only overlap, 2021 post;
- Fraction/Decimal: `-400`, `283/287`, `-4/287`, `-400/287` percent,
  `-40000/287` basis points;
- displays six-place `ROUND_HALF_EVEN`;
- no binary float o zero division silenciosa.

### Review/claim gate

- L1 exige review null y publication false;
- L2 exige reviewer, time, method, semantic/geography decisions, rationale,
  wording, sign-off e identity validos;
- L3-L5 hard fail;
- association/effect/causal/merit/blame/ranking claim hard fail v1;
- proposal nunca se trata como review;
- original-byte gap visible.

### Artifact/integrity gate C1 implementado ahora

- `PRAGMA integrity_check=ok`; local FK check vacio;
- IDs/PKs unicos y deterministas;
- las nueve tablas SQLite y sus proyecciones JSON tienen conteos, keys y filas
  exactas; DB/JSON/manifest/pointer local existen y sus hashes coinciden;
- manifest counts y artifact-set identity coinciden con los dos artifacts C1;
- source fingerprints pre/post, report-before-pointer y latest candidate
  pointer escrito al final pasan;
- no secret, workstation path o private session state;
- official personal data retenida.

### Gates de escala fuera de los `2.973` checks C1

- C2A pasa `33.726` pares / `111` checks; C2B pasa `2.865.602` / `107`;
- C2B verifica SQLite, roots, particiones, checkpoints, fuente y semantic parity;
- crash/resume, missing/corrupt shard, config drift, triggers append-only, clones
  adversariales y restore local byte-idéntico pasan;
- Parquet, unchanged-partition reuse multi-shard y rollback remoto siguen abiertos;
- origin durable publica, clean restore y rollback reconstruyen los mismos
  semantic roots: abierto;
- retencion nominal exacta y public-field lineage pasan en todas las
  particiones restauradas: fuente nominal resoluble localmente; origin remoto abierto.

## 24. Promocion atomica y rollback

Candidato actual no se promociona. El materializador local fsynca el report y
despues escribe el latest candidate pointer como ultimo commit. Ese pointer
selecciona un artifact set preproduccion inmutable; no crea release, membership,
validated link, publicacion ni promocion.

Release futuro:

1. fijar inputs reales, releases, config, as-of y metadata externa;
2. materializar versions/refs/evidence en staging, batches bounded;
3. construir reviews y memberships solo donde existen;
4. derivar sorted membership root y release ID;
5. commit DB solo tras integrity/FK gates;
6. escribir SQLite/Parquet/JSON/shards en directorio inmutable temporal;
7. calcular artifact hashes y manifest body;
8. ejecutar validator independiente y clean restore;
9. atomic rename de directorio;
10. atomic replace de un unico latest pointer;
11. leer desde origen publico y comparar manifest/artifacts;
12. conservar release previo y probar rollback.

Fallo en cualquier paso deja latest anterior. Reemplazo separado de DB/JSON/
manifest, missing shard, review ausente o restore fallido mantiene
`published_links=0` para esos items.

## 25. Camino fisico a millones

Nunca producto cartesiano global `actions x series`.

### Sparse generation

1. Particionar action por source/type/jurisdiction/date.
2. Particionar series por source/dataset/domain/unit/geography/release.
3. Filtrar incompatibles antes de temporal join.
4. Range seek por `(stable_series_key, period_start, period_end)`.
5. Candidate queue separada de review/release queues.
6. Dedupe logical pair antes de enrichment.
7. Modelo prioriza; nunca confirma review/efecto/causalidad.

Particion normativa:

```text
action_source_id=<opaque>/action_year=<yyyy>/
indicator_source_id=<opaque>/dataset_code=<opaque>/
geography_level=<opaque>/link_bucket=<00..ff>
```

Slice real usa `senado_votaciones/2020/eurostat_sdmx/nama_10r_3gdp/country`.
`link_bucket` son primeros dos hex del full logical SHA, no hash truncado
reinterpretado.

Orden dentro particion:

```text
action_id, indicator_id, stable_series_key, action_occurred_at,
outcome_link_id, outcome_link_version_id
```

Participant refs: action source/year + action hash bucket. Observation refs junto
al link. Manifest guarda rows, bytes, min/max IDs, schema y SHA por file.

### Control/data planes

- SQLite: queues, leases, reviews, releases, counts, small indices;
- Parquet Zstandard: versions, memberships, observation/participant/evidence;
- content-addressed object store: raw + release artifacts;
- bounded JSON/API: index + drill-down;
- batch joins/caches, no N+1;
- URL/content dedupe before download;
- lease, heartbeat, bounded retries, source rate limit, dead letter;
- checkpoint partition + last stable key, no OFFSET;
- backpressure y bounded concurrency;
- incremental reuse solo con exact source/method/config/schema roots.

### Plano humano escalable

- candidate generation escribe una queue separada, particionada y resumible;
- cada task referencia solo `outcome_link_version_id`, method/schema version,
  evidence-manifest ID y pointers bounded; no embebe otra copia completa del
  candidato, sus participantes ni los source rows;
- reviewer decision es un registro pequeno append-only keyed al immutable
  version ID: reviewer identity, assignment/lease, calibration cohort, method,
  semantic/geography decisions, rationale, confidence, sign-off y timestamp;
- leases atomicos, heartbeat, expiry/reclaim y dedupe garantizan una decision
  logica por reviewer/task aunque haya ejecucion at-least-once;
- high-risk/L2 exige dos reviews independientes cuando la politica lo requiera;
  disagreement abre adjudicacion, nunca majority inventada;
- conflicts, counterevidence, appeal, right of reply y correction/supersession
  tienen queues y SLA separados;
- scorecard mide assignment latency, queue age p50/p95/max, throughput,
  agreement, adjudication rate, reversal, appeal y correction latency;
- evidence lookup devuelve nombres/IDs oficiales completos desde shards/API
  keyset. Packet bounded minimiza duplicacion operacional, no informacion
  personal de dominio publico.

### Gates medidos por run

- input/output/excluded/error/dead-letter counts;
- candidate/reviewed/published counts separados;
- rows/bytes/files/row groups/min-max IDs/SHA por partition;
- wall time, throughput, peak RSS y disk peak;
- retry/rate-limit/HTTP status distributions;
- participant retention/evidence completeness;
- semantic replay hash;
- fault injection, interrupted resume, clean restore y rollback.

Batches, row groups, concurrency y shard bytes se fijan tras medir corpus real.
Ningun benchmark synthetic valida C2-C4. La aceptación actual usa exclusivamente
pares reales: C2A `33.726`, C2B `2.865.602`.

Las identidades oficiales referenciadas por millones de pair rows siguen
resolubles en fuente/shards/API keyset. Index bounded no implica supresión del
corpus nominal.

## 26. Exit criteria C1-C5

### C1

- schema/producer/independent validator implementados;
- 1 link version real + 3 observation refs + 264 participant refs + evidence;
- 0 review/membership/public rows mientras siga pendiente;
- deterministic replay, local integrity/FK, original-byte gap visible;
- los `2.973` checks cubren artifacts C1 locales; no prueban particiones,
  Parquet, origin durable, clean restore ni rollback;
- si luego existe review real, release local separado y atomic validation.

### C2

- >=1.000 pairs reales scoped: pasa físicamente con C2A `33.726`;
- sparse planner, keyset, batches bounded y restart checkpoint: pasa;
- generated candidate queue y decision-only review task contract keyed por
  immutable version ID: abierto;
- candidate/review/public counts separados;
- no N+1; peak RSS y throughput publicados: pasa para planner;
- failure/retry/dead-letter evidence real: pasa para planner, reviews abiertos.

### C3

- >=100.000 pairs/refs reales: pasa con C2B `2.865.602`;
- particiones SQLite + semantic parity: pasa; Parquet abierto;
- incremental unchanged-partition reuse: abierto;
- crash/resume, missing shard detection y restore local: pasan; rollback remoto abierto;
- nominal identity source resolution: pasa localmente; lineage/origin remoto abierto.

### C4

- >=1.000.000 pairs reales procesados: pasa con C2B `2.865.602`;
- partition/count/hash gates del planner pasan `107/107`;
- peak RSS/disk/wall time medidos; presupuesto de producción aún no aprobado;
- temporal, semantic status, FK y source identity checks del planner pasan;
- scale report declara `publication_eligible_rows=0`, sin claims ni rows inventadas;
- C4 no se promociona hasta retention/origin/restore/rollback durable.

### C5

- C4 en origen durable publico;
- immutable release + atomic latest;
- clean-client manifest/artifact verification;
- restore/rollback desde published artifacts;
- SLO/alerts y verificacion externa reproducible.

## 27. Manual artifact actual

Physical DB paths, bytes y hashes quedan fuera de la identidad semántica pública.
Los reports C2 actuales los capturan como execution locators y declaran que no
son relationship/claim inputs.

Manual artifact despues de release/source pinning y participant raw locators:

- path `etl/data/manual/outcome_links/reviewed_links_v1.json`;
- bytes 463.383;
- SHA-256
  `c96d9e2be844cadbd58997c519785f8402f1b75e5d929eeafdefbca238c3533a`;
- 1 candidate, 264 participant records, 0 reviews, 0 memberships/publications.

Este archivo autocontenido de `463.383` bytes es evidencia de C1, no formato de
review a escala. C2 debe derivar tasks decision-only que referencien immutable
version/evidence IDs y resolver detalle nominal desde shards bounded. No se
eliminan ni pseudonimizan los `264` nombres oficiales.

## 28. Siguiente gate controlable

1. Hecho local: schema aditivo release-independent, memberships ligadas al
   review correcto y `UPDATE/DELETE` bloqueados en las nueve tablas.
2. Hecho local: producer C0 desde este único input real, source fingerprints
   estables, report fsynced y local immutable candidate pointer escrito al
   final; no es promotion ni release.
3. Hecho local: validator independiente con `2.973` checks, duplicate-key gate,
   paridad exhaustiva DB/JSON y dos tests de replay real-only.
4. Hecho local: replay exacto de closures, IDs, aritmética y 264 participant
   refs; cero reviews, releases, memberships o publicaciones.
5. Resolver original bytes o mantener el gap bloqueante visible.
6. Fijar captura actor-source por checksum o marcar el enlace como derived;
   no L2 hasta origin/restore actor y provenance bounded de voto/texto.
7. Obtener review humano real sin fabricar identidad/sign-off.
8. Solo entonces crear review L2 y release local separado.
9. Probar restore/rollback del artifact set completo desde origen durable.
10. Hecho para el lane planner: sparse keyset, particiones, checkpoint/resume y
    fault injection pasan C2A/C2B; el bundle C1 sigue acotado/monolítico.
11. Separar candidate queue de decisiones append-only y probar leases,
    calibracion, dual review/adjudicacion, queue age, throughput, appeals y SLA.
12. Hecho para subgates físicos C2A/C2B con pares reales y telemetría; completar
    queue/review, multi-shard/Parquet, origin remoto, rollback y promoción C3-C5.

Escalar filas no escala autoridad. Review, provenance, identity retention y
claims gates permanecen obligatorios por particion y release.

## 29. Divulgación del candidato pendiente y separación de autoridad

Outcome linking v1 prepara para divulgación un candidato metodológico pendiente y
evidencia verificable byte por byte. Mientras no pase publicación/verificación
remota, son artifacts locales en formato público. Nunca lo presenta como vínculo
validado ni como una reproducción completa del pipeline.

Estado fuente actual: `policy_outcomes_public_status_v3`, `4.078` bytes,
SHA-256 `226dfdf943434607b633dfebfaf8475f7546bf6a4e25ee5426ba34e6f4249f87`.
Paquete content-addressed `5ac0187857fd1436cca31616e4072bb13812281f01983b1c4fae6598a803be48`;
manifest `9.496` bytes / SHA-256
`2bfe3f2d0850c6775349b763239300f50eb199a04167026798764bb20ff83d07`;
`17` assets exactos. La proyección pública determinista de los `2.973` checks
independientes tiene SHA-256
`8e97863250312acba99be9d8952febb5c5eae68993cc3fa036d6d30a4561bc8b`;
excluye hashes físicos y telemetría volátil del informe operacional sin perder
ningún resultado, count, root o reconstrucción semántica. El build local fresco
de `1.435` páginas, el audit completo y la verificación real del browser pasan;
publicación y verificación remota siguen pendientes.

- `scripts/materialize_outcome_context.py` escribe solo el bundle interno C0/L1;
- `scripts/validate_outcome_context.py` reconstruye fuentes, identidades,
  aritmética, schema y artefactos sin importar el producer;
- `scripts/export_policy_outcomes_snapshot.py` acepta exclusivamente un informe
  independiente con `status=passed`, reconstruye desde las bases reales el
  universo exacto `20 × 1` y publica status, manifest y evidencia antes de
  reemplazar el status visible;
- `/policy-outcomes/` muestra `1` candidato metodológico pendiente, `0` vínculos
  validados, la revisión humana pendiente y todos los límites de claim solo
  cuando status, manifest y los `17` assets pasan bytes y SHA-256; con cualquier
  ausencia, drift o path inseguro falla cerrado;
- el status pequeño no duplica filas individuales, pero enlaza el paquete
  público completo. La evidencia semántica conserva byte por byte los `264`
  nombres oficiales, escaños, grupos, votos y referencias. Eliminados o
  seudonimizados: `0`;
- el manifest propio declara `unsigned`. El origen de escala firmado se verifica
  criptográficamente durante cada export contra signer, fingerprint y trust root
  Ed25519 fijados; el trust root se publica como activo exacto separado y el
  manifest declara explícitamente que esa firma no atestigua este paquete;
- `etl/data/published/policy-outcomes-es-2026-02-25.json` queda como artefacto
  legacy y no es input de publicación.

Una integración futura que publique un link exige review L2 real, release,
membership y verificación pública exacta; no puede promover el candidato C0/L1.
