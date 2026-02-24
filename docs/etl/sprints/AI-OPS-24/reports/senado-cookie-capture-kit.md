# Senado Cookie Capture Kit (AI-OPS-24)

Problem: in this environment, Senado initiative/doc endpoints return `HTTP 403` to non-browser clients, so `backfill-initiative-documents` cannot download "qué se votó" texts without a browser-derived session.

This runbook captures cookies via Playwright and replays them in the downloader.

## 1) Capture Cookies (Interactive Browser)

Install Playwright (host Python):

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
```

Capture a representative Senado initiative page (solve any challenge in the browser window):

```bash
python3 scripts/manual_capture_playwright.py \
  --url "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=15&id1=610&id2=000002" \
  --label "senado_iniciativas_cookie_seed" \
  --wait-seconds 180
```

Outputs go under `etl/data/raw/manual/` (ignored by git). You want the emitted `*.cookies.json` or `*.storage.json`.

## 2) Replay Cookies Into The Downloader

Pick the cookies file:

```bash
ls -1 etl/data/raw/manual/senado_iniciativas_cookie_seed_*.cookies.json | tail -n 1
```

Then rerun with forced retry of forbidden URLs:

```bash
python3 scripts/ingestar_parlamentario_es.py backfill-initiative-documents \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --cookie-file "etl/data/raw/manual/<your>.cookies.json" \
  --cookie-domain "senado.es" \
  --retry-forbidden \
  --limit-initiatives 500 \
  --max-docs-per-initiative 2 \
  --timeout 30 \
  --sleep-seconds 1 \
  --sleep-jitter-seconds 1
```

Notes:
- If this starts returning `200`, increase `--limit-initiatives` gradually and keep sleep/jitter to reduce re-block risk.
- If it still returns `403`, the WAF may bind clearance to a browser profile/storage state. In that case, try capturing again and prefer `*.storage.json` (new profile), or use `scripts/manual_crawl_playwright.py` to crawl+save pages as a manual snapshot.

## 3) Verify Progress (KPIs + Missing URLs)

```bash
python3 scripts/ingestar_parlamentario_es.py quality-report \
  --db etl/data/staging/politicos-es.db \
  --include-initiatives \
  --initiative-source-ids congreso_iniciativas,senado_iniciativas
```

Export missing (still blocked) Senate URLs:

```bash
python3 scripts/export_missing_initiative_doc_urls.py \
  --db etl/data/staging/politicos-es.db \
  --initiative-source-ids senado_iniciativas \
  --only-missing \
  --only-status 403 \
  --out docs/etl/sprints/AI-OPS-24/exports/senado_missing_doc_urls_403_latest.txt \
  --format txt \
  --limit 500
```

