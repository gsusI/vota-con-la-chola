# GH Pages Next App

Static Next.js app used to generate the root landing page for GH Pages.

## Local usage

```bash
npm install
npm run dev
```

## Static export

```bash
NEXT_PUBLIC_BASE_PATH="/vota-con-la-chola" npm run export:gh
```

Build output is written to `out/` and then copied into `docs/gh-pages/` by `just explorer-gh-pages-build`.
