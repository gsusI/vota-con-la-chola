#!/usr/bin/env python3
"""Check immutable launch bytes after Git's filters, before publishing."""
import argparse
import hashlib
import gzip
import json
import subprocess


def verify(repo,prefix,ref):
    objects = subprocess.Popen(['git','-C',repo,'cat-file','--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    def read(path):
        objects.stdin.write((ref+':'+path+'\n').encode())
        objects.stdin.flush()
        header = objects.stdout.readline().decode().strip().split()
        if len(header) != 3 or header[1] != 'blob':
            raise ValueError('Missing Git blob: '+path)
        data = objects.stdout.read(int(header[2]))
        if objects.stdout.read(1) != b'\n':
            raise ValueError('Invalid Git batch framing')
        return data
    pointer=json.loads(read(prefix+'/latest.json'))
    base=prefix+'/'+pointer['release']
    def read_file(name):
        compressed = pointer.get('file_encodings', {}).get(name) == 'gzip' or (pointer.get('compressed_xml') and name.endswith('.xml'))
        parts = pointer.get('file_parts', {}).get(name)
        if parts:
            chunks = []
            for part in parts:
                chunk = read(base+'/'+part['path'])
                if len(chunk) != part['bytes'] or hashlib.sha256(chunk).hexdigest() != part['sha256']:
                    raise ValueError('Git changed transport part')
                chunks.append(chunk)
            data = b''.join(chunks)
        else:
            data = read(base+'/'+name+('.gz' if compressed else ''))
        return gzip.decompress(data) if compressed else data
    raw=read_file('manifest.json')
    if hashlib.sha256(raw).hexdigest()!=pointer['release']:raise ValueError('Git manifest hash mismatch')
    manifest=json.loads(raw)
    for name,f in manifest['files'].items():
        b=read_file(name)
        if len(b)!=f['bytes'] or hashlib.sha256(b).hexdigest()!=f['sha256']:raise ValueError('Git changed immutable bytes: '+name)
    archive=read_file('placsp-launch.zip')
    if len(archive)!=pointer['archive_bytes'] or hashlib.sha256(archive).hexdigest()!=pointer['archive_sha256']:raise ValueError('Git changed ZIP')
    objects.stdin.close()
    objects.wait()
    print(json.dumps({'git_bytes_verified':True,'files':len(manifest['files'])+2,'release':pointer['release']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',default='.');p.add_argument('--prefix',default='ui/gh-pages-next/public/spending/launch');p.add_argument('--ref',default='HEAD');a=p.parse_args();verify(a.repo,a.prefix,a.ref)
