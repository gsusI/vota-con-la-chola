#!/usr/bin/env python3
"""Check immutable launch bytes after Git's filters, before publishing."""
import argparse
import hashlib
import json
import subprocess


def verify(repo,prefix,ref):
    def read(path):return subprocess.check_output(['git','-C',repo,'show',ref+':'+path])
    pointer=json.loads(read(prefix+'/latest.json'))
    base=prefix+'/'+pointer['release']
    raw=read(base+'/manifest.json')
    if hashlib.sha256(raw).hexdigest()!=pointer['release']:raise ValueError('Git manifest hash mismatch')
    manifest=json.loads(raw)
    for name,f in manifest['files'].items():
        b=read(base+'/'+name)
        if len(b)!=f['bytes'] or hashlib.sha256(b).hexdigest()!=f['sha256']:raise ValueError('Git changed immutable bytes: '+name)
    archive=read(base+'/placsp-launch.zip')
    if len(archive)!=pointer['archive_bytes'] or hashlib.sha256(archive).hexdigest()!=pointer['archive_sha256']:raise ValueError('Git changed ZIP')
    print(json.dumps({'git_bytes_verified':True,'files':len(manifest['files'])+2,'release':pointer['release']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',default='.');p.add_argument('--prefix',default='ui/gh-pages-next/public/spending/launch');p.add_argument('--ref',default='HEAD');a=p.parse_args();verify(a.repo,a.prefix,a.ref)
