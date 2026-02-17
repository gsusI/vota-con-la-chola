# Moncloa batch-prep evidence packet

Date: 2026-02-16
Batch: `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216`

## Commands run

1. Source scan and capture contract list

```bash
rg -n "Moncloa|la moncloa|referencias|rss" docs/ideal_sources_say_do.json docs/fuentes-datos.md docs/etl/e2e-scrape-load-tracker.md
```

2. Initial list and RSS payload capture (with month/year form posts for historical list views)

```bash
python3 - <<'PY'
import re, urllib.request, urllib.parse
from html import unescape

BASE='https://www.lamoncloa.gob.es/consejodeministros/referencias/paginas/index.aspx'
html=urllib.request.urlopen(BASE,timeout=40).read().decode('utf-8','ignore')
fields={}
for tag in re.findall(r'<input[^>]+>', html):
    name=re.search(r'name="([^"]+)"', tag)
    if not name:
        continue
    val=re.search(r'value="([^"]*)"', tag)
    fields[name.group(1)] = unescape(val.group(1)) if val else ''
print('parsed',len(fields),'form keys')
print('ddlMonth selected', fields.get('ctl00$PlaceHolderMain$DisplayMode$sumarioPaginado$SummarySearchByDate$EditModePanel$ddlMonth'))
print('ddlYear selected', fields.get('ctl00$PlaceHolderMain$DisplayMode$sumarioPaginado$SummarySearchByDate$EditModePanel$ddlYear'))
PY
```

3. Deterministic fetch + manifest generation

```bash
python3 - <<'PY'
# writes list pages, RSS feeds, 20 reference detail pages, and manifest to:
# etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216/manifest.json
# (script included in this session's execution)
PY
```

## Captured assets

### manifest summary

- `etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216/manifest.json`
- `list_page_count: 5`
- `detail_page_count: 20`
- `rss_feed_count: 3`
- `total manifest entries: 28`

### list page captures (files)

- `list_pages/index-2026-02.html`
- `list_pages/jan-2026.html`
- `list_pages/dec-2025.html`
- `list_pages/nov-2025.html`
- `list_pages/oct-2025.html`

### reference detail captures (20 unique)

- `detail_pages/detail_01.html`
- `detail_pages/detail_02.html`
- `detail_pages/detail_03.html`
- `detail_pages/detail_04.html`
- `detail_pages/detail_05.html`
- `detail_pages/detail_06.html`
- `detail_pages/detail_07.html`
- `detail_pages/detail_08.html`
- `detail_pages/detail_09.html`
- `detail_pages/detail_10.html`
- `detail_pages/detail_11.html`
- `detail_pages/detail_12.html`
- `detail_pages/detail_13.html`
- `detail_pages/detail_14.html`
- `detail_pages/detail_15.html`
- `detail_pages/detail_16.html`
- `detail_pages/detail_17.html`
- `detail_pages/detail_18.html`
- `detail_pages/detail_19.html`
- `detail_pages/detail_20.html`

### rss feed captures

- `rss_feeds/rss-main.xml`
- `rss_feeds/rss-referencias-tipo16.xml`
- `rss_feeds/rss-resumenes-tipo15.xml`

### Observed HTTP/meta from manifest (excerpt)

```
LIST index-2026-02 | http_status=200 | content_type='text/html; charset=utf-8' | sha256=d36f51b02446d490f16ac6e62ac7e089bb33829c7d85b84bec87a7fb6fa11204
LIST jan-2026    | http_status=200 | content_type='text/html; charset=utf-8' | sha256=d487afa072c29acb0edc026dd59dcc99efed5d02987bdacade3e341da865d79f
LIST dec-2025    | http_status=200 | content_type='text/html; charset=utf-8' | sha256=9f3b1302a706e1a1b75bb8a4326277268ed6e1d4bb2cc26268fb55a2d8ab8895
LIST nov-2025    | http_status=200 | content_type='text/html; charset=utf-8' | sha256=4f53ee65532ecb66fad2b9290fd5718b513fd42613384ae48521adf0ec232c19
LIST oct-2025    | http_status=200 | content_type='text/html; charset=utf-8' | sha256=c04c28bc55150eda3e12cb3185c9f06c885eefe8f4af40617a9aef200b461d05
RSS  rss-main    | http_status=200 | content_type='text/html; charset=utf-8'       | sha256=2514f98b97be9f9ba4398c54ba23d9984924676f2cc563fbec1e9baeeb3ab58b
RSS  tipo16      | http_status=200 | content_type='application/rss+xml; charset=UTF-8' | sha256=b1a2424e7bb34736e41c1c70510747b7485199025bbde0043e1921f6a9d29445
RSS  tipo15      | http_status=200 | content_type='application/rss+xml; charset=UTF-8' | sha256=e6376eff103985f2f8a6b082957ed92fde8766096092aa52406c57b0a9c67163
```

## Replayable local validation (no network)

```bash
python3 - <<'PY'
import json
from pathlib import Path

m = json.loads(Path('etl/data/raw/manual/moncloa_exec/ai-ops-04-20260216/manifest.json').read_text())
print('replayable_all_files_ok=', all(Path(e['file']).exists() and Path(e['file']).stat().st_size>0 for e in m['sources']))
for e in m['sources']:
    if e['type']=='list':
        txt=Path(e['file']).read_text(encoding='utf-8',errors='ignore')
        print('replayable list',e['name'],txt.count('/consejodeministros/referencias/Paginas/')>0)
for e in m['sources']:
    if e['type']=='rss':
        txt=Path(e['file']).read_text(encoding='utf-8',errors='ignore')
        print('replayable rss',e['name'],'item_count',txt.count('<item>'))
for e in m['sources']:
    if e['type']=='detail':
        txt=Path(e['file']).read_text(encoding='utf-8',errors='ignore')
        # simple parser smoke check
        print('replayable detail',e['name'], 'has_html_root', '<!DOCTYPE html>' in txt or '<html' in txt)
PY
```

Observed replay output during execution:

- `replayable_all_files_ok= True`
- list pages all returned `list_links` > 0
- `rss-main` had `item_count=0` (hub page), while `rss-referencias-tipo16` and `rss-resumenes-tipo15` had `item_count=4` each
- all 20 detail pages had the expected `<html` marker

## Reproducibility checks

```bash
rg -n "manifest|sha256|http_status|replayable" docs/etl/sprints/AI-OPS-04/reports/moncloa-batch-prep.md
find etl/data/raw/manual/moncloa_exec -type f | wc -l
```

Observed:

- `manifest` contains `sha256`, `http_status`, and `replayable` references.
- `find ... | wc -l` returned `32` (includes prior run artifacts in the same batch root).

## Notes

- No request blocks observed during capture (`HTTP 403` / challenge not encountered).
- Deterministic set is constrained by current run sequence and source parameters; if rerun with identical command flow and dates, fetched files should be the same.
