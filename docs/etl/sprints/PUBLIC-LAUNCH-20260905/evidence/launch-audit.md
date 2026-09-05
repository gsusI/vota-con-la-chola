# Auditoría de entrada pública — 2026-09-05

Estado: `audited_entry_points`; recomendación de producto, no validación integral de datasets ni publicación. Dirección y secuencia únicas: [ROADMAP](../../../../../ROADMAP.md#prioridad-inmediata-lanzamiento-útil-para-la-comunidad). Lectura de GitHub API, índices públicos HF, navegador real y archivos locales. No se contactó a terceros.

## Hallazgos comprobados

| Evidencia | Observación | Consecuencia |
| --- | --- | --- |
| [GitHub](https://github.com/gsusI/vota-con-la-chola), API del 2026-09-05 | Público; descripción y web configuradas; 0 stars, 0 forks, 10 issues abiertos, sin releases; Discussions desactivado | Acceso ya existe; faltan paquete de lanzamiento y prueba de adopción. Contadores no miden calidad técnica |
| README público, blob `59565f60063f6b2dba4e5248a5c3cee30b9c3bce` | Misión, gobernanza y cifras operativas antes de reproducción; difiere del README local | No asumir que el trabajo local está publicado |
| Checkout al iniciar | `main`, HEAD `6571f26730`; 77 entradas modificadas/no seguidas; README 209 líneas, ROADMAP 1186 | Preservar trabajo existente y aislar implementación/publicación |
| [Portada](https://votaconlachola.org/), navegador real | Cuatro entradas principales y numerosas secciones; «Workbench», «Elige superficie», «0 server runtime». Sin entrada directa para contribuir/descargar corpus en el recorrido inicial | Mostrar pregunta y resultado; reducir decisiones iniciales |
| [Dinero público](https://votaconlachola.org/spending/), navegador real | 330577 registros, 262558 resultados, 3190620 referencias; veinte adjudicaciones fijas y descarga JSON; muestra declara 4835494,71 EUR. Sin filtro/buscador en la página inspeccionada | Demostración del contrato; todavía no investiga un órgano/proveedor elegido |
| [Explorador SQL](https://votaconlachola.org/explorer/), navegador real | Índice estático, sin ejecución SQL; 355 eventos, 299 temas, cero nodos/aristas y cero posiciones/evidencias temáticas en sus contadores | Corregir expectativa y facilitar reproducción externa |
| [Explicador de votos](https://votaconlachola.org/vote-explainer/), navegador real | Páginas por voto compartibles; lista inspeccionada empieza por febrero de 2026 con salvedades de resultado derivado | Menor trabajo de interfaz; requiere explicar fecha y cobertura |
| [Issue 20](https://github.com/gsusI/vota-con-la-chola/issues/20), comentarios por API | 0/5 revisores, 0/5 pistas; segundo snapshot anunciado el 2026-08-07, tres compromisos `declarado`, `no_change` | Entrega técnica previa todavía sin validación comunitaria |
| [Índice HF de escala](https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/blob/main/scale/latest.json), GET anónimo | Release `5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd`, 2026-08-19; declara 7 corpora, 5414326 filas, 8597 archivos, 500714815 bytes, 0 lanes promocionadas | Distribución ya existe; no requiere otra plataforma |
| [Índice HF general](https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/blob/main/latest.json), GET anónimo | Snapshot 2026-08-12; 127 tablas/134 archivos; vote/initiative gates false | Los dos índices no son el mismo corte ni contrato; instrucciones deben fijar el correcto |
| Registry/manifests locales | PLACSP: 263302 facts = 121555 anuncios + 141747 adjudicaciones, 50 Parquet, 20803781 bytes, snapshot fuente 2025-03-31. BDNS: 1360382 filas, 14 Parquet, 42955289 bytes | Filas no equivale a contratos; separar muestra, corpus, antigüedad y cobertura |
| `etl/data/published/scale-readiness-latest.json` | Artefacto del 2026-08-30: `not_ready`, `BOE document corpus checks failed` | No afirmar plataforma completa; validar entrega limitada con estado global abierto |

## Trabajo existente que debe reutilizarse

- Código MIT; condiciones de datos separadas por fuente en `docs/legal/data-rights.md`. No etiquetar todos los datos como MIT.
- `CONTRIBUTING.md`, `CITATION.cff`, plantillas de corrección/fuente/PR, gobernanza y guía de partners.
- `docs/dev/quickstart.md`: `just dev` con Docker/just/Python y muestras oficiales; desarrollo ETL, no análisis inmediato del corpus público.
- `docs/examples/placsp-actor-spending-evidence.sql`: consulta existente que requiere `etl/data/staging/spending-placsp-mvp.db`.
- `docs/examples/sample-plugin.md`, `publicdata_core/plugins.py`, `just reference-plugin-check`: SDK y ejemplo oficiales; no crear un SDK nuevo para el primer contribuidor.
- `just etl-contributor-gates`: auditoría/tests, schema, exportación de catálogo, privacidad y dry-run HF. Medir coste para primera contribución; no ejecutado en esta auditoría documental.

## Comparación de primeras entregas

Juicio de producto, no predicción estadística de viralidad:

| Alternativa | Ventaja | Pendiente | Recomendación |
| --- | --- | --- | --- |
| Contratación PLACSP | Unos 21 MB analíticos; semántica y página existentes; pregunta entendible por técnicos/periodistas | Unir reproducción y exploración; snapshot histórico; resolver versiones/lotes/fechas | Primera entrega limitada; demostrar L0 antes de titular cifras |
| Votos explicados | Interfaz compartible operativa | Actualidad, cobertura y conciliación; menor conexión con reutilización de datasets | Utilidad secundaria, sin ampliar |
| Recibo andaluz | Caso editorial y revisión publicados | Sin revisión externa; mantenimiento de frescura | Conservar historial y estado honesto |
| BDNS | Más de un millón de filas | Elegir pregunta y construir entrada específica; segundo foco simultáneo | Siguiente fuente tras adopción |
| Plataforma universal | Amplia base técnica | Cobertura, metodología, durabilidad y revisión humana | Fuera del camino del primer lanzamiento |

L0 debe demostrar calidad semántica y resultado útil. Si el corte falla, reducirlo explícitamente. Esta auditoría no inventa una exclusiva ni certifica ausencia de errores.

## Referencias externas

- [gobiernovasco.marketing](https://github.com/JaimeObregon/gobiernovasco.marketing): README centrado en reparto de dinero público, con herramienta, fuentes, parser y JSON. Inferencia de diseño: caso comprensible + datos reutilizables ofrece entrada más clara que catálogo de capacidades; no predice apoyo de su autor.
- [subvenciones](https://github.com/JaimeObregon/subvenciones): precedente BDNS de Jaime Gómez-Obregón. Explicar aportación diferencial y reconocer precedentes; tamaño no demuestra novedad.
- [GitHub: README](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes): utilidad, inicio, ayuda y contribución como entrada.
- [GitHub: good first issue](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/encouraging-helpful-contributions-to-your-project-with-labels): descubrimiento de tareas abordables; no garantiza participación.

## Procedencia y límites

Inputs locales: `docs/etl/real-corpus-registry.json`, `docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/placsp-real-s1-v5-semantic-manifest.json`, manifest BDNS referenciado por registry, `etl/data/published/scale-readiness-latest.json`, README, CONTRIBUTING, roadmaps y guías indicadas. Cifras leídas de manifests; no se repitió full-validation. Índice HF leído en vivo; no se descargaron/revalidaron sus 8597 archivos.

Consultas públicas reproducibles: `gh repo view gsusI/vota-con-la-chola --json visibility,description,homepageUrl,stargazerCount,forkCount,latestRelease`; `gh issue list --repo gsusI/vota-con-la-chola --state open`; `gh issue view 20 --repo gsusI/vota-con-la-chola --comments`; `gh release list --repo gsusI/vota-con-la-chola`; GET anónimo a los índices HF enlazados. Navegador: portada, `/spending/`, `/explorer/`, `/vote-explainer/`; hallazgos limitados a esas páginas.

No auditoría funcional exhaustiva, prueba móvil, test externo de onboarding ni nueva reproducción íntegra de release. Pendientes cubiertos por L0–L5. Sin modificaciones remotas, mensajes, commits ni despliegue en esta sesión.
