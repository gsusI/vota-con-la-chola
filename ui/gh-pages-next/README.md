# App Next de GH Pages

App estática en Next.js usada para generar el landing principal de GH Pages.

## Uso local

```bash
npm install
npm run dev
```

## Export estático

```bash
NEXT_PUBLIC_BASE_PATH="/vota-con-la-chola" npm run export:gh
```

La salida de build se escribe en `out/` y luego `just explorer-gh-pages-build` la copia a `docs/gh-pages/`.
