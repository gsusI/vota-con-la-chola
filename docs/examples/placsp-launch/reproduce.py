#!/usr/bin/env python3
"""Verify and query the frozen PLACSP alpha with Python's standard library."""
import argparse
import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import time
import urllib.request
import zipfile
from decimal import Decimal
from pathlib import Path, PurePosixPath

QUERIES = ('by-supplier', 'by-month', 'records')
MAX_DOWNLOAD_BYTES = 100_000_000
MAX_UNPACKED_BYTES = 500_000_000
MAX_ARCHIVE_FILES = 20_000

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load_verified(root):
    manifest = json.loads((root/'manifest.json').read_text())
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(manifest['files']) | {'manifest.json'}:
        raise ValueError('Bundle file-set mismatch')
    for name, expected in manifest['files'].items():
        path = root/name
        if path.is_symlink() or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
            raise ValueError('Unsafe bundle path')
        data = path.read_bytes()
        if sha(data) != expected['sha256'] or len(data) != expected['bytes']:
            raise ValueError('Checksum mismatch: '+name)
    rows = json.loads((root/'awards.json').read_text())
    with (root/'awards.csv').open(newline='') as f:
        csv_rows = list(csv.DictReader(f))
    if [{k:str(v) for k,v in r.items()} for r in rows] != csv_rows:
        raise ValueError('CSV/JSON parity mismatch')
    if len({r['award_key'] for r in rows}) != len(rows):
        raise ValueError('Duplicate award')
    for r in rows:
        if Decimal(r['amount_decimal'])*100 != r['amount_cents']:
            raise ValueError('Amount precision mismatch')
        if sha((root/r['capture_path']).read_bytes()) != r['entry_sha256']:
            raise ValueError('Capture hash mismatch')
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.execute('CREATE TABLE awards ('+', '.join('"'+k+'" '+('INTEGER' if k in ('amount_cents','award_ordinal') else 'TEXT') for k in rows[0])+')')
    connection.executemany('INSERT INTO awards VALUES ('+','.join('?' for _ in rows[0])+')',[list(r.values()) for r in rows])
    return connection, rows

def run_queries(root, connection, params):
    return {name:[dict(r) for r in connection.execute((root/(name+'.sql')).read_text(),params)] for name in QUERIES}

def reproduce(root, params):
    c, rows = load_verified(root)
    default = dict(authority='',supplier='',start='2025-01-01',end='2025-01-31')
    expected = json.loads((root/'expected.json').read_text())
    if run_queries(root,c,default) != expected:
        raise ValueError('Published SQL result mismatch')
    results = run_queries(root,c,params)
    c.close()
    return results

def unpack_verified(data, digest, root):
    if sha(data)!=digest:
        raise ValueError('Download SHA-256 mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos=archive.infolist()
        if sum(i.file_size for i in infos)>MAX_UNPACKED_BYTES or len(infos)>MAX_ARCHIVE_FILES:
            raise ValueError('Bundle exceeds bounded extraction budget')
        names=set()
        for info in infos:
            name=PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in info.filename or info.filename in names or (info.external_attr>>16)&0o170000==0o120000:
                raise ValueError('Unsafe or duplicate ZIP member')
            names.add(info.filename)
            target=root/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(archive.read(info))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--bundle',type=Path);group.add_argument('--url')
    p.add_argument('--sha256');p.add_argument('--authority',default='');p.add_argument('--supplier',default='')
    p.add_argument('--start',default='2025-01-01');p.add_argument('--end',default='2025-01-31')
    a=p.parse_args();start=time.monotonic()
    params={k:getattr(a,k) for k in ('authority','supplier','start','end')}
    if a.url:
        if not a.sha256 or not a.url.startswith('https://'):
            p.error('HTTPS URL and trusted --sha256 are required')
        with urllib.request.urlopen(a.url,timeout=60) as response:
            data=response.read(MAX_DOWNLOAD_BYTES + 1)
        if len(data)>MAX_DOWNLOAD_BYTES:raise ValueError('Download exceeds bounded release budget')
        with tempfile.TemporaryDirectory(prefix='placsp-reproduction-') as tmp:
            root=Path(tmp);unpack_verified(data,a.sha256,root);results=reproduce(root,params)
    else:
        results=reproduce(a.bundle,params)
    print(json.dumps({'verified':True,'seconds':round(time.monotonic()-start,3),'results':results},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
