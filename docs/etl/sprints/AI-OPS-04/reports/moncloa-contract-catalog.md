# Moncloa Contract Catalog (RSS/Referencias) — AI-OPS-04

Date: 2026-02-16
Batch root: `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216`
Input manifest: `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216/manifest.json`
Depends on: `2`
Parallel group: `P2`

## Goal
Produce deterministic field contracts for Moncloa `referencias` ingestion (RSS + HTML) before L2 code implementation.

## Sample Coverage

| Source family | Files in manifest | Parsed records | Notes |
|---|---:|---:|---|
| list HTML (`referencias/paginas/index.aspx`) | 5 | 18 items | Month slices Oct-2025..Feb-2026 |
| detail HTML (`referencias/Paginas/YYYY/...aspx`) | 20 | 20 pages | One page per referencia |
| RSS tipo16 (`rss-referencias-tipo16.xml`) | 1 | 4 items | Referencias feed |
| RSS tipo15 (`rss-resumenes-tipo15.xml`) | 1 | 4 items | Useful cross-reference to referencias URLs |
| RSS main (`rss-main.xml`) | 1 | 0 items | Captured payload is HTML, not XML |

## Stable ID Candidates (Deterministic)

| Candidate | Pattern / extraction | Coverage in sample | Example |
|---|---|---:|---|
| `stable_id_date8` | `([0-9]{8})` from referencia URL slug (`.../20260210-referencia-...`) | list: 18/18, detail: 20/20, rss16: 4/4, rss15: 0/4 | `20260210` |
| `stable_id_slug` | last URL segment without query (`*.aspx`) | list: 18/18, detail: 20/20, rss16: 4/4, rss15: 4/4 | `20260210-referencia-rueda-de-prensa-ministros.aspx` |
| `stable_id_guid` | RSS `<guid>` canonical URL (tipo16/tipo15) | rss16: 4/4, rss15: 4/4 | `https://www.lamoncloa.gob.es/.../20260210-referencia-...aspx` |

Preferred key for referencias records:
1. `stable_id_slug` (works across list/detail/rss16/rss15)
2. `stable_id_date8` as sortable helper only
3. `guid`/canonical URL retained for provenance

Escalation rule status: not triggered (stable_id candidates are present).

## Field Inventory Tables

### A) List HTML Contract (`referencias` index pages, n=18 items)

| Field | Extraction candidate(s) | Preferred rule | null-rate |
|---|---|---|---:|
| `stable_id` | `item_href -> stable_id_slug` | take slug from `href` | 0.0% |
| `title` | `<p class="title-advanced-news"><a>...` | strip HTML and trim | 0.0% |
| `published_at` | `<span class="date">d.m.yyyy</span>` | keep raw then normalize later | 0.0% |
| `event_date` | same as `published_at` | same source field | 0.0% |
| `source_url` | `item_href` | absolutize against site root at parse time | 0.0% |
| `summary/body excerpt` | none in list card | set null; fill from detail/RSS | 100.0% |

List example:
- `source_url`: `/consejodeministros/referencias/Paginas/2026/20260210-referencia-rueda-de-prensa-ministros.aspx`
- `published_at`: `10.2.2026`

### B) Detail HTML Contract (`referencias` detail pages, n=20 pages)

| Field | Extraction candidate(s) | Preferred rule | null-rate |
|---|---|---|---:|
| `stable_id` | canonical/og URL slug | slug from canonical URL | 0.0% |
| `title` | `h1#h1Title`, `og:title` | `h1` primary, `og:title` fallback | 0.0% |
| `published_at` | meta description date (`dd/mm/yyyy`) | extract first `dd/mm/yyyy` token | 0.0% |
| `event_date` | same as `published_at` | same extraction | 0.0% |
| `source_url` | canonical URL (`<link rel='canonical'>`) | canonical primary, `og:url` fallback | 0.0% |
| `summary/body excerpt` | first non-trivial paragraph in `MainContent` | first paragraph >= 80 chars, excluding `La Moncloa` boilerplate | 0.0% |

Detail example:
- `source_url`: `https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/2026/20260210-referencia-rueda-de-prensa-ministros.aspx`
- `published_at`: `10/02/2026`
- `summary/body excerpt`: `El Consejo de Ministros ha aprobado un acuerdo por el que se autoriza...`

### C) RSS Referencias Contract (`rss-referencias-tipo16.xml`, n=4 items)

| Field | Extraction candidate(s) | Preferred rule | null-rate |
|---|---|---|---:|
| `stable_id` | `<guid>`, `<link>` | slug from `guid`, fallback slug from `link` (strip `?qfr=16`) | 0.0% |
| `title` | `<item><title>` | direct text | 0.0% |
| `published_at` | `<item><pubDate>` | keep raw RFC-1123 | 0.0% |
| `event_date` | from `description_text` or URL date | secondary derivation only | 0.0% (derivable) |
| `source_url` | `<guid>` preferred over `<link>` | canonical URL without query | 0.0% |
| `summary/body excerpt` | `<item><description>` | keep both `description_html` and stripped `description_text` | 0.0% |

RSS tipo16 example:
- `guid`: `https://www.lamoncloa.gob.es/consejodeministros/referencias/Paginas/2026/20260210-referencia-rueda-de-prensa-ministros.aspx`
- `link`: `https://www.lamoncloa.gob.es/consejodeministros/referencias/Paginas/2026/20260210-referencia-rueda-de-prensa-ministros.aspx?qfr=16`
- `description_text`: `La Moncloa, martes 10 de febrero de 2026`

### D) RSS Resúmenes Cross-Reference Contract (`rss-resumenes-tipo15.xml`, n=4 items)

| Field | Extraction candidate(s) | Preferred rule | null-rate |
|---|---|---|---:|
| `stable_id` | `stable_id_slug` from `<guid>` | use slug (date8 not reliable here) | 0.0% |
| `title` | `<item><title>` | direct text | 0.0% |
| `published_at` | `<item><pubDate>` | direct text | 0.0% |
| `source_url` | `<guid>` | direct text | 0.0% |
| `summary/body excerpt` | `<item><description>` | preserve HTML and stripped text | 0.0% |

Important caveat: `stable_id_date8` is `null-rate=100.0%` in tipo15 sample because slugs are `ddmmyy-...`, not `yyyymmdd-...`.

## Null-Rate Summary (Key Fields)

| Contract slice | Records | stable_id | title | published_at | source_url | summary/body excerpt |
|---|---:|---:|---:|---:|---:|---:|
| list HTML referencias | 18 | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% |
| detail HTML referencias | 20 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| RSS tipo16 referencias | 4 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| RSS tipo15 resúmenes | 4 | 0.0% (`stable_id_slug`) | 0.0% | 0.0% | 0.0% | 0.0% |

## Parser Edge Cases (with examples)

1. `edge case`: `rss-main.xml` is not XML in this batch.
- Example: `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216/rss_feeds/rss-main.xml`
- Behavior: parse as HTML landing page, not RSS item stream.

2. `edge case`: URL path case mismatch (`Paginas` vs `paginas`) across sources.
- Example manifest URL: `.../referencias/Paginas/2026/20260210-referencia-...`
- Example canonical URL: `.../referencias/paginas/2026/20260210-referencia-...`
- Rule: lowercase path for canonicalization but preserve raw source for traceability.

3. `edge case`: list `href` values are relative, not absolute.
- Example: `/consejodeministros/referencias/Paginas/2026/20260210-referencia-...`
- Rule: absolutize with `https://www.lamoncloa.gob.es` before persistence.

4. `edge case`: RSS tipo16 title lexical variants exist.
- Observed values: `Referencia Consejo de Ministros`, `Referencia del Consejo de Ministros`
- Rule: do not key by title.

5. `edge case`: date formats differ by channel.
- list: `10.2.2026`
- detail meta: `10/02/2026`
- rss pubDate: `Tue, 10 Feb 2026 09:00:00 GMT`
- Rule: normalize into single datetime/date model downstream.

6. `edge case`: RSS descriptions contain HTML and relative links/images.
- Example from tipo15: description includes `<img ...>` and `<a href='/consejodeministros/referencias/...'>`
- Rule: preserve raw HTML + stripped text; resolve relative links when extracting joins.

7. `edge case`: window mismatch between sampled list pages and sampled detail pages.
- list extracted items: 18 (Oct-2025..Feb-2026)
- detail sample pages: 20 (includes Sept-2025 pages)
- Rule: contracts must support partial overlap during batch prep.

## L2 Implementation Guidance

1. Use `stable_id_slug` as canonical record key for referencias across list/detail/rss.
2. Ingest both `source_url_raw` and `source_url_canonical` (query stripped + absolutized + normalized case).
3. Keep dual summary fields: `summary_html_raw` and `summary_text`.
4. Parse and store three date channels separately before normalization:
- `published_at_raw` (rss)
- `event_date_raw` (detail/list)
- `event_date_norm` (derived)
5. Treat list pages as discovery/index only; do not expect summary/body from list cards.

## Acceptance Query

```bash
rg -n "stable_id|published_at|null-rate|edge case" docs/etl/sprints/AI-OPS-04/reports/moncloa-contract-catalog.md
```
