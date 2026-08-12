# Sitio público

Estado actual:
- La app pública vive en `ui/gh-pages-next` y se sirve como export estático desde Cloudflare Pages.
- El pipeline canónico es `just cloudflare-pages-build`.
- La salida pública está en `ui/gh-pages-next/out/`; `docs/gh-pages/` queda deprecado y no se versiona.
- El build por defecto no asume la subruta histórica `/vota-con-la-chola`.
- `/elecciones/andalucia-2026/` es la primera página electoral dedicada: usa `ui/gh-pages-next/public/elecciones/andalucia-2026/data/accountability.json`, muestra candidaturas oficiales, programas 2026, medidas programáticas declaradas por bloque, el primer historial scrapeado enlazado desde la Evidence API, 109 iniciativas legislativas oficiales del Parlamento andaluz, 4 documentos recientes de sentido del voto, 81 votaciones oficiales parseadas con conteos brutos por grupo, 25 votos enlazados a expediente oficial, 80 votos con triaje conservador de efecto legal, 25 resúmenes partido-tema, 8.827 votos nominales de diputado, 69 candidatos con resumen nominal enlazado, una cola voto-impacto de 81 ítems en 7 lotes con CSV en `ui/gh-pages-next/public/elecciones/andalucia-2026/data/parliament-vote-impact-review-queue.csv`, 20 resultados de votación revisados como señal legislativa sin mérito/culpa, 115 claims observados de responsabilidad legislativa (`100` partido, `15` candidato foco) con fuente primaria y limitación explícita, un comparador partido/candidato para esas señales, una matriz de responsabilidad verificable con 27 perfiles de partido y 5 candidatos foco, 10 paquetes por issue que cruzan programa/voto/BOJA (`8` con voto revisado, `7` con BOJA revisado, `6` con las tres capas) y ahora integran los `115` claims observados en `8` issues con `46` perfiles actor observados, 8 revisiones issue-level (`campo_agua`, `cultura_patrimonio`, `fiscalidad`, `energia_clima`, `educacion`, `sanidad`, `seguridad_libertades`, `vivienda`) sin scoring, 19 ítems de cola ejecución/presupuesto/outcomes para 8 temas con 13 fuentes oficiales verificadas, 11 archivos oficiales cacheados (`2` XLSX presupuesto/indicadores, `2` JSON de contratos menores 2024/2025, `5` JSON IECA/ODS, `1` muestra JSON de subvenciones y `1` archivo 7z de Tesorería), 204.635 filas oficiales candidatas (`188.537` presupuesto/ejecución, incluyendo `170.610` contratos menores y `240` pagos agregados de Tesorería; `12.285` indicadores/outcomes), 72 filas oficiales revisadas (`21` partidas presupuestarias como plan, `8` contratos menores como adjudicación administrativa, `4` concesiones de subvención, `6` pagos agregados de Tesorería, `28` indicadores como objetivo/previsión y `5` series IECA como baseline observado; sin entrega final, post-2026 outcome ni impacto observado) y CSV en `ui/gh-pages-next/public/elecciones/andalucia-2026/data/execution-evidence-queue.csv`, registros/fragmentos BOJA oficiales de la legislatura por bloque, 12 cambios legales BOJA revisados solo como cambio legal y una cola BOJA de revisión de impacto organizada en 10 lotes priorizados, con descarga CSV en `ui/gh-pages-next/public/elecciones/andalucia-2026/data/boja-impact-review-queue.csv`; no publica culpa/mérito aunque esos resultados estén revisados, porque faltan entrega final, beneficiarios, ejecución real, outcomes posteriores y causalidad antes de atribuir impacto ciudadano.
- Desde `2026-07-25`, `/elecciones/andalucia-2026/` usa `water-receipt.json` como entrada ciudadana: `81 KB` de HTML y `10 KB` de JSON con tres compromisos de agua revisados, fuentes oficiales y límites explícitos. Los artefactos técnicos completos quedan fuera del payload ciudadano. La misma salida se publica en Cloudflare Pages y en `gh-pages`, origen que todavía sirve el dominio canónico.

Destino:
- URL pública canónica: `https://votaconlachola.org/`.
- Cloudflare Pages debe apuntar a `ui/gh-pages-next/out/` como output directory.
- El proyecto conserva redirects/canonización de rutas legacy desde la capa Cloudflare cuando haga falta, pero ya no publica rama `gh-pages`.

Build local:

```bash
just cloudflare-pages-build
```

Cloudflare Pages:
- Build command: `just cloudflare-pages-build`
- Build output directory: `ui/gh-pages-next/out`
- Root directory: repo root

Deploy manual si hay credenciales Wrangler:

```bash
just cloudflare-pages-deploy
```

Nota: el deploy manual ejecuta primero `just cloudflare-pages-build`, que primea accountability desde los artifacts ya validados en `etl/data/published`. El refresh completo desde SQLite local queda separado para corridas ETL intencionales.
