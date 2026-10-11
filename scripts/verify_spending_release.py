#!/usr/bin/env python3
"""Verify a sealed spending release, including every compressed transport part."""
import argparse
import hashlib
import json
from pathlib import Path


def checked_path(root, name):
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('Release path escapes root')
    return target


def transport(root, pointer, name):
    parts = pointer.get('file_parts', {}).get(name)
    if parts:
        for part in parts:
            digest = hashlib.sha256()
            size = 0
            with checked_path(root, part['path']).open('rb') as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
                    size += len(block)
                    yield block
            if size != part['bytes'] or digest.hexdigest() != part['sha256']:
                raise ValueError('Transport part mismatch: ' + part['path'])
    else:
        compressed = pointer.get('file_encodings', {}).get(name) == 'gzip' or (pointer.get('compressed_xml') and name.endswith('.xml'))
        with checked_path(root, name + ('.gz' if compressed else '')).open('rb') as stream:
            while block := stream.read(1024 * 1024):
                yield block


def decoded(root, pointer, name):
    import zlib
    compressed = pointer.get('file_encodings', {}).get(name) == 'gzip' or (pointer.get('compressed_xml') and name.endswith('.xml'))
    decoder = zlib.decompressobj(31) if compressed else None
    for block in transport(root, pointer, name):
        yield decoder.decompress(block) if decoder else block
    if decoder:
        yield decoder.flush()
        if not decoder.eof or decoder.unused_data:
            raise ValueError('Invalid gzip transport: ' + name)


def verify(public):
    pointer = json.loads((public / 'latest.json').read_text())
    root = checked_path(public, pointer['release'])
    manifest_bytes = (root / 'manifest.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != pointer['release']:
        raise ValueError('Manifest identity mismatch')
    manifest = json.loads(manifest_bytes)
    checked = 0
    for name, expected in manifest['files'].items():
        digest = hashlib.sha256()
        size = 0
        for block in decoded(root, pointer, name):
            digest.update(block)
            size += len(block)
        if size != expected['bytes'] or digest.hexdigest() != expected['sha256']:
            raise ValueError('Original file mismatch: ' + name)
        checked += 1
    digest = hashlib.sha256()
    size = 0
    for block in transport(root, pointer, 'placsp-launch.zip'):
        digest.update(block)
        size += len(block)
    if size != pointer['archive_bytes'] or digest.hexdigest() != pointer['archive_sha256']:
        raise ValueError('Archive mismatch')
    rows = json.loads(b''.join(decoded(root, pointer, 'awards.json')))
    if len(rows) != pointer['rows'] or sum(r['amount_cents'] for r in rows) != pointer['amount_cents']:
        raise ValueError('Count or amount mismatch')
    if len({r['award_key'] for r in rows}) != len(rows):
        raise ValueError('Duplicate award keys')
    from collections import Counter
    stages = Counter(r.get('result_stage', 'not_published') for r in rows)
    audit = json.loads(b''.join(decoded(root, pointer, 'audit.json')))
    if audit['selected_rows'] != len(rows) or audit['amount_cents'] != pointer['amount_cents']:
        raise ValueError('Audit balance mismatch')
    if 'selected_result_stages' in audit:
        if dict(stages) != audit['selected_result_stages']:
            raise ValueError('Result stage balance mismatch')
        for row in rows:
            if {'8': 'awarded', '9': 'formalized'}.get(row['result_code']) != row['result_stage']:
                raise ValueError('Result code and stage disagree')
    return {'ok': True, 'release': pointer['release'], 'files_verified': checked,
            'rows': len(rows), 'amount_cents': pointer['amount_cents'],
            'result_stages': dict(stages), 'archive_sha256': pointer['archive_sha256'],
            'scope': 'local_sealed_release_transport_and_content_not_remote_publication'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.public)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
