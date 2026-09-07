#!/usr/bin/env python3
"""Copy the reviewed public shell and hashed assets to Workers Static Assets."""
import argparse, json, shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--site',required=True);p.add_argument('--output',default='infra/cloudflare/votaconlachola-worker/public');a=p.parse_args()
site=Path(a.site);dest=Path(a.output)
if not (site/'spending/index.html').is_file() or not (site/'_next/static').is_dir():raise SystemExit('Missing reviewed spending build')
dest.mkdir(parents=True,exist_ok=True)
files=list((site/'_next').rglob('*'))
files += [site/'spending/index.html',site/'spending/index.txt',site/'index.html',site/'index.txt',site/'favicon.svg',site/'favicon.ico']
files += list(site.glob('__next*.txt'))
files=[f for f in files if f.is_file()]
if len(files)>19000:raise SystemExit('Workers Free static file budget exceeded')
for f in files:
 if f.stat().st_size>25_000_000:raise SystemExit('Static asset too large')
 out=dest/f.relative_to(site);out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,out)
(dest/'_headers').write_text('/_next/static/*\n  Cache-Control: public, max-age=31536000, immutable\n/spending/\n  Cache-Control: no-cache\n/\n  Cache-Control: no-cache\n')
if sum(1 for f in dest.rglob('*') if f.is_file())>19000:raise SystemExit('Accumulated static assets exceed free budget')
print(json.dumps({'files':len(files),'bytes':sum(f.stat().st_size for f in files),'source':'reviewed gh-pages checkout','copied_bulk_awards':False}))
