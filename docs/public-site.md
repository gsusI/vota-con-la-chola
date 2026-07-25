# Sitio público

Estado actual:
- La app pública vive en `ui/gh-pages-next` y se sirve como export estático desde Cloudflare Pages.
- El pipeline canónico es `just cloudflare-pages-build`.
- La salida pública está en `ui/gh-pages-next/out/`; `docs/gh-pages/` queda deprecado y no se versiona.
- El build por defecto no asume la subruta histórica `/vota-con-la-chola`.
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
