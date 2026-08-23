# Plugin system v1

Estado: `v1 estable para manifest, lifecycle y compatibilidad; runtime registry incremental`

Fecha: `2026-08-19`

Contrato base: `docs/data-model/core-ontology-v1.md`

Schema del manifest: `docs/architecture/plugin-manifest-v1.schema.json`

## 1. Objetivo

Permitir que una persona contribuya una fuente, parser, extractor, linker, scorer o
publisher sin conocer todo el monolito ni cambiar rutas de producto. Un plugin debe
declarar exactamente qué consume, qué produce, cómo conserva procedencia, cómo
reintenta, cómo se particiona y qué gates prueban su salida con datos oficiales reales.

El sistema no crea una segunda ETL. Formaliza límites que ya existen en:

- `publicdata_core.BaseConnector`, `Extracted`, `SourceDefinition` y `WorkflowPlan`;
- `publicdata_connectors_es` y sus familias;
- `pipeline_work_items` / `pipeline_work_attempts`;
- `scripts/add_source.py` y el registry de capturas oficiales;
- normalizadores SQLite, extractores, linkers, review queues y publicadores actuales.

## 2. Estado actual, dirección y siguiente paso

### Ahora

- Existe un contrato mínimo de connector: `resolve_url()` + `extract()`.
- `Extracted` materializa payload, hash, URL, hora, ruta raw y records.
- `SourceDefinition` tipa metadata fuente y mantiene compatibilidad con
  `SOURCE_CONFIG`.
- El workflow común ya tiene cinco pasos: register, acquire, normalize, enrich,
  publish.
- Las familias reutilizables viven bajo `publicdata_*`; Vota conserva orquestación,
  DB, cadencia, UI y decisiones editoriales.
- El onboarding crea parser, captura oficial exacta, sidecar de procedencia, test y
  docs. La captura no puede ser synthetic, mock o placeholder.
- Todavía hay branching por `source_id`, registries manuales, interfaces implícitas
  para normalizers/linkers/publishers y gates no declarados en un manifest común.

### Dirección

- Un manifest v1 describe capacidades e invariantes; el registry carga solo plugins
  instalados y allowlisted.
- Los hooks reciben contextos tipados, referencias pequeñas y stores explícitos.
- Los bytes van a CAS; los facts masivos a partitions; SQLite mantiene control plane.
- Los plugins son deterministas o declaran su nondeterminism, modelos, prompts,
  seeds y review requirement.
- La compatibilidad se negocia antes de ejecutar.
- Ningún plugin puede rebajar real-only, identidad oficial pública, procedencia,
  uncertainty, publicación o allegation policy.

### Siguiente

`TODO 15` ya implementó el SDK mínimo y un plugin Congreso sobre una captura oficial
real, preservando URL, bytes, SHA-256, filas, comandos, IDs source-scoped e identidad
pública. `TODO 16` debe firmar manifests de snapshot, producir diffs verificables y
probar que el artifact publicado coincide con el build. No se usará dataset inventado
ni se usarán datos sintéticos, mock o placeholder.

## 3. Frontera de plugin

Un plugin es un paquete Python instalable o módulo in-repo con:

1. `plugin.json` conforme a `plugin_manifest_v1`;
2. entry point Python declarado;
3. uno o más tipos de capacidad;
4. tests sobre captura oficial exacta o corpus real;
5. documentación de fuente, derechos, comandos y limitaciones;
6. ownership y policy de versiones.

El manifest contiene metadata, nunca secrets ni cookies. El código del plugin no
decide qué se publica como acusación ni qué fuente es prioridad editorial.

### Se queda en el core

- loader/registry y resolución de compatibilidad;
- runtime context, queue, leases, CAS y DB transaction boundary;
- IDs y tipos de la core ontology;
- source record/version envelope;
- gates de real-only, provenance, identity, FK, publication hygiene y restore;
- error taxonomy, metrics y audit log;
- autorización de red, secrets y destinos de publicación.

### Puede vivir en plugins

- discovery específico del origen;
- adquisición HTTP/API/archive respetando runtime;
- parsing de formatos;
- normalización de campos de dominio;
- extracción de texto/claims/evidence;
- propuestas de linking;
- cálculo de señales o scores reproducibles;
- export de un contrato público versionado.

### Nunca vive solo en un plugin

- credenciales embebidas;
- supresión de identidad oficial pública;
- borrado de raw/history;
- decisión final de merge de identidad sin evidence/review;
- publicación automática de una señal como corrupción/ilegalidad;
- cambio incompatible del ontology/API sin versión mayor.

## 4. Tipos de plugin

Un paquete puede declarar varios tipos, pero cada hook conserva su contrato.

### 4.1 Connector

Descubre unidades de trabajo y adquiere bytes oficiales.

Responsabilidades:

- declarar fuentes/endpoints y rights basis;
- `plan`/`discover` con paginación o particiones acotadas;
- URL canonicalization y dedup;
- rate limit, retry y Retry-After;
- captura exacta, hash, content type, bytes y transport security;
- checkpoint/restart sin saltar registros;
- error claro ante WAF, 403/429, HTML inesperado o contrato roto.

No normaliza semántica política compleja. La compatibilidad legacy adapta
`BaseConnector.resolve_url/extract` a `discover/acquire`.

### 4.2 Parser

Convierte un immutable acquired artifact en source records.

Contrato:

- input bytes + artifact metadata;
- output iterator/stream de `SourceRecordEnvelope`;
- natural source record ID o source-scoped ordinal estable;
- raw record bytes/text o fingerprint exacto;
- parse warnings/errors con locator;
- sin red, DB writes ni side effects.

Un parser no descarta un campo personal oficial por clasificación o comodidad.

### 4.3 Normalizer

Convierte source records en facts de core ontology o tablas de dominio.

Contrato:

- batch input, no lookup N+1;
- declared concept outputs y natural keys;
- source record/evidence links por fact;
- valid/occurred/published/observed times separados;
- unknown states explícitos;
- batch upserts y additive schema compatibility.

Aunque TODO enumera seis tipos, `normalizer` es first-class porque separa parsing de
persistencia semántica.

### 4.4 Extractor

Deriva text fragments, evidence, claims, topics u otros objetos desde documents.

Contrato:

- input document version/hash;
- output con exact locator y fragment hash;
- extractor name/version;
- OCR/text quality y truncation;
- confidence/review state;
- replay determinista para mismos bytes/version.

### 4.5 Linker

Propone relaciones entre objetos existentes.

Contrato:

- source/target public IDs y kinds;
- relation code de ontology;
- evidence IDs;
- method/version, confidence y alternatives;
- decision state: `proposed`, `confirmed`, `rejected`, `superseded`;
- nunca merge destructivo ni identity-by-name.

### 4.6 Scorer

Calcula aggregate, position, anomaly o review-priority signal.

Contrato:

- input snapshot/partition IDs y hashes;
- method/version/parameters;
- numerator, denominator, coverage, unknowns y uncertainty;
- output reproducible y bounded;
- counterevidence/correction hooks;
- claim language separado del score.

Un scorer produce señales. No produce hallazgos legales ni acusaciones personales.

### 4.7 Publisher

Emite artifacts públicos o internos versionados.

Contrato:

- input manifests inmutables;
- JSON bounded, Parquet partitioned, SQLite snapshot o static/API shard;
- schema version, generated/snapshot dates, hashes, row/file/byte counts;
- source rights, provenance coverage, freshness y gaps;
- real-only and publication-hygiene gates;
- durable origin + restore verification cuando claim de publicación lo requiere.

No envía millones de rows como un único JSON al browser.

## 5. Lifecycle

El lifecycle detallado cabe dentro de los cinco pasos canónicos.

| Hook | Paso | Input | Output | Side effects permitidos |
|---|---|---|---|---|
| `register` | register | manifest + registry context | registered plugin/source descriptors | registry local |
| `validate_config` | register | resolved non-secret config | validation report | ninguno |
| `plan` | acquire | source + snapshot + cursor | bounded work refs | checkpoint plan |
| `discover` | acquire | partition/cursor | work refs + next cursor | queue enqueue por runtime |
| `acquire` | acquire | work ref | acquired artifact ref | network + CAS + fetch ledger |
| `parse` | normalize | artifact ref/read-only bytes | source record stream | ninguno |
| `normalize` | normalize | source record batch | fact batches | transaction-scoped writes |
| `extract` | enrich | document/fact refs | evidence/claim batches | CAS derived text + DB batch |
| `link` | enrich | bounded entity/fact windows | relationship proposals | proposal/review tables |
| `score` | enrich | immutable input manifest | derived signal partitions | derived store only |
| `validate` | enrich/publish | run/partition manifest | gate report | report write |
| `publish` | publish | validated immutable manifests | artifact manifest | approved destination only |
| `checkpoint` | cualquier | cursor/counters/state | durable checkpoint | control-plane write |
| `cleanup` | cualquier | expired lease/temp refs | cleanup report | temp scope only |

Orden normal:

`register -> validate_config -> plan -> discover -> acquire -> parse -> normalize -> extract/link/score -> validate -> publish`

Hooks no aplicables se omiten. `validate` nunca se omite antes de `publish`.

## 6. Contextos y envelopes

### PluginContext

Solo capabilities explícitas:

- `run_id`, `pipeline_id`, `snapshot_date`, `partition_key`;
- logger estructurado y metrics sink;
- read-only plugin config;
- secret handles por nombre, no valores serializados;
- HTTP client con timeout/retry/rate policy;
- CAS interface;
- queue/checkpoint interface;
- transaction factory o batch writer autorizado;
- cancellation/deadline signal;
- resource budget.

No se entrega acceso global al filesystem, entorno completo o conexión de publicación.

### WorkItemRef

- `plugin_id`, `pipeline_id`, `item_key`, `partition_key`;
- source ID/URL o opaque cursor;
- priority, available time y attempt limit;
- payload de referencias pequeño;
- idempotency key.

Nunca contiene bytes grandes, cookies o tokens.

### AcquiredArtifact

Compatible con `publicdata_core.Extracted`, pero separa bytes de records:

- source/resolved URL;
- fetched/observed time;
- content SHA-256, MIME, bytes, CAS key;
- transport security y HTTP metadata safe;
- source snapshot/partition/work item;
- no parsed records embebidos en el contrato v1 nuevo.

### SourceRecordEnvelope

- source ID, native ID, version fingerprint;
- observed/snapshot/published times;
- artifact hash/CAS ref y locator/ordinal;
- exact raw record representation o reference;
- tombstone flag;
- parser/version and warnings.

### FactBatch

- ontology concept/table contract;
- schema version;
- partition key;
- rows con stable public IDs/natural keys;
- source-record/evidence links;
- row count, logical hash and reject report.

### EvidenceBatch / LinkProposal / ScoreBatch

Todos declaran input manifest hashes, method/version, coverage, uncertainty, output
partition y evidence links. `LinkProposal` añade alternatives/review state.

### ArtifactManifest

- immutable release/artifact ID;
- plugin and contract versions;
- input/output hashes;
- partitions/files/rows/bytes;
- source/identity/evidence coverage;
- validation reports;
- durable origin and restore status;
- generated/snapshot times and caveats.

## 7. Manifest v1

Campos top-level obligatorios:

- `schema_version = plugin_manifest_v1`;
- `plugin_id`: reverse-DNS lowercase estable;
- `name`, `version`, `description`, `license`;
- `entry_point = module:object`;
- `plugin_types`;
- `maintainers` con owner handle, nunca email privado requerido;
- `compatibility`;
- `sources`;
- `capabilities` y `hooks`;
- `inputs`, `outputs`;
- `runtime`, `partitions`, `idempotency`, `provenance`;
- `quality_gates`, `test_hooks`, `security`, `publication`.

### Source declarations

Cada source:

- `source_id`, `name`, `source_kind`, `scope`;
- `official_base_urls` HTTPS o schemes internos aprobados para manifests;
- formatos/MIME;
- rights basis;
- expected update cadence;
- strict minimum o explicit full-universe rule;
- official capture paths + SHA sidecars para test hooks;
- `official_public_domain_personal_information_retained = true`;
- `synthetic_or_mock_data = false`;
- `implicit_fallback = false`.

### Compatibility

- `plugin_api`: rango SemVer compatible;
- `core_ontology`: major exacto/rango compatible;
- `python`: specifier;
- `sqlite_schema`: min/current compatibility level;
- input/output schema versions;
- optional features.

### Outputs

Cada output declara:

- ontology concept;
- contract/schema version;
- storage kind;
- natural key fields;
- partition fields;
- public ID field;
- provenance mode;
- boundedness/publication class.

## 8. Discovery y registry

### In-repo

- El registry lee manifests desde paths allowlisted.
- Orden determinista por `plugin_id`.
- Duplicate ID/version o source ownership ambiguo: fail.
- Entry point se importa después de validar manifest/compatibilidad.

### Instalable

Entry-point group futuro:

`vclc.publicdata.plugins`

La distribución expone una función que devuelve ruta al manifest, no un objeto ya
ejecutado. El loader valida el JSON antes de importar código.

### Seguridad

- Instalar un plugin equivale a instalar código. Requiere maintainer review.
- No existe auto-install desde manifest, URL o dataset.
- No se ejecuta código remoto descargado por el connector.
- Allowed hosts, methods, filesystem roots y secret names se declaran.
- El runtime puede negar capabilities aunque el manifest las solicite.

## 9. Configuración y secrets

Precedencia:

1. defaults no sensibles del manifest;
2. config de proyecto versionada;
3. overrides CLI/run;
4. secret handles inyectados por runtime.

El manifest declara `required_secret_names`, nunca values. Config efectiva se
redacta antes de logs/checkpoints. URLs con userinfo o query credentials fallan.

Todo override que cambia source scope, natural key, partitioning o output contract
forma parte del run manifest.

## 10. Ejecución y escala

### Delivery semantics

La queue ofrece at-least-once. El efecto es exactly-once lógico mediante:

- `UNIQUE(plugin_id, pipeline_id, item_key)`;
- artifact dedup por content hash;
- source record versions/fingerprints;
- natural keys;
- transactional batch commit;
- immutable output partitions y atomic manifest pointer update.

### Boundedness

Todo hook declara:

- max input/output batch rows;
- estimated bytes and memory;
- timeout;
- concurrency/rate limits;
- partition/cursor behavior;
- checkpoint interval.

Prohibido `list(all_records)` sobre universos no acotados. Parse/normalize/publication
usan iterators, batches o partition readers.

### Backpressure

- queue depth high watermark;
- downstream capacity feedback;
- bounded prefetch;
- worker concurrency por source/host;
- 403/429/error-rate circuit breaker;
- dead-letter after max attempts;
- one strict retry per sprint for blockers without new lever.

### Partición

Plugins declaran keys estables compatibles con core ontology, por ejemplo
source/time/territory/kind. Un cambio de partition strategy es minor si mantiene
logical IDs and compatibility manifest; major si rompe addressability.

### Reconciliation

El run report agrega por source/partition:

- discovered, enqueued, leased, fetched, parsed, normalized, enriched, published;
- duplicate/rejected/retry/dead;
- bytes/objects/rows;
- source URL/record/identity/evidence coverage;
- checksum and logical-row hash;
- FK/orphan/unknown/freshness;
- throughput, RSS, request/error latency and cost.

## 11. Error taxonomy

| Clase | Retry | Estado | Ejemplos |
|---|---|---|---|
| `transient_network` | sí, bounded | retry | timeout, 5xx temporal |
| `rate_limited` | sí, Retry-After | retry | 429 |
| `access_blocked` | no sin nueva palanca | blocked/dead | WAF 403/challenge |
| `not_found` | política source | terminal/recovery | 404 histórico |
| `contract_drift` | no automático | dead | shape/MIME inesperado |
| `parse_error` | solo nueva versión | dead/review | malformed payload |
| `validation_error` | no | dead/review | missing key/FK/provenance |
| `identity_ambiguous` | no | review | posibles matches múltiples |
| `publication_gate` | no | blocked | real-only/privacy/restore fail |
| `cancelled` | no | pending/released | shutdown/deadline |

Un error terminal conserva work item, attempt, payload reference y evidence. Nunca
se convierte silenciosamente en success o en fixture fallback.

## 12. Test hooks

Hooks obligatorios según tipo:

- `contract`: manifest/schema/import/compatibility;
- `official_capture_replay`: bytes exactos registrados, SHA verified;
- `idempotence`: replay dos veces, mismos logical IDs/counts;
- `schema`: output contract + FK/orphan;
- `provenance`: source URL/record/hash/evidence coverage;
- `strict_network`: real endpoint cuando se autoriza; fail-fast ante payload inválido;
- `scale`: representative official corpus, bounded RSS/throughput;
- `publish_dry_run`: manifests/checksums/rights/hygiene;
- `restore`: reconstruct and full-validate published artifact;
- `regression`: correction/tombstone/version behavior.

Test data policy:

- solo captura oficial exacta o subset exacto de registros reales, con URL, fecha,
  bytes, SHA-256 y rights basis;
- no synthetic, mock, invented, placeholder, loopback ni `example.*` como payload;
- transport may be isolated, but bytes and expected facts remain official real data;
- public-domain personal fields remain exact;
- an empty/blocked source stays empty/blocked.

## 13. Quality gates por tipo

### Connector/parser

- official origin allowlist;
- content hash/bytes/MIME;
- strict unexpected-HTML gate;
- minimum/full-universe count;
- record ID/fingerprint coverage;
- replay deterministic.

### Normalizer/extractor/linker

- natural key uniqueness;
- source record/evidence coverage;
- time semantics and unknown states;
- FK/orphan;
- identity ambiguity and review queue;
- extractor/linker version and confidence.

### Scorer

- input manifest pinning;
- denominator/unknown/coverage;
- reproducible parameters;
- counterevidence/correction path;
- allegation-policy language gate.

### Publisher

- schema version, hashes, rows/files/bytes;
- real-only scan;
- secrets/private-session/workstation hygiene;
- identity retention;
- bounded file/JSON budget;
- durable origin and restore when claimed;
- route/asset/evidence audit for public UI.

## 14. Versionado

### Plugin API SemVer

- patch: clarification/bugfix, no interface change;
- minor: additive optional field/hook/capability;
- major: required field, hook signature or semantic change.

### Plugin version

El plugin incrementa:

- patch: parser/fetch fix without logical output change;
- minor: additive source/output/field compatible;
- major: natural key, ID, interpretation or output contract incompatible.

### Data contract version

Separado del package version. Cada artifact declara plugin, ontology, input/output
schema y method versions. Reprocessing old bytes with new parser creates a new
artifact/version, no rewrite invisible.

### Deprecación

- warning mínimo de una minor release;
- replacement/migration documented;
- old public IDs remain resolvable;
- no delete until consumers and restore path migrate;
- incompatible removal only in major.

## 15. Compatibilidad con implementación actual

| Actual | Plugin v1 | Adaptación |
|---|---|---|
| `SourceDefinition` | manifest `sources[]` | lossless mapping + extra policy fields |
| `BaseConnector.resolve_url` | `plan/discover` | one-item adapter |
| `BaseConnector.extract` | `acquire + parse` | legacy adapter may return both |
| `Extracted` | `AcquiredArtifact + SourceRecordEnvelope` | split records from byte acquisition |
| `SOURCE_CONFIG` | registry view | generated compatibility mapping |
| manual connector list | plugin registry | migrate source family by family |
| source-id branches in pipeline | normalizer hooks | adapters until vertical migration |
| `pipeline_work_items` | runtime queue | same lease/idempotency spine |
| `add_source.py` | plugin scaffold | add manifest generation in TODO 15 |
| `etl-contributor-gates` | plugin test hooks | manifest-driven plus global gates |

No source IDs, CLI commands or published schemas change merely by adopting v1.

## 16. Reference Python protocols

Estas firmas son contract shapes, no implementación todavía:

```python
class ConnectorPlugin(Protocol):
    def plan(self, ctx: PluginContext) -> Iterable[WorkItemRef]: ...
    def acquire(self, item: WorkItemRef, ctx: PluginContext) -> AcquiredArtifact: ...

class ParserPlugin(Protocol):
    def parse(self, artifact: AcquiredArtifact, ctx: ReadOnlyContext) -> Iterator[SourceRecordEnvelope]: ...

class NormalizerPlugin(Protocol):
    def normalize(self, records: Sequence[SourceRecordEnvelope], ctx: BatchContext) -> FactBatch: ...

class ExtractorPlugin(Protocol):
    def extract(self, documents: Sequence[DocumentVersionRef], ctx: BatchContext) -> EvidenceBatch: ...

class LinkerPlugin(Protocol):
    def link(self, inputs: LinkWindow, ctx: BatchContext) -> Sequence[LinkProposal]: ...

class ScorerPlugin(Protocol):
    def score(self, inputs: ImmutableManifestRef, ctx: BatchContext) -> ScoreBatch: ...

class PublisherPlugin(Protocol):
    def publish(self, inputs: Sequence[ValidatedManifestRef], ctx: PublishContext) -> ArtifactManifest: ...
```

Runtime validates declared hooks before invoking them. A hook cannot request a
capability absent from the manifest/context.

## 17. Observabilidad

Todos los logs son structured and bounded:

- plugin/version/run/pipeline/work/partition/source IDs;
- lifecycle hook;
- attempt/status/error class;
- rows/bytes/duration/RSS;
- URLs sanitized, no auth/query secrets;
- content hash and checkpoint;
- zero personal-field suppression count where the source publishes identity.

Metrics do not use person names as labels. High-cardinality IDs stay in logs/reports,
not metric dimensions.

## 18. Publication and trust

- Manifest and artifact metadata are public-safe and reproducible.
- Official public personal identity remains in data rows and evidence where the
  source published it.
- Plugin maintainers cannot bypass global publication gates.
- A plugin that detects a risk emits an integrity signal with evidence and review
  state, not a public accusation.
- Corrections, counterevidence, responses and supersessions remain visible.
- A blocked official origin is recorded factually under the Name & Shame protocol.

## 19. Adoption sequence

1. Freeze this doc + manifest schema + validator.
2. TODO 15: implement SDK protocols, loader and one real official reference plugin.
3. Adapt `SourceDefinition`, `BaseConnector` and `Extracted` without breaking callers.
4. Generate compatibility `SOURCE_CONFIG` and connector registry from manifests.
5. Migrate one source family per thin slice; run old/new parity on exact same bytes.
6. Move source-id branching into declared normalizers.
7. Make contributor gates manifest-driven.
8. Add package entry-point discovery after in-repo registry is stable.
9. Expose plugin/output versions in transparency and Evidence API.

Rollback for every migration: retain legacy registry/adapter until byte, count,
logical-ID, provenance and publication parity pass.

## 20. Definition of Done v1

- Connector, parser, extractor, linker, scorer and publisher interfaces defined;
- normalizer explicitly included at parse/semantic boundary;
- manifest schema covers source, ontology outputs, lifecycle, compatibility,
  partitions, idempotency, provenance, resources, security and gates;
- lifecycle hooks map to five canonical workflow steps;
- versioning/deprecation and capability security are explicit;
- at-least-once queue + exactly-once logical effects documented;
- million-scale execution uses bounded batches, partitions, CAS and reconciliation;
- tests require exact official real captures and prohibit mock/synthetic data;
- public-domain personal identity retention is non-overridable;
- current implementation has an additive compatibility path;
- `just plugin-architecture-check` validates the document and schema;
- TODO 15 is the first runtime implementation, not hidden inside this design task.
