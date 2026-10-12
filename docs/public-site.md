# Sitio público

Estado actual (`2026-10-12`):
- La app pública vive en `ui/gh-pages-next`; el build canónico es `just cloudflare-pages-build` (el nombre es histórico) y la salida está en `ui/gh-pages-next/out/`.
- `https://votaconlachola.org/` lo sirve el Worker `infra/cloudflare/votaconlachola-worker/`: shell y `_next` desde Workers Static Assets; todo lo demás desde el bucket R2 `vclc-site` (prefijo `site/`). Sin dependencias de GitHub ni Hugging Face en tiempo de ejecución.
- La rama `gh-pages` se mantiene como registro auditable en git de cada publicación y es la fuente que se sincroniza a R2.
- Cada sincronización publica `/releases/latest.json` y `/releases/<id>/manifest.json` (sha256 por fichero + commit de `gh-pages`).
- `/datasets/` replica el último snapshot Parquet de HF (verificado contra `checksums.sha256`); el explorador `/legacy/explorer/` lo lee ahí (`?source=hf` fuerza HF).
- `/downloads/<release>/placsp-launch.zip` sirve entero el ZIP de PLACSP que `gh-pages` guarda troceado (git limita el tamaño por fichero); se verifica contra `spending/launch/latest.json` antes de subirlo.
- El proyecto Cloudflare Pages paralelo está retirado: no sirve el dominio y CI ya no despliega en él.
- `/elecciones/andalucia-2026/` es la primera página electoral dedicada: usa `ui/gh-pages-next/public/elecciones/andalucia-2026/data/accountability.json`, muestra candidaturas oficiales, programas 2026, medidas programáticas declaradas por bloque, el primer historial scrapeado enlazado desde la Evidence API, 109 iniciativas legislativas oficiales del Parlamento andaluz, 4 documentos recientes de sentido del voto, 81 votaciones oficiales parseadas con conteos brutos por grupo, 25 votos enlazados a expediente oficial, 80 votos con triaje conservador de efecto legal, 25 resúmenes partido-tema, 8.827 votos nominales de diputado, 69 candidatos con resumen nominal enlazado, una cola voto-impacto de 81 ítems en 7 lotes con CSV en `ui/gh-pages-next/public/elecciones/andalucia-2026/data/parliament-vote-impact-review-queue.csv`, 20 resultados de votación revisados como señal legislativa sin mérito/culpa, 115 claims observados de responsabilidad legislativa (`100` partido, `15` candidato foco) con fuente primaria y limitación explícita, un comparador partido/candidato para esas señales, una matriz de responsabilidad verificable con 27 perfiles de partido y 5 candidatos foco, 10 paquetes por issue que cruzan programa/voto/BOJA (`8` con voto revisado, `7` con BOJA revisado, `6` con las tres capas) y ahora integran los `115` claims observados en `8` issues con `46` perfiles actor observados, 8 revisiones issue-level (`campo_agua`, `cultura_patrimonio`, `fiscalidad`, `energia_clima`, `educacion`, `sanidad`, `seguridad_libertades`, `vivienda`) sin scoring, 19 ítems de cola ejecución/presupuesto/outcomes para 8 temas con 13 fuentes oficiales verificadas, 11 archivos oficiales cacheados (`2` XLSX presupuesto/indicadores, `2` JSON de contratos menores 2024/2025, `5` JSON IECA/ODS, `1` muestra JSON de subvenciones y `1` archivo 7z de Tesorería), 204.635 filas oficiales candidatas (`188.537` presupuesto/ejecución, incluyendo `170.610` contratos menores y `240` pagos agregados de Tesorería; `12.285` indicadores/outcomes), 72 filas oficiales revisadas (`21` partidas presupuestarias como plan, `8` contratos menores como adjudicación administrativa, `4` concesiones de subvención, `6` pagos agregados de Tesorería, `28` indicadores como objetivo/previsión y `5` series IECA como baseline observado; sin entrega final, post-2026 outcome ni impacto observado) y CSV en `ui/gh-pages-next/public/elecciones/andalucia-2026/data/execution-evidence-queue.csv`, registros/fragmentos BOJA oficiales de la legislatura por bloque, 12 cambios legales BOJA revisados solo como cambio legal y una cola BOJA de revisión de impacto organizada en 10 lotes priorizados, con descarga CSV en `ui/gh-pages-next/public/elecciones/andalucia-2026/data/boja-impact-review-queue.csv`; no publica culpa/mérito aunque esos resultados estén revisados, porque faltan entrega final, beneficiarios, ejecución real, outcomes posteriores y causalidad antes de atribuir impacto ciudadano.
- Desde `2026-07-25`, `/elecciones/andalucia-2026/` usa `water-receipt.json` como entrada ciudadana: `81 KB` de HTML y `10 KB` de JSON con tres compromisos de agua revisados, fuentes oficiales y límites explícitos. Los artefactos técnicos completos quedan fuera del payload ciudadano. Entonces la misma salida se publicaba en Cloudflare Pages y en `gh-pages`; desde `2026-10-12` el dominio la sirve desde R2.

Publicar:

```bash
just votaconlachola-gh-pages-publish
```

Construye, publica `gh-pages` y sincroniza R2 (`just site-origin-publish`; solo sube ficheros cambiados y verifica paridad antes de borrar). Necesita `R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY` en el entorno o en `.env`; sin ellas falla, porque una publicación no está completa hasta que el origen está sincronizado. `just etl-publish-hf` replica además el snapshot de HF en `/datasets/` (`just site-dataset-mirror`).

El Worker cambia poco y se despliega a mano con la sesión OAuth de wrangler:

```bash
just site-origin-worker-deploy
```

Vuelta atrás: `wrangler versions deploy <version>@100` desde `infra/cloudflare/votaconlachola-worker/`. Plan gratuito: R2 ≤ 10 GB, escrituras solo de ficheros cambiados, ≤ 19k ficheros estáticos en el Worker.
