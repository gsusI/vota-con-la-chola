# Promesas y compromisos v1

Estado: contrato normativo para `TODO 18/19`.

## Objetivo

Representar qué prometió o defendió un actor político sin convertir lenguaje
retórico en compromisos falsos. El texto fuente es inmutable. La clasificación,
los topics y cualquier evaluación posterior son capas interpretativas,
versionadas y corregibles.

El modelo debe soportar millones de segmentos y múltiples versiones del mismo
documento mediante identificadores deterministas, inserciones idempotentes,
índices por actor/fecha/tipo/topic y bytes fuera de SQLite.

## Principios no negociables

- Solo fuentes reales. Quedan prohibidos manifiestos, actores, citas y resultados
  sintéticos o de ejemplo en los artefactos de datos.
- Las identidades personales y organizativas publicadas oficialmente se conservan
  de forma exacta. Solo se excluyen secretos, sesiones privadas, rutas locales y
  datos no públicos.
- Una claim registra lo dicho, no su veracidad ni su cumplimiento.
- Una promise es una especialización de claim. No toda frase política es promesa.
- La evaluación de cumplimiento es otra observación y nunca reescribe la promesa.
- `unknown`, `needs_context` y `not_assessed` son resultados válidos.
- Cada fila pública debe llegar al documento, página, cita exacta y hash.

## Entidades

### `manifesto_documents`

Una versión exacta de un documento político público.

- `manifesto_document_id`: SHA-256 determinista del actor, elección, URL y hash
  del contenido.
- `text_document_id`, `source_record_pk`, `source_id`: enlaces de procedencia.
- `party_id`: actor organizativo directo; nunca se crea una persona proxy.
- `document_kind`: `manifesto`, `coalition_agreement`, `policy_platform`,
  `investiture_agreement` u `other_official_commitment`.
- título, elección, jurisdicción, idioma y fechas.
- URL oficial, SHA-256, bytes y número de páginas.

Un cambio de bytes crea una nueva versión documental, aunque la URL sea igual.

### `claim_extraction_runs`

Ejecución reproducible sobre una versión documental. Conserva versión de
pipeline, versión de segmentador, hash de configuración, estado, conteos y
errores. Permite reanudar y comparar sin mezclar resultados de versiones.

### `claims`

Proposición atribuible extraída del documento.

- `claim_id`: hash determinista del documento, página, ordinal y cita.
- actor directo (`party_id`) y label exacta en la fuente;
- texto exacto y normalizado;
- página inicial/final, sección y ordinal;
- método/versión/confianza de extracción;
- `review_status`: `pending`, `rule_confirmed`, `human_confirmed`, `rejected` o
  `needs_context`;
- `claim_status`: `active`, `withdrawn`, `corrected`, `superseded` o `disputed`.

Tipos admitidos:

| `claim_kind` | Regla semántica | Ejemplo abstracto |
|---|---|---|
| `explicit_promise` | acción futura atribuible, concreta y defendida como medida | aprobar, transferir, elevar, eliminar |
| `soft_commitment` | dirección futura sin acción o resultado suficientemente delimitado | impulsar, fomentar, favorecer |
| `preference` | opción normativa o política preferida sin compromiso operativo | preferimos, consideramos conveniente |
| `slogan` | lema o persuasión sin proposición verificable | una sociedad mejor |
| `coalition_commitment` | obligación futura contenida en acuerdo formal entre actores | las partes acuerdan presentar |
| `issue_position` | postura sobre un asunto sin promesa de ejecución | apoyo, rechazo, defensa de un principio |
| `context` | diagnóstico, antecedente, dato o explicación | la tasa fue X |

### `claim_evidence`

Ancla exacta entre claim y documento:

- página y offsets del texto extraído;
- cita exacta y SHA-256 de la cita;
- URL, hash documental y método de extracción;
- rol `primary`, `context`, `contradicting`, `correcting` o `superseding`.

La cita no se parafrasea. Si abarca dos páginas, se conservan ambas y los offsets
se refieren al texto normalizado por página.

### `promises`

Extensión uno-a-uno de una claim que supera la regla de promesa.

- `commitment_strength`: `explicit`, `strong`, `conditional`, `aspirational` o
  `unclear`;
- acción, objeto, población/territorio objetivo, fecha límite y condiciones;
- criterios verificables en JSON;
- `measurability_state`: `measurable`, `partially_measurable`, `not_measurable` o
  `unknown`;
- `observation_status`: inicialmente `not_assessed`; después solo puede ser
  `unknown`, `no_evidence`, `in_progress`, `fulfilled`, `partially_fulfilled`,
  `not_fulfilled`, `superseded` o `not_applicable` mediante evidencia separada.

No se infiere deadline, beneficiario, responsable ejecutivo ni métrica cuando la
fuente no los expresa.

### `claim_topics`

Relación N:M con `topics`. Cada enlace conserva método, versión, confianza y
estado de revisión. Los vocabularios son código de clasificación, no registros
políticos inventados. Un claim sin match queda sin topic; nunca se le asigna uno
por relleno.

## Reglas de extracción v1

1. Verificar HTTPS, firma PDF, tamaño no cero y SHA-256 esperado.
2. Extraer página por página. No usar un texto truncado para segmentar.
3. Detectar estructura explícita del documento: viñetas, numeración y encabezados.
4. Unir líneas de la misma viñeta; no unir viñetas vecinas.
5. Conservar página, ordinal, texto exacto extraído y su hash antes de clasificar.
6. Clasificar como `explicit_promise` solo cuando una medida estructurada contiene
   un verbo de acción futura o una construcción nominal inequívoca de acción.
7. Clasificar verbos direccionales vagos como `soft_commitment`, salvo que el
   objeto y el resultado verificable estén expresos.
8. El diagnóstico, la crítica a otro actor y el relato retrospectivo son
   `context`, incluso si incluyen verbos políticos.
9. Un lema aislado es `slogan`; no se publica como promesa.
10. Un acuerdo de coalición exige documento formal y actores firmantes. Una
    mención informal a cooperación no basta.
11. Topic tagging es multilabel, determinista y versionado. La ausencia de match
    permanece explícita.
12. La publicación v1 admite solo `rule_confirmed` o `human_confirmed`, evidencia
    primaria completa y actor/source verificables. `pending` nunca entra en el
    sample público.

## Ambigüedades y resolución

- **“Impulsaremos X”**: `explicit_promise` si X es una acción delimitada;
  `soft_commitment` si solo expresa dirección.
- **“Defendemos X”**: `issue_position`; puede ser promesa únicamente cuando el
  contexto inmediato introduce una lista de medidas que el actor se compromete a
  promover.
- **Objetivo sin medio**: promise `aspirational`, normalmente no medible.
- **Medida condicionada a competencia o mayoría**: promise `conditional`; la
  condición queda literal.
- **Cifra o plazo**: no implica por sí solo promesa. Debe existir acción atribuida.
- **Lista anidada**: el encabezado aporta contexto, pero cada medida conserva su
  propia cita. No se publica un fragmento que pierda el sentido sin ese contexto.
- **Responsabilidad compartida**: atribuir solo a firmantes explícitos. Otros
  actores quedan `unknown`.
- **Traducción**: el original es evidencia. Una traducción se publica como campo
  derivado con idioma, método y versión, nunca como cita original.
- **Cambios de programa**: nueva versión documental; los enlaces
  `correcting/superseding` conectan versiones sin borrar historia.
- **Cumplimiento**: no se deduce de notas de prensa ni de una sola evidencia
  indirecta. La promesa original queda intacta y la evaluación señala cobertura,
  contraevidencia y fecha de corte.

## Identidad e idempotencia

Los identificadores se calculan con SHA-256 sobre JSON canónico UTF-8:

- documento: actor estable + elección + URL + hash de bytes;
- claim: documento + página inicial/final + ordinal + cita exacta;
- evidence: claim + rol + documento + página + hash de cita;
- promise: claim;
- run: documento + versiones + hash de configuración.

Reprocesar los mismos bytes y configuración debe producir los mismos IDs y
conteos. Los upserts no cambian `created_at`; las filas ausentes de una nueva
ejecución no se eliminan sin una migración explícita.

## Escala

- PDF/HTML crudo y texto completo viven en object storage o filesystem
  content-addressed; SQLite conserva metadatos y citas acotadas.
- Extracción se particiona por `manifesto_document_id`; tagging, por `claim_id`.
- No hay lookups por fila: dimensiones y taxonomía se cargan en memoria y se
  escriben por lotes.
- Los índices principales cubren documento/página, actor/tipo/revisión,
  topic/claim y estado observable.
- La publicación es paginada y content-addressed; no se entrega una tabla de
  millones de claims en un único JSON.
- Cada run expone filas vistas/cargadas/publicables, error rate, bytes, páginas,
  duración y versión.

## Contrato del piloto BNG 2023

Fuente oficial:
`https://www.bng.gal/media/bnggaliza/files/2023/07/05/23_bng_xerais_programa.pdf`.

- SHA-256 esperado:
  `b8994deec0bbc45cdcbef5d7c5395cabf30b0509706303c3d8e76058c48eebfd`.
- 396.842 bytes, 68 páginas.
- Actor: `Bloque Nacionalista Galego`, acrónimo `BNG`.
- Elección: Eleccións Xerais 2023, ámbito estatal con programa centrado en
  Galicia.
- Segmentador: viñetas PDF page-aware.
- Publicación: muestra pequeña de claims rule-confirmed con fuente, página, cita,
  hash, topic y límites metodológicos; ningún claim pending.

## Definition of Done

- schema aditivo y `PRAGMA foreign_key_check` limpio;
- fuente real verificada por hash y estructura;
- extracción page-aware determinista;
- segunda ejecución idempotente;
- actor directo, evidencia exacta y topics versionados;
- sample público validado, limitado y sin filas pending;
- test real-only que usa el PDF oficial, no fixtures inventados;
- release note, tracker y roadmap actualizados con conteos y caveats reales.
