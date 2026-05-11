# Arquitectura de librerias reutilizables

Status: `draft`
Updated: `2026-05-09`

Este documento traduce el objetivo de `ROADMAP.md` a limites de paquete. Define que puede salir como libreria abierta, que debe quedarse en Vota con La Chola, que fuentes externas existen hoy, que pasos de proceso ya estamos ejecutando y que primer slice de codigo ya fue extraido.

Installability: root `pyproject.toml` packages only `publicdata_*` namespaces. Vota app/ETL wrappers (`etl/*`, `scripts/*`, `ui/*`) are excluded so another OSS project can install the reusable libraries without importing product code.

## Direccion

Vota con La Chola debe quedar como producto + orquestador:
- UI publica y Explorer.
- Prioridades, copy, marca, preguntas ciudadanas y presets.
- Recetas `just`, publicacion de snapshots del proyecto y operaciones de despliegue.
- Seeds/editorial propios: taxonomias, concerns, casos, explicadores, metodologia de producto.

La logica generica debe salir en librerias:
- contratos de fuente y conectores,
- fetch/retry/raw/provenance,
- parsers y normalizadores,
- modelos SQLite/Parquet/JSON de evidencia publica,
- extraccion de documentos,
- quality gates,
- publicacion de snapshots con licencias y privacidad.

Regla: librerias publican codigo y contratos. Datos siguen como snapshots independientes con metadatos de licencia por `source_id`.

## Cinco pasos canonicos

Todo workflow reutilizable debe caber en cinco pasos:

1. **Register**: declarar fuente, licencia, formato, endpoint, guardrails y fallback.
2. **Acquire**: descargar, reintentar, capturar raw, calcular hash, guardar run/fetch metadata.
3. **Normalize**: convertir payloads a entidades canonicas con IDs estables y raw traceable.
4. **Enrich**: enlazar, extraer texto, clasificar, revisar, medir calidad y dejar incertidumbre explicita.
5. **Publish**: emitir SQLite/JSON/Parquet/API/static snapshots con privacidad, licencias y freshness.

Cada dominio puede tener runtime distinto, pero no mas pasos conceptuales.

## Runtime shapes

Mismo workflow, distintas formas de ejecutar:

- **Network strict**: HTTP directo, aborta con HTML inesperado, `records_loaded` minimo y FK check.
- **Sample replay**: fixture determinista desde `etl/data/raw/samples/*` para tests y CI.
- **Manual replay**: directorio local de capturas cuando upstream bloquea red reproducible.
- **Browser-assisted**: Playwright/headful/cookie profile cuando hay WAF y hay palanca aprobada.
- **Archive fallback**: Wayback/direct variants para documentos historicos con 404/403/500.
- **Queue runtime**: `source_scrape_queue` ordena dependencias, normaliza comandos, valida run result.
- **Static publish**: exports bounded para UI, HF/Parquet, Cloudflare/static bundle.

## Paquetes propuestos

| Paquete | Extrae de | Responsabilidad generica | Se queda fuera |
| --- | --- | --- | --- |
| `publicdata-core` | `etl/*/types.py`, `etl/*/http.py`, `etl/*/raw.py`, `etl/politicos_es/fetch.py`, `etl/politicos_es/util.py` | contratos `Source`, `Connector`, `Extracted`, fetch strict, hash, raw path, stable JSON, retry policy | nombres Vota, rutas `ui/*`, seeds del producto |
| `publicdata-sqlite` | `etl/load/sqlite_schema.sql`, `etl/politicos_es/db.py`, `etl/parlamentario_es/db.py`, `etl/infoelectoral_es/db.py` | schema modular, migrations aditivas, provenance tables, FK gates, upsert helpers | tablas puramente UI/casos si no son evidencia reusable |
| `publicdata-connectors-es` | `etl/politicos_es/connectors/*`, `etl/parlamentario_es/connectors/*`, `etl/infoelectoral_es/connectors/*` | conectores oficiales de Espana/UE con samples, guardrails, source registry | priorizacion electoral/producto Vota |
| `publicdata-docs` | `etl/parlamentario_es/text_documents.py`, scripts `backfill_initiative_doc_*`, `export_text_extraction_queue.py`, `export_pdf_analysis_queue.py` | fetch/extract PDF/HTML, archive fallback, excerpting, doc fetch status | interpretacion politica final |
| `publicdata-evidence` | `etl/parlamentario_es/linking.py`, `topic_analytics.py`, `declared_stance.py`, `declared_positions.py`, `combined_positions.py`, review helpers | linking evidence, topic evidence, stance/position aggregation, review queues | topic copy, citizen pack priorities |
| `publicdata-policy-es` | `etl/politicos_es/policy_events.py`, `government_org.py`, `indicator_backfill.py`, sanction/liberty import/report scripts where generic | policy events, instruments, org graph, money/legal/outcome harmonization | Vota-specific explainers and public copy |
| `publicdata-publish` | `etl/*/publish.py`, `scripts/publicar_*`, `scripts/export_*_snapshot.py`, `scripts/check_public_privacy_leaks.py` | JSON/Parquet snapshot builders, HF publisher, privacy gate, freshness metadata | Cloudflare app composition and UI routes |
| `publicdata-ops` | `etl/ops/source_scrape_queue.py`, `etl/integrations/*`, tracker/report scripts with no product coupling | run queue, integrations, dashboards data, blocker evidence contracts | sprint naming and Vota-specific reports |

Extraction order should follow dependency order: core -> sqlite -> connectors -> docs/evidence -> publish/ops.

## Current external sources

Configured sources from `etl/politicos_es/config.py`, `etl/parlamentario_es/config.py`, and `etl/infoelectoral_es/config.py`.

| Source ID | Family | Scope | Format | Host/manifest | Status |
| --- | --- | --- | --- | --- | --- |
| `congreso_diputados` | representantes/accion/outcomes | nacional | json | www.congreso.es | packaged connector |
| `cortes_aragon_diputados` | representantes/accion/outcomes | autonomico | json | www.cortesaragon.es | packaged connector |
| `senado_senadores` | representantes/accion/outcomes | nacional | xml | www.senado.es | packaged connector |
| `europarl_meps` | representantes/accion/outcomes | europeo | xml | www.europarl.europa.eu | packaged connector |
| `municipal_concejales` | representantes/accion/outcomes | municipal | xlsx | concejales.redsara.es | packaged connector |
| `asamblea_madrid_ocupaciones` | representantes/accion/outcomes | autonomico | csv | ctyp.asambleamadrid.es | packaged connector |
| `asamblea_ceuta_diputados` | representantes/accion/outcomes | autonomico | json | www.ceuta.es | packaged connector |
| `asamblea_melilla_diputados` | representantes/accion/outcomes | autonomico | json | sede.melilla.es | packaged connector |
| `asamblea_extremadura_diputados` | representantes/accion/outcomes | autonomico | json | www.asambleaex.es | packaged connector |
| `asamblea_murcia_diputados` | representantes/accion/outcomes | autonomico | json | www.asambleamurcia.es | packaged connector |
| `jgpa_diputados` | representantes/accion/outcomes | autonomico | json | www.jgpa.es | packaged connector |
| `parlamento_canarias_diputados` | representantes/accion/outcomes | autonomico | json | parcan.es | packaged connector |
| `parlamento_cantabria_diputados` | representantes/accion/outcomes | autonomico | json | parlamento-cantabria.es | packaged connector |
| `parlament_balears_diputats` | representantes/accion/outcomes | autonomico | json | www.parlamentib.es | packaged connector |
| `parlamento_larioja_diputados` | representantes/accion/outcomes | autonomico | json | adminweb.parlamento-larioja.org | packaged connector |
| `parlament_catalunya_diputats` | representantes/accion/outcomes | autonomico | json | www.parlament.cat | packaged connector |
| `corts_valencianes_diputats` | representantes/accion/outcomes | autonomico | json | www.cortsvalencianes.es | packaged connector |
| `cortes_clm_diputados` | representantes/accion/outcomes | autonomico | json | www.cortesclm.es | packaged connector |
| `cortes_cyl_procuradores` | representantes/accion/outcomes | autonomico | json | www.ccyl.es | packaged connector |
| `parlamento_andalucia_diputados` | representantes/accion/outcomes | autonomico | json | www.parlamentodeandalucia.es | packaged connector |
| `parlamento_vasco_parlamentarios` | representantes/accion/outcomes | autonomico | json | www.legebiltzarra.eus | packaged connector |
| `parlamento_galicia_deputados` | representantes/accion/outcomes | autonomico | json | www.parlamentodegalicia.gal | packaged connector |
| `parlamento_navarra_parlamentarios_forales` | representantes/accion/outcomes | autonomico | json | parlamentodenavarra.es | packaged connector |
| `boe_api_legal` | representantes/accion/outcomes | legal | xml | www.boe.es | packaged connector |
| `moncloa_referencias` | representantes/accion/outcomes | ejecutivo | html | www.lamoncloa.gob.es | packaged connector |
| `moncloa_rss_referencias` | representantes/accion/outcomes | ejecutivo | xml | www.lamoncloa.gob.es | packaged connector |
| `dir3_unidades_age` | representantes/accion/outcomes | organigrama | xlsx | administracionelectronica.gob.es | packaged connector |
| `placsp_sindicacion` | representantes/accion/outcomes | dinero | xml | contrataciondelestado.es | packaged connector |
| `placsp_autonomico` | representantes/accion/outcomes | dinero | xml | contrataciondelestado.es | packaged connector |
| `bdns_api_subvenciones` | representantes/accion/outcomes | dinero | json | www.pap.hacienda.gob.es | packaged connector |
| `bdns_autonomico` | representantes/accion/outcomes | dinero | json | www.pap.hacienda.gob.es | packaged connector |
| `placsp_contratacion` | representantes/accion/outcomes | dinero | json | contrataciondelestado.es | configured, no connector registered |
| `bdns_subvenciones` | representantes/accion/outcomes | dinero | json | www.pap.hacienda.gob.es | configured, no connector registered |
| `eurostat_sdmx` | representantes/accion/outcomes | outcomes | json | ec.europa.eu | packaged connector |
| `bde_series_api` | representantes/accion/outcomes | outcomes | json | app.bde.es | packaged connector |
| `aemet_opendata_series` | representantes/accion/outcomes | outcomes | json | opendata.aemet.es | packaged connector |
| `ree_esios_indicators` | representantes/accion/outcomes | outcomes | json | apidatos.ree.es | packaged connector |
| `congreso_votaciones` | parlamentario | nacional | html | www.congreso.es | packaged connector |
| `senado_votaciones` | parlamentario | nacional | html | www.senado.es | packaged connector |
| `senado_iniciativas` | parlamentario | nacional | xml | www.senado.es | packaged connector |
| `congreso_iniciativas` | parlamentario | nacional | html | www.congreso.es | packaged connector |
| `congreso_intervenciones` | parlamentario | nacional | html | www.congreso.es | packaged connector |
| `programas_partidos` | parlamentario | nacional | csv | manifest://programas_partidos | packaged connector |
| `parl_initiative_docs` | parlamentario | nacional | bin | manifest://parl_initiative_docs | derived/backfill source, no connector registered |
| `infoelectoral_descargas` | electoral | electoral | json | infoelectoral.interior.gob.es | packaged connector |
| `infoelectoral_procesos` | electoral | electoral | json | infoelectoral.interior.gob.es | packaged connector |

## Processing inventory

| Layer | Current modules/scripts | Generic output |
| --- | --- | --- |
| Source registry | `SOURCE_CONFIG`, `registry.py`, `docs/etl/e2e-scrape-load-tracker.md` | source metadata contract, blocker metadata, license/freshness manifest |
| Fetch/raw/provenance | `fetch.py`, `http.py`, `raw.py`, `raw_fetches`, `run_fetches`, `source_records`, `ingestion_runs` | reproducible acquisition ledger |
| Parse | `parsers.py`, connector-local parsers | typed record streams from JSON/XML/CSV/XLSX/HTML/PDF |
| Normalize/upsert | `pipeline.py`, `db.py`, `sqlite_schema.sql` | stable IDs, FK-safe SQLite model, raw payload traceability |
| Identity/mandates | `persons`, `parties`, `institutions`, `mandates`, `territories`, `roles`, `genders` | reusable public-official identity graph |
| Parliamentary linking | `linking.py`, `backfill-member-ids`, `link-votes` | vote -> person -> initiative evidence graph |
| Document acquisition | `text_documents.py`, `document_fetches`, `text_documents`, initiative doc scripts | document fetch/extract state machine |
| Text extraction | `backfill_initiative_doc_extractions.py`, `backfill_initiative_text_versions.py`, PDF/HTML helpers | text versions, excerpts, review flags |
| Semantic enrichment | `topic_analytics.py`, `declared_stance.py`, `declared_positions.py`, `combined_positions.py` | topic evidence, positions, uncertainty |
| Human review | `review_queue.py`, `initdoc_review.py`, `apply_*_reviews.py`, MTurk skill queue | bounded review tasks and adjudicated decisions |
| Policy/action modeling | `policy_events.py`, `government_org.py`, `indicator_backfill.py`, seed imports | policy events, instruments, org units, indicators |
| Quality gates | `quality.py`, `report_*`, `validate_*`, `etl-tracker-gate` | measurable gates and public blocker evidence |
| Publish | `publish.py`, `publicar_*`, `export_*_snapshot.py`, `publicar_hf_snapshot.py` | JSON/Parquet/HF/static snapshots with privacy checks |
| Product/UI | `scripts/graph_ui_server.py`, `ui/graph/*`, `ui/citizen/*`, `ui/gh-pages-next/*` | stays in Vota; consumes library outputs |

## Workflow contracts

### Representatives

1. Register source and minimum strict load.
2. Fetch raw payload or replay sample/manual capture.
3. Normalize person, institution, party, role, territory, mandate.
4. Enforce FK/idempotence and close missing mandates.
5. Publish representative snapshot and Explorer data.

### Parliamentary evidence

1. Register vote/initiative/intervention/program source.
2. Ingest events and raw source records.
3. Link members, initiatives and documents.
4. Extract text, classify topics/stances, route review queue.
5. Publish vote/evidence/position snapshots and KPIs.

### Legal, money, outcomes

1. Register source family and effect reliability.
2. Fetch raw official records and details.
3. Normalize to policy events, instruments, org units or indicator series.
4. Link responsibility/context and quality gates.
5. Publish policy/outcome/responsibility snapshots.

### Document recovery

1. Register candidate URLs and prior fetch status.
2. Fetch direct, browser, local file, archive or direct variant.
3. Store bytes/text with source hash and status.
4. Extract canonical subject/excerpt/text version and review flags.
5. Publish coverage deltas and blocker evidence.

## First migration slice

Do not big-bang split. First slice should produce a reusable package with no product dependency:

1. Create `publicdata_core` with contracts, util, fetch/raw, `Extracted`, `BaseConnector`, strict payload validation.
2. Move one simple connector family behind the new contract, preferably `infoelectoral_es` because it has two JSON sources and small blast radius.
3. Keep Vota CLI wrappers importing the package, preserving current commands and DB paths.
4. Add sample replay tests for package and Vota wrapper.
5. Run `just etl-smoke-e2e`, source-specific sample tests, and `just privacy-check-public-artifacts` before any publish claim.

Exit gate for first slice:
- no UI changes required,
- existing source IDs unchanged,
- sample replay green,
- Vota app still orchestrates same workflow,
- package README explains how another OSS project can register a source and ingest to SQLite without Vota UI.

Current implementation note:
- `publicdata_core/` exists as the first in-repo package boundary for contracts, five-step workflow plans, fetch/raw/http, parser primitives and stable utility helpers.
- `publicdata_core.sources.SourceDefinition` is the typed source metadata contract; legacy `SOURCE_CONFIG` dicts can be generated from it.
- `publicdata_sqlite/` owns generic DB opening, schema introspection, source seeding, and source-record provenance upserts.
- `publicdata_connectors_es.infoelectoral` owns the reusable Infoelectoral connector family.
- `publicdata_connectors_es.government` owns reusable BOE legal and Moncloa executive feeds.
- `publicdata_connectors_es.money` owns reusable PLACSP contract and BDNS subsidy feeds.
- `publicdata_connectors_es.org` owns reusable Spanish public-organisation connectors, starting with DIR3 AGE units.
- `publicdata_connectors_es.outcomes` owns reusable official indicator-series connectors for Eurostat, BDE, AEMET and REE/ESIOS.
- `publicdata_connectors_es.parliamentary` owns reusable Congreso/Senado evidence feeds and party-program manifests.
- `publicdata_connectors_es.representatives` owns reusable national, European, regional and municipal representative rosters.
- `publicdata_policy_es/` owns reusable Spanish policy-event mapping, government-organisation mapping and indicator harmonization.
- `publicdata_ops/` owns queue dependency ordering and command-template normalization.
- `publicdata_docs/` owns document-recovery helpers: HTTP status normalization, public-safe runtime metadata, Playwright Node runtime fallback, URL canonicalization, dedupe, gzip handling, HTTP error extraction, local XML/HTML/PDF text extraction, deterministic extraction queues and Spanish parliamentary document recovery in `publicdata_docs.parliamentary_es`.
- `publicdata_evidence/` owns reusable evidence quality gates and review-loop mechanics for topic evidence and initiative-document extraction queues, including KPI computation, CSV/Label Studio import-export and adjudication application.
- `publicdata_publish/` owns public artifact privacy scanning, sensitive text redaction, public URL sanitization, generic HF/static snapshot packaging helpers, SQLite schema payload export and Parquet table export.
- Compatibility wrappers now expose the same contracts and fetch/raw/http helpers from `etl/politicos_es/*` and `etl/parlamentario_es/*`, so current CLI imports remain stable while new code can import `publicdata_core` directly.
- `etl/infoelectoral_es/*` keeps DB/CLI orchestration, while connector/config imports are wrappers around the reusable package.

## Extraction status

Done in this slice:
- `pyproject.toml`: installable package metadata for `publicdata_*` libraries only.
- `publicdata_core`: source, connector, fetch/raw/http/parser/workflow primitives.
- `publicdata_sqlite`: DB opening, schema introspection, source seeding and source-record provenance helpers.
- `publicdata_connectors_es`: Infoelectoral, BOE/Moncloa government feeds, PLACSP/BDNS money feeds, DIR3 organisation units, official outcome indicators for Eurostat/BDE/AEMET/REE, parliamentary evidence feeds, and representative rosters.
- `publicdata_policy_es`: BOE/Moncloa/PLACSP/BDNS policy-event mapping, DIR3 government-org mapping and outcome indicator harmonization.
- `publicdata_ops`: queue dependency ordering and command-template normalization.
- `publicdata_docs`: reusable document URL/status/runtime/text-extraction/queue helpers plus Spanish parliamentary document fetch/link/excerpt recovery.
- `publicdata_evidence`: review queue, initiative-document review and parliamentary quality-gate mechanics.
- `publicdata_publish`: privacy scanning, sensitive text redaction, public URL sanitization and generic HF/static snapshot/Parquet helpers.

Still Vota-bound until next slices:
- higher-level text-version/extraction-review queue scripts that encode Vota-specific initiative-document tables,
- concrete HF dataset orchestration, source legal-profile mapping, README copy and UI bundle assembly,
- product/editorial assets: concerns, citizen packs, copy, route structure and Explorer UI.

Next extraction slice should stay within five steps:
1. Move one source family into a reusable package.
2. Keep the old Vota module as a wrapper.
3. Preserve source IDs, samples and strict-network behavior.
4. Add package-level tests plus wrapper identity tests.
5. Run smoke, privacy and hygiene gates before claiming done.

## Open decisions

- Package names: internal namespace first, PyPI name later.
- Schema split: one monolithic SQL file can remain in Vota until `publicdata-sqlite` has additive migration tests.
- Licenses: package code MIT; data snapshots keep per-source license metadata.
- Connector ownership: generic source connectors should live outside Vota once contracts stabilize; Vota keeps source priority and publication cadence.
- Review workflows: generic queue/adjudication belongs in library, political meaning/copy stays in Vota.
