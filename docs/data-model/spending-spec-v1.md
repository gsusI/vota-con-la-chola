# Spending and procurement specification v1

Estado: `v1 estable para semántica monetaria, procedencia y publicación; mapeo físico aditivo`

Fecha: `2026-08-19`

Base: `docs/data-model/core-ontology-v1.md`

## 1. Propósito

Este contrato permite seguir dinero público sin convertir documentos administrativos
en afirmaciones que no prueban. Modela por separado presupuesto, modificación,
licitación, adjudicación, contrato, modificación contractual, obligación, factura,
pago, entrega y subvención. Conecta cada evento con actores, territorio y evidencia
oficial exacta.

El objetivo operativo es responder preguntas como:

- ¿qué organismo publicó, adjudicó, contrató, obligó o pagó?
- ¿qué persona u organización aparece como proveedor o beneficiario?
- ¿qué importe y semántica publicó la fuente?
- ¿qué documento oficial permite verificarlo?
- ¿qué paso previo o posterior falta para probar el flujo completo?

Un importe adjudicado no es dinero pagado. Un presupuesto no es gasto ejecutado. Una
factura no prueba entrega. Una transferencia no prueba impacto. La interfaz, API y
analítica deben conservar esas diferencias.

## 2. Principios no negociables

1. **Solo datos reales.** No se admiten filas sintéticas, mock, inventadas,
   placeholder ni escaladas por multiplicación.
2. **Importe exacto.** La autoridad monetaria es texto decimal canónico o minor
   units enteros más currency. `REAL` puede ser compatibilidad, nunca reconciliación.
3. **Semántica explícita.** Toda cantidad declara qué representa y si incluye
   impuestos.
4. **Evento por fase.** Notice, award, contract, invoice, payment y delivery son
   objetos diferentes aunque compartan expediente.
5. **Procedencia completa.** Cada fila llega a source record, versión, URL oficial y
   hash de contenido o documento.
6. **Identidad pública intacta.** Nombres e identificadores personales o jurídicos
   publicados oficialmente se conservan exactos. No se anonimizan por defecto.
7. **Resolución prudente.** Una etiqueta y un NIF fuente describen una occurrence;
   no fusionan actores entre fuentes sin identificador compartido o revisión.
8. **Historia append-only.** Correcciones, versiones y tombstones no borran estados
   observados anteriormente.
9. **Incertidumbre visible.** Campos ausentes son `unknown`; nunca se imputan a cero.
10. **Escala por partición.** El contrato soporta millones de filas mediante lectura
    streaming, batches set-based, IDs deterministas y publicación bounded.

## 3. Unidades de análisis

### 3.1 Spending item

Hecho monetario atómico publicado por una fuente. Ejemplos: crédito presupuestario
aprobado, adjudicación de un lote, obligación reconocida, factura registrada, pago o
subvención concedida.

No representa por sí solo todo el expediente. Varias versiones de un anuncio pueden
referirse al mismo procedimiento; varios awards pueden existir por lotes; varios
pagos pueden ejecutar un contrato.

### 3.2 Procurement procedure

Contenedor lógico de contratación: expediente, lotes, anuncios, adjudicaciones,
formalizaciones, modificaciones y documentos. No es automáticamente gasto ni pago.

### 3.3 Budget line

Crédito autorizado en una versión presupuestaria para una combinación verificable
de ejercicio, administración, unidad, programa, clasificación económica, fondo y
territorio. La ejecución se modela en eventos separados.

### 3.4 Actor occurrence

Participación de una persona u organización tal como aparece en una fuente y evento:
órgano de contratación, pagador, proveedor, beneficiario, adjudicatario, emisor de
factura, receptor de pago o responsable de entrega.

El rol pertenece a la relación, no a la identidad permanente del actor.

### 3.5 Evidence

Registro o documento oficial que prueba el valor publicado: página de detalle,
ATOM/CODICE, anuncio, resolución, contrato, factura pública, fichero contable,
transferencia, acta de recepción o informe de auditoría.

## 4. Taxonomía de eventos monetarios

`spending_kind` usa estos valores iniciales:

| Kind | Qué prueba | Qué no prueba |
|---|---|---|
| `budget_appropriation` | crédito autorizado | obligación, pago o resultado |
| `budget_amendment` | cambio de crédito | ejecución del crédito |
| `procurement_notice` | convocatoria o anuncio | adjudicación o contrato firmado |
| `procurement_award` | decisión de adjudicación publicada | formalización, factura o pago |
| `contract_commitment` | compromiso contractual publicado | obligación reconocida o pago |
| `contract_modification` | cambio contractual publicado | ejecución íntegra del nuevo total |
| `recognized_obligation` | obligación contable reconocida | salida bancaria final |
| `invoice` | factura registrada/publicada | conformidad, entrega o pago |
| `payment` | pago/desembolso publicado | entrega, calidad o impacto |
| `delivery_milestone` | entrega/hito/recepción publicada | impacto social o causalidad |
| `subsidy_award` | concesión de subvención | pago al beneficiario |
| `subsidy_payment` | desembolso de subvención | uso correcto o impacto |
| `refund_recovery` | reintegro o recuperación | motivo o responsabilidad no documentada |
| `other` | hecho monetario fuente no clasificado | equivalencia con cualquiera anterior |

Los conectores no pueden mapear una semántica desconocida al kind más cercano. Deben
usar `other`, conservar la etiqueta fuente y abrir una revisión de codebook.

## 5. Semántica del importe

Campos mínimos:

- `amount_decimal`: decimal exacto normalizado, sin separador de miles;
- `currency`: ISO 4217 publicada o `unknown`;
- `amount_semantics`: codebook explícito;
- `tax_semantics`: `excluding_tax`, `including_tax`, `tax_only`, `not_applicable`,
  `unknown`;
- `amount_source_text`: texto exacto cuando normalizar requiere interpretación;
- `amount_precision`: número de decimales fuente;
- `amount_min_decimal` / `amount_max_decimal` cuando la fuente publica rango;
- `amount_method`: `source_exact`, `source_sum`, `derived_conversion`, `unknown`;
- `exchange_rate_id` solo para conversiones publicadas como derivadas.

`amount_semantics` inicial:

- `budget_initial_credit`;
- `budget_final_credit`;
- `budget_amendment_delta`;
- `tender_base_budget`;
- `tender_estimated_value`;
- `award_amount`;
- `contract_signed_amount`;
- `contract_modified_amount`;
- `recognized_obligation_amount`;
- `invoice_gross_amount`;
- `payment_amount`;
- `subsidy_award_amount`;
- `subsidy_payment_amount`;
- `recovered_amount`;
- `source_other`;
- `unknown`.

Reglas:

- Nunca sumar importes con semánticas distintas como un único total.
- Nunca sumar versiones sucesivas del mismo hecho sin elegir la versión vigente.
- Distinguir importe base, impuestos e importe pagadero.
- Mantener moneda fuente. Una conversión a EUR es una vista derivada con fecha,
  tasa, fuente y método.
- Un `NULL` significa desconocido. Cero solo es válido si la fuente publica cero.
- Las conciliaciones usan `Decimal`, no binary float.

## 6. Modelo temporal

Campos disponibles según kind:

- `period_start`, `period_end`: periodo presupuestario o de ejecución;
- `published_on`: fecha de publicación oficial;
- `decision_on`: fecha de resolución/adjudicación;
- `signed_on`: formalización contractual;
- `effective_from`, `effective_to`: vigencia;
- `accrued_on`: devengo;
- `invoice_on`: emisión/registro de factura;
- `paid_on`: desembolso;
- `delivered_on`: entrega o recepción;
- `observed_at`: captura por el pipeline;
- `source_snapshot_date`: corte lógico solicitado.

Una sola fecha fuente se asigna al campo que su etiqueta prueba. No se copia a otras
fases para completar huecos. `date_precision` conserva `day`, `month`, `year`,
`interval` o `unknown`.

## 7. Modelo físico v1

La implementación aditiva crea tres tablas canónicas. Las tablas PLACSP/BDNS
existentes siguen preservando el detalle fuente y alimentan estas tablas.

### 7.1 `spending_items`

Una fila por hecho monetario semántico y versión fuente.

Campos principales:

- `spending_item_id`: ID textual estable y portable;
- `source_id`, `source_record_pk`, `source_record_id`;
- `source_snapshot_date`, `source_url`, `content_sha256`;
- `spending_kind`, `source_kind_label`;
- `stable_object_id`: expediente, lote, concesión u objeto fuente;
- `semantic_ordinal`: ordinal estable dentro del source record;
- `title`, `description`;
- `amount_decimal`, `payable_amount_decimal`, `currency`;
- `amount_semantics`, `tax_semantics`;
- fechas diferenciadas;
- `territory_id`, `territory_code`;
- `publication_state`;
- `extractor_method`, `extractor_version`;
- `raw_payload_json`, timestamps locales.

Clave natural:

`UNIQUE(source_id, source_record_id, spending_kind, semantic_ordinal)`

ID recomendado:

`sha256("spending-item-v1\0" + source_id + "\0" + source_record_id + "\0" + spending_kind + "\0" + semantic_ordinal)`

El ID no depende de nombre, importe ni fecha; una corrección de esos valores conserva
la identidad del slot semántico y queda versionada por source record/version.

### 7.2 `spending_item_actors`

Una fila por actor y rol en el hecho.

Campos principales:

- `spending_item_actor_id`;
- `spending_item_id`;
- `actor_role`: `appropriating_authority`, `contracting_authority`, `payer`,
  `supplier`, `beneficiary`, `invoice_issuer`, `payment_recipient`,
  `delivery_responsible`, `auditor`, `other`;
- `actor_kind`: `person`, `organization`, `public_body`, `unknown`;
- `source_label`, `source_identifier`, `source_identifier_scheme`;
- FKs opcionales a `person_id`, `institution_id`, `org_unit_id`, `party_id`;
- `identity_state`: `source_scoped`, `resolved`, `disputed`, `unknown`;
- `resolution_method`, `resolution_confidence`;
- `source_id`, `source_record_pk`, timestamps.

La etiqueta e identificador oficiales se publican completos. Una FK resuelta añade
navegación; nunca reemplaza el valor fuente.

### 7.3 `spending_item_evidence`

Una fila por ancla probatoria.

Campos principales:

- `spending_evidence_id`, `spending_item_id`;
- `evidence_role`: `primary_record`, `notice`, `award_decision`, `contract`,
  `invoice`, `payment_record`, `delivery_record`, `audit`, `context`;
- `source_id`, `source_record_pk`;
- `document_id` opcional;
- `source_url`, `document_url`, `document_label`, `document_kind`;
- `content_sha256`, `exact_quote`, `quote_sha256`;
- `page`, `section`, `selector`;
- `evidence_state`: `captured_bytes`, `official_url_only`, `missing`, `blocked`;
- timestamps.

`official_url_only` es evidencia navegable, pero no equivale a bytes preservados. El
gap debe ser visible y generar trabajo de captura.

### 7.4 `spending_item_links`

Relación dirigida entre fases u objetos.

- `subject_spending_item_id`, `relationship_type`, `object_spending_item_id`;
- `relationship_type`: `amends`, `announces`, `awards`, `formalizes`, `invoices`,
  `pays`, `delivers`, `refunds`, `supersedes`, `same_procedure_as`, `other`;
- `method`, `confidence`, `review_status`;
- evidencia y timestamps.

Un link por expediente compartido puede ser `rule_linked`; no se presenta como
confirmado si el origen no expone un identificador suficiente.

## 8. Mapeo PLACSP v1

Fuente: Plataforma de Contratación del Sector Público, sindicación ATOM/CODICE.

Mapeo inicial:

| Campo fuente | Destino | Regla |
|---|---|---|
| entry/source record | `spending_items.source_record_*` | conservar versión y hash exactos |
| expediente/lot/result ordinal | ID y `stable_object_id` | nunca nombre como identidad |
| award result | `spending_kind=procurement_award` | no mapear a payment |
| award amount | `amount_semantics=award_amount` | decimal string exacto |
| payable amount | `payable_amount_decimal` | separado del award amount |
| contracting party | actor `contracting_authority` | label e identifier exactos |
| winning party | actor `supplier` | label, NIF y scheme exactos, incluso persona pública |
| notice URL | evidence `primary_record` | URL oficial del registro |
| document references | evidence contextual | `official_url_only` hasta preservar bytes/hash |
| award date | `decision_on` | no copiar a `paid_on` |
| publication date | `published_on` | precisión fuente |
| CPV/territory/procedure | `raw_payload_json` + campos de contexto | codebooks sin inventar labels |

El primer corte público usa awards con autoridad, proveedor, importe exacto y URL
oficial. No afirma que el contrato esté firmado, facturado, pagado o entregado.

## 9. Presupuestos y modificaciones

Una línea presupuestaria se identifica por la combinación oficial más estable:
administración, ejercicio, versión, sección/centro gestor, programa, concepto,
subconcepto, fondo y territorio. Si la fuente no expone todas las dimensiones, se
conservan las disponibles y se declara el nivel de granularidad.

Las modificaciones son deltas, no nuevos presupuestos completos, salvo que la fuente
publique una versión consolidada. Campos adicionales:

- `budget_version_id` y `supersedes_version_id`;
- `amendment_kind`: crédito extraordinario, suplemento, transferencia,
  incorporación, generación, baja u otro valor fuente;
- origen y destino cuando exista transferencia;
- acto jurídico y fecha efectiva;
- importe delta con signo exacto;
- estado de consolidación y reconciliación.

No sumar snapshot inicial, modificaciones y snapshot final como si fueran tres gastos.

## 10. Procedencia y versionado

Cadena obligatoria:

`source -> bulk acquisition/archive -> source record version -> normalized source table -> spending item -> actors/evidence/links -> public release`

Para cada release:

- hash del archive o página oficial;
- hash del miembro/response cuando exista;
- source record ID y content hash;
- extractor y versión;
- query/criterio determinista de selección;
- recuentos source, normalizados, excluidos y publicados;
- hashes de DB/JSON/particiones;
- validación FK, idempotencia y conciliación;
- `real_data_only=true`, `synthetic_or_mock=false`;
- política `public_domain_information_policy=retained_exactly`.

Una fuente que desaparece genera tombstone/sighting; no borra la última versión. Una
corrección del origen crea una observación/version nueva. La publicación selecciona
versión vigente mediante regla documentada.

## 11. Resolución de actores

Orden de fuerza:

1. identificador oficial idéntico y namespace compatible;
2. mapping oficial publicado;
3. decisión humana revisada con evidencia;
4. occurrence source-scoped sin merge.

No basta nombre normalizado, dirección, dominio web ni similitud. Los identificadores
de personas y empresas publicados oficialmente se conservan. La clasificación
`person`/`organization` puede quedar `unknown`; no altera la etiqueta ni el ID fuente.

Cada merge conserva aliases, IDs previos, método, reviewer, fecha y posibilidad de
split. Toda vista histórica usa el estado de resolución correspondiente al release.

## 12. Reconciliaciones obligatorias

Por ingest/corte:

- source records vistos = cargados + rechazados explicados;
- items emitidos por kind y amount semantics;
- awards emitidos = resultados elegibles de la versión seleccionada;
- cada item tiene al menos un evidence row primario;
- cada actor row conserva label exacto y, si existía, identifier exacto;
- suma Decimal por currency/semantics coincide con la fuente elegible;
- `PRAGMA foreign_key_check` vacío e `integrity_check=ok`;
- replay sin cambio produce mismos IDs, filas y artifact hash;
- `NULL`, cero, importe negativo y reembolso se contabilizan por separado;
- duplicados/superseded/tombstones se informan, no se ocultan.

## 13. Contrato de publicación a millones

- Manifest pequeño con schema, release ID, counts, hashes y particiones.
- Particiones por `source_id / spending_kind / year / stable bucket`.
- JSON de UI deliberadamente bounded; Parquet/API para corpus completo.
- Cursor seek por `(source_id, year, spending_item_id)`, nunca `OFFSET` profundo.
- Archivos content-addressed e inmutables; pointer `latest` pequeño.
- Compresión Zstd/Gzip y checksums por fichero.
- Descarga de documentos por queue durable, leases, retry budget, dedupe URL/hash,
  rate limit por host y circuit breaker.
- Raw bytes fuera de SQLite; SQLite conserva hashes, paths relativos y lineage.
- La concurrencia se sube solo tras cohortes `100 -> 1k -> 10k -> 100k` verdes.
- Ninguna muestra se presenta como representativa ni como cobertura histórica total.

Gates de escala:

| Gate | Requisito |
|---|---|
| `S0` | un source record real, item, actor y evidence enlazados |
| `S1` | `100k` money facts reales, reconcile exacto y publicación particionada |
| `S2` | `1M` facts o documentos, origin durable y clean restore |
| `S3` | historia/versiones, delta entre snapshots y tombstones probados |
| `S4` | joins actor-procedure-payment bounded, SLO y rollback ensayados |

## 14. Reglas de consulta pública

Toda respuesta monetaria muestra:

- kind y amount semantics legibles;
- importe y currency sin redondeo engañoso;
- autoridad/pagador y proveedor/beneficiario tal como aparecen;
- fechas con etiqueta precisa;
- fuente y evidencia directa;
- estado de captura documental;
- caveat de fase (`adjudicado`, `contratado`, `pagado`, etc.);
- cobertura temporal/geográfica y fecha de snapshot.

Prohibido:

- titular “pagó” si solo existe award;
- llamar “beneficiario final” a un adjudicatario;
- inferir corrupción, favoritismo o ilegalidad por importe, repetición o red;
- atribuir el gasto a un cargo político sin competencia/rol temporal documentado;
- publicar un ranking sin denominador, versión, caveats y evidence links;
- ocultar public-domain identities para mejorar una métrica de privacidad.

## 15. Detección de riesgo y revisión humana

Señales como concentración, fraccionamiento aparente, baja concurrencia, sobrecoste o
red repetida son colas de revisión, no findings. Cada señal declara:

- regla y versión;
- población elegible y denominador;
- inputs exactos y evidence links;
- threshold y sensibilidad;
- falsos positivos conocidos;
- `corruption_finding=false` por defecto;
- doble revisión y right-of-reply antes de cualquier publicación nominativa como
  señal editorial.

Los datos fuente nominativos permanecen públicos aunque una señal derivada siga
interna o sea rechazada.

## 16. Edge cases abiertos

1. Expedientes re-publicados con distinto ID o URL.
2. Lotes sin ID estable y varios awards en una misma entry.
3. UTEs, consorcios y proveedores múltiples con reparto no publicado.
4. NIF enmascarado, extranjero, temporal o con scheme ausente.
5. Persona física frente a autónomo/empresa sin clasificación fiable.
6. Desiertos, renuncias, anulaciones, recursos y retroacciones.
7. Acuerdos marco, sistemas dinámicos y contratos basados.
8. Prórrogas y modificaciones que cambian duración pero no importe.
9. Importes con/sin IVA, payable amount y valor estimado mezclados por origen.
10. Moneda no EUR, tipo de cambio y fecha de conversión.
11. Importes negativos, reintegros y compensaciones.
12. Facturas rectificativas, pagos parciales y pagos agregados.
13. Cesión de contrato, subcontratación y titular real no publicado.
14. Territorio del órgano, prestación y beneficiario diferentes.
15. Presupuesto plurianual frente a anualidades y ejecución acumulada.
16. Datos eliminados del origen entre snapshots sin tombstone explícito.
17. Documento enlazado pero bytes bloqueados, expirados o mutados.
18. Fechas sin timezone o con solo mes/año.
19. Duplicados entre PLACSP y plataformas autonómicas.
20. Relación política/responsabilidad institucional que cambia durante el expediente.

Cada caso queda source-scoped y explícito hasta disponer de regla validada. Ninguno
autoriza completar datos por intuición.

## 17. Definition of Done de un conector

Un conector de gasto está DONE solo si:

1. usa una fuente oficial real y fija URL/hash;
2. captura raw/version lineage sin secretos ni paths locales;
3. emite IDs deterministas e idempotentes;
4. separa fases e importes correctamente;
5. conserva identidad pública exacta;
6. enlaza cada item a actor y evidence;
7. reconcilia counts e importes elegibles con Decimal;
8. pasa FK/integrity, replay y real-data-only gates;
9. publica muestra bounded y artefacto machine-readable;
10. documenta cobertura, exclusiones y `cannot answer yet`;
11. ofrece consulta reproducible actor -> item -> evidencia;
12. si afirma publicación, verifica la ruta live o registra blocker.

## 18. Estado actual y siguiente paso

Ahora:

- PLACSP H1 2025 contiene `330,577` versiones de registros, `262,558` versiones
  de resultados de adjudicación y `3,190,620` referencias documentales oficiales.
- El artifact analítico PLACSP v5 publica notices y awards separados; los importes
  nunca se etiquetan como pagos.
- BDNS ya supera un millón de concesiones reales y conserva identidad pública.
- Falta una capa canónica común que permita navegar actor -> item -> evidencia sin
  conocer cada tabla fuente.

Vamos a:

- materializar un primer corte PLACSP en las tablas canónicas de esta spec;
- publicar una muestra determinista y bounded de adjudicaciones reales;
- exponer autoridad y proveedor exactos, importe, fecha y evidencia oficial;
- validar replay, sums, hashes, FK, integridad y ausencia de datos inventados.

Siguiente después de ese corte:

- materializar el corpus PLACSP completo por particiones;
- conectar contratos, invoices/payments y delivery solo cuando existan fuentes que
  prueben cada fase;
- integrar presupuesto y ejecución;
- resolver actores con historia revisada;
- publicar dossiers de dinero con cobertura y gaps explícitos.
