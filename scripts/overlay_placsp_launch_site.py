#!/usr/bin/env python3
"""Overlay only the PLACSP launch routes onto a retained published site."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def overlay(build,site,report):
    pointer=json.loads((build/'spending/launch/latest.json').read_text())
    release=pointer['release']
    if len(release)!=64 or any(c not in '0123456789abcdef' for c in release):
        raise ValueError('Invalid release identity')
    files=[Path('index.html'),Path('index.txt'),Path('spending/index.html'),Path('spending/index.txt'),Path('spending/launch/latest.json')]
    for relative in [Path('_next/static'),Path('spending/launch')/release]:
        files.extend(p.relative_to(build) for p in (build/relative).rglob('*') if p.is_file())
    if not all((build/p).is_file() and not (build/p).is_symlink() for p in files):
        raise ValueError('Incomplete built launch')
    before={p.relative_to(site).as_posix():digest(p) for p in site.rglob('*') if p.is_file() and '.git' not in p.relative_to(site).parts}
    allowed={p.as_posix() for p in files}
    for rel in files:
        target=site/rel
        if target.is_symlink():raise ValueError('Published symlink refused')
        if target.exists() and (rel.parts[0]=='_next' or (len(rel.parts)>2 and rel.parts[:2]==('spending','launch') and rel.parts[2]!= 'latest.json')) and digest(target)!=digest(build/rel):
            raise ValueError('Immutable asset collision: '+rel.as_posix())
    for rel in files:
        target=site/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(build/rel,target)
    unchanged=0
    for rel,h in before.items():
        if rel not in allowed:
            if not (site/rel).is_file() or digest(site/rel)!=h:raise ValueError('Unrelated published file changed')
            unchanged+=1
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from publicdata_publish.privacy import collect_findings
    findings, scanned = collect_findings([p for p in site.iterdir() if p.name != '.git'])
    if findings:
        raise ValueError('Publication privacy check failed')
    result={'privacy_files_scanned':scanned,'privacy_findings':0,'schema_version':'placsp-scoped-publication-v1','release':release,'copied_files':len(files),'unrelated_files_retained_exactly':unchanged,'deleted_files':0,'routes':['/','/spending/'],'remote_mutation_performed':False}
    report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--site',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();overlay(a.build,a.site,a.report)
