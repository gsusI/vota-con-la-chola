# ROADMAP

Status: `canonical`
Updated: `2026-09-07`

Scope boundary: strategic direction, delivery sequence, evidence gates, ownership roles, and societal-scale completion. Operational row status remains in the tracker; near-term commands remain in the technical roadmap.

**Estimation status:** The launch below uses a proposed capacity limit, not a delivery estimate. Societal-scale estimates remain premature while representative source scope, durable raw origin, review operations, release authority, and production infrastructure remain unresolved.

## North Star de producto — propuesta para decisión (2026-09-07)

**Estado: ejecución autorizada para dinero público nacional (2026-09-07).** El mantenedor ordena alcanzar este foco y la North Star. Los umbrales siguientes pasan a ser criterios de aceptación; cumplirlos requiere evidencia, incluida validación externa. Los demás dominios cívicos conservan su visión sin convertirse en frentes simultáneos. Esta sección es la referencia canónica para esa discusión; los mandatos anteriores conservan su historial, pero sus entregas técnicas no acreditan competitividad. Investigación y límites: [referentes por dimensión](docs/producto/referentes-north-star-20260907.md).

**Decisión de infraestructura (2026-09-07):** por instrucción del mantenedor, la API de dinero público migra a un servicio blue/green aislado en el Hetzner existente, gestionado por Ansible. Las consultas dejan de depender de D1. Mantener límites de CPU/RAM/disco, datos inmutables de solo lectura, comprobación de salud antes/después y rollback; no ejecutar adquisición histórica ilimitada en ese servidor compartido. La migración conserva el corpus publicado y no acredita nueva cobertura. Evidencia operativa: [migración Hetzner](docs/etl/sprints/DINERO-NACIONAL-20260907/evidence/hetzner-migration.md).

### Promesa al usuario

**Que cualquier persona pueda entender y comprobar qué hacen las instituciones españolas con el poder y el dinero públicos en los asuntos que le importan: qué prometieron, qué decidieron, quién era responsable, a quién financiaron, qué ejecutaron y qué resultados se conocen; y seguir los cambios desde una misma web.**

España es el universo principal propuesto: Estado, comunidades autónomas y entidades locales; instituciones europeas cuando sus decisiones o fondos afecten al caso. Profundidad histórica nacional y actualidad verificable antes que un contador internacional. La ambición cubre el histórico digital públicamente recuperable de cada fuente, con inicio y lagunas explícitos; no presupone que todo exista desde 1999 ni que todo sea accesible.

Audiencia principal propuesta: ciudadanía que quiere comprender y fiscalizar un asunto concreto. Periodistas, investigadores y organizaciones cívicas necesitan profundidad y reproducción sobre los mismos datos. Empresas y administraciones también pueden consultar contratación; convertirse en un CRM de ventas públicas requeriría otra decisión de producto.

### Experiencia que debe existir

Una entrada por pregunta, tema, lugar, institución, representante o empresa. Desde ahí, un mismo recorrido: **respuesta comprensible → comparación e histórico → documento y pasaje que la respaldan → seguimiento o reutilización**. La interfaz comparte contexto, filtros y fechas; no obliga a descubrir qué herramienta interna contiene la respuesta.

- **Dinero:** buscar una empresa por NIF o nombre, reunir variantes verificadas y UTEs con atribución explícita; ver contratos, lotes, modificaciones y subvenciones. Presupuestado, adjudicado, formalizado, obligado y pagado se presentan separados. Comparar organismos y territorios con denominadores coherentes.
- **Representación y decisiones:** localizar responsables por competencia y mandato; ver iniciativas, votos, acuerdos y normas con significado y estado. Prometer, proponer, aprobar y ejecutar son acciones diferentes.
- **Promesas:** compromisos verificables con autor, fecha, plazo, competencia, fuente, criterios de cumplimiento y evolución revisada. Registrar desacuerdos y correcciones.
- **Resultados:** explicar indicadores y evolución territorial, metodología, revisiones y límites. Un cambio posterior a una medida no acredita causalidad. Los enlaces entre decisiones, gasto y resultados necesitan prueba explícita; donde falta, mostrarlo.
- **Alineamiento:** el usuario elige asuntos y pesos; puede comparar posiciones declaradas y acciones documentadas por separado. Evidencia insuficiente no se convierte en neutralidad. Preferencias privadas por defecto y sin recomendación electoral opaca.
- **Continuidad:** guardar o compartir una consulta, recibir novedades elegidas, abrir una fuente en una interacción, descargar un resultado reproducible y solicitar una corrección con seguimiento.

### Qué significa cobertura competitiva

Cada dominio publica un inventario fuente × territorio/organismo × periodo × tipo de registro. Para cada celda: universo esperado y cómo se obtiene, registros encontrados, descargados, normalizados, deduplicados, publicados, excluidos con motivo y pendientes. Las fuentes desconocidas o inaccesibles cuentan como brecha; no desaparecen del mapa.

En contratación, el universo candidato incluye PLACSP, plataformas autonómicas, perfiles locales/sectoriales que aporten registros ausentes y TED para publicaciones españolas. Reconciliar solapamientos por identificadores y relaciones entre anuncios; no sumar feeds como si fueran contratos diferentes. Presupuestos, ejecución, subvenciones, parlamentos, boletines, elecciones, cargos e indicadores tendrán inventarios propios, sin sumar sus filas en un contador de adjudicaciones.

Dos medidas separadas: **cobertura de adquisición** sobre registros publicados por fuentes enumeradas y **cobertura del fenómeno real**, desconocida cuando la publicación oficial es incompleta. Los mínimos/máximos de fecha nunca sustituyen continuidad. La ficha de GALASA debe distinguir “no hemos encontrado”, “fuente sin datos”, “fuente pendiente” y “cero adjudicaciones dentro de un ámbito reconciliado”.

### Umbrales de aceptación para poder afirmar competitividad

Son criterios de aceptación del objetivo autorizado, no resultados actuales ni prestaciones medidas de competidores. Deben cumplirse por dominio anunciado; una media global no oculta una comunidad o tipo de registro ausente.

| Dimensión | Objetivo propuesto | Prueba necesaria |
| --- | --- | --- |
| Universo | 100% de fuentes identificadas del ámbito anunciado inventariadas; estado visible de todas | Registro público contrastado con directorios oficiales y revisión independiente; “identificadas” no equivale a todas las existentes |
| Adquisición | ≥99% de registros elegibles reconciliados en cada fuente-periodo declarado completo | Denominador oficial o enumeración reproducible; si solo existe muestreo, publicar estimación e intervalo, sin etiquetar completo |
| Actualidad | ≥95% de novedades de fuentes diarias visibles en ≤24 h; alerta de retraso >48 h | Tiempo desde disponibilidad en origen, medido durante 30 días; en fuentes periódicas, cadencia propia |
| Identidad | ≥99% de precisión y ≥95% de recuperación en muestra revisada de enlaces entre entidades | Muestreo por fuente, nombres ambiguos y UTEs; tamaño e incertidumbre publicados; abstención ante homónimos |
| Trazabilidad | 100% de afirmaciones y cantidades con fuente, fecha y transformación reproducible | Verificar captura conservada cuando sea redistribuible, pasaje o campo y versión; enlaces inferidos diferenciados |
| Utilidad | ≥90% de tareas resueltas correctamente sin ayuda, mediana ≤2 min | Al menos 20 participantes externos, ≥10 sin perfil técnico, tareas y respuestas fijadas antes; tasas por tarea y perfil |
| Rapidez | Primera respuesta útil ≤3 s; filtros p95 ≤1 s en el escenario acordado | Dispositivo y red móviles especificados, caché fría/caliente, mezcla real de consultas y concurrencia publicada |
| Accesibilidad | WCAG 2.2 AA como objetivo; todos los recorridos esenciales con teclado y lector de pantalla | Auditoría automática y manual, zoom, móvil y movimiento reducido; no afirmar conformidad por pasar un escáner |
| Reutilización | Paridad exacta de resultados y cantidades entre UI, API y exportación de igual versión | Enlaces compartibles, exportaciones completas acotadas por trabajo y reproducción independiente |
| Operación | Objetivo de disponibilidad 99,9% mensual y restauración ensayada | Presupuesto y carga acordados, medición externa y ensayo de recuperación; compatibilidad con coste cero aún no demostrada |

### Métrica principal y controles contra autoengaño

**Personas por semana que resuelven una pregunta cívica correctamente con evidencia verificable.** En pruebas: respuesta contrastada por un evaluador independiente. En producción: estimación basada en encuestas voluntarias y auditoría de muestras; guardar o descargar es solo una señal de uso, nunca prueba automática de comprensión. No instrumentar preferencias políticas personales para medirla.

Publicar junto a esa métrica cobertura por dominio, frescura, éxito por tarea, errores/correcciones, repetición de uso y coste operativo. No sustituirla por filas, documentos, visitas, commits, pruebas pasadas o componentes desplegados. La métrica tiene línea base pendiente.

### Situación de partida y decisiones abiertas

La release local vigente declara **47.397 resultados de adjudicación, 2004-01-01 a 2025-06-30**, con continuidad nacional sin demostrar. La evidencia del despliegue acredita consulta paginada, CSV y ocho resultados de GALASA dentro de ese corpus; no acredita todos sus contratos. Fuentes: `infra/cloudflare/spending-api/src/release.json` y evidencia de lanzamiento. Esta investigación no reaudita todos los dominios ni la producción: las demás dimensiones requieren línea base homogénea antes de puntuarlas.

El coste cero sigue siendo una restricción del mantenedor. No se cambia plan ni proveedor: falta demostrar que esa restricción sea compatible con volumen, documentos, actualización, búsqueda y disponibilidad de la North Star. Si no lo es, presentar la incompatibilidad con mediciones y opciones para decisión explícita, sin rebajar silenciosamente cobertura ni activar facturación.

### Ejecución autorizada: dinero público nacional

Ahora: contratación parcial; denominador nacional, actualización recurrente y usabilidad externa sin acreditar. Destino: consulta nacional útil, trazable y actualizada de contratación, subvenciones, presupuestos y ejecución, conservando sus unidades separadas. La prioridad de esta secuencia sustituye los recortes históricos del lanzamiento cuando impidan alcanzar el objetivo; conserva requisitos de privacidad, evidencia y coste cero.

| Entrega | Resultado exigido | Gate de avance |
| --- | --- | --- |
| DN-01 Reconciliación y cobertura | Inventario reproducible de lo adquirido, seleccionado y publicado; lagunas explícitas por fuente y periodo | Balances exactos y motivos de exclusión; cifras nacionales desconocidas etiquetadas, sin inventar denominador |
| DN-02 Contratación nacional | Histórico recuperable de PLACSP y fuentes complementarias españolas, versiones y entidades reconciliadas | Publicación de cada cohorte con fuentes, paridad y cobertura; procesamiento reanudable y presupuesto de almacenamiento/escrituras |
| DN-03 Actualidad y consulta | Ingestión incremental recurrente, búsquedas por NIF/órgano/territorio/CPV/texto, perfiles, seguimiento y descargas | Medición de frescura y tareas reales; operaciones sostenibles en coste cero, retrasos visibles |
| DN-04 Otros flujos de dinero | Subvenciones, presupuestos y ejecución por fuente/territorio, relaciones probadas con contratación | No duplicar transferencias/contratos ni presentar adjudicaciones como pagos; misma evidencia y evaluación |
| DN-05 Competitividad demostrada | Pruebas independientes, auditoría de cobertura, accesibilidad, carga, restauración y operación | Umbrales North Star cumplidos; no declarar completo por cerrar DN-01–04 técnicamente |

Siguiente acción: medir la base física y la selección publicada, recuperar el estado de adquisición histórica existente y ampliar una cohorte con controles de publicación. No reescribir bases originales ni reimportar D1 a ciegas. Dependencias externas de revisión y fuentes se registran; avanzar en trabajo controlable mientras se resuelven.


## Prioridad inmediata: lanzamiento útil para la comunidad

Mandato 2026-09-07: mover consultas de `/spending/` a un backend gratuito con límites duros, filtros y paginación en servidor. Sustituye para esta superficie la restricción previa de no crear API. Ahora: 47.397 resultados consultables mediante Workers Free + D1, páginas de 12 filas, búsqueda y CSV explícito; arranque y assets desde Cloudflare verificados. Destino: ampliar cobertura conservando evidencia y cero sobrecostes. Siguiente: incorporar nuevas capturas con presupuestos de importación y paridad; sin prometer disponibilidad ilimitada al agotar cuotas.

Mandato 2026-09-06: `/spending/` debe consultar todo el histórico disponible, sin recorte mensual previo al calendario. Publicar nueva release inmutable y verificar Galasa con rango 1999–2027; conservar distinción entre adjudicado, estimado y pagado. Sustituye la limitación mensual descrita en el lanzamiento inicial.

Estado: `release mensual publicada`; `L0–L5` técnicos verificados y cohorte completa de enero de 2025 ampliada a 2.632 resultados elegibles con 1.960 XML originales. Responde al mandato del mantenedor de dar foco y hacer aprovechable públicamente lo desarrollado. Esta secuencia tiene prioridad de ejecución sobre las ondas de expansión posteriores; conserva su historial, requisitos y estados.

**Ahora:** código, web y datos ya son públicos. El índice HF de escala declara siete corpora y 5.414.326 filas, pero la portada ofrece numerosas herramientas, `/spending/` solo veinte adjudicaciones fijas y `/explorer/` un índice sin ejecución SQL. GitHub no tiene releases y el issue de revisión ciudadana sigue sin revisores independientes. Evidencia y límites: [auditoría del 5 de septiembre](docs/etl/sprints/PUBLIC-LAUNCH-20260905/evidence/launch-audit.md).

**Destino:** que alguien ajeno al proyecto responda una pregunta sobre dinero público, abra la fuente y reproduzca el resultado; después pueda aportar una consulta, una corrección o una fuente oficial mediante una tarea acotada. Primera audiencia: desarrolladores de datos, periodistas y fiscalizadores cívicos. La misión ciudadana y `/citizen/` se conservan; la campaña inicial sirve a quienes pueden reutilizar y ampliar la evidencia.

**Propuesta de valor:** «Investiga decisiones públicas con datos descargables y resultados que puedes comprobar». Primera entrega: cohorte mensual PLACSP fechada y acotada al corpus congelado. Mantener el nombre del proyecto. Diferenciación: pregunta → consulta → resultado → expediente oficial → reproducción.

**Pregunta inicial:** «¿A quién adjudicó este organismo, cuánto y en qué expedientes, durante enero de 2025?». Tres consultas del mismo dataset: adjudicaciones por órgano/proveedor; distribución temporal; desglose hasta expediente y fuente. No sumar anuncios con adjudicaciones ni confundir adjudicación con pago. Normalizar variantes tipográficas mediante identificadores publicados o una clave conservadora de nombre; retener siempre el texto XML literal. No convertir concentraciones o anomalías en acusaciones. Publicar una release no actualiza la fecha de sus datos.

### Hitos de lanzamiento

Presupuesto propuesto: máximo diez jornadas de trabajo concentrado para un candidato de lanzamiento. Son límites de capacidad, no estimaciones verificadas ni fechas prometidas. Si un hito excede su límite, reducir presentación; no rebajar integridad ni evidencia. Las respuestas externas no tienen plazo garantizado.

| Hito | Capacidad | Entrega | Condición de salida | Estado |
| --- | --- | --- | --- | --- |
| `L0` Corte defendible | 1 jornada | Release inmutable y corte de adjudicaciones; ficha de fuente, fechas, unidad, cobertura, exclusiones, derechos y hashes | Reconciliar corpus y cifras web; distinguir anuncios/adjudicaciones/lotes/versiones; comprobar duplicados, fechas e importes; cada resultado de demo tiene fuente y captura verificable. Si falla, reducir el corte hasta que pase; ningún scrape masivo como requisito | VERIFICADO Y PUBLICADO |
| `L1` Reutilización real | 2 jornadas | Paquete pequeño CSV/Parquet, tres consultas SQL parametrizadas, resultados esperados, diccionario y comando documentado | Descarga anónima fijada por hash; en entorno vacío, sin bases locales previas ni secretos, las tres consultas reproducen los resultados publicados. Registrar runtime, bytes y tiempo. Objetivo: primera respuesta en menos de 10 minutos desde prerrequisitos explícitos | DESCARGA ANÓNIMA VERIFICADA |
| `L2` Demo pública | 3 jornadas | Ampliar `/spending/` con selección de órgano/proveedor/periodo sobre el corte aprobado, resultado, enlace compartible, CSV y evidencia. Portada con un caso protagonista y accesos a datos/contribución | Respuesta visible sin instalar ni registrarse; mismo resultado al recargar enlace en escritorio/móvil; fuente a una interacción; fecha y límites visibles. Reutilizar componentes/exportadores; carga acotada y animaciones de layout con respeto a movimiento reducido | WEB PÚBLICA VERIFICADA |
| `L3` Entrada de colaboradores | 1 jornada | README breve con demo antes de arquitectura, guía de reproducción y tres rutas de aportación; seis tareas pequeñas; créditos por dataset/consulta/revisión y release candidata | Cada tarea especifica archivo, entrada, salida esperada, validación y responsable. Al menos dos se resuelven sin conocimientos del dominio ni acceso privado. Reutilizar SDK, plantillas y `CITATION.cff` | PUBLICADO |
| `L4` Verificación | 2 jornadas propias | Prueba del recorrido y reproducción, defectos corregidos y publicación desde cambios aislados y revisables | Gates del corte y privacidad/datos reales pasan; hashes/resultados coinciden entre descarga y web; tres personas ajenas prueban recorrido y dos reproducen una consulta. Sin respuestas externas, publicar como alfa técnica con ese gate pendiente; no afirmar validación comunitaria | TÉCNICA OK; EXTERNA PENDIENTE |
| `L5` Presentación y adopción | 1 jornada propia | Release GitHub, vídeo de 60–90 segundos, ejemplo reproducible y convocatoria sobre una tarea concreta | Release/enlaces verificados. Envíos solo con autorización específica. Registrar respuestas, reproducciones, correcciones y PR reales; revisar adopción a los 14 días de difusión. Ningún contacto individual es dependencia del lanzamiento | RELEASE/VÍDEO PUBLICADOS; ADOPCIÓN ABIERTA |

**Siguiente:** recoger revisión externa y revisar adopción a 14 días; release y descarga anónima verificadas. Ejecución: [roadmap técnico](docs/roadmap-tecnico.md#lanzamiento-comunitario-primer-trabajo); estado operativo: [tracker](docs/etl/e2e-scrape-load-tracker.md#lanzamiento-comunitario-con-foco-2026-09-05). Los hitos acotan `W9-002`, `W9-004`, `W9-005`, `W9-007`, `W9-008` y `W9-009`; no crean otra plataforma.

### Recortes y criterio para volver a ampliar

- Una sola entrega en construcción. Infraestructura adicional solo si bloquea un hito del corte; presupuesto orientativo 80% reutilización/demo/comunidad y 20% reparación necesaria.
- Diferir adquisición a un millón de documentos, cobertura territorial completa, nueva ontología/SDK, causalidad, ranking político, resolución universal de identidades y operación masiva de revisión. Mantener los sistemas existentes; no borrarlos ni anunciar su cierre.
- No construir SQL general en navegador, cuentas, editor de dashboards, nueva API ni nuevo repositorio. Primer acceso analítico: descarga + consultas reproducibles; la web puede usar agregaciones estáticas del mismo corte.
- BDNS es la siguiente fuente candidata tras demostrar reutilización de PLACSP. Votos explicados siguen como utilidad secundaria. El recibo andaluz conserva historial y estado real; actualizar con evidencia o presentar como corte histórico, nunca como seguimiento vigente por omisión.
- El cierre global `foundation.ready` sigue abierto. Una alfa limitada puede publicarse con gates propios del corte, sin promover lanes ni esconder fallos globales. No modificar un gate para hacer pasar evidencia defectuosa.
- Éxito inicial: 5 reproducciones externas, 3 aportaciones externas aceptadas y 1 consulta/caso creado sin ayuda directa. Son objetivos, no resultados actuales. Stars y visitas son señales secundarias. Si a los 14 días nadie reutiliza, observar dónde se atascan tres usuarios y reparar esa entrada antes de añadir datasets.
- Reconocer contribuciones en el resultado: autor y revisión de cada consulta/caso, crédito de procedencia por dataset, enlace al PR/corrección y sección de aportaciones en cada release. Incluir trabajo editorial y de datos, no solo commits. No inventar revisiones ni atribuir trabajo ajeno al proyecto.

## Revision Record

| Revision | Date | New input | Material changes |
| --- | --- | --- | --- |
| `REV-21` | `2026-09-05` | Maintainer requests the shortest useful public launch and contributor adoption instead of further parallel expansion | Prioritizes a bounded PLACSP question, reproducible reuse, existing UI and contributor entry through `L0–L5`. Records live entry gaps and capacity/acceptance gates. Preserves scale backlog, existing dirty work, incomplete readiness and the distinction between planning and publication. |
| `REV-01` | `2026-08-23` | Maintainer mandate for end-to-end accountability at million-item scale using official real data and retaining public-domain identity | Canonical mission, scale classes, SLOs, ten delivery waves, and societal-scale DoD established and updated from current artifacts. |
| `REV-02` | `2026-08-23` | Systematic scope audit of this canonical roadmap plus current C1/C2, actor-graph, comparison, origin, restore, and review evidence | Added claim ledger, normalized topics, initiatives, outcome-based epics, granular stories, ownership, uncertainty, bidirectional traceability, explicit estimate omission, decision questions, audit log, and residual-risk register. Existing `W*` truth remains authoritative and unchanged by the planning index. |
| `REV-03` | `2026-08-24` | Signed anonymous clean-room recovery of the seventh analytical corpus | Closed every-lane analytical recovery: `candidate_occurrences` restored from an empty root with zero reuse/credentials/remote mutation, then independently validated from bundled controls and the external signer policy. Raw-document origin and outcome C2 durability remain separate open gates. |
| `REV-04` | `2026-08-24` | Scale-safe outcome identity, portable C2B delivery, and C2C review-capacity evidence | Separated the `2,865,602`-row source planner, exact official-public identity companion, bounded content-addressed Parquet package, and immutable capacity-only review snapshot. Preserved L0/no-claim boundaries and kept real human operation, promotion, public release, durable remote origin, and external reproduction open. |
| `REV-05` | `2026-08-29` | Pinned-runtime rebuild and adversarial closeout of C2B/C2C local capacity | Pinned Python `3.12` and PyArrow `20.0.0` where physical identity matters, rebuilt C2C from current schema, passed `330` independent checks plus `12` crash/path/lease tests, closed a C2B hard-link control-path bug, and passed `22` identity plus `23` package tests. No human, promotion, publication, remote-origin, or societal-scale gate was upgraded. |
| `REV-06` | `2026-08-29` | Full local repository closeout after C2B/C2C implementation | Proved a real 25-partition interruption/resume and byte-exact C2B replay, passed `1,503` Python plus `234` Node tests, reconciled two abandoned BDNS run markers as explicit errors without changing their real counts, passed all `101` staging databases, rebuilt `1,435` static pages, and passed real-only/publication-hygiene gates over `130,735`/`17,072` files. Remote publication and real human operation remain open. |
| `REV-07` | `2026-08-29` | Real 10,000-object document acquisition and partitioned scale contract | Replaced the monolithic acquisition manifest with `30` deterministic gzip JSONL partitions, independently preflighted `10,000` prior official files, completed exactly `10,000/10,000` fresh official downloads with zero failure, and rehashed all `20,000` prior/fresh files. Added durable request events, conservative crash-window budget recovery, explicit host ceilings, redirect refusal, and future host-fair queue priority. The canonical local closeout passes `1,442` Python tests (`12` contextual skips), `234/234` Node tests, `1,435/1,435` static pages, and real-only/publication-hygiene gates over `142,731`/`17,076` files. Representative `100k`, real monetary rates, raw-origin restore, OCR review, and `1M` remain open. |
| `REV-08` | `2026-08-29` | Exact real official source-universe audit before any 100,000-object acquisition claim | Streamed and independently replayed `304,165` provenance edges through disk-backed SQLite without network access. Current evidence contains `104,064` unique official public URLs / `100,418` HTTPS, but only `90,121` HTTPS URLs combine an implemented source-specific semantic contract with clean physical host proof. Numeric acquisition supply therefore misses `100,000` by `9,879`; representativeness remains `DEC-01` and was not inferred. Readiness now fails closed on report/input/hash/count drift. |
| `REV-09` | `2026-08-29` | Disk-bounded, crash-recoverable preparation of the complete currently eligible document universe | Replaced in-memory cohort planning with ordered SQLite cursors, bounded gzip shards, exact execution/selection identities, exact Parliament `(db_ref, table_name)` provenance pairs, per-target kernel locks, immutable-input checks, and journaled manifest-last publication. A new `10,000`-row v4 cohort has zero SQL selection/payload differences from the historical real cohort after normalizing only the additive provenance-pair field. The same path prepares and independently preflights all `90,121` currently eligible official documents / `2,849,994,795` prior bytes at `53,198,848` bytes planner peak RSS, with `90,121/90,121` real/public-information rows and zero blocked hosts. This proves bounded preparation, not new network acquisition, representativeness, the missing `9,879` URLs, or `1M`. |
| `REV-10` | `2026-08-30` | Exact numeric 100,000-row planning, BOE tail recovery controls, and current full-corpus processing | Closed numeric supply and planning without overstating acquisition: source-universe replay now finds `101,303` contract-eligible official HTTPS URLs and zero numeric gap; deterministic selection pins exactly `100,000` rows (`98,748` BOE document XML, `1,166` BOE summaries, `86` Parliament of Andalusia records) with selection SHA-256 `c81d3c0...`, bounded validation, zero blocked hosts, zero mock/synthetic rows, and exact public-information retention. BOE physical capture advanced to `100,051/100,867` documents before a measured transport timeout; `815` remain unfinished and central readiness fails closed. Added atomic progress checkpoints, conservative request-budget recovery, telemetry-backed budget/transient requeue commands, and route-level network/timeout circuits. Current captured corpus independently validates `122,607` official instances / `120,757` contents, `2,211,203,471` native characters, and `856/856` additive OCR pages; human review remains `0/40`, raw durable origin remains open, representativeness remains `DEC-01`, and `1M` remains open. |
| `REV-11` | `2026-08-30` | Content-addressed, bounded BOE lineage control for the real 100,051-row corpus | Replaced the current `234,632,869`-byte monolithic JSONL control with a `7,717`-byte manifest-last index and `11` immutable gzip shards totaling `16,081,029` bytes. Logical SHA-256 remains exactly `99739ca6...`; independent validation rehashes every shard, all `100,051` real document captures, and all `1,156` referenced summary captures, enforces strict URL order and `10,000`-row / `64 MiB` uncompressed shard ceilings, and preserves all official public information with zero mock/synthetic rows. Provenance and readiness consume the index. BOE tail, generation supersession, raw durable restore, human review, representativeness, and `1M` remain open. |
| `REV-12` | `2026-08-30` | Crash-safe BOE lineage activation and non-destructive generation retention | Added immutable manifest archives, one activation receipt per live index, predecessor-linked supersession, manifest-last switching, explicit refusal of ambiguous historical reactivation, and a policy forbidding automatic deletion. The production audit full-hashes the active `11`-shard generation and binds it to one exact archived index plus one receipt with zero orphan, unactivated, interrupted-staging, or deletion state. A real-capture interruption test proves a failed rebuild leaves the old live index byte-identical and valid, retains/reports the unactivated candidate, then completes a successor and verifies both generations plus the predecessor chain. This closes lineage interrupted-rebuild and supersession mechanics, not the `815`-job BOE transport tail, final native/OCR generation lifecycle, durable raw restore, human review, representativeness, or `1M`. |
| `REV-13` | `2026-08-30` | Terminal-only native/OCR activation with sharded manifests and restorable state | Replaced the `128 MB` native live JSONL with a `5,423`-byte index over `13` immutable gzip shards and the `815 KB` OCR JSONL with a `1,194`-byte index over one immutable shard. Each terminal generation now archives its index, snapshots SQLite state content-addressably, writes an activation receipt before switching the live index last, forbids deletion, and rejects ambiguous historical reactivation. Full production audits decompress every shard, restore both state snapshots, run SQLite `quick_check`, and report zero orphan, unactivated, interrupted-staging, or deletion state. A real-capture failure-injection regression proves interrupted native activation leaves the old generation byte-identical, retains the candidate, and completes non-destructively. Native and OCR processing remain exact at `122,607` instances / `119,338` CAS objects and `856` pages / `131` OCR CAS objects. This closes current captured-generation lifecycle, not BOE transport, human review, representative selection, durable raw/CAS restore, or `1M`. |
| `REV-14` | `2026-08-30` | Full raw/native/OCR origin replication and bounded clean-restore mechanics | Added a resumable queue spanning exactly `240,226` distinct real objects: `120,757` raw documents, `119,338` native text CAS objects, and `131` OCR CAS objects. The local filesystem drill checksum-replicated all `5,902,869,836` bytes with zero failure in `149.810731s`, activated a `9,512`-byte index over `25` immutable shards, snapshotted the `216,457,216`-byte queue state, and passed a full lifecycle audit. A bounded clean-room pass then restored and rehashed every object and byte in `58.161139s` with `716,831,460` bytes of bounded scratch. Real production captures drive the regression test. This closes complete local origin/restore mechanics only; `durable_public_origin_proven=false`, no remote publication occurred, and authorized immutable public-origin replication remains open. |
| `REV-15` | `2026-08-30` | Deterministic byte-bounded publication packs for the exact real-object generation | Bound the exact `240,226`-object origin manifest into `25` deterministic gzip tar packs capped at `10,000` objects and `448 MiB` payload each. All `5,902,869,836` payload bytes compress to `1,793,094,983` archive bytes plus `17,893,134` member-manifest bytes. A full validator restores and rehashes every member in `14.348405s`; lifecycle audit restores the `97,771,520`-byte queue snapshot and reports zero orphan, unactivated, staging, or deletion state. A real-object replay proves deterministic archive and member-manifest hashes. This is an immutable local publication package only; remote mutation, durable public origin, and independent remote restore remain false. |
| `REV-16` | `2026-08-30` | Exact append-only public-origin release plan and read-only remote collision preflight | Rehashed and bound `90` real pack/member/control/evidence files totaling `1,911,188,479` upload bytes to content-addressed release `7ba59649...`. Added a resumable Hugging Face publisher that forbids deletes and immutable overwrite, requires checksum parity before resume, uploads data before its release manifest, verifies the sealed release, and changes `document-origin/latest.json` last. Separate CLI and recipe authority fences block remote write unless explicitly enabled. The live read-only preflight finds `91/91` immutable release paths and the pointer absent with zero collision or unexpected path. Full mounted-source verification passes `1,464` Python tests with `12` contextual skips. No upload, commit, pointer change, durable-origin claim, or independent remote restore occurred. |
| `REV-17` | `2026-08-30` | Full real-document language/encryption profile with honest uncertainty and crash-safe generations | Profiled all `122,607` current real official file instances / `120,757` distinct contents from fully rehashed raw and native CAS bytes. The v2 public contract reports `122,288` machine-language candidates, `319` explicit unknown instances, source-declared/model agreement or conflict, and `120,757/120,757` explicitly unreviewed contents; candidates are not promoted as human ground truth. Encryption is observed for every file, including all `1,437` PDFs (`1` encrypted, `1,436` not encrypted). Independent replay rehashes and reclassifies every distinct content with zero failure or file-set mismatch. The full lifecycle audit validates two retained generations / `26` shards / one supersession and restored SQLite state with zero orphan, interrupted, unactivated, or deleted artifacts. Central readiness consumes all three gates and still fails exactly on the BOE physical corpus tail. |
| `REV-18` | `2026-08-30` | Lossless PDF normalization and exact native-text locators for every captured document | Corrected a real PDF defect where markup normalization interpreted cross-page angle-bracket text as HTML and silently removed `50,958` public characters across six CAS objects. Extraction is now algorithm-version bound and plain PDF text preserves angle-bracket content; the current corpus contains `2,211,254,429` native characters with zero truncation. Added a crash-safe, content-deduplicated locator generation for all `122,607` instances / `120,757` contents: `30,634` exact PDF-page locators plus `332,530` bounded normalized-text spans become `363,164` content locators / `379,445` instance locators in `38` immutable shards. The manifest copies no public text. Independent validation rehashes `5,312,661,661` raw bytes and `2,256,345,242` native UTF-8 bytes, recomputes every locator, and reports zero missing, unexpected, mismatched, dead, or synthetic rows. Dependent profile replay remains `120,757/120,757` with three retained generations / `39` shards / two supersessions. Fresh origin/restore and packaging rehash all `240,226` current objects / `5,902,879,469` bytes; append-only release `9991abcb...` binds `122` immutable files / `2,011,389,596` bytes, and read-only remote preflight finds all `123` release paths plus the pointer absent with zero conflict or mutation. Central readiness requires all these gates and fails exactly on the BOE tail. Semantic markup sections, representative office formats, final post-BOE generation, human quality, authorized durable public origin, and `1M` remain open. |
| `REV-19` | `2026-08-30` | Scale-bounded semantic markup lineage and exact real-format coverage | Replaced anonymous markup spans with source-derived major XML/HTML XPath sections while preserving exact native CAS offsets and hashes. A depth-3 canary was rejected after averaging about `79` locators/document and reaching `25,061` on one BOE file; the corrected major-container algorithm averages `6.780402` content locators/document and caps the observed maximum at `1,568`, projecting `6,780,402` content locators rather than about `79M` at one million documents. Generation and independent replay fail fast above `2,000` locators/content; the complete-report gate also enforces average `<=10`. The complete generation covers all `120,757` contents with `782,814` semantic markup-section locators across `119,473` markup contents, `5,333` bounded exact fallback spans across `322` contents whose structure could not be proven, and `30,634` PDF-page locators: `818,781` content / `879,104` instance rows in `88` immutable shards. Independent replay rehashes every raw/native byte and reports zero missing, unexpected, mismatched, or failed rows; two retained locator generations / `126` shards pass full lifecycle audit. The real profile proves the only observed formats are `108,042` XML, `13,128` HTML, and `1,437` PDF; office-format instances are exactly `0`, so office extraction support is explicitly not claimed and no fake cohort was introduced. Central readiness remains fail-closed on the BOE physical tail. |
| `REV-20` | `2026-08-30` | Full real-XLSX processing, bounded evidence locators, current origin package, and honest factory economics | Current inventory now reconciles `122,653` real instances / `120,801` distinct contents, including `46` XLSX instances / `44` distinct workbooks and `2,845,172` worksheet rows. Independent `openpyxl` replay verifies all `44` distinct XLSX contents and their public cell values; the observed cohort contains zero formulas, so formula correctness is not claimed. The locator generation adds `261` bounded XLSX row groups, averages `5.931818` locators/workbook, caps at `6`, and projects `5,931,818` rows at one million XLSX documents under a hard `10M` contract. All `46` XLSX source URLs are path-inferred `mapped_unverified`, receive no provenance credit, and leave total corpus gaps at `113`. Current local origin replication, clean restore, `25` deterministic packs, and release preparation cover `240,278` objects / `6,048,142,788` payload bytes; release `a891bbab...` binds `154` immutable files / `2,250,233,559` bytes. Local dry-run and live read-only Hugging Face collision preflight pass, but no remote mutation or durable-public-origin claim occurred. Native/OCR current-full warm-output telemetry passes; cold-output benchmarks are absent and monetary cost remains unknown, never zero. Enforced central readiness reaches and preserves the BOE blocker: active lineage references `1,156/1,166` successful summaries and the document queue remains `100,051` success / `1` dead / `815` unfinished. `DEC-01`, real human review, authorized durable remote origin/restore, cold economics, BOE closure, and real `1M` execution remain open. |

## Executive Summary

Outcome: public users must be able to trace promises, decisions, responsibility, money, implementation, outcomes, disputes, and corrections to primary official evidence without an automated anomaly becoming a corruption verdict.

Current posture is useful foundation, not societal scale. Seven real corpora and three million-row lanes exist, but zero lanes are promoted because representativeness, source-total reconciliation, durable recovery, correction handling, or other lane-specific gates remain open. Analytical releases have durable origin and clean-restore evidence. Full raw/native/OCR local-origin mechanics now replicate, restore, deterministically package every current object, and prepare an exact collision-free append-only public-origin release. A durable public document origin still does not exist because no remote write was authorized or performed. Document numeric supply and exact `100,000` planning now pass, but physical completion, representative strata, human quality, durable remote recovery, and document `R2` do not.

Immediate release truth as of `2026-08-30`:

- actor graph v1 and promise/action comparison C1 are locally validated but still require live publication and exact remote verification;
- all seven published analytical corpora now have signed, checksum-bound clean-room recovery evidence; the newest isolated candidate-occurrence drill validates `10,820` real rows / `2` Parquet files with zero reuse, credentials, undeclared files, or remote mutation;
- outcome-context C1 public v3 status, immutable `17`-asset evidence package, full `1,435`-page build, local route/asset audit, and real browser verification agree; remote publication and exact live verification remain open;
- outcome C2A physically processes all `33,726` national-only real pairs. C2B separates its `2,865,602`-row source planner from an exact public-identity companion (`119,116` member-vote rows, `490` names, `458` actions) and a bounded content-addressed package (`1,205` pair plus `8` identity Parquet files). These are internal L0 capacity facts, never outcome relationships or scale-promotion claims;
- outcome C2C materializes capacity for `2,865,603` real tasks and `2,865,604` required review slots, but deliberately contains zero trust roots, reviewers, authorizations, conflicts, assignments, claims, decisions, adjudications, promotions, release bindings, or publications. A separately versioned operational snapshot and real authorities/reviewers remain prerequisites;
- document planning selects exactly `100,000` real official rows and validates them under bounded memory. Current processing covers `122,653` real instances / `120,801` contents, including `46` XLSX instances / `44` distinct workbooks and `2,845,172` worksheet rows; all public cell values replay independently, while zero observed formulas leave formula correctness unproven. Physical BOE state remains `100,051/100,867` document successes, `1` telemetry-backed timeout failure, and `815` unfinished jobs; active BOE lineage references only `1,156/1,166` successful summaries. This is not completed representative `100k` acquisition or `R2`;
- outcome human review, durable remote artifact origin, remote clean restore/rollback, public release, and any reviewed public outcome link remain open;
- high-risk integrity findings remain unauthorized while representative lanes and the review/correction plane are incomplete.

Delivery is organized into four initiatives and eleven non-overlapping outcome epics. Existing Waves `W0..W9` retain detailed scope and status; the systematic planning layer below indexes rather than duplicates them. Named human owners, source-universe approvals, review staffing, and publication authority remain decision-changing gaps. Estimates are intentionally omitted until those choices make scope coherent.

## 1. Mission

Build Spain's open, evidence-backed accountability infrastructure.

The system must let a citizen, journalist, researcher, auditor, or public servant answer:

- what was promised,
- what was voted and by whom,
- what rule or executive act was approved,
- who had formal responsibility,
- what money was budgeted, awarded, paid, or withheld,
- what was implemented or enforced,
- what outcome followed,
- what evidence supports each statement,
- what remains unknown, disputed, stale, or blocked,
- and how a published conclusion changed after correction or counterevidence.

Every public claim must drill down to primary evidence. Anomaly detection may create a review signal. It may never publish a corruption verdict by itself.

## 2. Authority And Status

This file owns future direction and sequencing.

- Strategy and model background: `docs/roadmap.md`.
- Near-term engineering execution: `docs/roadmap-tecnico.md`.
- Live source and pipeline status: `docs/etl/e2e-scrape-load-tracker.md`.
- Confirmed official-data access obstruction: `docs/etl/name-and-shame-access-blockers.md`.
- Stable implementation knowledge: `project_kb/README.md`.

Rules:

- Derived documents may refine this roadmap but may not introduce net-new scope.
- A work item is `DONE` only when its exit gate has current evidence.
- Local code, a passing unit test, or a large generated file is not production readiness.
- Missing artifacts, blocked sources, and unverified identities stay open.
- Every non-trivial slice records current state, destination, next action, command, artifact, and definition of done.

## 3. Non-Negotiable Real-Data Policy

Only records captured from identifiable official public sources count toward coverage, capacity, quality, or readiness.

Required for every counted corpus:

- official source identity and allowlisted origin,
- retrieval timestamp and HTTP outcome,
- immutable raw checksum,
- source record identity or explicit source-scoped fallback,
- parser and schema version,
- exact transformation lineage,
- manifest with row, file, byte, and checksum totals,
- independent validation against the materialized artifact,
- public-domain status and provenance classification,
- current limitation and next gate.

Captured official samples may support deterministic tests. They must retain source metadata and checksums. Generated records, invented people, invented transactions, loopback HTTP results, and placeholder origins never count toward a roadmap gate.

Public-domain identity is accountability evidence. Names, public identifiers, birth fields, official contact details, candidacy facts, supplier and beneficiary identities, appointments, donations, and comparable personal information published by an authoritative public source must be retained exactly with source URL, retrieval, checksum, and record/field lineage. Entity classification may describe a person or organization; it may never suppress an official public field. Secrets, credentials, workstation traces, private session state, and information not obtained from a public source remain forbidden in public artifacts.

The machine-enforced registry is `docs/etl/real-corpus-registry.json`. The canonical audit is:

```bash
just etl-scale-readiness
```

## 4. Scale Contract

Scale is an end-to-end operating property. It includes discovery, fetch, preservation, parsing, normalization, identity, enrichment, review, publication, correction, recovery, and cost.

### 4.1 Scale classes

| Class | Real corpus | Required proof |
| --- | ---: | --- |
| `R0 captured` | `1-9,999` official records | provenance, repeatable parse, idempotence, public-field retention, artifact validation |
| `R1 operational` | `100,000+` official records or full smaller universe | bounded memory, resumability, reconciliation, quality sample, bounded publication |
| `R2 million` | `1,000,000+` official items | freshness SLO, recovery, incremental rebuild, durable origin, clean restore, cost report |
| `R3 national history` | `10,000,000+` facts and `1,000,000+` documents | multi-year completeness, revision history, source drift, distributed workers, public release SLO |
| `R4 ecosystem` | `100,000,000+` facts | independent replicas, stable contracts, horizontal operation, audited releases, contributor governance |

Rows alone never promote a lane. Promotion also requires representative scope, source-total reconciliation, durable public origin, clean-room restore, corrections, and a public delivery contract.

### 4.2 Mandatory million-scale SLOs

| Property | Gate |
| --- | --- |
| Provenance | `100%` of published claims resolve to an official source, retrieval, checksum, parser, and evidence row |
| Source URL | `100%` public URL or a documented immutable official-source replacement |
| Idempotence | replay creates zero duplicate logical facts and emits a reconciled delta |
| Work durability | every item is pending, leased, succeeded, or dead; no silent loss |
| Recovery | killed workers resume from durable state; expired leases are reclaimable |
| Memory | bounded by batch, shard, or document limits, never total corpus size |
| Fetch | `>=99.5%` after bounded retries for reachable in-contract items; every residual failure classified |
| Parse | `>=99%` for supported digital formats; OCR and unsupported formats separated |
| Reconciliation | discovered, fetched, stored, parsed, normalized, and published counts balance per run |
| Freshness | every source has an owner and measured SLA; overdue data is public status |
| Unknowns | missing, disputed, blocked, and `no_signal` remain explicit |
| Publication | manifests and bounded shards; no browser route loads a million-row blob |
| Corrections | accepted corrections appear in the next release with immutable history |
| Recovery drill | raw objects and analytical artifacts restore from a clean environment |
| Publication hygiene/security | official public fields retained exactly; secrets, local traces, and non-public state blocked; dependency and least-privilege checks pass |
| Cost | bytes, requests, CPU, memory, OCR pages, storage, and cost per `1,000` items reported |

### 4.3 Priority lanes

Each lane must reach `R2` independently:

1. actors: people, candidates, mandates, appointments, party offices, identifiers, aliases;
2. parliamentary action: initiatives, versions, amendments, signatories, votes, speeches;
3. documents: PDFs, HTML, attachments, OCR pages, extracted measures, document versions;
4. responsibility: rules, policy events, institutions, competences, delegation, current owner;
5. public money: budgets, execution, contracts, lots, awards, suppliers, subsidies, beneficiaries;
6. implementation: staffing, permits, inspections, sanctions, service delivery, audit findings;
7. outcomes: indicator observations, methodology versions, revisions, confounders;
8. accountability: issue ledgers, evidence edges, claims, counterevidence, corrections, appeals;
9. participation: review tasks, calibration, adjudication, contributor and release evidence.

## 5. Verified Baseline and Dated Proof Register — updated 2026-08-29

This section preserves dated milestone evidence. Its figures are verified snapshots, not a substitute for live operational status. `docs/etl/e2e-scrape-load-tracker.md` remains the authority for current commands, blockers, and mutable execution state; material direction changes still begin here.

`just etl-scale-readiness` currently validates seven materialized official-source corpora:

| Lane | Real rows | Files | Current proof | Promotion blockers |
| --- | ---: | ---: | --- | --- |
| Member votes | `1,809,222` | `8,373` gzip shards | every file, checksum, payload, member count, source record, and public URL audited; all `102,172` historical HTTP rows / `1,166` URLs classified without rewriting; checksum captures cover `33,683` rows / `484` URLs; durable HF origin and clean restore verified | immutable capture is missing for `68,489` rows / `682` URLs; two bounded HTTPS-equivalence probes returned `403`; official-total reconciliation and representative chamber history remain open |
| Eurostat indicators | `1,755,809` | `37` Parquet files | full provenance, schema/hash/row validation, `26/26` unchanged partitions reused; durable HF origin and clean restore verified | four-dataset scope is not representative; no second-snapshot revision proof; corrections workflow incomplete |
| PLACSP money facts | `263,302` | `50` Parquet files | v5 exact manifest/file/row/hash validation; all `128,849` source-published counterparty names and identifiers retained, including `8,260` natural-person and `3,058` unclassified rows; `50/50` unchanged partitions reused; durable HF origin and clean restore verified | incomplete historical universe; awards are not payments; identity resolution open |
| BDNS subsidy facts | `1,360,382` | `14` Parquet files | current v7 full-row validation and correct `s2_1m` capacity label; all `1,360,382` official beneficiary names and all `163,270` source-published identifiers retained; `1,419/1,419` queue/page/version/source/amount totals exact; `89/89` selected daily windows complete; durable HF origin and isolated clean-room restore verified | no second snapshot or full-history/representative reconciliation |
| Accountability ledger | `126,760` | `13` Parquet files | clean real-only rebuild; full source/URL/lineage validation; `13/13` unchanged partitions reused; `26` blank legacy source IDs explicitly inferred from allowlisted BOE URLs; durable HF origin and clean restore verified | parliamentary-heavy mix; below `R2` |
| Actor mandates | `88,031` | `108` Parquet files | official origins, full URL coverage, identity states, `108/108` unchanged partitions reused; durable HF origin and clean restore verified | below `R1`; uneven jurisdiction mix; external identity precision/recall open |
| Candidate occurrences | `10,820` effective / `42,056` captured base | `2` semantic Parquet files | exact official BOE names and source paragraphs retained for all `42,056` base rows; `10,820` reviewed effective rows have normalized person/party/source/document lineage; `88` are correction-backed; independent full validation; `2/2` unchanged partitions hardlinked; signed durable origin and isolated anonymous clean restore pass; all `776` pending correction paragraphs have immutable dual-review tasks backed by a deduplicated `3,713`-candidacy / `31,241`-candidate context corpus | eight historical correction documents remain unapplied and all `776` tasks await two independent human decisions; November 2019 has a source identifier defect; outcomes deliberately unknown; representative scope and `R2` remain open |

Current truth:

- registered real corpora: `7`;
- real million-scale row lanes: `3`;
- promoted lanes: `0`;
- document truth at `2026-08-30`, superseding older dated milestones retained below: exact source replay contains `337,704` provenance edges, `115,246` official public URLs, `111,600` HTTPS URLs, and `101,303` contract-eligible physically proven HTTPS URLs, so numeric supply has zero gap. The planner deterministically selects and preflights exactly `100,000` real rows (`98,748` BOE XML, `1,166` BOE summary XML, `86` Parliament HTML), selection SHA-256 `c81d3c0...`, zero blocked hosts, zero mock/synthetic rows, and exact public-information retention. Physical BOE state is not complete: `100,051/100,867` document successes, `1` dead timeout, `815` unfinished; `1,166/1,357` summaries succeeded and all `191` dead summaries are exact official `404`, but active document lineage references only `1,156/1,166` successful summaries. Current corpus processing covers `122,653` eligible instances / `120,801` content hashes / `5,652,067,717` instance bytes, verifies checksum plus public URL for `122,540` rows with `113` explicit provenance gaps and zero checksum conflicts, extracts `3,192,030,152` native public characters into `119,346` current CAS objects with zero failure/retry/dead/truncation, and validates `856/856` OCR pages / `131` OCR CAS. Exact locators cover every instance through `30,634` PDF pages, `782,814` source-derived major markup sections, `5,333` exact fallback spans, and `261` XLSX row groups; full raw/native replay recomputes `879,374` instance locators with zero mismatch. The observed format mix is `108,042` XML / `13,128` HTML / `1,437` PDF / `46` XLSX. All `44` distinct XLSX contents independently replay `2,827,577` nonempty rows / `28,615,639` cells; the instance inventory contains `2,845,172` worksheet rows. Zero observed formulas means formula correctness is unproven. XLSX row groups average `5.931818`, cap at `6`, and project `5,931,818` locator rows at one million workbooks under the `10M` ceiling. All `46` XLSX source mappings are path-inferred `mapped_unverified`, receive no provenance credit, and remain within the `113` gaps. Human review remains `0/40`; enforced central readiness fails on BOE lineage/queue checks. This closes numeric supply, deterministic planning, current native/OCR processing, and semantic PDF/XML/HTML/XLSX lineage—not representative acquisition, non-XLSX office formats, formula validation, durable remote origin/restore, human quality, or `1M`;
- repository proof: the completed Docker-backed run passes `1,473` Python tests (`12` contextual skips), and the Node suite passes `234/234`. All `130` staging SQLite databases pass the enforced integrity audit after two abandoned BDNS `running` markers were changed to explicit `error` state while preserving their real `0/0` and `100,000/100,000` seen/loaded counts. The latest real-only gate scans `153,948` files with zero findings, publication hygiene scans `17,293` artifacts with zero findings, repo-root hygiene passes, and the full static build generates `1,435/1,435` pages. The central control now atomically replaces stale success with `status=not_ready`, `foundation.ready=false`, and exact reason `BOE document corpus checks failed`. These gates deliberately retain official public-domain identity fields. This is local acceptance evidence; no remote publication was performed;
- candidate occurrences: seven exact BOE proclamation documents now preserve `42,056` immutable base nominations across `4,901` candidacies for the 2015, 2016, April 2019, May 2019, 2023 and 2024 election dates (`25,077` titular; `16,979` substitute; `185` not-proclaimed candidacies). Eleven correction documents preserve all `956` exact paragraphs. The reviewed three-document 2023/2024 base remains `10,815` rows / `1,188` candidacies and materializes through `17` exact operations into `10,820` effective nominations; its `180` reviewed correction paragraphs divide into `127` operation evidence and `53` structural/context rows. The other eight correction documents retain `776` exact paragraphs in `captured_unapplied`; a deterministic dual-review queue maps every paragraph to exact BOE URL/checksum/text and structural candidate hints, while one deduplicated JSONL retains their full `3,713` candidacies / `31,241` public candidate rows once. All `776` decisions remain blank, regeneration preserves completed human work or fails on evidence drift, and the `31,241` rows remain machine-blocked from effective state. The official November 2019 proclamation and corrections are captured in the document corpus but candidate ingestion fails closed because one candidacy heading omits its required number; no number is invented. Every captured base row keeps its exact public name, paragraph, URL, checksum, source record and document lineage. Every effective row has person, party, source-record and document-source lineage; `10,795` exact base person links are reused, `25` changed/new names receive source-scoped identities, and all `88` correction-backed rows receive immutable source records. The semantic artifact remains `2` Parquet partitions / `2,083,541` bytes, preserves all `10,820` effective names/text, validates fully, and replays `2/2` unchanged. Its signed analytical origin and isolated anonymous GET-only clean restore pass without suppressing official identity. The separate `8,926` elected outcomes remain another fact type; BOE `is_elected` stays null. Cross-source identity is not inferred; representative scope and `R2` remain open;
- BDNS: current partitioned durable acquisition and v7 artifact reconcile `1,360,382` official rows, `1,419` page captures, `1,360,382` immutable version sightings, exact official identity retention, correct `s2_1m` classification, and unchanged `14`-file replay; append-only expansion revalidated source totals and completed all `89/89` selected daily windows without retry or dead work;
- durable analytical origin: published content-addressed HF release v2 `5d9ce557...` is remotely verified for all seven registered corpora (`5,414,326` rows, `8,597` canonical data files, `500,714,815` data bytes) with no public-identity transformation. Its stable artifact contract `d7de5544...6565` exactly matches the current local data/provenance contract. Live pointer, manifest, registry/readiness metadata, corpus parity, real-only policy, and SSH Ed25519 attestation pass without errors or warnings. All seven registry flags remain `durable_public_origin=true`; external second-party reproduction remains open;
- clean-room recovery: the six historical corpora were restored into fresh empty caches and isolated validators full-validated all `5,403,506` rows / `8,595` data files. A separate seventh-lane drill restored candidate occurrences with anonymous GET only into a nonexistent destination, downloaded `8` selected files / `2,211,900` bytes with zero reuse, credentials, or remote mutation, and independently reconciled `10,820` rows / `2` Parquet files / `2,083,541` data bytes against bundled controls and the external signer policy. All seven registry flags are `clean_room_restore=true`; this does not claim raw-document-origin recovery, source-database reconstruction, historical completeness, representativeness, or promotion;
- explicit release recovery and rollback planning: restore accepts an exact `scale/snapshots/<date>/<full-manifest-sha256>` target and validates the path against the fetched manifest without reading `scale/latest.json`. A fresh full rollback-candidate drill against prior published release `623b4a5a...` recovered and checksum-verified `8,619/8,619` files / `504,093,303` bytes in `1,199.614s`, then independently full-validated all six corpora / `5,403,506` rows with official-public identity retention and peak RSS `1,007.453 MB`. A later GET-only plan rechecked current `5872efaf...` and target `623b4a5a...`, bound all evidence by SHA-256, proved zero row/file/byte delta, captured compare-and-swap expectations, and requires preservation of both immutable releases. It records `authorized=false` and `mutation_performed=false`. The disposable cache was removed after proof. Actual pointer activation, formal RPO and measured activation RTO remain open;
- analytical SQLite rebuild: the explicitly restored actor corpus rebuilds through bounded Parquet batches into an atomic SQLite artifact. Two independent runs reconcile `88,031` rows, `108` files, `9,236,064` input bytes, `88,031` unique mandate IDs, exact logical row hash `eb7fdb8e...`, integrity/FK checks, and identical `71,168,000`-byte DB SHA-256 `61cfdf8e...`. This proves deterministic analytical recovery, not yet reconstruction of the normalized production schema;
- outcome C2 portable delivery and review capacity: C2B packages all `2,865,602` real L0 pairs as `1,205` pair files plus `8` exact official-public identity files (`251,522,252` Parquet bytes total), retains `119,116` member-vote rows / `490` public names / `458` actions, and passes byte-exact canonical/replay parity. The canonical run was deliberately interrupted after `25` durable partitions, invalidated stale success controls, resumed those `25` checkpoints, and completed all `1,205` pair partitions; manifest root `81cc315e...` binds the recovery result while semantic `2afaf9ef...`, physical `f2d50fa5...`, and portable `049f9718...` roots remain exact. The independent scan runs in `376.845s` at `621.047 MiB` peak RSS and enforces a `1 GiB` ceiling; its `22` identity and `23` package adversarial tests pass. C2C, rebuilt under pinned Python `3.12`, materializes `2,865,603` real tasks / `2,865,604` slots in a `2,864,201,728`-byte SQLite artifact (SHA-256 `a97f9941...`), passes `330` independent checks at `159,727,616` bytes peak RSS and all `12` crash/resume/path/lease tests. Every trust-root, reviewer, authorization, conflict, assignment, claim, decision, adjudication, eligibility, promotion, release-binding and publication table is empty. These are local capacity facts only; durable remote origin, operational snapshot construction, real reviewers, promotion and publication remain open;
- accountability ledger: `126,760` real rows are recovered and validated after removing `10` fixture-derived money rows; the mix remains parliamentary-heavy and below `R2`;
- vote source transport: the disk-backed audit reconciles all `1,809,222` rows, `8,373` shard hashes and `6,426` distinct URLs. HTTPS covers `1,707,050` rows / `5,260` URLs. All `102,172` HTTP rows / `1,166` URLs are Senate legislatures 10 and 12; local checksum captures cover `33,683` rows / `484` URLs, while `68,489` rows / `682` URLs remain uncaptured. Two bounded HTTPS candidates returned `403` HTML, so historical URLs remain unchanged and promotion stays blocked;
- documents: the current disk-backed source-universe replay reconciles `337,704` real provenance edges into `115,246` official public URLs / `111,600` HTTPS. Exactly `101,303` HTTPS URLs satisfy the implemented semantic and physical contract, closing the numeric supply gap for `100k` while leaving representativeness under `DEC-01`. Planner v4 deterministically selects and preflights exactly `100,000` official rows (`98,748` BOE document XML, `1,166` BOE daily-summary XML, `86` Parliament of Andalusia HTML), selection SHA-256 `c81d3c0...`, with zero blocked hosts, zero mock/synthetic rows, and all public information retained. This is a complete plan, not a completed physical fetch. BOE summaries are terminal at `1,166` successes plus `191` exact official `404`; document acquisition is `100,051/100,867` success, `1` dead network timeout and `815` unfinished, while active lineage references `1,156/1,166` successful summaries. No repeat probe is authorized this sprint without a new transport lever. Current inventory contains `122,653` eligible official instances / `120,801` contents / `5,652,067,717` instance bytes. Native v3 processes all `120,801` contents into `3,192,030,152` public characters and `119,346` current CAS objects with zero failures, retries, dead work or truncation. Exact locator v5 generation covers `30,634` PDF pages + `782,814` major markup sections + `5,333` fallbacks + `261` XLSX row groups and independently replays all `879,374` instance locators without mismatch. The real format cohort is `108,042` XML / `13,128` HTML / `1,437` PDF / `46` XLSX. All `44` distinct XLSX contents replay independently; their `261` locators average `5.931818` and cap at `6`, projecting `5,931,818` at one million workbooks below the `10M` ceiling. The XLSX cohort has zero formulas, so formula correctness and non-XLSX office formats remain unproven. OCR validates `856/856` pages / `131` CAS; human review remains `0/40`. Numeric supply, exact planning, current native/OCR processing, and semantic PDF/XML/HTML/XLSX lineage close; physical BOE completion, representative selection, other office formats, formula validation, human quality, durable remote origin/restore, cold economics, and `1M` remain open;
- BOE lineage control: the current `100,051` real document rows publish as `11` immutable content-addressed gzip shards / `16,081,029` compressed bytes behind a `7,717`-byte manifest-last index. Logical SHA-256 `99739ca6...` binds the original `234,632,869` uncompressed bytes. An independent disk-bounded validator rehashes every shard, document, and referenced summary, enforces strict URL order and shard ceilings, and preserves official public information with zero mock/synthetic rows. Immutable index archives and activation receipts now preserve predecessor-linked supersession without deletion; the production full-shard lifecycle audit binds one active generation with zero orphan/unactivated/interrupted state, while a real-capture forced-interruption test proves the old index remains valid and both predecessor/successor generations survive a completed transition;
- raw-object origin: the current local drill checksum-replicates and clean-restores all `240,278` distinct real objects (`120,801` raw, `119,346` native CAS, `131` OCR CAS) / `6,048,142,788` payload bytes. `25` deterministic packs cap at `10,000` objects and `448 MiB` payload; full validation rehashes every object. Release `a891bbab...` binds `154` immutable files / `2,250,233,559` bytes. Local dry-run and live read-only Hugging Face collision preflight pass with zero conflict or mutation. Authorized append-only upload, remote parity, independent empty-root remote restore, retention/cost proof, and durable-public-origin status remain open;
- document provenance: the current audit reconciles all `122,653` eligible inventory rows, verifies checksum plus public URL for `122,540`, reports zero checksum/declared-byte conflicts, and emits `113` explicit gaps. All `46` XLSX source mappings are inferred from repository paths, remain `mapped_unverified`, have zero checksum-bound retrieval receipts, and receive no provenance credit. The no-network recovery lane classifies `26` seeded gap instances across three expected targets and `87` unseeded gaps, reuses the `43`-row checkpoint, performs zero requests, and publishes no false relation. Close gaps only with byte-identical immutable evidence or an exact primary-source manifest;
- readiness drift control: the builder validates the current inventory, registry counts, BOE summary/document manifests, provenance audit, gap queue, no-network recovery report/checkpoint, native extraction and full validation, exact locators, OCR and independent validation, human assignment contract, reviewed CSV, release controls, economics, and identity-retention policy. It treats unavailable cold-output benchmarks as explicit measurement gaps while keeping required integrity checks fail-closed. The enforced current run reaches and fails on `BOE document corpus checks failed`: active lineage references `1,156/1,166` successful summaries and the queue remains `100,051` success / `1` dead / `815` unfinished. No older green JSON becomes authoritative;
- corruption-risk publication: `0` promoted representative lanes and therefore no inferred high-risk public verdict is authorized.

Status: `LOCAL SCALE CONTROLS ADVANCED; CURRENT BOE READINESS BLOCKED; SOCIETAL SCALE INCOMPLETE`.

## 6. Target Architecture

### 6.1 Control plane

- One durable work contract for discovery, fetch, parse, OCR, normalize, identity, enrich, review, aggregate, and publish.
- Atomic claims, leases, heartbeats, retry classes, dead letters, host budgets, and circuit breakers.
- Stable payload references only; no document bytes inside queue rows.
- SQLite remains the reproducible snapshot and single-node baseline.
- Move operational coordination to a server database only after measured lock/throughput pressure; preserve SQLite export semantics.

### 6.2 Object plane

- Raw and derived bytes keyed by SHA-256.
- Stream to bounded partial files; publish only after checksum and size completion.
- Local disk is disposable cache.
- Versioned S3-compatible public origin is the durable source for public artifacts.
- Metadata includes URL, status, headers allowed by policy, size, checksum, retrieval, attempt, content type, and parser lineage.
- Retention, replication, encryption, lifecycle, and restore are explicit.

### 6.3 Transform plane

- Separate resumable stages with bounded batches.
- Additive schema evolution and stable public IDs.
- Input checksum plus transformer version controls invalidation.
- Unchanged inputs reuse verified partitions.
- Digital text extraction precedes OCR; OCR is page-scoped and cacheable.
- Model-assisted extraction creates evidence candidates, never unreviewed public allegations.

### 6.4 Analytical plane

- SQLite for canonical navigation and integrity constraints.
- Typed Parquet for high-volume immutable facts.
- Partition by bounded source/snapshot/jurisdiction/year keys.
- Manifests contain schema, counts, min/max, checksums, supersession, and source coverage.
- Aggregates rebuild from canonical facts; dashboards are never the only copy.

### 6.5 Public delivery plane

- Static-first citizen surfaces with bounded JSON indexes and drill-down shards.
- Public dataset/object origin for large analytical downloads.
- Stable cursors, content hashes, immutable release IDs, cache headers, and old-link tests.
- Every claim exposes freshness, coverage, uncertainty, evidence, correction state, and shareable state.

### 6.6 Integrity and review plane

- Signals are triage artifacts, not findings.
- High-risk publication requires corroboration, human review, conflict disclosure, counterevidence, right of reply where appropriate, and correction/version history.
- Official court, audit, or control-body findings remain distinct from project inference.
- Reviewer operational credentials and non-public session state follow least-exposure rules. Official public-domain identity evidence remains publishable and traceable.
- Million-scale review uses a generated candidate queue plus small append-only decision records keyed to immutable evidence/version IDs. Review tasks reference bounded evidence packets; they do not duplicate entire candidate, participant, or source corpora.
- Review operations must expose leases, heartbeat/reclaim, identified reviewers, calibration state, independent dual review, adjudication, conflicts, appeals, queue age, throughput, and correction SLA. Public-source names and identifiers remain in referenced evidence at every scale; task minimization is not identity redaction.

## 7. Delivery Program

Dependencies are strict. A later wave may prototype, but it cannot claim completion before its inputs pass.

### Wave 0 — Truthful foundation and artifact recovery

Target: two weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W0-001` | `PARTIAL 2026-08-13`: enforce official-real-only registry in local and CI readiness | none | six scale corpora pass file/provenance gates; all `25` configured fallback sources have immutable path/size/SHA-256/official-HTTPS registry entries, `9` deep sidecars validate against archived official captures, five inherited invented-person fixtures were replaced with exact public records, and `just etl-audit-official-samples` fails on drift or known invented/test markers; next: add equivalent capture-sidecar coverage to every legacy source rather than relying on the central hash registry alone |
| `W0-002` | Remove obsolete capacity-only outputs, generators, recipes, and roadmap claims | `W0-001` | repository search and artifact inventory show no such output used for readiness |
| `W0-003` | `DONE 2026-08-12`: regenerate and scale BDNS semantic root from fresh official acquisition | storage preflight | `1,360,382` rows; v6 manifest/full validation; exact source/amount/public-field balance; `1/1` unchanged partition reused through `14/14` hardlinks; validator peak RSS `292.719 MB` via disk-backed exact uniqueness |
| `W0-004` | `DONE 2026-08-12`: regenerate accountability-ledger root from current canonical evidence | BDNS optional; votes required | clean real-only root contains `126,760/126,760` lineage and public URLs, `126,757` resolved actor states plus `3` explicit unresolved states, full validation, `13/13` unchanged replay, durable origin and clean restore; the separate scale/representativeness gate remains open |
| `W0-005` | `PARTIAL 2026-08-30`: reconcile live document inventory to actual object/text files | none | current captured generation balances `122,607/122,607` eligible official rows / `120,757` contents / `5,524,892,735` bytes; `122,539` rows have checksum plus public URL and `68` gaps remain explicit with zero checksum conflict. All contents extract into `119,338` verified current text objects / `2,211,254,429` public characters with zero retry, dead work, failure, or truncation; every content and instance has independently replayed PDF-page, semantic markup-section, or exact fallback-span locators; `856/856` routed pages remain independently validated; `40` real review rows contain zero invented labels. Final BOE tail, post-tail regeneration, representative office-format acquisition, durable raw restore, and human review remain open |
| `W0-006` | Repair the 350 vote rows without public URLs or document a checksum-backed official replacement | official source availability | `DONE 2026-08-12`: verified Congreso capture URL plus official/captured checksums; `0` unexplained missing URL rows |
| `W0-007` | `PARTIAL 2026-08-12`: inventory official HTTP lineage and secure/capture immutable replacements | `W0-006` | all `102,172` HTTP rows / `1,166` URLs classified; `33,683` rows / `484` URLs have local checksum captures; `68,489` rows / `682` URLs still require immutable official captures or content-equivalent HTTPS; two bounded HTTPS probes returned `403`; promotion policy explicit and no silent rewrite |
| `W0-008` | `DONE 2026-08-13`: make tracker, technical roadmap, registry, readiness, and project knowledge match current artifacts | `W0-001..007` | registry-backed readiness machine-validates document inventory, provenance, native extraction, OCR, independent validations, and unlabeled human-review queue; no absent artifact is `DONE`; commands and next gates current |

Wave exit:

- current real artifacts are complete, named, independently validated, and recoverable locally;
- readiness report contains no stale or missing artifact claim;
- every open gap has owner, next command, input requirement, and exit gate.

### Wave 1 — Durable origin and clean-room recovery

Target: four weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W1-001` | `PARTIAL 2026-08-12`: use the existing public HF dataset for immutable analytical scale releases and retain S3-compatible CAS for raw objects | `W0` | scale path/version/latest contract implemented; raw-object bucket/retention contract still open |
| `W1-002` | `PARTIAL 2026-08-12`: upload immutable raw objects by SHA-256 | `W1-001` | 16-worker local CAS replay is idempotent for `6,792` real objects and full-manifest restore passes; remote S3-compatible upload, versioning/retention proof, and all-document coverage remain open |
| `W1-003` | `DONE 2026-08-19`: upload Parquet/shards/manifests as immutable release | `W1-001` | published signed release v2 `5d9ce557...` is content-addressed and remotely verified for `7` corpora / `5,414,326` rows / `8,597` data files / `500,714,815` data bytes; artifact, corpus, registry/readiness metadata, policy, and signature parity pass without warnings |
| `W1-004` | `DONE 2026-08-12`: add bounded origin-to-cache fetch by checksum | `W1-002` | worker streams atomically, verifies bytes/SHA-256, reuses verified files, checks storage before download, and restored all six real corpora from fresh empty caches |
| `W1-005` | `DONE 2026-08-24`: run clean-room restore of every registered analytical lane | `W1-003..004` | isolated no-project validators full-validate the six legacy corpora (`5,403,506` rows / `8,595` data files), and a fresh anonymous GET-only seventh-lane drill restores `candidate_occurrences` into a nonexistent root with `8` checksum-valid selected files plus `6` signed control files; bundled-registry validation reconciles `10,820` rows / `2` Parquet / `2,083,541` data bytes, exact `14`-file inventory, official public identity retention, zero cache reuse, zero credentials, and zero remote mutation |
| `W1-006` | Prove remote raw-object immutability, versioning, retention, lifecycle, and recovery | `W1-001..002` | independent configuration audit plus write/read/version/delete-guard/restore drill on a dedicated non-production prefix; secrets excluded; retention and recovery evidence current |
| `W1-007` | `PARTIAL 2026-08-12`: define RPO/RTO, release rollback, and supersession | `W1-003` | prior immutable release `623b4a5a...` full-restored `8,619` checksum-valid files / `504,093,303` bytes in `1,199.614s` and full-validated all six corpora / `5,403,506` rows. GET-only rollback plan from live `5872efaf...` passes all checks with zero data delta, evidence SHA bindings, compare-and-swap, immutable-release preservation, `authorized=false`, and `mutation_performed=false`; next: activate/revert under explicit authority, record supersession, approve formal RPO, and measure pointer activation RTO |
| `W1-008` | `PARTIAL 2026-08-12`: publish storage health without secrets or workstation paths | `W1-003` | public-safe local artifact aggregates real BDNS/PLACSP preflights, validates reserve/headroom arithmetic, hashes its evidence and omits roots/session/workstation state; next: place the artifact in the next explicitly authorized public release and monitor freshness |
| `W1-009` | `PARTIAL 2026-08-13`: publish exact official `source_records` instead of suppressing public identity evidence | `W0-001`, `W1-003` | HF packaging includes `source_records` by default and excludes only operational `raw_fetches`, `run_fetches`, and `lost_and_found`; the regenerated audit passes `231,438` exact rows / `269,872,457` raw-payload bytes / `34` sources, requires official public HTTP origin, rejects secrets/private-session/workstation markers, and reports `identity_fields_removed=0`; next: complete local Parquet packaging and publish/restore only with explicit release authority |

Wave exit: local disk can be lost without losing published evidence.

### Wave 2 — Real document and OCR factory

Target: six weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W2-001` | `DONE_FOR_CAPTURED_GENERATION 2026-08-30`: classify every real document by source, MIME, size, language, page count, encryption, and text density | `W0-005` | all `122,607` eligible instances / `120,757` contents classify source/MIME/size/format and carry a machine-language candidate or explicit unknown; all `1,437` PDFs classify `44,927` pages, text density and encryption (`1` encrypted). Full independent raw/CAS replay and a three-generation / `39`-shard lifecycle audit pass. Every machine label remains explicitly unreviewed; representative-language approval, human quality and final post-BOE regeneration remain open under `DEC-01`/`W2-006..007` |
| `W2-002` | `PARTIAL 2026-08-30`: apply per-host discovery/fetch budgets and politeness | `W1` | all requests remain behind host concurrency/start-interval controls. Worker now persists atomic progress, exact durable request events, conservative crash-window budget accounting, explicit host ceilings, redirect refusal, host-fair priority, and route-level circuits for HTTP hard failures plus network/timeout outages. Budget-only requeue requires exact zero-request terminal telemetry; transient requeue requires positive-request current-attempt telemetry. The BOE tail physically exercised request recovery and the `500,000` ceiling, then stopped under route failure. Source steward approval, recovered BOE health, representative strata, and complete `100k` acquisition remain open |
| `W2-003` | `PARTIAL 2026-08-30`: stream fetch with byte/time limits, checksum, partial cleanup, retries, and dead letters | `W2-002` | fresh control cohort remains `10,000/10,000` with zero failure. Historical BOE expansion advanced to `100,051/100,867` document successes / `3,064,836,413` bytes; `1` item is dead after three network-timeout attempts and `815` are unfinished. Exact current lineage is bounded into `11` content-addressed gzip shards / `16,081,029` compressed bytes plus a `7,717`-byte index; full independent validation rehashes all rows, raw captures and referenced summaries. Manifest archives, activation receipts, predecessor linkage, a full-shard lifecycle audit, and a real-capture forced-interruption/successor test prove manifest-last availability and non-destructive supersession. Only `1,156/1,166` successful summaries are referenced, so central readiness fails closed. Retry only after a new route-health lever; then requeue the telemetry-backed transient failure and reclaim expired leases normally |
| `W2-004` | `PARTIAL 2026-08-30`: extract digital PDF, HTML, and office text by page/section | `W2-001` | current captured corpus completes `122,607/122,607` instances / `120,757/120,757` contents, `2,211,254,429` public characters, `119,338` current text CAS, and zero retries/dead/failures/truncations. Algorithm-bound PDF normalization preserves real angle-bracket content. Scale-bounded locator v3 covers every content and instance with `30,634` exact PDF pages, `782,814` source-derived major XML/HTML sections across `119,473` contents, and `5,333` exact fallback spans across `322` contents where structure cannot be proven: `818,781` content / `879,104` instance locators, no copied public text. Independent replay rehashes all raw/native bytes and recomputes every locator with zero mismatch; lifecycle audit validates two retained generations / `126` shards. A rejected depth-3 canary exposed a `25,061`-locator outlier; the corrected major-container design averages `6.780402` locators/content, caps the observed maximum at `1,568`, and enforces `<=10` / `<=2,000`. Semantic PDF/HTML/XML lineage is closed for this captured generation. Real format evidence is exactly `108,042` XML / `13,128` HTML / `1,437` PDF / `0` office files, so office support remains unclaimed until a representative real cohort is acquired; final BOE generation and authorized durable public origin also remain open |
| `W2-005` | `DONE 2026-08-30` for the current real corpus: route only text-poor pages to OCR | `W2-004` | all `856/856` routed pages terminal and independently validated; reason, input manifest, engine/languages/version/configuration, state, and additive CAS persisted. The live OCR manifest is a `1,194`-byte terminal-only index over one immutable shard; archived index, activation receipt, and restored `589,824`-byte SQLite state pass the full lifecycle audit with zero orphan/unactivated/staging/delete state |
| `W2-006` | `PARTIAL 2026-08-30`: build a stratified 100,000-document official cohort | `W2-001..005` | numeric supply and exact planning pass. Independent replay sees `101,303` eligible HTTPS URLs and zero numeric gap. Planner pins exactly `100,000` real rows (`98,748` BOE XML, `1,166` BOE summaries, `86` Parliament HTML) with selection SHA-256 `c81d3c0...`; preflight validates every prior file/source contract, zero blocked hosts, zero mock/synthetic rows, public-information retention, bounded RSS, and a pristine queue. This cohort is numeric, not yet approved as representative. Physical current BOE acquisition remains `100,051/100,867`, human OCR quality remains `0/40`, and final full-cohort processing must be regenerated after BOE completion |
| `W2-007` | `PARTIAL 2026-08-30`: human-review extraction and OCR quality | current real corpus, then `W2-006` | deterministic `40`-page packet still covers every no-text/material-gain result and both source/reason groups after binding to current native/OCR manifests; `0/40` human decisions complete; next requires identified reviewers, two independent decisions, metrics by stratum, and adjudication. No machine label may fill the gap |
| `W2-008` | `PARTIAL 2026-08-30`: publish cost and throughput per 1,000 documents/pages | `W2-006` | prior fresh `10,000/10,000` acquisition economics remain valid for that exact run. Current native generation covers `120,757` contents / `5,312,661,661` raw-content bytes / `2,211,254,429` characters; the recorded cold v6 run was `223.155s` with `1.161 GB` self peak RSS, while the additive v7 repair reused existing CAS and is not a cold throughput measurement. Current OCR adds `856/856` pages in `107.887s`, `89,632` characters, `131` CAS, zero dead/retry. BOE tail telemetry records request-budget recovery and the route outage but cannot yield a completed `100k` cost denominator. Monetary cost remains `unknown_not_measured`, never zero; representative strata, provider rates, and completed physical `100k` remain open |
| `W2-009` | Scale to one million documents by source cohorts | `W2-006..008` | local full-corpus origin/restore and deterministic publication-pack mechanics now pass for `240,226` current objects / `5,902,879,469` bytes with bounded queue, shards, state, scratch, `25` packs and full rehash. Append-only release `9991abcb...` is collision-free in read-only remote preflight but not uploaded; still require explicit release authority, durable public origin, independent remote restore, representative real `1M`, `R2` SLO, bounded delivery, and correction path |

Wave exit: one million official documents are preserved and usable, not merely downloaded.

### Wave 3 — Actors, candidates, offices, and identity

Target: eight weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W3-001` | `PARTIAL 2026-08-13`: establish reproducible official candidate origins | external lever | seven BOE proclamation documents plus eleven correction documents are checksum-preserved and machine-reconciled; sparse exact-date and exact-ID acquisition fails closed on missing IDs; the November 2019 source defect and reproducible Interior archive access remain blocked |
| `W3-002` | `PARTIAL 2026-08-13`: ingest official election cohorts and retain every official public identity field | `W3-001` | BOE base capture preserves `42,056` immutable occurrences / `4,901` candidacies and all `956` exact correction paragraphs. The reviewed subset preserves `10,815` base rows / `1,188` candidacies; `127` paragraphs support `17` operations, `53` remain context, and effective state reaches `10,820` normalized rows. Eight correction documents / `776` paragraphs and their `31,241` base candidates remain explicit pending evidence barred from effective output. A deterministic `776`-task dual-review queue and deduplicated `3,713`-candidacy / `31,241`-candidate context corpus preserve every public field and reject invented or drifted decisions. The semantic artifact validates full public-name/source-text/lineage retention, keeps outcomes null, and replays `2/2` unchanged files; next: complete dual review and adjudication, compile accepted operations per document, resolve the November 2019 source identifier defect without inference, add result links as separate facts, authorize durable release/restore, and extend cohorts |
| `W3-003` | Add official regional and municipal candidacy/result sources | source contracts | jurisdiction/election coverage matrix and source totals |
| `W3-004` | Add party-office and political-appointment history | official registries/bulletins | appointment/dismissal dates and appointing authority traceable |
| `W3-005` | `IN PROGRESS — LOCAL VALIDATED, PENDING PUBLICATION 2026-08-23`: time-aware actor graph and entity resolution v1 | `W3-002..004`, core ontology | real projection materializes `133,595` source-scoped actors, `237,973` relationships/evidence, `79,208` public identifiers and `4,186` aliases; `55/55` source origins mapped, including all `3` conflicting upstream IDs as `7` deterministic namespaced origins; `0` inherited actor-lifespan dates, cross-source/name merges or unsupported organization-change events. Independent full-row validator, FK/integrity, atomic-failure safety and actual producer replay pass with release `e52dd7fa...` / JSON `9272fb73...`; the rebuilt `1,436,168,192`-byte SQLite source now contains and uses `idx_actor_graph_node_versions_release_source_actor`. Lossless Parquet reconciles `1,331,749` rows in `179` partitions / `183` Zstd files, including `2,396,140` FK references with `0` missing; incremental replay reuses `179/179`. Static `/actor-graph/` live publication remains before this source-scoped MVP is DONE. Gold set, multi-snapshot history, durable origin/restore, one-million representative actor facts and relationship-shell promotion remain in `W3-006..008` |
| `W3-006` | Create stratified adjudicated identity gold set | `W3-005` | dual review, adjudication, precision/recall by source and name pattern |
| `W3-007` | Add immutable merge/split history | `W3-005` | old evidence identities remain reconstructable |
| `W3-008` | Reach one million real actor/candidate/mandate/appointment rows | `W3-002..007` | `R2` manifest, identity quality, restore, public origin, corrections |

Wave exit: public actor histories never depend on an unreviewed ambiguous identity merge.

### Wave 4 — Parliamentary decisions and text-at-decision

Target: eight weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W4-001` | Complete Congress/Senate legislature/session discovery | source contracts | official event totals and missing ranges published |
| `W4-002` | Preserve initiative and amendment versions | `W2` | text-at-vote-time distinct from later consolidated text |
| `W4-003` | Ingest signatories, speeches, committee stages, and group/member votes | `W4-001..002` | source totals and FK balance per chamber/legislature |
| `W4-004` | Preserve yes/no/abstain/absence/no-vote as distinct source states | `W4-003` | no fabricated member assignment from aggregate gaps |
| `W4-005` | Repair or classify all vote-total mismatches | `W4-003..004` | each mismatch has a source-supported reason or open incident |
| `W4-006` | Link actors through reviewed source identities | `W3`, `W4-003` | link quality reported; unresolved visible |
| `W4-007` | Publish million-row analytical facts and bounded drill-down shards | `W4-003..006` | `R2` validation, origin, restore, public payload budget |

Wave exit: a vote explainer reproduces the official decision, people, text, totals, provenance, and known gaps.

### Wave 5 — Money, implementation, and enforcement

Target: twelve weeks. Priority: `P0`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W5-001` | Expand PLACSP through complete bounded official archive cohorts | `W1` storage | gap-free period catalog, version/tombstone balance, one million real facts |
| `W5-002` | `PARTIAL 2026-08-12`: complete BDNS pagination and revision handling | `W0-003`, `W1` storage | selected-window pagination is complete at `89/89`; durable HF origin and empty-cache restore pass; worker preflight fails closed before claim and the latest check is `blocked_storage` with headroom `-5,177,384,960`; next: restore storage headroom, then second snapshot/revisions and full historical cohorts |
| `W5-003` | Add budget appropriations and execution | official source contract | budget version, unit, program, territory, and execution semantics preserved |
| `W5-004` | Separate notice, award, modification, invoice, payment, and budget execution | `W5-001..003` | no award represented as payment |
| `W5-005` | Resolve counterparties with reviewed identifiers and merge history | `W3-005..007` | entity precision/recall; official natural-person identifiers retained with provenance |
| `W5-006` | Add inspections, sanctions, permits, staffing, and audit findings | official sources | typed implementation facts with authority and effective dates |
| `W5-007` | Reconcile monetary totals by source, period, currency, tax treatment, and revision | `W5-001..006` | declared discrepancies and no float-induced drift |
| `W5-008` | Publish bounded public-money dossiers | `W5-007` | source-to-entity-to-contract-to-payment evidence chain |
| `W5-009` | `DONE 2026-08-19`: establish the canonical spending-event contract and first public PLACSP path | `W5-001`, `W5-004` | spec fixes `14` event kinds, exact-decimal, actor, evidence, version and scale semantics; release `7abe9ac6...` materializes `20` real awards / `40` actors / `38` evidence rows from the official `330,577`-record corpus, validates the exact `146,382,691`-byte archive, preserves `10/5/5` legal/natural/unclassified identities, reconciles `4,835,494.71 EUR`, and is live at `/spending/` with award != payment. Next: full partitioned canonical materialization, second snapshot/history, and first evidence-backed award -> contract/payment/delivery link |

Wave exit: the product distinguishes promised, budgeted, contracted, paid, delivered, inspected, sanctioned, and unknown.

### Wave 6 — Responsibility and issue ledgers

Target: ten weeks. Priority: `P1`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W6-001` | Ingest BOE and official bulletin rules, decrees, orders, resolutions, and appointments | `W2` | originator, approver, publisher, effective date, version, repeal state |
| `W6-002` | Model competence, delegation, transfer, oversight, and current owner | official legal sources | time-bounded responsibility edge with evidence |
| `W6-003` | Define controlled issue taxonomy and versioned codebook | domain review | inclusion/exclusion examples and change history |
| `W6-004` | Extract measures and obligations from official text | `W2`, `W6-003` | evidence span, extractor version, confidence, review state |
| `W6-005` | Link promises, decisions, rules, money, implementation, enforcement, audits, and outcomes | `W4..006`, `W5` | every edge typed and traceable; unknown edges explicit |
| `W6-006` | Rebuild the accountability ledger to one million representative facts | `W6-001..005` | domain/source/role mix, actor quality, `R2` origin/restore/corrections |
| `W6-007` | Publish three complete issue-led dossiers | `W6-006` | citizen can see who did what, who owns it now, and what is missing |
| `W6-008` | `DONE 2026-08-19`: canonical promise model and first official manifesto slice | `W2-004`, `W6-003` | additive direct-party model covers explicit promises, soft commitments, preferences, slogans, coalition commitments, positions and context; checksum-pinned BNG 2023 PDF yields `266` page-aware claims / `266` exact evidence anchors / `91` rule-confirmed promises / `323` topic links; live `/promises/` sample contains `20` real source-linked promises, keeps `6` incomplete fragments out and makes fulfillment `not_assessed`; idempotence, FK, quote/page/hash, real-only and live origin gates pass, including exact `396,842`-byte official PDF hash. Next: second ideologically distinct manifesto and human adjudication sample |
| `W6-009` | `DONE 2026-08-19`: canonical agreements, meetings, lobbying and influence contract plus first official executive path | `W2`, `W6-003` | spec v1 and `11` additive tables separate meetings, roles, agenda, agreements, evidence, topics and influence assertions. Official La Moncloa capture `21,234` bytes / SHA `ab08b7dc...` yields `11` sessions, `11` adopted agreements, `37` parties, `20` visibly derived/unreviewed topics and `22` exact evidence anchors; attendance claims `0`, influence assertions `0`. Release `6f75ec32...` / JSON `8d8ce219...` passes deterministic replay, FK, integrity, real-only, public-hygiene and browser gates; live `/agreements/`, exact JSON and three official source pages return HTTP `200`. Next: official agenda/lobby disclosure with published personal identities, second snapshot/history, and agreement -> implementation evidence |
| `W6-010` | `DONE 2026-08-20`: canonical geopolitics contract and first official foreign-policy path | `W2`, `W6-003`, `W6-009` | spec v1 and `8` additive tables cover treaties, resolutions, sanctions, aid, defence, international votes, action actors/evidence/topics/links, explicit positions and later observations with `10M/100M/1M` scale boundaries. Real-only release `6683fd44...` / JSON `ea8c3eb1...` materializes the `2` exact international procedures in the pinned `21,234`-byte Moncloa capture as `2` actions / `11` actors / `2` evidence rows / `4` derived topics / `2` agreement links; positions, later observations, entry-into-force, implementation and geopolitical inference remain `0`/not assessed. Replay, FK, integrity and UI tests pass; live `/geopolitics/`, exact JSON and both official source pages return HTTP `200`; desktop/mobile browser QA and the current `44`-route audit pass. Next: `TODO 28`, time-aware actor graph and entity resolution |
| `W6-011` | `IN PROGRESS — LOCAL VALIDATED, PENDING PUBLICATION 2026-08-20`: promise/action comparison engine C1 | `W3-005`, `W4`, `W6-008` | method v1 and `4` additive tables materialize `5` explicit real assessments / `18` evidence rows: `3 ambiguous_mapping`, `1 insufficient_evidence`, `1 not_comparable`, `0 aligned/conflicted/changed_framing`. Independent reconstruction, deterministic replay, FK/integrity, public-identity retention and UI contract pass for release `ea65f3b8...` / JSON `24b6edd0...`; release identity closes over the action cutoff, actor-graph release, four action pairs and the exact ordered projection of all `97` real rows observed by the bounded search. A real SQLite header-only drift replay preserves exact derived bytes. V1 rejects `changed_framing` until actor-authored change evidence and its gate exist. Action corpus cutoff `2026-02-12` is stale, ranking remains hidden, million-row physical execution is unproven and promotion is per-file atomic but not artifact-set atomic. `/comparisons/` and exact asset are local only; live route/hash audit remains before `TODO 29` or this item can close |

Wave exit: responsibility attribution is temporal, sourced, and separable from political rhetoric.

### Wave 7 — Outcomes and causal discipline

Target: eight weeks. Priority: `P1`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W7-001` | Approve representative indicator codebook | domain review | unit, geography, frequency, methodology, known breaks, intended use |
| `W7-002` | Add official national, regional, and municipal outcome sources | `W7-001` | source contracts and coverage matrix |
| `W7-003` | Capture second and later snapshots with revisions/deletions | `W7-002` | unchanged/changed/deleted observations version correctly |
| `W7-004` | Reach one million representative outcome observations | `W7-002..003` | `R2` validation, origin, restore, correction workflow |
| `W7-005` | Define descriptive, associational, quasi-experimental, and causal claim levels | methodology review | UI language and publication gate per level |
| `W7-006` | Record confounders, comparison group, sensitivity, and caveats | `W7-005` | causal claim cannot publish without method evidence |
| `W7-007` | Link observed outcomes to issue ledgers conservatively | `W6`, `W7-006` | chronology shown separately from causality |
| `W7-008` | `PARTIAL — FIRST VERTICAL SLICE DONE 2026-08-20`: canonical indicator/revision contract and first public Eurostat family | `W1`, `W7-001..003` | The bounded first slice is implemented and live: spec v1 plus `5` additive tables preserve release/vintage, revision lineage, exact decimal text, source status, uncertainty, geography, interval, methodology and cell-level provenance. Release `a5d27828...` materializes one pinned official Eurostat family into `86` Spanish territorial series / `2,091` observations / `2,091` evidence pointers / `113` provisional marks. Independent raw-cell replay, FK/integrity, real-only, public-hygiene and UI tests pass. Live `/indicators/` and exact `2,448,614`-byte JSON pass desktop/mobile QA; dataset/methodology/reuse links return `200`; global audit passes `44` routes / `48` critical assets / `119` evidence objects. This slice does not close its dependencies: `W7-001..003` remain open for an approved representative codebook and second official snapshot with observed changed/unchanged/deleted revisions. The validated `1,755,809`-observation corpus proves real processing scale, not representative outcomes |
| `W7-009` | `IN PROGRESS — C1 LOCAL PACKAGE/BUILD PASS; C2A+C2B LOCAL DELIVERY PASS; LIVE/REMOTE ORIGIN/REVIEW OPEN 2026-08-24`: outcome context | `W3-005`, bounded `W4-002..006`, `W6`, `W7-005..008` | C1's `9` append-only tables materialize one real pending candidate over `20` initiative-linked Senate votes, `25` Eurostat observations and `264` named public participants; `2,973` independent checks pass; reviews/releases/memberships/validated/public links remain `0`. Public v3 is `4,078` bytes / SHA `226dfdf9...`; package `5ac01878...` binds `17` exact assets, preserves all `264` public names, and passes local build/browser gates. C2A physically validates `33,726` pairs with `111` checks. C2B keeps the `3,587,743,744`-byte / SHA `04c82651...` source planner separate from an exact public-identity companion (`119,116` member-vote rows, `490` names, `458` actions, `8` Parquet / `5,366,852` bytes; semantic `e6891375...`) and a portable package covering all `2,865,602` L0 rows in `1,205` pair plus `8` identity Parquet files / `251,522,252` bytes. Package semantic root `2afaf9ef...`, physical root `f2d50fa5...`, and portable root `049f9718...` survive intentional interruption, 25-checkpoint resume, full validation, copy-only replay, and exact byte comparison; ranking/publication-eligible rows=`0`. All C2 rows remain internal L0 and claim-free. Remote C1 publication, durable remote C2 origin/restore/rollback, original vote XML, actor-source capture, identified human review and any L2/public outcome link remain open |

Wave exit: the product can say what changed without implying unsupported causation.

### Wave 8 — Integrity signals, review, and corrections

Target: eight weeks. Priority: `P0` before any high-risk public inference.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W8-001` | Version review task, evidence, confidence, disagreement, and adjudication contracts | `W0` | append-only review history |
| `W8-002` | Create real historical review calibration set from official findings | legal/editorial review | gold labels cite court/audit/control-body sources |
| `W8-003` | Define signal thresholds and minimum cohorts | `W5`, `W8-002` | small-cohort and missing-data suppression tested |
| `W8-004` | Require corroboration and conflict disclosure | `W8-003` | no single weak signal can become public high-risk claim |
| `W8-005` | Implement counterevidence, appeal, right-of-reply, and correction queues | `W8-001` | each path reaches public supersession state |
| `W8-006` | Measure agreement, reversal, drift, correction latency, and queue age | `W8-002..005` | release scorecard |
| `W8-007` | Publish only reviewed signals with evidence cards and limitations | `W8-003..006` | legal/editorial/publication-hygiene gate and immutable claim version |
| `W8-008` | `PARTIAL — C2C CAPACITY LOCAL PASS; REAL OPERATIONS/PROMOTION/RELEASE OPEN 2026-08-29`: operate a million-task human review and control plane | `W1`, `W8-001..006` | immutable capacity snapshot materializes `2,865,603` real tasks and `2,865,604` required slots while retaining bounded links to exact official-public identity evidence. Python `3.12` is pinned because host-runtime drift changed physical SQLite hashes; current DB is `2,864,201,728` bytes / SHA `a97f9941...`, semantic root `21acddf2...`, and passes `330` independent checks plus `12` real-artifact crash/resume/path/lease tests. Capacity contains zero trust roots, reviewers, authorizations, conflicts, assignments, claims, decisions, adjudications, semantic/public eligibility events, promotions, release bindings or publications. Completion still requires a separately versioned operational snapshot with real externally authorized identities plus atomic leases, heartbeat/reclaim, calibration, dual review, adjudication, appeals, queue-age/throughput SLOs, correction SLA and immutable release evidence |

Wave exit: a disputed claim can be audited and corrected without erasing history.

### Wave 9 — Public product and open-source scale

Target: continuous after Wave 1; promotion gate after Waves 3-8. Priority: `P1`.

| ID | Task | Dependency | Exit evidence |
| --- | --- | --- | --- |
| `W9-001` | `DONE 2026-08-19`: publish source coverage and obstruction map | `W0` | live `/obstruction-tracker/` and v2 feed expose freshness, completeness, last run, `27` open incidents / `14` blocked sources, `7` real corpora / `3` million-row lanes / `4` promotion gaps, and `119/119` internally hosted evidence files; `7` copies redact only operational private traces, `112` remain byte-equivalent, public-domain personal information is retained, and the live audit passes `44` routes / `48` critical assets / `119` evidence objects with zero failures |
| `W9-002` | Publish vote, actor, issue, money, and responsibility explainers | corresponding lanes | primary evidence within three meaningful interactions |
| `W9-003` | `DONE 2026-08-19`: publish stable Evidence API and schema compatibility policy | `W1`, analytical contracts | live `/api/v1/index.json` points to immutable API release `feb61b39...`, derived from exact source/schema/exporter/upstream hashes; `4` collections expose `5,830` real objects in `26` content-addressed pages with opaque seek cursors, per-record provenance, explicit unknown states, `180`-day / `2`-release deprecation policy and `1,147/1,147` public labels retained exactly; live verifier fetched `32` files / `11,452,986` bytes with zero errors. Promise, spending, agreements, geopolitics and indicators vertical slices are live. Next: `TODO 28`, time-aware actor graph and entity resolution |
| `W9-004` | Provide source-adapter SDK and one-command validation | pipeline contracts | new contributor runs capture-to-artifact without private state |
| `W9-005` | Create bounded starter issues and maintainer ownership map | `W9-004` | no critical lane has one undocumented owner |
| `W9-006` | Require two-person review for schema, identity, publication, and allegation-policy changes | governance | protected ownership and review evidence |
| `W9-007` | Publish contributor, review, data-correction, security, and citation paths | none | response SLO and templates visible |
| `W9-008` | Measure first-contribution time, review latency, retention, bus factor, and source adoption | `W9-004..007` | quarterly community scorecard |
| `W9-009` | Support independent snapshot replicas and reproducibility attestations | `W1`, `W9-003` | external maintainer reproduces and signs release manifest |
| `W9-010` | `DONE 2026-08-19`: publish operational transparency dashboard and release-note flow | `W1`, `W9-001` | live `/transparency/` and v1 feed expose `10` source-linked metrics, source freshness/health, `27` open obstructions / `119` evidence files, local readiness, signed durable release `5d9ce557...` with `5,414,326` real rows / `8,597` data files, current metadata, and `10` real release notes; build covers `1,433` static routes and live audit covers `44` routes / `48` critical assets / `119` evidence objects |
| `W9-011` | `DONE 2026-08-19`: freeze core ontology v1 and current-schema bridge | contributor platform | human + machine contracts define `19` concepts, `26` evidence-backed relation types, ID/time/provenance/uncertainty rules, `49` mappings to current real schema tables, official-only/public-identity policy, and `10M` fact / `1M` document / `100M` no-rewrite scale boundaries; fail-closed validator and `8` tests pass |
| `W9-012` | `DONE 2026-08-19`: freeze plugin architecture v1 | `W9-011` | human + JSON Schema contracts define `7` plugin types, `14` lifecycle hooks, `19` ontology outputs, `10` mandatory real-data test hooks, bounded partitions, capability security, at-least-once execution with logical exactly-once effects, official-capture provenance, and public-identity retention; fail-closed validator and `8` tests pass |
| `W9-013` | `DONE 2026-08-19`: ship minimal SDK and official reference plugin | `W9-012` | typed loader/registry/contracts plus Congreso reference plugin replay one checksum-pinned `2,073`-byte official capture into the standard SQLite schema twice; `3` exact public records remain `3` source records / `3` mandates / `3` linked persons, `0` FK failures, stable logical hash, exact source URL, idempotence, and public identity retention; `10` focused tests plus global official-sample audit pass |
| `W9-014` | `DONE 2026-08-19`: publish signed reproducible scale snapshot flow | `W1`, `W9-011` | immutable live release `5d9ce557...` signs the exact manifest and artifact contract with SSH Ed25519; independent live checks reconcile `7` real corpora / `5,414,326` rows / `8,597` data files / `500,714,815` data bytes, current registry/readiness, real-only policy and official public identity retention; exact prior/current diff reports `6` added / `2` changed / `0` removed / `8,617` unchanged bundle files; private key remains outside Git/publication and `W9-009` stays open for an external maintainer's second attestation |

Wave exit: three independent maintainers can ship a connector or review batch, and an external party can reproduce a release.

## 8. Critical Path

The following is the societal-scale dependency order. Immediate delivery follows `L0–L5` above; broader acquisition and lane promotion are not prerequisites for a separately validated, explicitly limited public alpha.

1. `W0`: truthful artifact inventory and recovery.
2. `W1`: durable public origin and clean restore.
3. `W2`: preserve zero-gap numeric supply; recover BOE transport only after a new lever; finish and enforce the `100,867`-document source queue; approve `DEC-01`; execute the exact `100,000` cohort physically; regenerate final inventory/provenance/text/OCR; close human quality and raw-origin restore; then reach document `R2`.
4. `W3` and `W4`: actor identity and parliamentary completeness.
5. `W5`: money, implementation, and enforcement.
6. `W6`: responsibility and issue ledgers.
7. `W7`: representative outcomes and causal guardrails.
8. `W8`: high-risk review/correction machinery.
9. `W9`: public product, API, and contributor replication throughout, with final promotion after upstream gates.

Parallelism allowed:

- W1 storage contract can start while W0 artifact recovery finishes.
- W2 document inventory can start from current real objects while W1 origin is prepared.
- W3 official-source discovery and W4 reconciliation can proceed independently.
- W9 documentation, source catalog, and safe public explainers can ship continuously.

Parallelism forbidden:

- no public inferred integrity signal before W8;
- no identity merge before adjudicated identity evidence;
- no causal claim before W7 methodology gate;
- no lane promotion from row count alone;
- no source marked complete while official totals or time ranges remain unknown.

## 9. Release And Accountability Cadence

Every ingestion run emits:

- source and snapshot identity,
- discovered/fetched/stored/parsed/normalized/published counts,
- bytes and checksums,
- attempts, retries, dead items, and blocker classes,
- elapsed time, CPU, RSS, and storage delta,
- parser/schema versions,
- freshness and source-total reconciliation,
- publication-hygiene findings,
- current limitations and next action.

Every weekly closeout:

- update the tracker from generated evidence,
- publish visible progress under repository control,
- close or reclassify stale work,
- run publication hygiene, integrity, readiness, and relevant tests,
- list newly observed blockers and owners.

Every public release:

- immutable release manifest,
- schema and method changelog,
- source coverage and freshness report,
- validation and publication-hygiene reports,
- known limitations,
- corrections and superseded claims,
- restore attestation,
- rollback pointer.

Every quarter:

- coverage matrix by jurisdiction, time, source, and lane,
- SLO and cost scorecard,
- correction and reversal analysis,
- identity and extraction quality sample,
- community health and bus-factor scorecard,
- roadmap re-prioritization based on public impact and evidence gaps.

## 10. Success Metrics

Data:

- real rows/documents by lane and scale class;
- official universe coverage by source and period;
- provenance, public URL, and source-record coverage;
- source-total and monetary reconciliation;
- identity precision/recall and unresolved rate;
- extraction/OCR quality by stratum;
- freshness and source-drift incidents.

Operations:

- successful unattended refreshes;
- queue age, retry rate, dead rate, recovery time;
- throughput, peak RSS, storage growth, and cost per `1,000`;
- clean restore time and checksum success;
- release rollback time.

Public value:

- evidence drill-down completion;
- explainers used and shared;
- correction response and publication latency;
- citations by journalists, researchers, civil society, and public bodies;
- documented decisions improved or errors corrected because evidence was available.

Community:

- active maintainers and reviewers;
- first-contribution time and review latency;
- contributor retention;
- independently maintained source adapters;
- independent release reproductions;
- critical-lane bus factor.

## 11. Definition Of Societal-Scale Done

The goal is achieved only when all are true:

- every priority lane reaches `R2` with official real records or the complete documented official universe when smaller;
- at least the core vote, actor, document, money, responsibility, outcome, and correction lanes have durable public origins and clean-room restores;
- national-history lanes operate incrementally with declared freshness and cost SLOs;
- public routes remain bounded, accessible, evidence-first, and reproducible;
- identity, extraction, and review quality are measured on adjudicated official evidence;
- integrity signals cannot bypass corroboration, human review, counterevidence, and correction;
- releases are auditable, reversible, retain official public-domain identity, exclude secrets/non-public state, and are independently reproducible;
- at least three independent maintainers can operate critical paths;
- no known missing evidence or blocked source is mislabeled as complete.

Until then, the system may be useful and impactful, but the societal-scale goal remains open.

## Sources and Evidence

This layer records planning evidence. It does not replace artifact validators or the operational tracker.

### Source inventory

| Source ID | Source | Date/version | Authority | Limits or staleness |
| --- | --- | --- | --- | --- |
| `SRC-01` | Maintainer mandate recorded in this file, §§1, 3, 4, and 11 | `2026-08-23` | Highest for mission, real-data policy, public-identity retention, scale, and completion | Does not prove implementation or live state. |
| `SRC-02` | `ROADMAP.md`, §§5-10 and work items `W0..W9` | working tree `2026-08-30` | Canonical direction, sequence, and declared status | Status claims require cited generated evidence; this planning layer cannot upgrade them. |
| `SRC-03` | `docs/etl/real-corpus-registry.json` and `etl/data/published/scale-readiness-latest.json` | current local artifacts inspected `2026-08-30` | Machine authority for registered corpora and readiness flags | Current artifact is atomically replaced with `not_ready` / `foundation.ready=false` on the incomplete BOE corpus checks; no prior success remains authoritative. |
| `SRC-04` | `docs/etl/e2e-scrape-load-tracker.md` | current working tree `2026-08-30` | Operational source/pipeline status and evidence links | Large append-only log; newest evidence wins, unresolved contradictions stay visible. |
| `SRC-05` | `docs/roadmap-tecnico.md` | updated `2026-08-30` | Near-term derived execution and `SCALE*`/`ACC*`/`OUT*`/`INT*`/`PUB*` IDs | Cannot create scope or mark canonical work complete. |
| `SRC-06` | `docs/etl/sprints/ACTOR-GRAPH-20260820/evidence/actor-graph-validation.json` and partition validation | current local evidence | Strongest current actor-graph validation | Local validation does not prove live publication, durable origin, representative identity quality, or external reproduction. |
| `SRC-07` | `docs/etl/sprints/COMPARISON-ENGINE-20260820/evidence/promise-action-comparisons-validation.json` | current local evidence | Strongest current C1 comparison validation | Five assessments are bounded coverage; live publication and million-scale execution remain unverified. |
| `SRC-08` | `docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/outcome-context-validation.json`, public v3 package, and `reports/outcome-context-c0-l1.md` | current local evidence `2026-08-23` | Strongest current outcome C0/L1 validation, exact public package and limitations | Local package/build/audit do not prove live publication; C2 and human review are not proven by C1. |
| `SRC-09` | `docs/etl/name-and-shame-access-blockers.md` | append-only through `2026-08-23` | Canonical confirmed public-data obstruction history | Records observed access failures, not motive or institutional intent. |
| `SRC-10` | Schema, materializers, validators, tests, build outputs, and live route checks referenced by each `W*` item | per-artifact versions | Implementation and acceptance evidence | A test or local file alone never proves production/live behavior. |
| `SRC-11` | C2A/C2B pinned scope files, planner/validator code, physical SQLite source planners, manifests, receipts, exact tests, and independent acceptance audit | working tree and audit `2026-08-24` | Current local C2 eligibility scope, source-planner execution, interruption/resume, parity and local-restore evidence | Planner proof does not establish portable delivery, durable remote origin, public release, analytical relationship validity or lane promotion. |
| `SRC-12` | C2B identity audit/companion plus portable package manifest, report, canonical validation, replay validation, pinned Python/PyArrow contract and adversarial tests under `docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/` | local artifacts and independent audit `2026-08-29` | Exact official-name retention, bounded Parquet delivery, manifest/physical/portable roots, interruption/resume, hard-link fail-closed controls and byte-exact replay | Workstation-local packaging does not prove durable remote origin, human review, semantic validity, promotion or public release. |
| `SRC-13` | C2C pinned real scope, additive schema, pinned Python runtime, capacity materializer, validator, operator capability report, manifest/report/validation and adversarial tests | local artifacts and independent audit `2026-08-29` | Million-task capacity, deterministic physical rebuild, immutable capacity/operations separation, append-only event contracts and zero-human-event truth | Capacity is not reviewer operation; real trust roots, reviewers, authorizations, conflicts, assignments, decisions, adjudication, promotion and publication remain open. |
| `SRC-14` | Exact `100k` planner/preflight validations, current BOE corpus/fetch checkpoint, source-universe replay/validation, inventory/provenance/native/OCR validations, BOE/native/OCR lifecycle audits, and BOE timeout incident under `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/` | local physical evidence `2026-08-30` | Strongest current document numeric-supply, deterministic-plan, captured-corpus processing, bounded activation/state-restore, queue-state, request-failure, and policy evidence | Does not prove representative selection, complete physical acquisition, human quality, remote publication, or `1M`. |
| `SRC-15` | Current XLSX lineage, independent XLSX/native/locator validations, provenance audit, local origin/restore/pack/release reports, read-only HF preflight, and factory economics reports under `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/` | local physical and remote read-only evidence `2026-08-30` | Strongest current XLSX semantic replay, locator-fanout, current-object recovery/package, remote collision, and measurement-boundary evidence | Inferred XLSX URLs are not provenance; zero formulas do not validate formula semantics; warm-output telemetry is not a cold benchmark; read-only preflight is not publication or durable remote recovery. |

### Atomic claim ledger

| Claim ID | Normalized claim | Source | Evidence status | Decision impact | Destination |
| --- | --- | --- | --- | --- | --- |
| `CLM-01` | Only identifiable official public records count toward coverage or scale. | `SRC-01`, `SRC-03` | Confirmed policy | Rejects generated, mock, synthetic, loopback, and placeholder capacity claims. | `TOP-01`, `XREQ-01`, all epics |
| `CLM-02` | Official public-domain identity fields must remain exact and traceable; only secrets, private state, workstation traces, and non-public data are blocked. | `SRC-01`, `SRC-03` | Confirmed policy | Publication and review minimization cannot become identity redaction. | `TOP-02`, `XREQ-02`, `STORY-001`, `STORY-019`, `STORY-052` |
| `CLM-03` | Million scale is an end-to-end property across acquisition, processing, review, publication, correction, and recovery. | `SRC-01`, `SRC-02` | Confirmed requirement | Row count alone cannot close a lane. | `TOP-03`, `INIT-01..04`, `XREQ-05..08` |
| `CLM-04` | Every public claim must resolve to primary evidence and expose unknown, stale, blocked, disputed, and correction state. | `SRC-01`, `SRC-02` | Confirmed requirement | Controls API/UI and release gates. | `TOP-04`, `TOP-19`, `STORY-054`, `XREQ-03`, `XREQ-09` |
| `CLM-05` | Anomaly or integrity scoring is triage, never an automated corruption verdict. | `SRC-01`, `SRC-02` | Confirmed policy | Blocks high-risk inference before corroboration and review. | `TOP-17`, `EPIC-09`, `XREQ-13` |
| `CLM-06` | Seven registered corpora and three million-row lanes exist, but promoted lanes remain zero. | `SRC-02`, `SRC-03` | Confirmed current state | Work must target missing promotion gates, not more unqualified row counts. | `TOP-05`, `EPIC-01`, `DEC-01` |
| `CLM-07` | Durable analytical origin and clean restore exist for registered releases, while full raw-object origin, retention, restore, and source reconstruction remain open. | `SRC-02`, `SRC-03`, `SRC-04` | Confirmed with bounded scope | Keeps `W1-001..002`, `W1-006..007` open. | `TOP-06`, `EPIC-02`, `DEC-02` |
| `CLM-08` | Current captured document corpus passes numeric `R1`, full native/OCR processing validation, and crash-safe sharded activation with restorable state; representative strata, complete physical BOE acquisition, human OCR quality, durable raw/CAS origin, and one million documents remain open. | `SRC-02`, `SRC-03`, `SRC-04`, `SRC-14` | Confirmed with limitations | Prevents `W2` promotion. | `TOP-07`, `EPIC-03`, `DEC-01` |
| `CLM-09` | Candidate and actor evidence retain official names; cross-source identity quality, merge history, durable actor origin/restore, and representative million scale remain open. | `SRC-02`, `SRC-06` | Confirmed with limitations | Actor graph may publish only as source-scoped MVP. | `TOP-08`, `EPIC-04`, `DEC-06` |
| `CLM-10` | Actor graph v1 is locally validated and pending live publication; local validation is not completion. | `SRC-02`, `SRC-06` | Confirmed current state | Requires exact route/asset/hash/live proof before status closure. | `STORY-019`, `STORY-058`, `DEC-09` |
| `CLM-11` | Member-vote volume exceeds one million, but historical capture, official-total reconciliation, chamber coverage, and text-at-decision gaps remain. | `SRC-02`, `SRC-04` | Confirmed with limitations | Keeps parliamentary lane unpromoted and blocks stronger downstream outcome links. | `TOP-09`, `EPIC-05`, `DEC-03` |
| `CLM-12` | Awards and subsidy grants are not payments, implementation, or outcomes; lifecycle facts must stay distinct. | `SRC-02`, `SRC-04` | Confirmed semantic constraint | Prevents misleading public-money claims. | `TOP-10`, `EPIC-06`, `XREQ-09` |
| `CLM-13` | Responsibility must be time-bounded and evidenced separately from rhetoric, influence, implementation, and outcomes. | `SRC-01`, `SRC-02` | Confirmed requirement | Defines ledger edges and public dossiers. | `TOP-11`, `EPIC-07` |
| `CLM-14` | Outcome observation volume exceeds one million, but four datasets are not representative and no second-snapshot revision proof exists. | `SRC-02`, `SRC-03`, `SRC-04` | Confirmed with limitations | Keeps outcome `R2` and causality gates open. | `TOP-12`, `EPIC-08`, `DEC-01`, `DEC-12` |
| `CLM-15` | Outcome C1 has one real bounded pending candidate and zero reviews, releases, memberships, validated links, or public links. | `SRC-02`, `SRC-08` | Confirmed current state | No association, effect, merit, blame, or corruption statement may publish from it. | `TOP-13`, `STORY-046`, `XREQ-13` |
| `CLM-16` | Outcome C1 public v3 status, manifest, all `17` assets, fresh local build, route audit, and real browser verification agree; remote publication/live parity remain open. | `SRC-02`, `SRC-08`, `SRC-10` | Confirmed locally; live state unverified | Blocks C1 publication closure until exact remote parity and live browser evidence pass. | `TOP-13`, `STORY-046`, `DEC-04` |
| `CLM-17` | C2A physically processes and independently reconstructs all `33,726` national-only real pairs with keyset batching, atomic checkpoints, partitions, crash/resume, missing/corrupt-shard failure and semantic parity; `111` checks pass. | `SRC-05`, `SRC-10`, `SRC-11` | Confirmed local physical capacity; durable remote origin unverified | Proves bounded local behavior, not public eligibility, analytical validity, lane promotion or remote recoverability. | `TOP-14`, `STORY-047`, `DEC-05` |
| `CLM-18` | Comparison C1 is locally validated but pending live publication and remains bounded, stale, and non-million-scale. | `SRC-02`, `SRC-07` | Confirmed current state | Requires live proof; ranking and strong claims remain hidden. | `TOP-15`, `STORY-040`, `STORY-058` |
| `CLM-19` | Human review must separate generated candidates from append-only decisions and operate leases, calibration, dual review, adjudication, appeals, and correction at real-task scale. | `SRC-01`, `SRC-02`, `SRC-05` | Confirmed requirement; implementation open | Defines `W8` and blocks high-risk release. | `TOP-16`, `EPIC-09`, `DEC-07` |
| `CLM-20` | Public delivery must remain bounded and evidence-first; no browser route loads a million-row blob. | `SRC-01`, `SRC-02` | Confirmed requirement | Requires indexes, shards, stable cursors, and drill-down. | `TOP-18`, `EPIC-10`, `XREQ-10` |
| `CLM-21` | Confirmed public-data access obstruction must stay factual, reproducible, append-only, and linked to evidence. | `SRC-01`, `SRC-09` | Confirmed policy | Keeps blockers visible without motive claims. | `TOP-20`, `STORY-003`, `STORY-022`, `STORY-054`, `XREQ-14` |
| `CLM-22` | External maintainer reproduction and multi-maintainer operation remain open even though signed release machinery exists. | `SRC-02`, `SRC-05` | Confirmed current state | Keeps ecosystem completion open. | `TOP-21`, `EPIC-11`, `DEC-10` |
| `CLM-23` | No coherent effort estimate exists because major source, ownership, architecture, review, and release choices remain open. | `SRC-02`, `SRC-05` | Inferred from unresolved gates; estimate intentionally omitted | Prevents false precision or target-shaped planning. | `TOP-22`, `DEC-01..11`, estimation omission |
| `CLM-24` | C2B physically processes and independently reconstructs all `2,865,602` strict real pairs over `458` Senate actions, `6,400` annual series, `89` `ES*` geographies and `79,722` observations into a `3,587,743,744`-byte SQLite shard (SHA `04c82651...`); `107` checks, interruption/resume and byte-identical local restore pass. | `SRC-11` | Confirmed local million-pair physical capacity; durable remote origin/public release unverified | Converts discovery arithmetic into measured local execution while leaving promotion, public claims and remote disaster recovery closed. | `TOP-14`, `STORY-065`, `DEC-05` |
| `CLM-25` | C2B preserves the exact official-public identity dimension separately and packages every planner row into bounded Parquet: `119,116` member-vote identity rows / `490` names / `458` actions plus `2,865,602` pair rows in `1,213` Parquet files / `251,522,252` bytes; semantic, physical and portable roots survive full validation, hard-link/path/resource adversaries, and byte-exact replay; `22` identity and `23` package tests pass. | `SRC-12` | Confirmed local portable-delivery capacity; remote durability and semantic promotion unverified | Replaces the single large SQLite file as the delivery format without duplicating names millions of times or turning L0 pairs into claims. | `TOP-02`, `TOP-14`, `STORY-065`, `DEC-05` |
| `CLM-26` | C2C materializes capacity for `2,865,603` real tasks / `2,865,604` review slots under pinned Python `3.12`; all `330` independent checks and `12` adversarial tests pass while every human, authority, decision, promotion, release and publication table remains empty; operational mutations require a separately versioned snapshot. | `SRC-13` | Confirmed local capacity only; human operation and public release open | Proves queue cardinality, deterministic recovery and immutable control contracts while preventing fake reviewers/decisions from masquerading as progress. | `TOP-16`, `STORY-053`, `DEC-07` |
| `CLM-27` | Document numeric supply and deterministic `100,000`-row planning pass, but physical BOE source capture is `100,051/100,867`; `815` jobs remain unfinished after a measured route timeout and readiness rejects the corpus. | `SRC-14` | Confirmed local plan, processing, and failure evidence; external route state may change | Removes the old numeric-supply blocker while preserving physical acquisition, representative-quality, recovery, and promotion gates. | `TOP-07`, `EPIC-01`, `EPIC-03`, `STORY-003`, `STORY-014..015`, `DEC-01` |
| `CLM-28` | All `44` distinct real XLSX contents replay independently, bounded row-group locator fanout projects below `10M` at one million workbooks, and the current complete object set restores and packages locally; XLSX URL provenance, formulas, cold-output economics, authorized remote origin, BOE completion, human review, and real `1M` remain open. | `SRC-15` | Confirmed with explicit measurement and provenance limits | Adds one real office format and current recovery mechanics without converting inferred URLs, warm caches, or local packages into stronger claims. | `TOP-07`, `EPIC-02..03`, `STORY-005..006`, `STORY-010`, `STORY-012`, `STORY-015`, `DEC-02`, `RISK-02`, `RISK-12`, `RISK-14` |

## Terminology Corrections

| Source term | Normalized term | Reason | Scope effect |
| --- | --- | --- | --- |
| “Scale” or “millions” | `R2` lane promotion | One million rows without representative scope, recovery, correction, and delivery is only a capacity fact. | Every scale story uses §4 gates, not row count alone. |
| “Candidate” in outcome work | outcome-link review candidate | Avoids confusion with election candidates/people. | `STORY-045..046` never imply a validated relationship. |
| “Public personal information” | official public-domain identity evidence | Clarifies accountable source fields versus private/non-public data. | Exact source fields stay; task packets may reference rather than duplicate them. |
| “Privacy check” | publication-hygiene and security gate | Gate blocks secrets, sessions, workstation traces, and non-public state—not official public identities. | Applies through `XREQ-02` and `XREQ-11`. |
| “Corruption signal” | internal integrity review signal | A statistical anomaly is not misconduct evidence or a verdict. | Public release requires `EPIC-09`; automated verdict stays excluded. |
| “Outcome” | official indicator observation or separately reviewed outcome claim | Observation does not establish policy effect. | `EPIC-08` keeps chronology, association, and causality distinct. |
| “Linked” | typed evidence edge with explicit claim level | Temporal proximity or shared topic is not causal linkage. | `STORY-043`, `STORY-045` must expose method and uncertainty. |
| “Done” | exit gate passed with current artifact and environment evidence | Local code/test/size is insufficient. | Existing `W*` status remains authoritative; planning stories do not upgrade it. |
| “Live” | remotely fetched route and exact asset validated after publication | A static local build is not live. | Applies to actor, comparison, outcome, API, and dashboard stories. |
| “Durable origin” | externally recoverable immutable object/artifact origin with retention evidence | Local CAS or a generated manifest alone is not durable. | Keeps raw-object and outcome origin work open. |
| “Clean restore” | reconstruction from an empty environment using only declared immutable inputs | Cache replay or analytical restore does not prove source-DB reconstruction. | Restore acceptance names exact layer restored. |
| “C1/C2” | outcome pipeline maturity cohorts | C1 is bounded contract/release proof; C2 is sparse, partitioned, resumable real-pair processing. | Neither label implies reviewed L2 claims or `R2` promotion. |

## Topic Inventory

| Topic ID | Topic | Classification | Evidence | Notes |
| --- | --- | --- | --- | --- |
| `TOP-01` | Official-real-only corpus qualification | Required constraint | `CLM-01` confirmed | No synthetic/mock/generated capacity credit. |
| `TOP-02` | Exact official public-identity retention | Required constraint | `CLM-02` confirmed | Field-level provenance required. |
| `TOP-03` | End-to-end scale contract and lane promotion | Required | `CLM-03`, `CLM-06` confirmed | All priority lanes target `R2`. |
| `TOP-04` | Claim-to-primary-evidence traceability | Required | `CLM-04` confirmed | Includes uncertainty and correction state. |
| `TOP-05` | Registry, readiness, artifact truth, and drift control | Required/reused | `CLM-06`; `W0` partial | Registry exists; legacy evidence gaps remain. |
| `TOP-06` | Immutable object/artifact origin, restore, rollback, RPO/RTO | Required/dependency | `CLM-07` confirmed bounded | Analytical origin reused; raw coverage and formal operations open. |
| `TOP-07` | Document discovery, preservation, extraction, OCR, and quality | Required | `CLM-08` confirmed bounded | Numeric `R1`; representativeness/human quality/`R2` open. |
| `TOP-08` | Candidate, mandate, appointment, and time-aware actor identity | Required | `CLM-09`, `CLM-10` | Source-scoped graph exists; adjudicated cross-source resolution open. |
| `TOP-09` | Parliamentary discovery, versions, vote semantics, reconciliation | Required | `CLM-11` | Million rows observed; lane not promoted. |
| `TOP-10` | Money lifecycle, counterparties, execution, enforcement | Required | `CLM-12` | Awards/subsidies must not imply payment or delivery. |
| `TOP-11` | Rules, competence, responsibility, issues, measures, evidence edges | Required | `CLM-13` | Temporal attribution; unknown edges explicit. |
| `TOP-12` | Representative indicator sources, vintages, revisions, methodology | Required | `CLM-14` | Four-dataset scale corpus is insufficiently representative. |
| `TOP-13` | Outcome C1 contract, evidence package, zero-state public status | Required/current | `CLM-15..16` | v2/v3 correction/publication gate open. |
| `TOP-14` | Outcome C2 sparse planner, exact identity companion, bounded portable partitions, checkpoint/resume, and million-pair physical proof | Required/current | `CLM-17`, `CLM-24` and `CLM-25` pass locally; durable remote origin/public promotion open | C2A `33,726` and C2B `2,865,602` are measured physical L0 facts; exact names remain bundled once in normalized evidence, never converted into reviewed links or claims. |
| `TOP-15` | Promise/action comparison | Required/current | `CLM-18` | Local C1 bounded; live and scale gates open. |
| `TOP-16` | Review capacity, identity/authority, leases, calibration, adjudication, appeals, correction | Required/current | `CLM-19`, `CLM-26`; million-task capacity passes locally, operation remains open | Capacity rows and append-only contracts exist; no real reviewer, decision, adjudication, promotion or publication is claimed. |
| `TOP-17` | Integrity-signal corroboration and allegation safety | Required constraint | `CLM-05`, `CLM-15` | No automated verdict. |
| `TOP-18` | Bounded static public product and Evidence API | Required/reused | `CLM-20` | Existing routes/API are reusable contracts, not proof for new lanes. |
| `TOP-19` | Freshness, gaps, unknown/no-signal, and supersession | Cross-cutting | `CLM-04` | Visible in every release. |
| `TOP-20` | Public-source access obstruction evidence | Required operational | `CLM-21` | Factual, append-only, no motive inference. |
| `TOP-21` | Contributor SDK, governance, bus factor, independent replicas | Required | `CLM-22` | External reproduction remains open. |
| `TOP-22` | Estimate readiness and delivery authority | Question/dependency | `CLM-23` | Named owners, scope, budgets, and authority unresolved. |
| `TOP-23` | Performance, observability, and cost per 1,000 | Required cross-cutting | §4.2 and §9 | Must use physical real runs, not extrapolated fixtures. |
| `TOP-24` | Additive schema, stable IDs, immutable versions | Required constraint/reused | §§6.3-6.4; `W9-011..013` | Existing ontology/plugin contracts reduce but do not remove integration work. |

## Initiative Map

| Initiative ID | Strategic outcome | Included epics | Boundary | Status |
| --- | --- | --- | --- | --- |
| `INIT-01` | Every official byte and derived fact is captured, processed, recovered, and measured at scale. | `EPIC-01`, `EPIC-02`, `EPIC-03` | Evidence supply chain only; excludes identity/inference semantics. | Foundation partial; analytical recovery strong, raw/document `R2` open. |
| `INIT-02` | Public action, actors, money, and responsibility form a temporal evidence graph. | `EPIC-04`, `EPIC-05`, `EPIC-06`, `EPIC-07` | Descriptive accountability facts; excludes unsupported outcome causality and allegations. | Multiple bounded slices exist; no included lane fully promoted. |
| `INIT-03` | Outcome and integrity claims are method-bounded, human-reviewed, appealable, and correctable. | `EPIC-08`, `EPIC-09` | Includes observations, claim levels, review, correction; excludes automated verdicts. | C1 frozen local package/build, C2A/C2B physical delivery and C2C capacity pass locally; live publication, durable remote origin, real review, promotion and release remain open. |
| `INIT-04` | Citizens and independent contributors can consume, reproduce, extend, and audit releases. | `EPIC-10`, `EPIC-11` | Public delivery and ecosystem; does not waive upstream evidence gates. | Several routes/contracts live; pending lanes and external reproduction open. |

## Epic Overview

| Epic ID | Epic | Outcome | Need | Included topics | Main uncertainty |
| --- | --- | --- | --- | --- | --- |
| `EPIC-01` | Verified evidence foundation | Maintainers can distinguish current, recoverable, official artifacts from gaps and retired non-evidence. | Required | `TOP-01..05`, `TOP-19..20` | Legacy capture-sidecar completeness. |
| `EPIC-02` | Durable evidence origin and recovery | Operators can lose local state and restore exact raw and analytical releases with measured rollback. | Required | `TOP-06`, `TOP-23..24` | Raw-origin provider, retention policy, activation authority, RPO/RTO. |
| `EPIC-03` | Million-document evidence factory | Researchers receive preserved, extracted, quality-measured official documents through bounded resumable work. | Required | `TOP-07`, `TOP-23` | Representative corpus definition, OCR reviewers, source access. |
| `EPIC-04` | Time-aware public actor identity | Users can trace candidates, mandates, offices, identifiers, aliases, and merge/split history without unsupported identity merges. | Required | `TOP-02`, `TOP-08`, `TOP-24` | Adjudicated gold set and multi-snapshot representative scope. |
| `EPIC-05` | Reproducible parliamentary decisions | Users can reproduce who voted how on which version of text and see every gap. | Required | `TOP-04`, `TOP-09`, `TOP-19` | Historical capture and official-total/chamber reconciliation. |
| `EPIC-06` | Money-to-implementation evidence chain | Users can distinguish budget, award, contract, payment, delivery, enforcement, and unknown. | Required | `TOP-02`, `TOP-10`, `TOP-24` | Complete history, payment/execution sources, entity resolution. |
| `EPIC-07` | Temporal responsibility and issue ledgers | Users can identify who held which formal responsibility and which sourced action/evidence edges exist. | Required | `TOP-04`, `TOP-11`, `TOP-15`, `TOP-19` | Legal/domain codebook ownership and representative ledger mix. |
| `EPIC-08` | Defensible outcome observations and links | Users see what changed, with vintage and method, without unsupported causal attribution. | Required | `TOP-12..15`, `TOP-17`, `TOP-19` | Representative codebook, second snapshots, C1 live release, durable C2 origin/rollback, human review and promotion. |
| `EPIC-09` | Reviewed and correctable integrity claims | Reviewers can triage, corroborate, adjudicate, appeal, supersede, and measure claims at real-task scale. | Required | `TOP-16..17`, `TOP-19`, `TOP-23` | Reviewer staffing, calibration source, legal/editorial thresholds. |
| `EPIC-10` | Bounded public evidence product | Citizens can navigate evidence, status, limitations, and corrections through stable small public assets. | Required | `TOP-04`, `TOP-18..20` | Live publication authority and parity for pending routes. |
| `EPIC-11` | Reproducible contributor ecosystem | Independent maintainers can add sources, review work, reproduce releases, and share ownership. | Required | `TOP-21..24` | Named maintainers, external replica, governance adoption. |

## Detailed Breakdown

Stories index existing canonical work. They add acceptance boundaries and ownership roles; they do not replace each referenced work item's detailed evidence or status.

### EPIC-01 - Verified evidence foundation

**Outcome:** Maintainers and public users can tell which official artifacts exist, which qualify, which are stale or retired, and which gaps block promotion.

**Boundary:** Includes registry, inventory, reconciliation, capture lineage, artifact validation, and roadmap/tracker truth. Excludes durable external storage and downstream semantics.

**Dependencies:** Official source contracts; access to existing artifacts and evidence.

**Epic audit result:** Keep. Outcome is independently acceptable before durable-origin work.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-001` | Maintainer gets a fail-closed inventory where only official real corpora qualify and every official public identity field remains exact. | Required; partial | Registry/CI qualification and retirement of capacity-only artifacts; `W0-001..002`, `SCALE-001..003`. | Integrity/control | Data platform maintainer; named owner open | `SRC-03`, source allowlists | Registry/readiness rehash every declared file and reject non-official, generated, mock, synthetic, loopback, placeholder, identity-removing, or missing artifacts. | Legacy per-source sidecars incomplete; material variance, not estimable. |
| `STORY-002` | Data maintainer rebuilds BDNS and accountability roots from current canonical official evidence and sees exact reconciled deltas. | Required; current roots validated | Artifact recovery only; `W0-003..004`, related `SCALE*`. | Transform/analytical | Lane maintainer; named owner open | `STORY-001`, real source roots | Canonical validators prove all rows/files/bytes/hashes, public identity retention, idempotence, FK/integrity, and explicit non-promotion. | Representative scope remains open; bounded variance. |
| `STORY-003` | Source steward sees every document/vote provenance gap classified with reproducible evidence and next action. | Required; partial | Document inventory, missing URLs, HTTP lineage, obstruction evidence; `W0-005..007`, `SCALE-019..024`. | Ingest/integrity | Source stewards; assignments open | Official source availability, `SRC-09` | Eligible totals balance; each gap has immutable evidence or remains open; blocked access is logged factually; no silent URL rewrite or false recovery. | Historical upstream access can block closure; material variance. |
| `STORY-004` | Program maintainer reads one consistent status across roadmap, technical plan, tracker, registry, and readiness output. | Required; current synchronization slice done | Truth synchronization and drift checks; `W0-008`, `SCALE-001`. | Governance/control | Program maintainer; named owner open | `STORY-001..003` | Generated evidence and docs agree; absent/stale artifacts cannot be `DONE`; current/next/DoD recorded. | High drift rate across many artifacts; bounded recurring work. |

#### EPIC-01 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Registry, readiness builder, validators, tracker, obstruction log | Bind every legacy source and artifact to registry-backed checks | Close source-sidecar gaps and retire remaining non-evidence paths | Named lane stewards and complete legacy capture lineage |

### EPIC-02 - Durable evidence origin and recovery

**Outcome:** Operators can recover exact declared releases after losing local state, and can roll back safely with measured objectives.

**Boundary:** Includes raw and analytical origins, immutable addressing, restore, retention, rollback, supersession, and storage health. Excludes source re-scraping completeness and semantic promotion.

**Dependencies:** `EPIC-01`; external storage and release authority.

**Epic audit result:** Keep. Separate operational outcome; analytical evidence exists while raw-origin scope remains open.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-005` | Storage operator selects explicit immutable origins for analytical releases and raw checksum-addressed objects. | Required; partial | Origin contracts and responsibility split; `W1-001`, `SCALE-032`. | Object/release | Storage/release maintainer; named owner open | `EPIC-01`, provider decision | Versioning, retention, lifecycle, public access, cost, credentials, and recovery contracts are approved without secrets in artifacts. | Raw-origin provider/policy open; not estimable. |
| `STORY-006` | Storage operator uploads every eligible raw object once by checksum and independently proves immutability and recovery. | Required; local subset only | Full raw-object corpus, not analytical Parquet; `W1-002`, `W1-006`, `SCALE-033..034`. | Object | Storage/release maintainer | `STORY-005`, full object manifest | Remote object count/bytes/hashes match; version/delete guard and clean restore pass on dedicated prefix; local disk is unnecessary. | Full-object volume, provider features, and retention cost open; material variance. |
| `STORY-007` | Release maintainer publishes content-addressed analytical artifacts and exact official source records without identity suppression. | Required; analytical release done, source-record rollout partial | Immutable analytical release and public-source payload; `W1-003`, `W1-009`, `SCALE-035`. | Release/public data | Release maintainer | `STORY-001`, `STORY-005` | Remote pointer, manifest, artifact contract, signature, corpus parity, and exact public-field audit pass; operational private state excluded. | Next release authority and full source-record packaging proof open; bounded variance. |
| `STORY-008` | Recovery operator starts empty and reconstructs every registered analytical lane by declared checksum. | Required; current analytical lanes proven | Origin-to-cache and clean-room validation; `W1-004..005`, `SCALE-036..037`. | Recovery | Storage/release maintainer plus lane validators | `STORY-007`, storage headroom | Fresh environment fetches only immutable inputs; independent validators pass rows/files/bytes/hashes/identity; no canonical local input leaks in. | Normalized production-schema reconstruction still open; material variance. |
| `STORY-009` | Release authority can activate, revert, and supersede a release under compare-and-swap with measured RPO/RTO and public storage health. | Required; read-only drill partial | Rollback activation, supersession, storage status; `W1-007..008`, `SCALE-038`. | Release/operations | Release authority unassigned; operator executes | `STORY-007..008`, explicit mutation authority | Authorized activation/revert preserves both immutable releases, records supersession, measures RTO/RPO, and publishes a secret-free current status. | Authority and formal objectives open; not estimable. |

#### EPIC-02 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Signed HF analytical releases, bounded restore, local CAS, rollback plan | Extend common manifest/checksum contract across raw and analytical layers | Remote raw-object replication, retention drill, authorized pointer activation, normalized rebuild | Provider decision, release authority, full raw coverage, formal RPO/RTO |

### EPIC-03 - Million-document evidence factory

**Outcome:** Researchers receive searchable official documents whose bytes, text/OCR, provenance, quality, throughput, and failures remain reproducible at one-million-document scale.

**Boundary:** Includes document discovery, fetch, classification, extraction, OCR, human quality review, cost, and bounded delivery. Excludes semantic policy claims derived from text.

**Dependencies:** `EPIC-01..02`; official-source access.

**Epic audit result:** Keep. Current numeric `R1` proves a bounded slice, not representative `R2`.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-010` | Extraction operator sees every document classified by source, format, size, language, pages/sheets, encryption, and text density. | Required; current captured generation done | Inventory and full document profile; `W2-001`, `SCALE-005`, `SCALE-015`. | Ingest | Document pipeline maintainer | `STORY-003` | Reconciled inventory has explicit values/unknowns for all `122,653` eligible instances / `120,801` contents; every machine-language candidate is unreviewed; all `44` distinct XLSX contents replay through independent `openpyxl`; raw/CAS replay and generation lifecycle pass. | Final post-BOE generation, representative strata, formulas, non-XLSX office formats, and human language-quality review remain open; bounded variance. |
| `STORY-011` | Source operator runs polite bounded discovery/fetch where every item becomes succeeded, retryable, or dead and no partial is orphaned. | Required; partial 2026-08-29 | Host budgets and durable work states; `W2-002..003`, `SCALE-004`, `SCALE-006..009`. | Control/ingest | Source steward plus document pipeline maintainer | `STORY-005..006`, source contracts | Atomic leases, heartbeat/reclaim, retry classes, circuit breakers, byte/time limits, checksum completion, and per-host SLO reports pass on real work. Current public operations snapshot independently reconciles `9,084` real Senate URLs, `6,990` terminal, `2,094` unfinished, `9,187` attempts, `0` overdue leases, and `0` orphan partials; it exposes `3,176` official legacy HTTP URLs without rewriting evidence. Separate fresh proof streams a `30`-partition manifest, preflights `10,000` captured real objects, re-downloads `10,000/10,000` through exactly `10,000` requests, rehashes all `20,000` prior/fresh files, validates current source structure, and preserves `57` measured content revisions. | New explicit budgets/durable request events/redirect refusal/host fairness await a physical cold proof; source-steward policy and representative multi-host `100k` remain open; material variance. |
| `STORY-012` | Researcher receives page/section/row-group-linked digital text for all supported real documents with zero silent truncation. | Required; current PDF/XML/HTML/XLSX corpus done, other office formats open | Native extraction plus exact PDF pages, source-derived major markup sections, exact fallback spans, and bounded XLSX row groups; `W2-004`, `SCALE-010..011`. | Transform/object | Document pipeline maintainer | `STORY-010..011` | Instance/content/CAS totals balance; extractor and locator algorithm versions, input/output hashes, page/section/span/row-group locators, retries/failures, bounded RSS, full replay, and lifecycle audit validate independently. XLSX fanout averages `5.931818`, caps at `6`, and projects `5,931,818` locator rows at one million workbooks under the `10M` ceiling. | Zero formulas were observed, so formula correctness is unproven; non-XLSX office formats, final BOE generation, and human quality remain open; bounded variance after acquisition. |
| `STORY-013` | Researcher receives additive OCR only for text-poor pages, preserving native text and engine lineage. | Required; current routed cohort done | OCR routing and CAS; `W2-005`, `SCALE-012..014`. | Transform/object | Document pipeline maintainer | `STORY-012` | Every routed page terminal; reason, engine/language/config/version, input/output hash, text gain, and no-text state independently validate. | Future language/format mix may change engine needs; material variance. |
| `STORY-014` | Domain reviewer measures extraction/OCR quality across an approved representative 100,000-document cohort. | Required; numeric supply and exact plan pass, physical completion and human review open | Representative cohort and adjudicated quality; `W2-006..007`, `SCALE-015..017`. | Quality/review | Domain review lead unassigned | `STORY-010..013`, representative-strata decision, reviewers | Sampling frame covers source/format/size/language strata; physical selected rows complete; dual decisions and adjudication complete; metrics and errors publish by stratum. | Representative frame, BOE route recovery, and reviewer capacity open; not estimable. |
| `STORY-015` | Program operator processes one million official documents with measured requests, bytes, CPU, RSS, OCR pages, storage, failures, and cost per 1,000. | Required; captured corpus exceeds `100k`, acquisition control proof is `10k`, exact numeric plan is `100,000`, bounded crash-safe document generations and complete current local origin/restore/package are proven, million open | Physical `R2` execution and bounded public delivery; `W2-008..009`, `SCALE-020`, `SCALE-027`. | End-to-end document lane | Document and release maintainers | `STORY-006`, `STORY-011..014` | Source-universe replay proves `101,303` eligible HTTPS URLs and zero numeric gap. Bounded planner independently validates exact `100,000` selection. Current processing validates all `122,653` captured instances. Current local origin/restore covers `240,278` objects / `6,048,142,788` payload bytes and the immutable release plan binds `154` files / `2,250,233,559` bytes; local dry-run and read-only remote collision preflight pass without mutation. Physical BOE state is only `100,051/100,867`, active lineage references `1,156/1,166` successful summaries, and readiness fails closed. Completion requires a new route-health lever, terminal physical acquisition, representative approval, final regenerated processing, human quality, authorized remote origin and empty-root restore, cold-output telemetry, monetary rates, and every §4.2 gate on one million real documents; no browser or control artifact may be monolithic. | BOE availability, representative mix, remote-origin authority/provider, cold benchmarks, meter rates, human review, and million-source limits open; not estimable. |

#### EPIC-03 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Real inventory, PDF/XML/HTML/XLSX native-text CAS, exact bounded locators, additive OCR, validators, complete current local origin/restore/package, unlabeled review packet | Unify durable queue/origin and stratum metrics across discovery through publication | Non-XLSX office/formula validation, human review, representative expansion, authorized remote origin/restore, cold-output and monetary telemetry, million-document run | Approved strata, reviewers, remote release authority/provider, source access, meter rates, named lane owner |

### EPIC-04 - Time-aware public actor identity

**Outcome:** Citizens can reconstruct candidates, mandates, appointments, public identifiers, aliases, and reviewed identity changes without name-only merging.

**Boundary:** Includes official person/organization occurrences, source-scoped identities, time, evidence, resolution review, and merge/split history. Excludes private enrichment and unsupported inferred identity.

**Dependencies:** `EPIC-01..03`; official electoral, institutional, and bulletin sources; ontology v1.

**Epic audit result:** Keep. Actor identity is reusable infrastructure with its own quality and release gates.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-016` | Election researcher reconstructs each captured candidacy and correction from exact official text while unapplied ambiguity remains blocked. | Required; partial | Official origins and existing election cohorts; `W3-001..002`. | Ingest/normalize | Election-source steward; named owner open | `STORY-003`, source identifiers, human reviewers | Base/correction/effective totals reconcile; every public field and source paragraph remains exact; missing identifiers fail closed; dual-review decisions bind immutable evidence. | Archive access, 2019 source defect, 776 review tasks; material variance. |
| `STORY-017` | Citizen can inspect comparable official regional and municipal candidacy/result cohorts. | Required; open | Net-new jurisdiction sources; `W3-003`. | Ingest/normalize | Election-source stewards unassigned | Source contracts, `STORY-016` | Coverage matrix and official totals pass by election/jurisdiction; candidacy and result remain separate fact types; full public identity retained. | Source diversity/contracts open; not estimable. |
| `STORY-018` | Citizen sees dated party-office and political-appointment history with appointing authority. | Required; open | Offices and appointments only; `W3-004`. | Ingest/normalize | Bulletin/registry source steward unassigned | `EPIC-03`, official registries | Appointment/dismissal/version/source totals and actor references reconcile; unknown start/end states remain explicit. | Official registry universe and source ownership open; not estimable. |
| `STORY-019` | Researcher navigates a time-aware source-scoped actor graph and exact public labels without unsupported cross-source merges. | Required; local v1 validated, live pending | Current MVP and live route; `W3-005`, related `ACT-003..004`, `PUB-001..002`. | Analytical/public | Identity platform maintainer plus public UI maintainer; names open | `STORY-016..018`, ontology, release authority | Full-row/FK/integrity/replay/partition checks pass; source-origin conflicts remain namespaced; local route/asset equals published/live bytes; limitations visible. | Actor source-content provenance, live publication, durable origin/restore open; material variance. |
| `STORY-020` | Identity reviewers measure precision/recall and can merge or split identities without erasing old evidence. | Required; open | Gold set and immutable resolution history; `W3-006..007`, `ACT-005..006`. | Identity/review | Identity review lead unassigned | `STORY-019`, dual review/adjudication | Stratified official-evidence gold set has independent reviews/adjudication; metrics report source/name patterns; every merge/split is versioned and reversible. | Label policy, reviewers, threshold approval open; not estimable. |
| `STORY-021` | Public and operators consume one million representative actor/candidate/mandate/appointment facts with recovery and correction proof. | Required; open | Actor-lane `R2`; `W3-008`, `ACT-007..008`. | End-to-end actor lane | Identity and release maintainers | `STORY-019..020`, `EPIC-02` | §4.2 gates pass on representative real corpus; origin, clean restore, public shards, identity quality, and corrections verify. | Current graph row count is not representative one-million actor facts; not estimable. |

#### EPIC-04 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| BOE candidate corpora/queue, normalized actor sources, source-scoped graph, ontology | Connect election/appointment versions to graph and public drill-down | Regional/municipal sources, office history, gold set, merge/split history, `R2` release | Identity reviewers, source stewards, actor origin/restore, live publication |

### EPIC-05 - Reproducible parliamentary decisions

**Outcome:** Citizens can reproduce an official decision from session and text version through member/group votes, totals, actor links, and evidence gaps.

**Boundary:** Includes Congress/Senate discovery, initiative/amendment versions, parliamentary stages, vote-state semantics, reconciliation, identity links, and bounded publication. Excludes outcome effect claims.

**Dependencies:** `EPIC-02..04`; chamber source access.

**Epic audit result:** Keep. Million observed member rows do not close missing history, text, reconciliation, or capture gates.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-022` | Parliamentary source steward publishes exact chamber/legislature/session discovery totals and missing ranges. | Required; open | Discovery coverage; `W4-001`, `PAR-001`. | Ingest/control | Parliamentary source steward unassigned | Source contracts, obstruction policy | Official catalogs reconcile to discovered work; gaps and blocked ranges have evidence, owner, and next lever. | Upstream catalogs/WAF and historical ranges; material variance. |
| `STORY-023` | Researcher opens the exact initiative or amendment text version in force at decision time. | Required; open | Text-at-decision version preservation; `W4-002`, `PAR-002`. | Object/normalize | Parliamentary data maintainer | `EPIC-03`, `STORY-022` | Each decision references checksum-pinned version bytes and effective interval; later consolidated text is distinguishable; missing original bytes stay explicit. | Historical original XML/PDF availability; material variance. |
| `STORY-024` | Researcher inspects signatories, speeches, committee stages, and group/member votes with balanced source totals. | Required; partial | Parliamentary event facts; `W4-003`. | Ingest/normalize | Parliamentary data maintainer | `STORY-022..023` | Source totals and FK balance pass per chamber/legislature; every fact has source record, URL, retrieval, checksum, and parser lineage. | Chamber heterogeneity and incomplete sessions; material variance. |
| `STORY-025` | Citizen sees yes, no, abstention, absence, and no-vote as distinct source states and every total mismatch classified. | Required; partial | Vote semantics and reconciliation; `W4-004..005`, `PAR-003..004`. | Normalize/integrity | Parliamentary data maintainer | `STORY-024` | No aggregate gap fabricates member state; each event balances or carries source-supported mismatch class/open incident. | Residual historical capture gaps; material variance. |
| `STORY-026` | Citizen follows each parliamentary actor through a reviewed source identity or explicit unresolved state. | Required; open | Actor linking quality; `W4-006`, `PAR-005`. | Identity/analytical | Identity and parliamentary maintainers | `EPIC-04`, `STORY-024` | Link precision/recall sampled; reviewed/conflict/unresolved states and evidence are public; no name-only merge. | Gold set and actor provenance open; not estimable. |
| `STORY-027` | Citizen loads bounded vote indexes/shards while operators validate a representative million-row lane from origin and clean restore. | Required; partial capacity | `R2` analytical/public delivery; `W4-007`, `PAR-006..007`, `SCALE-040`. | Analytical/public/recovery | Parliamentary and release maintainers | `STORY-022..026`, `EPIC-02` | Representative reconciliation plus §4.2 passes; stable index/shard hashes, old links, cache behavior, and evidence drill-down validate live; no monolith. | Existing 1.8M rows are not representative promotion; material variance. |

#### EPIC-05 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Member-vote shards/audits, initiative links, normalized parliamentary schema | Bind text-at-decision, actor graph, totals, and public evidence routes | Complete discovery, original-version capture, reconciliation repair, representative `R2` release | Chamber stewards, historical bytes, official universe totals, actor quality |

### EPIC-06 - Money-to-implementation evidence chain

**Outcome:** Citizens can distinguish and trace public-money lifecycle states from budget through payment, delivery, inspection, sanction, and audit evidence.

**Boundary:** Includes PLACSP, BDNS, budgets, execution, counterparties, implementation/enforcement facts, exact money, and dossiers. Excludes inference that an award or grant caused an outcome.

**Dependencies:** `EPIC-02`, `EPIC-04`; official procurement, subsidy, budget, payment, and control sources.

**Epic audit result:** Keep. Lifecycle semantics form one outcome; identity and source acquisition remain explicit dependencies.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-028` | Money-source steward ingests complete bounded PLACSP and BDNS historical cohorts with versions, tombstones, pagination, and revisions. | Required; partial | Procurement/subsidy acquisition; `W5-001..002`, `MON-001..002`, `SCALE-043..046`. | Ingest/object | Procurement and subsidy stewards unassigned | `EPIC-02`, source/storage preflight | Period catalogs and pages balance to official totals; all work terminal/reclaimable; second snapshot proves changed/deleted state; public counterparties retained exactly. | Archive breadth, disk headroom, source contracts; material variance. |
| `STORY-029` | Budget analyst distinguishes appropriation, execution, notice, award, change, invoice, payment, and delivery as versioned fact types. | Required; budget open, first award path live | Budget/lifecycle contract; `W5-003..004`, `W5-009`, `MON-003..004`. | Normalize/analytical | Public-money data maintainer | `STORY-028`, official budget/payment sources | Exact Decimal/currency/tax semantics pass; no award is labeled payment; first slice and full materialization share additive stable contract and evidence. | Budget/payment source availability and mapping depth; material variance. |
| `STORY-030` | Entity reviewer resolves counterparties with official identifiers and immutable conflict/merge history while retaining all source fields. | Required; open | Money-entity identity; `W5-005`, `MON-005`. | Identity/review | Identity review lead plus money maintainer | `EPIC-04`, `STORY-028` | Stratified precision/recall, reviewed states, provenance, and reversible merge/split evidence pass; natural-person and unclassified public records remain exact. | Gold set and identifier quality open; not estimable. |
| `STORY-031` | Auditor accesses typed staffing, permit, inspection, sanction, service-delivery, and audit-finding facts with authority and effective dates. | Required; open | Implementation/enforcement sources; `W5-006`, `MON-007`. | Ingest/normalize | Control-source stewards unassigned | Official source contracts, `STORY-029` | Every fact has typed lifecycle state, authority, period, source, version, and evidence; missing stages remain unknown rather than inferred. | Source universe and legal semantics open; not estimable. |
| `STORY-032` | Citizen opens bounded dossiers whose source totals and monetary amounts reconcile through available lifecycle stages. | Required; open beyond first award slice | Reconciliation/public dossier; `W5-007..009`, `MON-006..008`, `PUB-015`. | Analytical/public | Money and public UI maintainers | `STORY-028..031`, `EPIC-02` | Source/period/currency/tax/revision totals reconcile without float drift; entity-to-contract-to-payment/delivery chain links evidence or displays missing; `R2` origin/restore and live route pass. | Complete payment/delivery sources and representative million scale; not estimable. |

#### EPIC-06 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| PLACSP/BDNS corpora, canonical spending contract, first live award slice | Bind versioned money events to actor graph, budget/execution, enforcement, and evidence API | Complete archives, second snapshots, budgets/payments, control sources, full dossiers | Source stewards, identity reviewers, authoritative lifecycle sources |

### EPIC-07 - Temporal responsibility and issue ledgers

**Outcome:** Citizens can see which institution or public actor held formal responsibility at a date and how sourced promises, actions, rules, money, implementation, and evidence connect.

**Boundary:** Includes legal acts, competence, issues, measures, typed edges, promise/action comparison, and issue dossiers. Excludes unsupported influence or causal-outcome attribution.

**Dependencies:** `EPIC-03..06`; domain/legal review.

**Epic audit result:** Keep. Bounded live vertical slices demonstrate contracts, while representative ledger and comparison publication remain open.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-033` | Citizen identifies originator, approver, publisher, effective rule version, competence, delegation, oversight, and current owner for a date. | Required; open | Rules and responsibility graph; `W6-001..002`, `ACC-001..002`. | Ingest/analytical | Legal-source steward and data maintainer; names open | `EPIC-03..04`, legal sources | Every responsibility edge has type, interval, source, evidence, version/repeal state; conflicting/unknown ownership visible. | Legal interpretation and source coverage; not estimable. |
| `STORY-034` | Domain reviewer maintains a versioned issue codebook and evidence-span measures with explicit confidence/review state. | Required; open beyond first slices | Taxonomy and measure extraction; `W6-003..004`, `ACC-003..004`. | Semantic/review | Domain/editorial lead unassigned | `EPIC-03`, methodology approval | Inclusion/exclusion examples, version history, exact text spans, extractor version, confidence, and adjudicated sample pass. | Taxonomy authority and multilingual/domain depth open; not estimable. |
| `STORY-035` | Researcher traverses typed promise→decision→rule→money→implementation→audit→outcome edges while missing edges remain explicit. | Required; open | Representative ledger construction; `W6-005..006`, `ACC-005`. | Analytical | Accountability graph maintainer | `STORY-029`, `STORY-033..034`, `EPIC-05` | Each edge has typed semantics, time, source and evidence; million representative facts pass origin/restore/quality/corrections; no chronology-to-causality leap. | Representative domain mix and actor quality open; not estimable. |
| `STORY-036` | Citizen opens three complete issue-led dossiers showing actions, responsibility, evidence, and missing facts. | Required; open | Public dossiers; `W6-007`, `PUB-002`. | Public product | Editorial/public UI maintainer | `STORY-035`, `EPIC-10` | Three distinct issues pass evidence-within-three-interactions, freshness, uncertainty, correction, accessibility, and bounded-payload checks. | Issue selection/editorial ownership open; material variance. |
| `STORY-037` | Citizen inspects official manifesto promises with page/hash evidence and explicit `not_assessed` fulfillment. | Required slice; first manifesto live | Promise contract expansion; `W6-008`, `PUB-014`. | Semantic/public | Promise data and editorial maintainers | `STORY-034`, official manifestos | Second ideologically distinct source and adjudicated extraction sample join current exact source-linked slice without changing unsupported states. | Source diversity and human adjudication open; bounded variance. |
| `STORY-038` | Citizen inspects executive meetings/agreements while attendance and influence remain absent unless directly evidenced. | Required slice; first path live | Agreement/lobby disclosure; `W6-009`, `PUB-016`. | Semantic/public | Executive-source and editorial maintainers | `STORY-034`, official agenda/lobby sources | Second snapshot/history, disclosed public participants, exact evidence, and agreement→implementation links validate; influence assertion remains zero without evidence. | Official lobby/agenda disclosure availability; material variance. |
| `STORY-039` | Citizen inspects foreign-policy actions separately from positions, entry into force, implementation, and later outcomes. | Required slice; first path live | Geopolitics expansion; `W6-010`, `PUB-017`. | Semantic/public | Foreign-policy source and editorial maintainers | `STORY-033..035`, official legal sources | BOE/legal-stage evidence and later source versions extend current slice; absent positions/effects remain not assessed; live exact assets pass. | Source selection and geopolitical terminology review; material variance. |
| `STORY-040` | Citizen compares sourced promises and actions using explicit bounded outcomes while strong/ranked claims remain hidden without evidence. | Required; local C1 validated, live pending | Comparison C1 and later scale; `W6-011`, `CMP-001`. | Analytical/public | Comparison maintainer plus editorial reviewer | `EPIC-04..05`, `STORY-037`, publication authority | Exact local release/replay/FK/evidence checks pass; source/public/build/live bytes match; stale cutoff is visible; changed-framing remains rejected without actor-authored evidence. | Live publication, fresh action corpus, artifact-set atomicity, million physical run open; material variance. |

#### EPIC-07 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Accountability ledger, promise/agreement/geopolitics contracts, local comparison C1 | Connect legal responsibility, issue codebook, actions, money, actor graph, and bounded public dossiers | Representative rules/competence corpus, reviewed measure extraction, million-fact ledger, live comparison | Legal/domain owners, issue selection, fresh action evidence, comparison publication |

### EPIC-08 - Defensible outcome observations and links

**Outcome:** Citizens see official outcome observations, revisions, chronology, and only the strongest claim level supported by reviewed method evidence.

**Boundary:** Includes indicator codebook/sources, vintages, revisions, descriptive-to-causal claim levels, conservative links, C1 release evidence, and C2 sparse execution. Excludes unreviewed association/effect/merit/blame/corruption claims.

**Dependencies:** `EPIC-02`, `EPIC-04..07`; statistical/domain methodology review.

**Epic audit result:** Keep. Current million-row observation volume and one bounded candidate prove neither representativeness nor a validated policy effect.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-041` | Method reviewer approves a representative indicator codebook and national/regional/municipal source matrix with observed revision behavior. | Required; open | Codebook, sources, second snapshots; `W7-001..003`, `OUT-001..002`. | Method/ingest | Statistical methodology lead and source stewards unassigned | Official statistics contracts | Units, geography, frequency, methods, breaks, uses, coverage, vintages, and changed/unchanged/deleted cases are approved and machine-tested. | Representative scope and second-snapshot availability; not estimable. |
| `STORY-042` | Researcher queries one million representative official observations with exact decimals, methodology, origin, restore, and corrections. | Required; row capacity exists, promotion open | Outcome-lane `R2`; `W7-004`, `OUT-003`. | Analytical/release | Outcome data and release maintainers | `STORY-041`, `EPIC-02` | §4.2 passes for approved source/geography/topic mix; revision/correction workflow and bounded shards validate from clean restore. | Current four-dataset corpus is not representative; material variance. |
| `STORY-043` | Reader sees whether a statement is descriptive, associational, quasi-experimental, or causal and can inspect required method evidence. | Required; policy defined, operational gate open | Claim-level methodology; `W7-005..006`. | Method/integrity/public | Methodology lead plus editorial reviewer unassigned | Approved publication language, `EPIC-09` | Each level has machine gate, UI wording, required comparison/confounder/sensitivity/caveat evidence, and explicit failure state; stronger level cannot bypass prerequisites. | Method/legal approval and domain-specific standards; not estimable. |
| `STORY-044` | Citizen follows a conservative issue→outcome chronology while causality remains separate and unsupported links remain absent. | Required; open | Outcome-ledger edges; `W7-007`. | Analytical/public | Accountability graph maintainer plus method reviewer | `STORY-035`, `STORY-041..043` | Each displayed edge binds versions, geography, time, evidence, decision, and claim level; chronology cannot render as causal; `no_signal` stays explicit. | Geographic/temporal comparability and confounders; material variance. |
| `STORY-045` | Statistics user inspects the first Eurostat family with exact cell provenance and no causal implication, then sees it expanded only under approved codebook/revision gates. | Required slice; first family live | Existing indicator contract and next-source gate; `W7-008`, `OUT-004`, `PUB-018`. | Analytical/public | Outcome data and public UI maintainers | `STORY-041` | Current release remains byte/source/replay exact; dataset/method links stay live; second snapshot proves revision semantics before status expansion. | Current slice does not close `W7-001..003`; bounded variance. |
| `STORY-046` | Release reviewer receives a corrected C1 v3 evidence package that exposes the one pending methodological candidate and source provenance while reporting zero validated relationship and zero association/effect/merit/blame/corruption claims. | Required/current; locally generated, not released | C1 contract/build/publication closure; `W7-009`, `OUT-005`, `PUB-001..002`. | Analytical/release/public | Outcome maintainer, independent validator, release maintainer | `STORY-019`, `STORY-023..026`, `STORY-041..045`, publication authority | Producer/validator/source DB/public JSON/build/live asset agree on contract, counts, hashes, source cutoffs, URLs, XML/provenance gaps, one pending candidate, zero reviews/releases/memberships/validated/public links, and non-causal scope; exact release package immutable. | Actor raw provenance, original vote XML, live authority, and material variance remain open. |
| `STORY-047` | Pipeline operator physically processes C2A's national-only `33,726` eligible real pairs through keyset batches, partitions, checkpoint/resume, and exact semantic parity without Cartesian expansion. | Local physical acceptance passed; remote durability/promotion open | C2A execution gate under `W7-009` / `OUT-005`; no public claim. | Control/analytical | Outcome pipeline maintainer; named owner open | Frozen C1 method/schema/validation contract, `SRC-11`, durable origin contract | `33,726/33,726` pairs reconcile; `111/111` checks, interruption/resume, missing/corrupt-shard tests, bounded memory, semantic root `0fc7c257...`, and independent acceptance pass. | Durable remote origin/restore and promotion remain open; not estimable. |
| `STORY-065` | Pipeline operator runs C2B over the wider strict `2,865,602`-pair real eligibility universe and proves at least one million pairs physically, incrementally, portably and recoverably processed without suppressing public identity. | Local planner and portable-package acceptance passed; durable remote origin/public release open | C2B million physical proof under `W7-009` / `OUT-005`; never a public relationship claim by itself. | Control/analytical/recovery | Outcome pipeline and release maintainers; named owners open | `STORY-047`, `EPIC-02`, storage/request budget | Source planner reconciles `2,865,602/2,865,602` rows. Exact identity companion retains `119,116` member-vote rows / `490` names / `458` actions in `8` Parquet. Portable delivery contains `1,205` pair files plus those `8` identity files / `251,522,252` bytes; 25-partition interruption/resume, bounded-resource validation, exact inventory, copy-only replay and byte equality pass with semantic root `2afaf9ef...`, physical root `f2d50fa5...`, portable root `049f9718...`, publication/ranking eligibility=`0`. | Durable remote origin, isolated remote restore/rollback, provider cost, public release, review and claim authority remain open; not estimable. |

#### EPIC-08 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Million-row Eurostat corpus, live bounded indicator slice, C1 append-only schema/materializer/validator, accepted C2A/C2B planners, exact C2B identity/package, and C2C capacity snapshot | Bind actor/vote/text provenance, indicator versions, method gates, public status, durable C2 origin, and a separately versioned real operational review snapshot | Approved representative codebook, second snapshots, C1 live proof, C2 remote origin/restore/rollback, real review operation, `R2` release | Statistical lead, actor/vote provenance, review/release owners and durable-origin provider |

### EPIC-09 - Reviewed and correctable integrity claims

**Outcome:** Reviewers and affected parties can audit, challenge, correct, and supersede high-risk claims without erasing history; public users see only reviewed evidence-bound states.

**Boundary:** Includes review contract, calibration, thresholds, corroboration, counterevidence, right of reply, appeals, corrections, metrics, and million-task operations. Excludes automatic corruption verdicts and invented calibration labels.

**Dependencies:** `EPIC-01..02`, `EPIC-04..08`; legal/editorial governance and real reviewers.

**Epic audit result:** Keep. Cross-cutting publication safety has a distinct independently operated outcome and control plane.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-048` | Reviewer records append-only task, evidence version, decision, confidence, disagreement, and adjudication state. | Required; schema pieces exist, full workflow open | Review state contract; `W8-001`, `INT-001`. | Review/control | Review-platform maintainer and editorial lead unassigned | Immutable evidence IDs, reviewer identity policy | State machine forbids mutation/erasure, binds exact evidence/version/method, and reconstructs every transition; credentials/private sessions remain excluded from public output. | Cross-lane contract and owner open; material variance. |
| `STORY-049` | Calibration lead provides real historical labels based only on cited official court, audit, or control-body findings. | Required; open | Official calibration set; `W8-002`, `INT-002`. | Review/method | Calibration/editorial lead unassigned | Legal review, official findings | Stratified examples cite immutable official evidence; dual labels/adjudication complete; project inference is separate from official finding. | Availability, legal interpretation, class imbalance; not estimable. |
| `STORY-050` | Integrity reviewer receives only threshold-qualified signals with minimum cohorts, corroboration, and conflict disclosure. | Required; open | Signal thresholds and publication prerequisites; `W8-003..004`, `INT-004`. | Integrity/method | Methodology and editorial leads unassigned | `STORY-049`, money/outcome evidence | Tests suppress small/missing cohorts; no single weak signal becomes public claim; at least required independent corroboration and conflicts are machine-checked. | Thresholds and corroboration policy open; not estimable. |
| `STORY-051` | Affected party or evidence contributor can submit counterevidence, reply, appeal, and correction that reaches immutable public supersession. | Required; open | Challenge/correction paths; `W8-005`, `INT-003`. | Review/public | Editorial corrections owner unassigned | `STORY-048`, public policy/legal review | Each path has receipt, owner, SLA, evidence, decision, appeal, release membership, public replacement, and preserved prior version; no quiet deletion. | Right-of-reply policy, abuse handling, legal owner; not estimable. |
| `STORY-052` | Program lead measures agreement, reversal, drift, queue age, throughput, correction latency, and release eligibility from real decisions. | Required; open | Review scorecard and gated publication; `W8-006..007`. | Review/observability/release | Review operations and release maintainers | `STORY-048..051`, `EPIC-10` | Metrics derive from immutable real tasks/decisions; only eligible reviewed claim versions enter signed releases with evidence cards/limitations; identity remains resolvable. | No completed representative review cohort; material variance. |
| `STORY-053` | Review operators process one million real tasks with atomic leases, bounded evidence references, dual review, adjudication, appeals, and correction SLA. | Capacity accepted locally; real operation open | Million-task control plane; `W8-008`, `INT-005..006`. | Control/review/recovery | Review-platform and operations owners unassigned | `EPIC-02`, `STORY-048..052`, reviewer workforce | Immutable capacity snapshot reconciles `2,865,603` real tasks / `2,865,604` slots and rejects mutation; human/authority/decision/promotion/release tables stay exactly empty. Completion requires a new content-addressed operational snapshot populated only from real trust, identity, authorization, conflict and assignment evidence; lease/heartbeat/reclaim/crash tests, dual review/adjudication, queue-age/throughput/cost and correction evidence must then pass. | Workforce, real authority inputs, calibration, conflict policy, concurrent operating infrastructure; not estimable. |

#### EPIC-09 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Append-only patterns, candidate review queues, integrity-signal internal states, correction principles | Standardize immutable evidence/version IDs and release membership across lanes | Calibration set, review state machine, dual-review operations, appeals/corrections, million-task run | Legal/editorial owners, reviewers, thresholds, workforce model, real completed decisions |

### EPIC-10 - Bounded public evidence product

**Outcome:** Citizens can find source coverage, accountability evidence, uncertainty, and corrections through stable accessible routes and bounded assets.

**Boundary:** Includes static-first routes, Evidence API, explainers, transparency/obstruction feeds, live parity, accessibility, and evidence links. Excludes raw million-row browser payloads and release claims without upstream gates.

**Dependencies:** Relevant upstream epics; release authority and public hosting.

**Epic audit result:** Keep. Public delivery is independently testable but cannot upgrade upstream evidence state.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-054` | Citizen sees current source coverage, freshness, completeness, and factual obstruction evidence. | Required; first dashboard live | Coverage/obstruction publication; `W9-001`, `PUB-003`. | Public/status | Public UI and source-operations maintainers | `EPIC-01`, `SRC-09` | Feed and route counts/hashes/evidence links validate live; incidents remain factual/append-only; only operational private traces are sanitized. | Historical response/resolution metrics open; bounded variance. |
| `STORY-055` | Citizen reaches primary vote, actor, issue, money, and responsibility evidence within three meaningful interactions. | Required; partial by slice | Cross-lane explainers; `W9-002`, `PUB-002`. | Public/editorial | Public product and lane editorial owners unassigned | `EPIC-04..08` per explainer | User route exposes source, freshness, coverage, uncertainty, correction state, and exact drill-down; accessibility/mobile/share-state and bounded payload pass. | Upstream lane completeness and editorial ownership; material variance. |
| `STORY-056` | Researcher consumes stable bounded collections using opaque seek cursors and versioned schema compatibility. | Required; Evidence API v1 live | API contract/expansion; `W9-003`, `PUB-001`, `PUB-013`. | Public API/release | API maintainer | `EPIC-02`, canonical analytical contracts | Immutable index/release/pages/schema validate remotely; per-record provenance and unknowns present; deprecation policy and old links tested; new collections cannot bypass source gates. | Lane onboarding and long-term compatibility owner; bounded variance. |
| `STORY-057` | Citizen sees operational readiness, release notes, source health, and limitations tied to immutable releases. | Required; first dashboard live | Transparency/release flow; `W9-010`, `PUB-008`. | Public/status/release | Public UI and release maintainers | `STORY-054`, `EPIC-02` | Metrics and notes trace to current evidence/release hashes; stale metrics display as stale; build/routes/assets/a11y validate live. | Historical comparable metrics and ongoing owner open; bounded recurring work. |
| `STORY-058` | Release reviewer proves actor graph, comparison C1, and outcome C1 source artifacts equal public/build/live assets before any pending status closes. | Required/current; open | Cross-route publication closure; `W3-005`, `W6-011`, `W7-009`, `PUB-001..002`. | Release/public QA | Release maintainer plus independent verifier; authority open | `STORY-019`, `STORY-040`, `STORY-046` | Full gated build passes tests, real-only/publication hygiene, size budgets, exact byte/hash parity, route audit, desktop/mobile browser, accessibility, and remote source links after source branch publication. | Publication timing/authority and C1 evidence-package correction; bounded variance. |

#### EPIC-10 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Static-first site, Evidence API v1, live transparency/obstruction and bounded vertical slices | Add each lane through immutable pointer/index/shards and evidence cards | Pending route releases, broader explainers, historical status metrics, correction views | Release authority, editorial owners, upstream promoted lanes |

### EPIC-11 - Reproducible contributor ecosystem

**Outcome:** Multiple independent maintainers can add official sources, validate review batches, reproduce releases, and share critical ownership.

**Boundary:** Includes adapter/plugin contracts, one-command validation, starter issues, ownership/review policy, contributor paths, community metrics, and independent replicas. Excludes ungoverned third-party data and any relaxation of official-real-only gates.

**Dependencies:** `EPIC-01..02`, stable ontology/API contracts, governance participation.

**Epic audit result:** Keep. Technical SDK foundations exist, but independent operation and bus-factor outcomes remain open.

| Story ID | Actor and observable outcome | Need / evidence | Boundary and work refs | Owning layer | Delivery owner | Dependencies | Acceptance evidence | Uncertainty and estimate effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `STORY-059` | New contributor runs one command from official capture through schema, artifact, and validation without private maintainer state. | Required; reference path exists, generalized flow open | Source-adapter SDK; `W9-004`, `PUB-004`, `PUB-010..011`. | Contributor platform | SDK maintainer; named owner open | Ontology/plugin contracts, official fixture capture | Fresh environment reproduces exact sample and failure modes; capability boundaries, idempotence, provenance, public identity, and docs pass without secrets. | Cross-source adapter diversity and onboarding proof open; material variance. |
| `STORY-060` | Contributor selects a bounded issue with official evidence, expected artifact, dependencies, owner, and DoD. | Required; open | Starter issue catalog/ownership map; `W9-005`, `PUB-005`. | Governance | Community maintainer unassigned | `STORY-059`, tracker gaps | Each issue is independently acceptable, links source/evidence, names exclusions and reviewer, and no critical lane lacks documented ownership. | Maintainer capacity and issue curation open; bounded recurring work. |
| `STORY-061` | Maintainer gets two-person review for schema, identity, publication, and allegation-policy changes plus visible correction/security/citation paths. | Required; open | Governance and public contribution paths; `W9-006..007`, `PUB-006`. | Governance/security | Governance lead and security/editorial owners unassigned | Repository protection and response policy | Protected rules, required reviewers, escalation templates, response SLOs, and public paths are tested; no single person can silently alter high-risk policy. | Platform enforcement and named reviewers open; not estimable. |
| `STORY-062` | Community maintainer publishes quarterly first-contribution time, review latency, retention, source adoption, and bus-factor evidence for contributors and users. | Required; open | Community scorecard; `W9-008`. | Governance/observability | Community maintainer | `STORY-060..061`, real contribution events | Metrics derive from real repository/review events with period/method; missing metrics explicit; no synthetic activity. | Insufficient historical contributor events; material variance. |
| `STORY-063` | External maintainer restores, validates, and independently signs an immutable release without private local state. | Required; open | Independent replicas/attestation; `W9-009`, `W9-014`, `PUB-007`, `PUB-012`. | Release/governance | External maintainer unassigned; release maintainer supports | `EPIC-02`, public trust roots | Independent environment fetches, checksums, validates, and signs declared release; attestation/trust root published; differences reconciled; old release remains recoverable. | External participant and trust policy open; not estimable. |
| `STORY-064` | Platform maintainer preserves ontology/plugin/schema compatibility while new real-data adapters and outputs scale without rewrites. | Required; core contracts done, adoption ongoing | Contract stewardship; `W9-011..013`, `PUB-009..011`. | Architecture/contributor platform | Architecture/SDK maintainer | `STORY-059`, API compatibility | Human/machine contracts, migration/deprecation rules, reference plugin, capability checks, and real official test hooks pass for each extension. | Long-term owner and multi-plugin compatibility evidence open; bounded recurring work. |

#### EPIC-11 implementation composition

| Existing/reused | Integration | Net-new work | Missing evidence or owner |
| --- | --- | --- | --- |
| Core ontology, plugin architecture, reference adapter, signed snapshot flow, Evidence API | Package contributor workflow with issue/review/release governance | General one-command path, maintainer map, community metrics, external replica/attestation | Named maintainers/reviewers, external participant, governance enforcement |

## Cross-Cutting Requirements

| ID | Requirement | Applies to | Acceptance evidence | Estimate treatment |
| --- | --- | --- | --- | --- |
| `XREQ-01` | Official-real-only qualification | All epics | Every counted row/object resolves to allowlisted official source, capture/retrieval, immutable hash, source identity, and lineage; real-only gate has zero findings. | Required in every story; no separate estimate. |
| `XREQ-02` | Exact official public-domain identity retention | `EPIC-01`, `EPIC-04..11` | Source-to-artifact field counts/values reconcile; no official name/identifier/contact/candidacy/appointment/donation field is suppressed; secrets/private state remain blocked. | Required; no privacy-redaction work estimated. |
| `XREQ-03` | Claim-to-primary-evidence provenance | `EPIC-04..10` | `100%` published claims resolve through source URL/replacement, retrieval, checksum, parser/schema, evidence row, and immutable version. | Required; missing provenance blocks release. |
| `XREQ-04` | Additive schema and immutable history | `EPIC-01`, `EPIC-04..09`, `EPIC-11` | Stable IDs, append-only versions/transitions, FK/integrity, replay, supersession, and reconstruction tests pass; no destructive history loss. | Required; migration depth remains story-specific. |
| `XREQ-05` | Durable work and bounded memory | `EPIC-01..09` | Items are pending/leased/succeeded/dead; lease/reclaim and kill/resume pass; RSS bounded by batch/shard/document, not corpus. | Required; million physical evidence needed before estimate confidence. |
| `XREQ-06` | Idempotence and incremental reuse | `EPIC-01..09`, `EPIC-11` | Replay creates zero duplicate logical facts, emits reconciled delta, and reuses checksum-identical partitions safely. | Required. |
| `XREQ-07` | End-to-end reconciliation and drift | `EPIC-01..10` | Discovered/fetched/stored/parsed/normalized/reviewed/published totals balance per run; source/schema/parser drift fails closed. | Required; unresolved upstream totals add material variance. |
| `XREQ-08` | Durable origin, clean restore, rollback | `EPIC-02..11` | Immutable external origin, fresh restore, independent full validation, old-release recovery, supersession, and measured RPO/RTO pass for claimed layer. | Required for `R2`; provider/authority decision open. |
| `XREQ-09` | Explicit unknown and semantic-state separation | All public facts/claims | Missing, stale, disputed, blocked, `no_signal`, not assessed, award/payment, chronology/causality, and candidate/reviewed/published states render distinctly. | Required. |
| `XREQ-10` | Bounded accessible public delivery | `EPIC-04..11` | Static indexes/shards/cursors stay within budgets; no million-row blob; keyboard/mobile/accessibility/live route and old-link checks pass. | Required; route-specific work remains nested in stories. |
| `XREQ-11` | Publication hygiene and least exposure | All releases | Secrets, credentials, cookies, private sessions, workstation paths, and non-public state scan clean; official public fields remain exact. | Required; security owner open. |
| `XREQ-12` | Freshness, SLO, telemetry, and cost | All lanes | Source owner/SLA, overdue status, attempts/retries/dead, wall time, CPU, RSS, bytes, storage, OCR, and cost per `1,000` derive from real runs. | Required; cost unknown until physical cohorts/provider rates exist. |
| `XREQ-13` | Corroboration, human review, counterevidence, correction | `EPIC-07..10` | Models cannot publish high-risk findings; required evidence, independent review, conflicts, reply/appeal, supersession, and correction SLA pass. | Required; review model is decision-changing. |
| `XREQ-14` | Evidence-first obstruction handling | `EPIC-01`, `EPIC-03..05`, `EPIC-10` | One bounded retry without new lever; exact failure/log/URL/timestamps/owner/escalation recorded append-only; no motive speculation. | Required operational constraint. |
| `XREQ-15` | Two-person governance and reproducibility | `EPIC-09..11` | High-risk schema/identity/publication/policy changes have two reviewers; releases are independently reproducible and signed. | Required for societal-scale done; external owner open. |

## Ownership Matrix

Role ownership is explicit; named people are not assigned without evidence.

| Capability | Authoritative system | Reused layer | New layer | Delivery owner | Owner confidence |
| --- | --- | --- | --- | --- | --- |
| Mission, sequence, promotion | `ROADMAP.md` | Waves and §4/§11 gates | Systematic planning index | Program maintainer | Role confirmed; named owner unassigned. |
| Operational source status | ETL tracker | Existing source rows/evidence | Remaining reconciliations and current closeouts | Per-source steward | Role required; assignments incomplete. |
| Corpus qualification | Registry/readiness artifacts | Real-only and public-identity checks | Legacy sidecars/drift closure | Data platform maintainer | Implementation exists; named owner unassigned. |
| Raw object origin | Object manifests/CAS contract | Local CAS and adapter | External versioned origin/retention/restore | Storage/release maintainer | Owner open; provider open. |
| Analytical release/recovery | Signed immutable release contract | HF releases and validators | Authorized rollback/RPO/RTO and normalized reconstruction | Release maintainer plus release authority | Maintainer role clear; authority unassigned. |
| Documents/OCR | Document inventory/extraction/OCR artifacts | Current real pipeline | Representative strata, human quality, million run | Document pipeline maintainer plus domain review lead | Technical role clear; review owner open. |
| Actor identity | Actor/candidate schemas and actor graph | Source-scoped graph and BOE corpora | Gold set, merge/split history, representative `R2` | Identity platform maintainer plus identity review lead | Roles clear; named owners/reviewers open. |
| Parliamentary action | Parliamentary schemas/source contracts | Existing vote/initiative corpora and shards | Complete discovery/text/reconciliation/identity links | Parliamentary source/data maintainer | Named chamber stewards open. |
| Public money | Money-event schema/source contracts | PLACSP/BDNS and first spending slice | Full history, budget/payment/implementation joins | Public-money data maintainer plus source stewards | Named owners and sources open. |
| Responsibility/issues | Accountability ontology/ledger | Current ledger and vertical slices | Legal competence corpus, approved codebook, representative edges | Accountability graph maintainer plus legal/domain leads | Domain/legal ownership open. |
| Outcomes/method | Indicator and outcome-context contracts | Eurostat corpus/slice, frozen C1 package, accepted C2A/C2B planners, exact identity/package and C2C capacity | Representative codebook, C1 live release, C2 durable origin/rollback, operational review snapshot and `R2` revisions | Outcome pipeline maintainer plus statistical methodology lead | Technical packaging/capacity proven locally; methodology/review/release/origin owners open. |
| Review/corrections | Append-only review and release contracts | Existing internal queues/state patterns | Calibration, operations, appeals, million-task plane | Review-platform maintainer plus editorial corrections owner | Entire operating team unassigned. |
| Public UI/API | Static site and Evidence API contracts | Existing live routes/components | Pending routes, broader explainers, correction views | Public product/UI/API maintainers | Roles clear; release/editorial owners open. |
| Security/publication hygiene | Repository gates and release policy | Current scanners/checks | Two-person enforcement and incident ownership | Security reviewer plus release maintainer | Named security reviewer open. |
| Contributor ecosystem | Ontology/plugin/SDK/governance contracts | Reference plugin and signed flow | Generalized onboarding, scorecard, external replica | SDK/community/governance maintainers | Named maintainers and external participant open. |

## Uncertainty and Decision Register

| ID | Item | Need | Evidence | Implementation | Estimate effect | Resolver | Decision/evidence needed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `DEC-01` | Representative source universe by lane | Required | Current mixes confirmed incomplete; document audit now finds `115,246` unique official public URLs / `111,600` HTTPS / `101,303` acquisition-eligible, and exact numeric `100,000` planning passes | Depth open; numeric document gap is `0`, but representativeness is not inferred and current source weight is heavily BOE | Material variance; not estimable | Domain leads plus program maintainer | Approve jurisdiction/time/source/topic/format/language/size strata and official totals for each lane. Decide whether the pinned `98,748` BOE documents + `1,166` BOE summaries + `86` Parliament records are acceptable only as numeric load proof or require a new representative selection before physical execution. |
| `DEC-02` | Durable raw-object origin and retention | Required | Current local replication, clean restore, deterministic packing, release preparation, and read-only remote collision preflight pass for `240,278` objects / `6,048,142,788` payload bytes; no remote mutation or remote restore occurred | Provider, authorization, retention and remote recovery policy open | Material variance; not estimable | Storage/release owner | Choose origin/versioning/retention/access/cost policy; authorize exact append-only release; prove remote parity, independent empty-root restore, rollback, and delete guard before setting durable-public-origin status. |
| `DEC-03` | Historical vote/text capture closure | Required | Exact residual gaps and `403` evidence confirmed | Dependency open | Material variance | Parliamentary stewards | Obtain immutable official captures/equivalence or formally preserve unresolved block and scope consequence. |
| `DEC-04` | Outcome C1 v3 evidence-package release | Required now | Exact local contract, package and build pass; live release open | Local path frozen; publication decision open | Bounded variance unless evidence changes | Outcome maintainer, independent validator, release reviewer | Preserve exact status/manifest/assets and require live hash/browser acceptance before closing publication. |
| `DEC-05` | Outcome C2 durable origin, recovery and promotion after accepted sparse execution | Required | C2A `33,726`, C2B `2,865,602`, exact identity companion and bounded copy-replay package confirmed locally | Portable local delivery frozen; remote origin/provider/promotion open | Local throughput/RSS/bytes measured; remote cost and operational variance not estimable | Outcome pipeline and storage/release maintainers | Choose durable immutable origin, upload exact package/controls, prove isolated empty-root restore/rollback and only then consider public promotion; L0 pairs remain non-claims. |
| `DEC-06` | Actor identity quality and raw actor-source provenance | Required | Source-scoped graph validated; gold set/raw source hashes incomplete | Depth/owner open | Material variance | Identity lead and source stewards | Approve identity policy/gold strata and bind actor references to immutable source content or label them derived. |
| `DEC-07` | Human review operating model | Required | C2C capacity and append-only contracts exist; trust/identity/authority and completed decisions remain exactly absent | Capacity accepted; operational snapshot/owners/workforce open | Material variance; not estimable | Editorial/legal/review operations leads | Approve trust roots and identity/conflict/assignment inputs, build a separately content-addressed operational snapshot, then operate calibration, dual review/adjudication, SLA, appeals and compensation/capacity if applicable. |
| `DEC-08` | Statistical claim-level and allegation policy approval | Required | Normative guardrails exist; cross-domain thresholds incomplete | Owner/depth open | Material variance | Statistical, editorial, and legal leads | Approve definitions, evidence minimums, language, cohorts, confounders, corroboration, and release authority. |
| `DEC-09` | Main/public release and rollback authority | Required | Procedures and read-only rollback plan exist | Authority open | Bounded variance | Maintainer governance | Name approvers, branch/release order, compare-and-swap authority, emergency rollback and supersession procedure. |
| `DEC-10` | Independent maintainers and replica | Required for final DoD | Tooling exists; second-party reproduction absent | Owner/dependency open | Material variance | Community/governance lead | Recruit three critical-path maintainers and one external reproducer; publish attestations and bus-factor map. |
| `DEC-11` | Budget, infrastructure envelope, and delivery horizon | Unknown | No target, rates, staffing, or provider envelope supplied | Not selected | Not estimable | Maintainer/sponsor | Supply constraints only after scope decisions; estimate bottom-up, never reverse-fit target. |
| `DEC-12` | Snapshot/revision cadence per source | Required | First snapshots common; second-snapshot proof sparse | Depth open | Material variance | Source stewards plus release maintainer | Approve freshness SLA, effective/retrieval/vintage semantics, deletion handling, and correction cadence per source. |

## Assumptions and Exclusions

### Assumptions

- Status is a point-in-time classification for `2026-08-30`. Any artifact, live route, source cutoff, or upstream behavior change triggers registry/tracker refresh before a status upgrade.
- Existing code, data, schemas, routes, and contracts are reusable only at the exact layer independently validated; reuse never implies missing integration, parity, ownership, security, or scale behavior.
- SQLite remains the reproducible snapshot/single-node baseline. Operational coordination changes only after measured lock or throughput pressure and must preserve export semantics.
- Official public-source identity fields remain public and exact. Bounded task packets may reference immutable evidence instead of duplicating it; this is a scale optimization, not redaction.
- Unassigned owner labels are capability roles, not claims that a named person or funded team exists.
- C2A/C2B local physical acceptance changes capacity status only. Durable remote origin, isolated restore, public promotion, human review and claim authority remain independent gates; no pair row is a validated relationship.
- C2C capacity acceptance changes queue/control capacity only. Its empty trust-root and operational tables are a mandatory truth condition, not missing rows to fill automatically; real operations require a separately reviewed unpublished working snapshot and a later immutable export.
- External source blocks may persist. Work proceeds on controllable slices while blockers stay factual and visible under `XREQ-14`.

### Exclusions

- Synthetic, mock, invented, generated, placeholder, loopback, or duplicated records as coverage, quality, capacity, calibration, or readiness evidence.
- Suppression, pseudonymization, or removal of personal information published by an authoritative public source for accountability purposes.
- Secrets, credentials, cookies, private session state, workstation-identifying traces, or data not obtained from public sources in public artifacts.
- No automated corruption verdict. Unsupported motive, causal, effect, merit, or blame claims without the required evidence/review level are excluded.
- Silent WAF bypasses, fabricated source equivalence, invented identifiers, inferred votes, inferred payments, or inferred identity merges.
- Destructive schema/history rewrites without explicit approved migration, recovery, and compatibility evidence.
- Unapproved live publication, pointer mutation, destructive rollback, or external communication; authorized release work remains scoped in `STORY-009`, `STORY-058`, and `DEC-09`.
- Work/cost estimates in this revision.

### Estimation omission

Estimation is premature and was not requested. No `EST-*`, hours, cost, schedule promise, budget capacity, or target-fit total is supplied. Estimate readiness requires at minimum `DEC-01`, `DEC-02`, `DEC-04..11` to resolve scope, architecture, owners, review capacity, release authority, and constraints. When ready, estimate bottom-up at story level with conditional branches, measured throughput, provider rates, review labor, contingency, and confidence; do not reuse wave target durations as estimates.

## Coverage and Traceability

### Claim-to-delivery forward trace

| Claim/topic | Destination | Estimate line | Coverage result | Notes |
| --- | --- | --- | --- | --- |
| `CLM-01` / `TOP-01` | `XREQ-01`; all `65` stories | Omitted | Covered | Universal qualification gate. |
| `CLM-02` / `TOP-02` | `XREQ-02`, `XREQ-11`; `STORY-001`, `016`, `019`, `028..032`, `052..053`, `059` | Omitted | Covered | Task references never become identity redaction. |
| `CLM-03` / `TOP-03` | §4; `INIT-01..04`; `XREQ-05..08`, `XREQ-12` | Omitted; `DEC-01..02`, `DEC-11` | Covered | Scale requires full operating contract. |
| `CLM-04` / `TOP-04` / `TOP-19` | `XREQ-03`, `XREQ-09`; `EPIC-05..10` | Omitted | Covered | Evidence, freshness, unknown, dispute, and correction states explicit. |
| `CLM-05` / `TOP-17` | `EPIC-09`, `XREQ-13`; `STORY-043`, `048..053` | Omitted; `DEC-07..08` | Covered | Automated verdict excluded. |
| `CLM-06` / `TOP-05` | `EPIC-01`; `STORY-001..004`; `DEC-01` | Omitted | Covered | Zero promoted lanes remains visible. |
| `CLM-07` / `TOP-06` | `EPIC-02`; `STORY-005..009`; `XREQ-08`; `DEC-02`, `DEC-09` | Omitted | Covered | Analytical and raw recovery scope separated. |
| `CLM-08` / `TOP-07` | `EPIC-03`; `STORY-010..015`; `DEC-01..02`, `DEC-07` | Omitted | Covered | Numeric `R1` not representative `R2`. |
| `CLM-09` / `TOP-08` | `EPIC-04`; `STORY-016..021`; `DEC-06` | Omitted | Covered | Source-scoped graph and adjudicated resolution separated. |
| `CLM-10` | `STORY-019`, `STORY-058`; `DEC-09` | Omitted | Covered | Local actor validation cannot close live state. |
| `CLM-11` / `TOP-09` | `EPIC-05`; `STORY-022..027`; `DEC-03` | Omitted | Covered | Vote volume and parliamentary completeness separated. |
| `CLM-12` / `TOP-10` | `EPIC-06`; `STORY-028..032`; `XREQ-09` | Omitted | Covered | Money lifecycle semantics explicit. |
| `CLM-13` / `TOP-11` | `EPIC-07`; `STORY-033..040` | Omitted; `DEC-01`, `DEC-08` | Covered | Responsibility, rhetoric, influence, and outcomes separated. |
| `CLM-14` / `TOP-12` | `EPIC-08`; `STORY-041..045`; `DEC-01`, `DEC-12` | Omitted | Covered | Current observation volume not representative. |
| `CLM-15` / `TOP-13` | `STORY-046`; `XREQ-09`, `XREQ-13` | Omitted | Covered | Zero review/release/link state is acceptance-critical. |
| `CLM-16` / `TOP-13` | `STORY-046`, `STORY-058`; `DEC-04` | Omitted | Covered | v2/v3 evidence package stays open until exact live proof. |
| `CLM-17` / `TOP-14` | `STORY-047`; `DEC-05`; `XREQ-05..08`, `XREQ-12` | Omitted | Covered as accepted local physical work | C2A `33,726` capacity is proven; durable origin, promotion and claims remain closed. |
| `CLM-18` / `TOP-15` | `STORY-040`, `STORY-058`; `DEC-09` | Omitted | Covered | Comparison C1 live and scale gates remain open. |
| `CLM-19` / `TOP-16` | `EPIC-09`; `STORY-048..053`; `DEC-07..08` | Omitted | Covered | Candidate and decision records remain separate. |
| `CLM-20` / `TOP-18` | `EPIC-10`; `STORY-054..058`; `XREQ-10` | Omitted | Covered | Bounded delivery is a release gate. |
| `CLM-21` / `TOP-20` | `STORY-003`, `STORY-022`, `STORY-054`; `XREQ-14` | Omitted | Covered | Factual obstruction, no motive claim. |
| `CLM-22` / `TOP-21` | `EPIC-11`; `STORY-059..064`; `DEC-10` | Omitted | Covered | Tooling and independent operation remain distinct. |
| `CLM-23` / `TOP-22` | Estimation omission; `DEC-01..12` | Intentionally omitted | Covered | No false estimate. |
| `CLM-24` / `TOP-14` | `STORY-065`; `DEC-05`; `XREQ-05..08`, `XREQ-12` | Omitted | Covered as accepted local million-pair execution | C2B `2,865,602` capacity is physical and recoverable locally; remote durability/public promotion remain unproven. |
| `CLM-27` / `TOP-07` | `EPIC-01`, `EPIC-03`; `STORY-003`, `STORY-014..015`; `DEC-01`; `XREQ-05..07`, `XREQ-12`, `XREQ-14` | Omitted | Covered | Numeric supply/plan, physical acquisition, representation, processing generation, and promotion remain separate gates; BOE blocker is factual and append-only. |
| `TOP-23` | `XREQ-12`; `STORY-015`, `021`, `027`, `032`, `042`, `047`, `053`, `065` | Omitted; `DEC-11` | Covered | Requires measured real physical runs. |
| `TOP-24` | `XREQ-04`; `STORY-019..021`, `029..035`, `046..048`, `056`, `059`, `064` | Omitted | Covered | Existing ontology/schema reuse is bounded. |

### Canonical work-family reverse trace

| Existing IDs | Planning destination | Coverage boundary |
| --- | --- | --- |
| `W0-001..008` | `EPIC-01`, `STORY-001..004` | Existing status/evidence stays in Wave 0 and tracker. |
| `W1-001..009` | `EPIC-02`, `STORY-005..009` | Analytical origin proof does not close raw origin or authorized rollback. |
| `W2-001..009` | `EPIC-03`, `STORY-010..015` | Numeric `R1` does not close representative quality or document `R2`. |
| `W3-001..008` | `EPIC-04`, `STORY-016..021` | Current graph is source-scoped and live-pending; no unreviewed merge. |
| `W4-001..007` | `EPIC-05`, `STORY-022..027` | Million vote rows do not close historical/text/reconciliation gaps. |
| `W5-001..009` | `EPIC-06`, `STORY-028..032` | Current award/subsidy facts do not imply payment/delivery/outcome. |
| `W6-001..011` | `EPIC-07`, `STORY-033..040` | Existing vertical slices remain bounded; comparison live gate open. |
| `W7-001..009` | `EPIC-08`, `STORY-041..047`, `STORY-065` | `W7-009` contains C1 closure, C2A, and C2B next scale proof; none implies L2 claim. |
| `W8-001..008` | `EPIC-09`, `STORY-048..053` | C2C proves local task/slot and append-only control capacity; review operation still requires real authorities, reviewers, completed decisions, corrections, immutable operational export and measured SLOs. |
| `W9-001..014` | `EPIC-10..11`, `STORY-054..064` | Done infrastructure is reused; external operation and pending routes remain open. |
| `SCALE-001..014` | `EPIC-01`, `EPIC-03`, `EPIC-09`; `XREQ-05..07`, `XREQ-13` | Queue/readiness/integrity primitives; real million operation remains separate. |
| `SCALE-015..023` | `EPIC-02..03`, `STORY-005..015` | Format/origin/OCR/100k technical backlog; exact tracker status retained. |
| `SCALE-024..031`, `SCALE-038..042`, `SCALE-046..049` | `XREQ-05..12`, `EPIC-02`, `EPIC-10` | Shared Parquet, reconciliation, public-delivery, operations, DR, and cost work. |
| `SCALE-032` | `EPIC-04`, `STORY-021` | Actor/candidate/mandate `R2`; current source-scoped counts insufficient. |
| `SCALE-033` | `EPIC-05`, `STORY-027` | Member-vote/action `R2`; capture/reconciliation gaps open. |
| `SCALE-034` | `EPIC-07`, `STORY-035` | Accountability-fact `R2`; representative mix open. |
| `SCALE-035..036` | `EPIC-06`, `STORY-028..032` | Contract/subsidy `R2`; history/revisions/semantics open. |
| `SCALE-037` | `EPIC-08`, `STORY-041..045` | Indicator `R2`; representative mix/revisions/corrections open. |
| `SCALE-043..045` | `EPIC-09`, `STORY-048..052` | Review/correction states exist; calibrated public workflow open. |
| `SCALE-050..052` | `EPIC-11`, `STORY-060..063` | Contributor throughput and multi-maintainer proof open. |
| `ACC-001..005` | `EPIC-07`, `STORY-033..035` | Technical responsibility/ledger work remains derived from `W6`. |
| `OUT-001..005` | `EPIC-08`, `STORY-041..047`, `STORY-065` | `OUT-004` bounded live observation slice; `OUT-005` C1/C2A/C2B portable-delivery gates remain as classified. |
| `INT-001..006` | `EPIC-09`, `STORY-048..053` | C2C capacity is accepted locally; real trust/identity/operation/export and all high-risk publication prerequisites remain open. |
| `PUB-001..003`, `PUB-008`, `PUB-013` | `EPIC-10`, `STORY-054..058` | Bounded API/status infrastructure and live evidence routes. |
| `PUB-004..007`, `PUB-009..012` | `EPIC-11`, `STORY-059..064` | SDK/governance/reproducibility; external maintainer proof open. |
| `PUB-014..018` | `STORY-032`, `STORY-037..039`, `STORY-045` | Existing public vertical slices remain inputs to broader canonical epics, not proof of representative lane completion. |

Orphan claims: none identified. Unsupported deliverables: none treated as confirmed; C2 durable-origin/promotion and C2C real-operation/export work plus all owner-open work are required proposals backed by canonical gaps, while C2A/C2B portable execution and C2C capacity are confirmed only locally. Duplicate coverage: `STORY-058` owns only cross-route release acceptance; upstream actor/comparison/outcome semantics remain owned by `STORY-019`, `STORY-040`, and `STORY-046`. Consciously excluded topics are listed under Exclusions.

## Decision-Changing Questions

| Priority | Question | Why it matters | Outcome if A | Outcome if B |
| --- | --- | --- | --- | --- |
| `P0` | Which source/jurisdiction/time strata define representative completion for each lane? | Changes corpus size, connectors, quality samples, and promotion. | Approved matrix makes `R1/R2` acceptance and estimates coherent. | Without it, rows can grow but lanes remain unpromotable and unestimable. |
| `P0` | Which external raw-object origin, retention, and recovery policy is authorized? | Controls durability, cost, restore, and document/outcome promotion. | Implement `STORY-005..006` against chosen contract. | Keep raw-dependent lanes explicitly open. |
| `P0` | Who owns statistical methods, legal/editorial gates, and final high-risk publication decisions? | No reviewed outcome/integrity claim can ship without accountable authority. | Freeze claim/review language and acceptance. | Continue descriptive/zero-state publication only. |
| `P0` | Who authorizes publication of the frozen C1 v3 package after exact remote parity and live browser verification? | Local status, `17` assets, build, route audit and browser proof now agree; authority/live state are the remaining release boundary. | Publish immutable package, verify live, record release. | C1 remains locally validated and publicly unclosed. |
| `P0` | Which durable immutable origin will hold the accepted C2A/C2B shards and C2C capacity manifest, and can an isolated operator restore/rollback them byte-identically? | Local physical capacity and local restore pass; workstation-local artifacts are not disaster recovery. | Upload, independently restore, revalidate roots, exercise rollback, then decide whether each downstream gate may advance. | Keep C2 as internal L0/capacity evidence with no public relationship or human-operation claim. |
| `P0` | Can missing historical vote/text bytes and actor raw-source hashes be recovered exactly? | Blocks stronger provenance and outcome L2 prerequisites. | Bind immutable bytes and validate. | Preserve explicit unresolved blocks/derived labels and keep L2 closed. |
| `P0` | Who supplies and governs real reviewers for identity, OCR, outcome, and integrity queues? | Review labor/quality is critical path and main unknown cost. | Operate calibration, dual review, adjudication, and SLA. | Keep review-dependent releases and estimates open. |
| `P1` | Who may publish main/public branches and activate or revert release pointers? | Required for safe live closure and measured rollback. | Execute audited compare-and-swap and live verification. | Local validation remains pending publication. |
| `P1` | Which three independent maintainers and external reproducer will own critical paths? | Final societal-scale DoD requires real distributed ownership. | Validate bus factor and second-party attestation. | Ecosystem completion remains open despite tooling. |
| `P1` | What budget, provider, staffing, and horizon constraints apply after scope freezes? | Needed for coherent bottom-up estimate and capacity plan. | Estimate stories using measured real throughput and conditional branches. | Continue sequencing by evidence/impact without fabricated cost or dates. |

## Audit Log

| Pass ID | Audit | Scope reviewed | Material findings | Corrections made | Residual issues |
| --- | --- | --- | --- | --- | --- |
| `PASS-01` | Full lexical, semantic, structural, evidence, boundary, uncertainty, estimate-readiness, and adversarial loop | Entire canonical roadmap plus first systematic layer, one line/item at a time | “Scale,” “candidate,” “outcome,” “live,” “done,” “privacy,” “durable origin,” and “restore” could overstate scope; early C2 wording bundled eligibility with execution; several claim destinations pointed to shifted story IDs. | Added terminology corrections; separated capacity from promotion, official identity from private state, observations from effects, local from live, analytical from raw restore; split C2A execution from C2B million proof; corrected story trace. | `DEC-01..12`; risks below. |
| `PASS-02` | Full lexical, semantic, structural, evidence, boundary, uncertainty, estimate-readiness, and adversarial loop | Revised sources, 24 atomic claims, 24 topics, four initiatives, eleven epics, 65 stories, requirements, ownership, and bidirectional trace | Potential overlap between upstream lane stories and public release QA; “reuse” could imply portability; named ownership was unsupported; wave target durations could be mistaken for estimates; initiative ranges and one topic/actor trace were too implicit. | Limited `STORY-058` to cross-route acceptance, kept semantics with upstream owners, bounded every reuse claim to validated layer, used unassigned role owners, explicitly barred wave targets from estimation, enumerated initiative epics, and made `TOP-19`/community actor trace explicit. | No named owners, approved source matrices, review workforce, or estimate inputs. |
| `PASS-03` | Targeted lexical, semantic, structural, evidence, boundary, uncertainty, estimate-readiness, and adversarial loop | Changed/current/high-risk lines: C1 v3, C2A/C2B, actor/comparison live state, public identity, origin/restore, review, ownership, exclusions, estimation | Eligibility arithmetic could be misread as physical throughput; local physical capacity could be misread as promotion or a relationship claim; pending publication could be misread as live. | Froze the deterministic `17`-asset C1 package; recorded accepted C2A/C2B physical runs, independent checks and recovery tests; kept L0/no-claim/publication boundaries explicit; preserved all official public identities. | C1/C2 remote publication, durable remote origin/restore/rollback, human decisions, actor/vote raw provenance remain open. |
| `PASS-04` | Post-implementation lexical, semantic, structural, evidence, boundary, uncertainty, estimate-readiness, and adversarial loop | C2B identity/package/replay and C2C schema/materializer/validator/operator/capacity evidence, every changed status claim, trace edge and risk | Host Python drift changed the C2C physical hash; a hard-linked C2B validation control could be detached and followed by success instead of failing the anomalous run; first-build and verified-recovery reports were conflated by one test; capacity could be misread as real reviewer operation. | Pinned Python `3.12` and PyArrow `20.0.0`; rebuilt and repinned C2C; rejected linked validation controls before invalidation; made report-state assertions exact; recorded `330 + 12`, `22`, and `23` passing checks/tests; preserved zero-human and no-publication state. | Durable C2 origin/restore/rollback, real operational snapshot builder/export, reviewers/authorities, human decisions, promotion, C1 live publication and full-repo post-change gates remain open. |
| `PASS-05` | Targeted lexical, semantic, structural, evidence, boundary, uncertainty, estimate-readiness, and adversarial loop | `REV-08`, document baseline, `W2-006`, strict order, `STORY-014..015`, `DEC-01`, and `RISK-14` against the source-universe report plus independent replay | Stored-corpus `100k`, acquisition supply `100k`, host-level physical proof, and representativeness could be conflated; total HTTPS exceeds `100k` while eligible supply does not. | Named each gate separately; bound `104,064` public / `100,418` HTTPS / `90,121` eligible / `9,879` target gap; changed physical wording to host-level proof; kept `DEC-01`, human review, monetary rates, raw origin, and `1M` open. | `9,879` contract-eligible URLs, representative-strata approval, next cold control proof, and all prior promotion gaps remain open. |
| `PASS-06` | Targeted scale, provenance, crash-safety, privacy-hygiene and claim-boundary loop | `REV-09`, document baseline, `W2-006`, `STORY-015`, v4 planner/preflight/equivalence evidence and `RISK-14` | The old producer streamed partitions but still materialized the candidate universe, flattened Parliament reference pairs, allowed output-lock collisions, and could strand DB/partitions after process death. A `90,121` preparation could also be misread as a network acquisition or representative `100k`. | Moved selection/deduplication to file-backed SQLite; added deterministic bounded sub-shards, exact selection/execution hashes, exact reference pairs, sorted per-target kernel locks, before/after input hashes, journaled staging and manifest-last publication. Proved exact normalized `10k` SQL parity and preflighted every current eligible row under `62 MB` planner RSS. | No new network request was made; physical cold proof remains `10k`; eligible supply is still short `9,879`; `DEC-01`, human review, monetary rates, raw origin, `100k`, and `1M` remain open. |
| `PASS-07` | Full post-`REV-10` lexical, semantic, structural, evidence, boundary, uncertainty, estimate-readiness, and adversarial loop | Updated executive truth, `W0/W2`, source/claim ledger, `STORY-014..015`, `DEC-01`, critical path, coverage, and risks against exact planner, queue, provenance, extraction, OCR, source-universe, readiness, and access-incident evidence | “100k closed” could conflate zero-gap supply, deterministic selection, physical acquisition, representative quality, or `R2`; a progress report with schema status `running` could be mistaken for terminal success; current processing could be mistaken for final post-tail generation; a timeout could be overstated as intentional obstruction or permanent outage. | Split five gates explicitly; recorded `100,000` planned vs `100,051/100,867` BOE captured vs `122,607` current processed; kept `815` unfinished, `0/40` review, durable raw origin, final regeneration, and `1M` open; changed global status to current-readiness blocked; described BOE incident factually without motive; preserved exact official public identity and zero mock/synthetic policy. | BOE health/new lever, `DEC-01`, human review, state-generation rotation, raw origin/restore, production rates, and `1M` remain open. |
| `PASS-08` | Bounded-lineage scale, reproducibility, provenance, privacy, and failure-boundary loop | `REV-11`, BOE exporter, independent validator, provenance loader, readiness contract, registry, and real `100,051`-row production output | A fixed-name shard set could corrupt the current index during failed regeneration; an index-only hash could hide shard drift; in-memory distinct-hash tracking would grow toward `1M`; sharding could be mistaken for physical BOE completion. | Published content-addressed generation directories before manifest-last index replacement; bound every shard by compressed/uncompressed hash, bytes, rows and URL bounds; added independent full raw/summary rehash; moved audit distinct hashes to SQLite; kept `815` unfinished and readiness failure explicit. | Interrupted reconstruction proof, explicit generation supersession/retention, BOE tail, `DEC-01`, human review, raw origin/restore, and `1M` remain open. |
| `PASS-09` | Activation, interruption, retention, rollback-ambiguity, privacy, and stale-state loop | `REV-12`, BOE manifest publisher, lifecycle auditor, registry/readiness contract, and real-capture interruption test | Manifest-last protects the live pointer only if old/new indices and generations remain reconstructable; a crash before activation could strand an unreported candidate; reactivating a historical index could falsify predecessor order; cleanup could erase evidence. | Archived exact indices by SHA-256, added immutable activation receipts and predecessor chains, refused historical reactivation outside an explicit rollback workflow, prohibited automatic deletion, classified unactivated/orphan/staging state, full-hashed retained shards, and forced interruption before the live switch using real captured rows. The prior index remained byte-identical and valid; successful continuation retained both generations and closed the chain. | Production currently has only one active lineage generation because no changed corpus has been activated since this control was installed. BOE tail, native/OCR state-generation rotation, raw durable restore, `DEC-01`, human review, and `1M` remain open. |
| `PASS-10` | Native/OCR partial-publication, monolith, state-restore, crash-window, privacy, and stale-input loop | `REV-13`, shared generation publisher/reader/auditor, extraction/OCR producers and validators, readiness registry, and real-capture failure-injection test | Both producers previously rewrote monolithic “latest” JSONL on every run, including nonterminal work. At `1M`, a crash or bounded partial run could expose incomplete state; the SQLite work state was input-bound but not preserved as an independently restorable activation artifact. | Added terminal-only activation; bounded content-addressed gzip shards; small live indices; immutable archived indices and prewritten receipts; live switch last; checksum-addressed SQLite backups; full decompression, checksum, restore and `quick_check`; explicit orphan/unactivated/staging detection; no-delete policy; and historical-reactivation refusal. Failure injection with real captured rows proves the old generation remains byte-identical while an interrupted candidate is retained and visible. Production native and OCR audits pass at full depth. | Current production has one active native and one active OCR lifecycle generation, so real changed-production predecessor chains remain for the post-BOE generation. BOE tail, raw/CAS durable origin, `DEC-01`, human review, monetary rates, and `1M` remain open. |
| `PASS-11` | Million-object publication fanout, archive nondeterminism, size ceiling, partial activation, privacy, and deletion loop | `REV-15`, exact origin manifest, pack queue, full pack verifier, lifecycle audit, registry/readiness contract, and real-object deterministic replay | Uploading `240,226` loose objects creates excessive remote file/commit fanout; count-only blocks can exceed provider limits; ordinary tar/gzip metadata changes physical hashes; mutable delete-pattern uploads can destroy prior evidence. | Added exact source-manifest binding, resumable pack state, simultaneous `10,000`-object and `448 MiB` payload ceilings, normalized tar ownership/mode/time and gzip time, content-addressed pack/member-manifest names, terminal-only activation, state snapshot, no-delete policy, full member restore/rehash, and byte-identical replay from actual production objects. | Package remains local. Explicit release authority, append-only remote upload, remote parity, independent clean restore, BOE tail, `DEC-01`, human review, and `1M` remain open. |
| `PASS-12` | Language-label overclaim, structured-text misclassification, full-replay cost, generation drift, privacy, and stale-readiness loop | `REV-17`, exact document profile, independent validator, lifecycle audit, registry and central readiness | Normalized model confidence can be extreme on list-heavy official XML/HTML and does not establish correct language; calling it “detected” would overstate evidence. A profile can also drift from raw/native bytes or expose a partial generation at `1M`. | Renamed the public result to machine-language candidate, preserved confidence/runner-up and source-declared agreement/conflict, marked all contents unreviewed, retained explicit unknowns, fully rehashed raw/native inputs, independently replayed all `120,757` contents, and activated bounded immutable shards/state with predecessor linkage and no deletion. | Human language-quality review, representative strata approval, final post-BOE generation, authorized public origin, and real `1M` remain open. |
| `PASS-13` | Targeted real-format, provenance, locator-fanout, recovery, economics, publication-authority, and stale-readiness loop | `REV-20`, `SRC-15`, `CLM-28`, `STORY-010/012/015`, `DEC-02`, `RISK-02/12/14`, and current XLSX/origin/release/economics evidence | “Office support” could overclaim unobserved formats or formula semantics; path-derived XLSX URLs could be mistaken for provenance; local restore/read-only remote preflight could be mistaken for durable publication; warm-output timing or absent rates could be reported as cold cost; new processing could hide the BOE lineage/queue blocker. | Named XLSX-only observed support; required independent replay of all `44` distinct workbooks; kept zero formulas as an open validation gap; denied provenance credit to all `46` inferred mappings; bound `261` row groups to explicit one-million fanout limits; separated local origin/release preparation from remote publication; treated missing cold benchmarks as measurement gaps while integrity stays fail-closed; preserved the exact BOE mismatch and queue state. | `DEC-01`, BOE lineage/tail, human review, non-XLSX office/formula cohorts, authorized remote origin/restore, cold telemetry, monetary rates, and real `1M` remain open. |

## Residual Risks and Open Issues

| Risk ID | Open issue | Impact | Owner | Next evidence |
| --- | --- | --- | --- | --- |
| `RISK-01` | Zero lanes currently satisfy every promotion gate. | Societal-scale claim remains false despite useful high row counts. | Program maintainer plus lane owners | Per-lane representative matrix and full §4.2 attestation. |
| `RISK-02` | Full raw-document/object remote origin remains unproven; exact current local replication, clean restore, and immutable bounded packaging pass for `240,278` objects / `6,048,142,788` payload bytes, and release `a891bbab...` passes local dry-run plus read-only remote collision preflight only. | Loss of local state can still lose source evidence; document/outcome promotion remains blocked. | Storage/release owner unassigned | Authorize append-only upload of the exact `25`-pack / `154`-file generation, then prove remote parity, empty independent restore, full rehash, rollback, version/delete guard, retention and real cost. |
| `RISK-03` | Historical vote/text captures and some official endpoints remain blocked or incomplete. | Parliamentary reconstruction and downstream L2 provenance incomplete. | Parliamentary source stewards unassigned | Immutable official bytes/equivalence or append-only unresolved incident with scope impact. |
| `RISK-04` | Actor graph lacks adjudicated cross-source gold set, merge/split history, and complete raw actor-source hashes. | False identity joins or overclaimed actor provenance could misattribute responsibility. | Identity lead unassigned | Dual-reviewed gold set, precision/recall, immutable resolution events, content-hash binding. |
| `RISK-05` | Outcome C1's frozen local package is not yet published and verified live. | A correct local package can still diverge during remote deployment. | Outcome and release maintainers | Publish exact `5ac01878...` package and `226dfdf9...` status; verify every remote asset hash and desktop/mobile browser branch. |
| `RISK-06` | C2A/C2B physical delivery and C2C capacity are proven only on local single-node artifacts without durable remote origin or isolated remote restore. | Loss of local state or provider/restore defects could invalidate operational recoverability; L0 rows or empty capacity slots could be overread as claims or completed review. | Outcome pipeline and storage/release owners unassigned | Upload exact shards/databases/manifests to authorized immutable origin; independent clean restore/rollback and revalidation; preserve non-public/no-claim/no-human-operation flags. |
| `RISK-07` | C2C supplies million-task capacity and lifecycle constraints, but human OCR, identity, outcome, and integrity review operations still lack real trust roots, completed representative work, immutable operational export and assigned workforce. | Quality, allegation safety, correction SLA, operational security and major cost remain unknown. | Review/editorial/legal owners unassigned | Build a separately reviewed operational snapshot from real authority/identity evidence; run calibration, dual reviews, adjudications, appeals/corrections and agreement/latency/cost scorecard; export immutably before use. |
| `RISK-08` | Actor graph, comparison and frozen outcome C1 package remain pending live publication. | Local truth is not public truth; statuses can drift. | Release authority unassigned | Source branch publication, full build, exact remote assets, route/browser/accessibility audit, status update. |
| `RISK-09` | Source snapshots and action cutoffs can be stale; second-snapshot semantics are sparse. | Public conclusions may lag or mishandle revisions/deletions. | Source stewards plus release maintainer | Approved freshness SLAs and real changed/unchanged/deleted second-snapshot tests. |
| `RISK-10` | Legal/statistical/editorial thresholds and right-of-reply governance have no named authority. | High-risk claims cannot be safely approved or corrected. | Maintainer governance | Named accountable roles and approved method/publication/correction policies. |
| `RISK-11` | Three-maintainer operation and external second-party reproduction remain absent. | Bus factor and independent trust remain below final DoD. | Community/governance lead unassigned | Ownership map, real contributions, independent restore/validation/signature. |
| `RISK-12` | C2B/C2C provide measured local million-run capacity and the document factory reports current-full native/OCR warm-output telemetry, but cold-output benchmarks, monetary meter rates, production provider/storage/egress envelope, reviewer staffing, and representative all-lane cost remain absent. | Converting warm local capacity into cold throughput, delivery time, or monetary cost would be false precision; missing cost is unknown, not zero. | Sponsor/maintainer | Resolve `DEC-01..11`, run cold-state-and-output document benchmarks, price the chosen durable origin and egress, operate real review, then estimate bottom-up from measured telemetry. |
| `RISK-13` | Canonical roadmap, technical roadmap, tracker, generated registries, and live assets can drift independently. | False `DONE`, stale metrics, or contradictory public status. | Program/release maintainer | Automated cross-artifact status contract plus weekly generated-evidence closeout. |
| `RISK-14` | Numeric supply, exact planning, current PDF/XML/HTML/XLSX processing, bounded locators, and current local origin/restore/package pass, but the pinned cohort is BOE-heavy, active lineage references `1,156/1,166` successful summaries, physical capture remains `100,051/100,867`, and the route timed out. | Calling this “100k acquired” would erase the lineage mismatch, `815` unfinished jobs, representativeness, final processing, human quality, durable remote recovery, and promotion gaps. | Source stewards plus document/platform maintainers | Wait for a new BOE lever, reconcile all successful-summary lineage, finish/revalidate the tail, approve or replace `DEC-01`, activate the changed final generation, then prove human quality, authorized remote recovery, cold economics, physical representative `100k`, and all `1M` promotion gates. |
