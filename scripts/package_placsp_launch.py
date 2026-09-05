#!/usr/bin/env python3
"""Seal a checked PLACSP slice and its independently computed SQL answers."""
import argparse
import hashlib
import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,sort_keys=True,indent=2)+'\n')

def package(bundle,public):
    rows=json.loads((bundle/'awards.json').read_text())
    groups=defaultdict(lambda:[0,0]);months=defaultdict(lambda:[0,0])
    for r in rows:
        key=tuple(r[k] for k in ('authority_id','authority','supplier_id_scheme','supplier_id','supplier'))
        groups[key][0]+=1;groups[key][1]+=r['amount_cents']
        months[r['decision_date'][:7]][0]+=1;months[r['decision_date'][:7]][1]+=r['amount_cents']
    suppliers=[dict(zip(('authority_id','authority','supplier_id_scheme','supplier_id','supplier'),key),award_results=v[0],amount_cents=v[1]) for key,v in groups.items()]
    suppliers.sort(key=lambda r:(-r['amount_cents'],r['authority_id'],r['authority'],r['supplier_id_scheme'],r['supplier_id'],r['supplier']))
    keys=('award_key','authority_id','authority','supplier_id_scheme','supplier_id','supplier','contract_id','lot_id','decision_date','amount_cents','source_url','entry_sha256','capture_path')
    expected={'by-supplier':suppliers,'by-month':[dict(month=k,award_results=v[0],amount_cents=v[1]) for k,v in sorted(months.items())], 'records':[{k:r[k] for k in keys} for r in rows]}
    dump(bundle/'expected.json',expected)
    for p in (ROOT/'docs/examples/placsp-launch').iterdir():
        if p.is_file():shutil.copyfile(p,bundle/p.name)
    files={p.relative_to(bundle).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    manifest={'schema_version':'placsp-launch-package-v1','files':files}
    dump(bundle/'manifest.json',manifest)
    release=hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest()
    target=public/release
    if target.exists():
        raise ValueError('Immutable release already exists')
    shutil.copytree(bundle,target)
    archive=target/'placsp-launch.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():
                info=zipfile.ZipInfo(p.relative_to(bundle).as_posix(),date_time=(2026,9,5,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
                z.writestr(info,p.read_bytes())
    pointer=dict(release=release,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),archive_bytes=archive.stat().st_size,rows=len(rows),amount_cents=sum(r['amount_cents'] for r in rows))
    dump(public/'latest.json',pointer)
    print(json.dumps(pointer))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True,type=Path);p.add_argument('--public',required=True,type=Path);a=p.parse_args();package(a.bundle,a.public)
