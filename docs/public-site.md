# Sitio público

Estado actual:
- La app pública vive en `ui/gh-pages-next` y se publica como estático en `docs/gh-pages`.
- El pipeline `just explorer-gh-pages-build` ya genera el sitio y ahora escribe `CNAME` para `votaconlachola.org`.
- El build por defecto ya no asume la subruta histórica `/vota-con-la-chola`.
- Cloudflare mantiene un Worker en `votaconlachola.org/*` para canonizar rutas legacy (`/vota-con-la-chola/...`), añadir slash a rutas de directorio y servir el snapshot publicado desde la rama `gh-pages` mientras el cutover DNS/GitHub Pages se estabiliza.

Destino:
- URL pública canónica: `https://votaconlachola.org/`.
- Mantener `https://gsusI.github.io/vota-con-la-chola/` solo como fallback opcional mediante `GH_PAGES_NEXT_BASE_PATH=/vota-con-la-chola`.

Siguiente paso operativo:
- Publicar con `just explorer-gh-pages-publish`.
- En GitHub Pages, fijar `votaconlachola.org` como custom domain del branch publicado.
- Mantener DNS apuntando al hosting elegido para la rama `gh-pages`, o retirar el Worker cuando el cutover quede resuelto por DNS/CNAME directo.
