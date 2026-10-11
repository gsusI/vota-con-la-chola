#!/usr/bin/env python3
"""Inventory captured PLACSP catalogs and local holdings; optional bounded HEAD sizing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import urllib.error
import urllib.request


def probe_archive(row):
    result = dict(row)
    request = urllib.request.Request(row['source_url'], method='HEAD', headers={
        'User-Agent': 'vota-con-la-chola-public-data/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            length = response.headers.get('Content-Length')
            result['remote'] = {
                'http_status': response.status,
                'bytes': int(length) if length and length.isdigit() else None,
                'last_modified': response.headers.get('Last-Modified'),
                'etag': response.headers.get('ETag'),
                'content_type': response.headers.get('Content-Type'),
            }
    except urllib.error.HTTPError as exc:
        result['remote'] = {'http_status': exc.code, 'bytes': None}
    except (OSError, ValueError) as exc:
        result['remote'] = {'http_status': None, 'bytes': None, 'error_type': type(exc).__name__}
    result['probed_at'] = datetime.now(timezone.utc).isoformat()
    return result


def probe_archive_sizes(archives):
    # This origin can close HEAD connections or omit lengths. Two unknowns are
    # enough evidence to stop; do not repeat an unsupported probe across history.
    unknown_streak = 0
    result = []
    for archive in archives:
        if unknown_streak >= 2:
            result.append(dict(archive, remote={
                'http_status': None, 'bytes': None,
                'not_probed_reason': 'size_probe_unsupported_stop_after_two_unknowns'}))
            continue
        row = probe_archive(archive)
        unknown_streak = unknown_streak + 1 if row['remote']['bytes'] is None else 0
        result.append(row)
    return result


def local_holdings(paths):
    databases = []
    for path in paths:
        item = {'file': path.name, 'bytes': path.stat().st_size}
        if path.suffix != '.db':
            item['state'] = 'archived_not_queried'
            databases.append(item)
            continue
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            conn.row_factory = sqlite3.Row
            item['state'] = 'queried_read_only'
            item['archives'] = [dict(r) for r in conn.execute('''
                SELECT period, source_url, content_sha256, bytes, raw_path, status,
                       members_total, uncompressed_bytes, fetched_at
                FROM placsp_bulk_archives ORDER BY period, fetched_at''')]
            for archive in item['archives']:
                archive['raw_file_exists'] = Path(archive.pop('raw_path')).is_file()
            item['records'] = dict(conn.execute('''SELECT count(*) versions,
                count(DISTINCT stable_contract_id) distinct_contract_ids,
                min(entry_updated_at) first_update, max(entry_updated_at) last_update
                FROM money_contract_records''').fetchone())
            item['result_rows_all_versions'] = [dict(r) for r in conn.execute('''
                SELECT result_code, count(*) rows FROM money_contract_award_results
                GROUP BY result_code''')]
        databases.append(item)
    return databases


def build_inventory(catalog_paths, db_paths, *, probe_sizes=False):
    catalogs, archives = [], []
    seen = set()
    for path in catalog_paths:
        data = path.read_bytes()
        catalog = json.loads(data)
        family = catalog['family']
        if family in seen:
            raise ValueError('duplicate family catalog')
        seen.add(family)
        catalogs.append({k: catalog[k] for k in
            ('family', 'catalog_url', 'as_of_date', 'discovered_at', 'status', 'expected', 'missing')}
            | {'report_sha256': hashlib.sha256(data).hexdigest()})
        for row in catalog['archives']:
            archives.append(dict(row, family=family,
                period_closed=row['period'] < catalog['as_of_date'][:7].replace('-', '')))
    holdings = local_holdings(db_paths)
    by_url = {}
    for db in holdings:
        for row in db.get('archives', []):
            by_url.setdefault(row['source_url'], []).append(dict(row, database=db['file']))
    if probe_sizes:
        archives = probe_archive_sizes(archives)
    for row in archives:
        row['local_captures'] = by_url.get(row['source_url'], [])
        row['acquisition_state'] = ('captured_requires_member_reconciliation'
            if any(x['raw_file_exists'] and x['status'] == 'ok' for x in row['local_captures'])
            else 'not_present_in_queried_databases')
    measured = [a for a in archives if a.get('remote', {}).get('http_status') == 200
                and a['remote']['bytes'] is not None]
    return {
        'schema_version': 'placsp_acquisition_inventory_v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'catalogs': catalogs, 'archives': archives, 'holdings': holdings,
        'capacity': {'free_bytes': shutil.disk_usage('.').free,
                     'sized_archives': len(measured), 'selected_archives': len(archives),
                     'remote_compressed_bytes_known': sum(a['remote']['bytes'] for a in measured)},
        'national_record_denominator': None,
        'limitations': [
            'Catalog containers are not contracts, awards, or proof of national coverage.',
            'HEAD size is transport planning evidence, not a downloaded checksum or completeness proof.',
            'Mutable current-month captures require refresh even when a local archive exists.',
            'Archived databases are preserved and not counted as currently queryable holdings.',
            'Cross-family and cross-period identifiers require reconciliation before adding record counts.',
            'Other PLACSP datasets, direct regional/local sources and TED remain separate universe gaps.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', action='append', type=Path, required=True)
    parser.add_argument('--db', action='append', type=Path, default=[])
    parser.add_argument('--probe-sizes', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = build_inventory(args.catalog, args.db, probe_sizes=args.probe_sizes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report['capacity']))


if __name__ == '__main__':
    main()
