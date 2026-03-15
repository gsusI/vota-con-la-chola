# App Next del sitio público

App estática en Next.js usada para generar el sitio público principal.

## Uso local

```bash
npm install
npm run dev
```

## Export estático

```bash
npm run export:gh
```

La salida de build se escribe en `out/` y luego `just explorer-gh-pages-build` la copia a `docs/gh-pages/`.

Por defecto el build está preparado para servir el sitio sin `CNAME` forzado. Si quieres publicar un dominio personalizado directamente desde GitHub Pages, exporta `GH_PAGES_CNAME=<tu-dominio>` en el publish/build.

Si necesitas mantener el fallback histórico en una subruta de GitHub Pages, sobreescribe el base path:

```bash
NEXT_PUBLIC_BASE_PATH="/vota-con-la-chola" npm run export:gh
```
