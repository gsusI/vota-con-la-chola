# App estática pública

App estática en Next.js usada para generar el sitio público servido por Cloudflare Pages.

## Uso local

```bash
npm install
npm run dev
```

## Export estático

```bash
npm run build
```

La salida de build se escribe en `out/`. El flujo canónico desde la raíz del repo es:

```bash
just cloudflare-pages-build
```
