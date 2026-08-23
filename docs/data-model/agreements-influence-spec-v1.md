# Agreements, meetings, lobbying, and influence specification v1

Estado: `v1 estable para hechos, procedencia e inferencias; mapeo físico aditivo`

Fecha: `2026-08-19`

Base: `docs/data-model/core-ontology-v1.md`

## 1. Propósito

Este contrato permite documentar quién se reúne con quién, qué agenda se publicó,
qué partes aparecen en un acuerdo y qué relación demostrable existe entre contacto,
decisión y resultado. Evita el error central de este dominio: presentar proximidad,
coincidencia temporal o una reunión como prueba de influencia indebida.

Debe responder, sin exceder la evidencia:

- qué reunión, acuerdo, pacto o disclosure publicó una fuente oficial;
- cuándo ocurrió, se firmó, se aprobó, se publicó o estuvo vigente;
- qué personas y organizaciones aparecen y con qué rol exacto;
- qué agenda, tema, posición o resultado consta en el documento;
- qué dato falta, qué clasificación es derivada y qué inferencia está sin revisar;
- qué evidencia primaria permite reproducir cada hecho.

## 2. Principios no negociables

1. **Solo datos reales.** Ninguna fila sintética, mock, placeholder, multiplicada o
   generada cuenta como dato, evidencia, cobertura o prueba de escala.
2. **Hecho e influencia separados.** Reunión, asistencia, agenda, propuesta,
   acuerdo, decisión e influencia son objetos distintos.
3. **La reunión no prueba influencia.** Contacto, acceso o proximidad temporal no
   demuestran que una parte causó o condicionó una decisión.
4. **La ausencia no se rellena.** Participantes, agenda, posición, resultado o
   contraparte no publicados quedan `unknown` o `not_disclosed`.
5. **Identidad pública intacta.** Nombres, cargos e identificadores personales o
   jurídicos publicados oficialmente se conservan exactos y con procedencia.
6. **Rol temporal.** El cargo o afiliación aplicable se resuelve en la fecha del
   evento; nunca se proyecta el cargo actual hacia el pasado.
7. **Documento y versión.** Un acuerdo corregido, adenda o agenda actualizada crea
   versión o relación append-only; no borra la captura anterior.
8. **Topics con método.** Un tema explícito y una clasificación por reglas o modelo
   tienen estados distintos.
9. **Alegaciones fuera de hechos.** Corrupción, conflicto de interés, quid pro quo,
   captura regulatoria o influencia indebida requieren evidencia y revisión propias.
10. **Escala por particiones.** Millones de disclosures se procesan por fuente,
    periodo y cursor, con batches idempotentes y artefactos públicos bounded.

## 3. Unidades de análisis

### 3.1 Meeting

Evento de interacción publicado o documentado: reunión bilateral, audiencia,
encuentro de agenda pública, sesión colegiada, mesa de negociación, comparecencia,
evento con lobby o contacto registrado.

Una referencia a una sesión del Consejo de Ministros prueba la existencia de una
sesión y los resultados que la referencia declara. No prueba la lista completa de
asistentes si esta no aparece en la captura.

### 3.2 Meeting participant occurrence

Aparición source-scoped de persona u organización vinculada a una reunión. El rol
pertenece a la relación: `attendee`, `convener`, `host`, `guest`, `lobbyist`,
`public_official`, `counterparty`, `observer`, `disclosing_body` u `other`.

Una organización convocante o publicadora no se marca como asistente. Cada fila
declara `attendance_claim_state` para impedir esa conversión silenciosa.

### 3.3 Agenda item

Tema, propuesta, expediente o punto asociado a una reunión. Puede estar:

- `source_explicit`: título o texto publicado como agenda;
- `source_summary`: resultado resumido por la fuente;
- `derived_topic`: clasificación reproducible posterior;
- `unknown`: la fuente confirma la reunión pero no publica agenda.

Una agenda no prueba que el asunto se tratara; el resultado o acta requiere evidencia
distinta.

### 3.4 Agreement

Compromiso o decisión formal publicada: acuerdo de coalición, investidura, pacto
parlamentario, acuerdo ejecutivo, convenio, memorando, declaración conjunta, adenda,
acuerdo interinstitucional u otro compromiso oficial.

El acuerdo conserva partes, signatarios, adoptantes, obligaciones, vigencia, estado,
documentos, enmiendas y terminación como hechos separados.

### 3.5 Lobbying disclosure

Registro oficial de contacto, cliente representado, persona pública, asunto, fecha,
gasto declarado, contribución, expediente o documento. Se materializa como meeting,
participant, agenda item y evidence; los campos particulares del registro fuente se
preservan en `raw_payload_json` y tablas source-specific.

### 3.6 Influence assertion

Interpretación versionada sobre una relación potencial entre una acción de una parte
y una decisión o resultado. Nunca ocupa una tabla factual. Debe declarar método,
evidencia favorable/contraria, temporalidad, alternativas, confianza, revisión y
estado de publicación.

## 4. Taxonomías v1

### 4.1 `meeting_kind`

- `bilateral_meeting`;
- `public_agenda_meeting`;
- `lobbying_contact`;
- `parliamentary_negotiation`;
- `coalition_negotiation`;
- `council_session`;
- `committee_session`;
- `hearing`;
- `roundtable`;
- `conference_event`;
- `written_contact`;
- `other`.

### 4.2 `agreement_kind`

- `coalition_agreement`;
- `investiture_agreement`;
- `parliamentary_pact`;
- `executive_decision`;
- `interinstitutional_agreement`;
- `collective_bargaining_agreement`;
- `memorandum_of_understanding`;
- `convention`;
- `joint_declaration`;
- `amendment_or_addendum`;
- `other_official_agreement`.

### 4.3 `agreement_status`

- `proposed`;
- `negotiating`;
- `adopted`;
- `signed`;
- `in_force`;
- `partially_implemented`;
- `implemented`;
- `expired`;
- `terminated`;
- `superseded`;
- `withdrawn`;
- `disputed`;
- `unknown`.

`adopted` no equivale a firmado, vigente, ejecutado ni cumplido.

### 4.4 Roles de parte

- `proposer`;
- `negotiating_party`;
- `adopter`;
- `signatory`;
- `counterparty`;
- `implementing_body`;
- `guarantor`;
- `witness`;
- `affected_body`;
- `publishing_body`;
- `other`.

### 4.5 Niveles de inferencia

| Nivel | Significado | Publicación por defecto |
|---|---|---|
| `fact_only` | solo hecho fuente; no afirma influencia | sí |
| `temporal_proximity` | contacto y decisión próximos en tiempo | con caveat |
| `content_alignment` | posición y decisión comparten contenido | revisión obligatoria |
| `plausible_pathway` | existe mecanismo documentado posible | doble revisión |
| `substantiated_influence` | evidencia primaria/corroborada atribuye influencia | revisión legal/editorial |
| `improper_influence_allegation` | posible conducta indebida | no publicar sin política W8 completa |

La confianza numérica no permite saltar de nivel.

## 5. Tiempo y versiones

Campos de meeting:

- `started_at`, `ended_at` y `event_date`;
- `time_precision` y `timezone`;
- `published_at`, `observed_at`, `source_snapshot_date`;
- `scheduled_state`: `scheduled`, `occurred`, `cancelled`, `postponed`, `unknown`.

Campos de agreement:

- `proposed_on`, `adopted_on`, `signed_on`;
- `effective_from`, `effective_to`;
- `published_on`, `observed_at`, `source_snapshot_date`;
- `date_precision`.

Reglas:

- una agenda futura no se convierte en reunión ocurrida;
- una referencia posterior no cambia la fecha del evento;
- una firma no prueba entrada en vigor;
- una adenda se enlaza con `amends`; no reescribe el acuerdo base;
- dos publicaciones iguales en fechas distintas siguen siendo observaciones distintas
  salvo que el origen publique un identificador/versionado compartido verificable.

## 6. Identidad y actores

Campos por occurrence:

- `source_label`, sin reescribir el nombre oficial;
- `source_identifier` y `source_identifier_scheme`;
- `actor_kind`: `person`, `organization`, `public_body`, `collective`, `unknown`;
- `actor_role` o `party_role`;
- `role_title_source`, si aparece;
- `represented_organization_source`, si aparece;
- IDs normalizados opcionales a `persons`, `parties`, `institutions` u org units;
- `identity_state`: `source_scoped`, `resolved`, `disputed`, `unknown`;
- método, confianza, reviewer y evidencia de resolución.

Prohibiciones:

- no fusionar por nombre parecido;
- no inferir asistencia desde la composición general de un órgano;
- no inferir cliente representado desde el empleador actual;
- no ocultar una persona física porque su nombre sea dato personal si el origen
  oficial lo publicó en ese contexto;
- no completar una lista parcial con cargos conocidos por otras fuentes.

## 7. Agenda, posición y resultado

Cada agenda item conserva:

- etiqueta y descripción fuente;
- `item_ordinal` si el documento impone orden;
- `agenda_state`: `scheduled`, `discussed`, `decided`, `deferred`, `cancelled`,
  `source_summary`, `unknown`;
- expediente o identificador externo;
- topic assignments;
- acuerdo o decisión resultante, si existe enlace explícito;
- evidencia exacta.

Posiciones de participantes son claims separados. `attended` no implica `supported`.
Una decisión colegiada no se atribuye individualmente a todos los asistentes sin una
fuente que publique esa atribución.

## 8. Evidencia

Cada meeting o agreement llega a:

`source -> source_record -> raw capture/document -> exact evidence -> normalized fact`

Campos mínimos:

- `source_id`, `source_record_pk`, `source_record_id`;
- URL oficial pública;
- hash SHA-256 de la captura o documento;
- rol de evidencia;
- excerpt exacto y su hash cuando exista;
- página, sección, selector o path JSON;
- `evidence_state`: `captured_bytes`, `official_url_only`, `missing`, `blocked`;
- método y versión del extractor.

Roles iniciales:

- meeting: `announcement`, `agenda`, `attendance`, `minutes`, `outcome`, `context`;
- agreement: `primary_text`, `official_summary`, `signature`, `publication`,
  `amendment`, `implementation`, `termination`, `context`;
- influence: `supporting`, `contrary`, `context`, `methodology`.

La URL viva no sustituye al hash de la captura. El hash no sustituye a la URL pública.

## 9. Topics

`agreement_topics` y el equivalente de agenda guardan:

- topic canónico y etiqueta pública;
- `assignment_kind`: `source_explicit`, `reviewed`, `derived_rule`, `derived_model`;
- método y versión;
- evidencia o exact match;
- confianza opcional;
- `review_status`.

Las clasificaciones derivadas se publican como clasificación, no como texto literal de
la fuente. Un cambio de codebook crea una nueva versión de assignment.

## 10. Modelo físico v1

La implementación aditiva usa estas tablas:

- `accountability_meetings`: evento, estado, tiempo, lugar y procedencia;
- `meeting_participants`: occurrence de actor y rol, con claim de asistencia explícito;
- `meeting_agenda_items`: agenda/resultado publicado, con estado factual;
- `meeting_evidence`: evidencias exactas de reunión, agenda, asistencia o resultado;
- `agreements`: acuerdo/decisión y estado temporal;
- `agreement_parties`: partes, adoptantes, firmantes y organismos afectados;
- `agreement_evidence`: texto/documentos de acuerdo y ejecución;
- `agreement_topics`: temas explícitos o derivados con método;
- `influence_assertions`: inferencias separadas, versionadas y revisables.

Claves naturales:

- meeting: `UNIQUE(source_id, source_record_id, meeting_ordinal)`;
- participant: `UNIQUE(meeting_id, actor_role, participant_ordinal)`;
- agenda item: `UNIQUE(meeting_id, item_ordinal)`;
- agreement: `UNIQUE(source_id, source_record_id, agreement_ordinal)`;
- party: `UNIQUE(agreement_id, party_role, party_ordinal)`;
- evidence: `UNIQUE(subject_id, evidence_ordinal)`;
- topic: `UNIQUE(agreement_id, topic_key, assignment_method, assignment_version)`.

IDs públicos:

`sha256(contract + source_id + source_record_id + ordinal + semantic_kind)`

No dependen de título, nombre, fecha normalizada o resultado de entity resolution.

## 11. Contrato de `influence_assertions`

Campos obligatorios:

- `influence_assertion_id` y `assertion_version`;
- subject/object actor, meeting, agreement, decision o outcome;
- `inference_level` y `assertion_kind`;
- enunciado exacto y limitaciones;
- `method`, `method_version` y ventana temporal;
- evidencia favorable, contraria y contextual;
- alternativas consideradas;
- confianza opcional;
- `review_status`, reviewers y adjudicación;
- `publication_state` y motivo;
- timestamps append-only y supersession.

Gates:

- `fact_only` puede publicarse sin insinuar influencia;
- niveles superiores exigen al menos una evidencia favorable y caveat visible;
- `content_alignment` exige evidencia de la posición previa y de la decisión;
- `plausible_pathway` exige mecanismo y secuencia temporal documentados;
- `substantiated_influence` exige corroboración y doble revisión;
- `improper_influence_allegation` permanece privado hasta cerrar W8, derecho de
  réplica y revisión legal/editorial;
- una fila `unreviewed` nunca se presenta como conclusión.

## 12. Conector oficial La Moncloa v1

El primer slice usa la captura oficial real de referencias del Consejo de Ministros:

- fuente: `moncloa_referencias`;
- objeto capturado: JSON de registros extraídos de páginas oficiales;
- cada registro seleccionado materializa una sesión `council_session`;
- solo resúmenes que contienen explícitamente `acuerdo` materializan un agreement;
- `Consejo de Ministros` se registra como `convening_body` y `adopter`;
- `Gobierno de España / La Moncloa` se registra como `disclosing_body` y
  `publishing_body`;
- ningún ministro se marca como asistente: la captura no contiene una lista completa;
- el excerpt público es el `summary_text` exacto, con path JSON y hash;
- topics se asignan por codebook determinista y se etiquetan `derived_rule`;
- se materializan cero `influence_assertions`.

Este slice demuestra acuerdo + reunión + actores institucionales + fecha + topics +
evidencia. No demuestra asistentes personales, negociación previa, ejecución,
cumplimiento, presión externa ni influencia.

## 13. Escala a millones

### 13.1 Adquisición

- particionar por `source_id`, año/mes, jurisdicción y cursor estable;
- guardar checkpoints y leases durables;
- deduplicar URL y hash antes de descargar;
- usar bounded concurrency por host, retries con jitter y respeto a 429/Retry-After;
- stream de bytes a object storage content-addressed; nunca cargar el corpus completo
  en memoria ni almacenar PDFs masivos como BLOB SQLite;
- separar discovery, fetch, parse, normalize, enrich, review y publish;
- conservar tombstones y estados de acceso bloqueado.

### 13.2 Normalización

- batches de al menos miles de filas con `executemany` o carga set-based;
- caches en memoria para dimensions durante una partición;
- no ejecutar lookup SQL por occurrence;
- índices por fuente/fecha/kind, actor/rol, topic, estado de revisión y cursor;
- writers particionados y single-writer por shard SQLite; Parquet/object store para
  scans analíticos multi-millón;
- replays at-least-once con efecto lógico exactly-once mediante claves naturales.

### 13.3 Publicación

- snapshots inmutables, firmados y content-addressed;
- manifiestos y estadísticas completas, pero páginas públicas bounded;
- API con keyset pagination; nunca offset profundo;
- una página no incorpora todos los participantes/evidencias del corpus;
- índices actor, fecha, organización y topic publicados por partición;
- cambios y correcciones se expresan como deltas/versiones, no reemplazos mudos.

Objetivos operativos antes de promoción `R2`:

- `>=1,000,000` meetings/agreements reales, no filas replicadas;
- `>=99.9%` registros con source record y hash verificable;
- `100%` inferencias fuera de tablas factuales;
- `100%` personal public-domain retenido cuando el origen lo publique;
- `0` FK violations;
- replay idempotente por partición;
- restore desde origen durable sin depender de workstation;
- segunda captura que pruebe unchanged/changed/deleted;
- p95 de normalización y publicación medido por cada 100,000 filas;
- evidencia pública bounded y verificable desde UI/API.

## 14. Gates de calidad

1. Todos los facts tienen `source_record_pk`, URL y hash.
2. Cada excerpt coincide byte por byte con el campo capturado o documento extraído.
3. Cada actor tiene role; attendance solo si la fuente lo declara.
4. Cada topic declara assignment kind, método y versión.
5. Cada agreement distingue adopted/signed/in_force/implemented.
6. Cada meeting distingue scheduled/occurred/cancelled/unknown.
7. `PRAGMA foreign_key_check` devuelve cero filas.
8. Dos replays producen IDs, conteos y hash lógico iguales.
9. El artefacto público pasa el scanner real-only.
10. Toda inferencia publicada declara nivel, revisión, evidencia y limitaciones.
11. No se eliminan nombres o identificadores oficiales públicos.
12. La UI usa lenguaje factual: `publicó`, `registró`, `aprobó`; nunca `influyó`
    sin un assertion publicable.

## 15. Casos límite

- reunión anunciada y luego cancelada: dos estados/versiones, nunca `occurred`;
- lista de asistentes parcial: `attendance_scope=partial`;
- cargo sin persona: conservar cargo, persona `unknown`;
- persona sin cargo: conservar nombre, cargo `unknown`;
- organización representada ambigua: no resolver;
- múltiples clientes en un disclosure: occurrences separadas;
- agenda redactada: conservar redacción fuente y estado `partially_redacted`;
- acuerdo sin texto completo: summary factual + evidence state; no inventar cláusulas;
- misma decisión repetida en dos referencias: observaciones separadas hasta
  reconciliación revisada;
- documento corregido sin aviso: nueva captura/hash y diff; no overwrite;
- nombres homónimos: no merge por nombre;
- evento con gasto: enlazar spending item; no duplicar el importe como pago;
- mención de una ley o entidad: no convertir automáticamente en parte firmante;
- coincidencia entre petición de lobby y norma: `content_alignment` como máximo hasta
  documentar mecanismo, secuencia y corroboración.

## 16. Evolución compatible

Cambios aditivos permitidos:

- nuevos kinds, roles, evidence roles y topic codebooks;
- nuevas tablas source-specific;
- columnas opcionales e índices;
- nuevas assertion methodologies;
- nuevas particiones y transportes de API.

Requieren v2:

- redefinir reunión como prueba de influencia;
- mezclar facts e inference assertions;
- cambiar IDs públicos emitidos;
- eliminar procedencia o historia;
- anonimizar por defecto identidades oficiales públicas;
- equiparar adopted, signed, in force, implemented o fulfilled.
