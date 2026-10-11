#!/usr/bin/env python3
"""Resume one catalog-bound PLACSP archive through normalization and validated Parquet.

Run with the project's Python/pyarrow runtime. Existing durable queues provide
download/member checkpoints. No public pointer or production database is changed.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT))


def plan(args):
    catalog = json.loads(args.catalog.read_text())
    if catalog['status'] != 'ok' or catalog['family'] not in ('main', 'minor', 'aggregated'):
        raise ValueError('catalog must identify a validated PLACSP family')
    date.fromisoformat(args.snapshot_date)
    rows = [r for r in catalog['archives'] if r['period'] == args.period]
    if len(rows) != 1:
        raise ValueError('period must occur exactly once in the captured official catalog')
    if args.min_free_bytes < 0 or args.max_archive_bytes <= 0:
        raise ValueError('invalid storage budget')
    output, reports, db = relative(args.output_root), relative(args.report_root), relative(args.db)
    # Avoid accidental mixing with another cohort's output; enqueue also binds
    # pipeline identity to the exact archive contract and snapshot date.
    contract = {'family': catalog['family'], 'period': args.period,
        'snapshot_date': args.snapshot_date, 'source_url': rows[0]['source_url'],
        'database': db, 'pipeline_id': args.pipeline_id, 'output_root': output}
    base = ['scripts/ingest_placsp_archives.py', '--db', db, '--pipeline-id', args.pipeline_id]
    stages = [
        ('enqueue', base + ['--report-out', f'{reports}/enqueue.json', 'enqueue',
            '--snapshot-date', args.snapshot_date, '--archive', f"{args.period}={rows[0]['source_url']}"]),
        ('download', base + ['--report-out', f'{reports}/download.json', 'work-archives',
            '--max-items', '1', '--download-attempts', '1', '--timeout', '60',
            '--max-archive-bytes', str(args.max_archive_bytes), '--min-free-bytes', str(args.min_free_bytes)]),
        ('normalize', base + ['--report-out', f'{reports}/normalize.json', 'work-members',
            '--claim-size', '1', '--min-free-bytes', str(args.min_free_bytes)]),
        ('export', ['scripts/export_semantic_partitions.py', '--lane', 'public_money_facts',
            '--db', db, '--output-root', output, '--snapshot-date', args.snapshot_date,
            '--manifest-out', f'{reports}/manifest.json', '--max-peak-rss-mb', '1024', '--enforce']),
        ('validate', ['scripts/validate_semantic_partitions.py', '--lane', 'public_money_facts',
            '--root', output, '--manifest', f'{reports}/manifest.json',
            '--report-out', f'{reports}/validation.json', '--enforce']),
    ]
    return contract, stages


def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def validate_existing_inputs(args, receipt_path):
    if receipt_path.exists() and not args.db.exists():
        raise ValueError('restore the archived cohort database before resuming its receipt')
    if not receipt_path.exists() and args.output_root.exists() and any(args.output_root.iterdir()):
        raise ValueError('refusing an existing export without a matching batch receipt')
    if args.db.exists() and args.db.stat().st_size:
        with sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            pipelines = {r[0] for r in conn.execute('SELECT pipeline_id FROM placsp_bulk_runs')}
            if pipelines - {args.pipeline_id}:
                raise ValueError('use a dedicated cohort database; another pipeline is present')


def run(args):
    contract, stages = plan(args)
    if args.plan_only:
        print(json.dumps({'contract': contract, 'stages': stages}, indent=2))
        return 0
    # Check runtime before starting acquisition, rather than discovering missing
    # Parquet support after downloading and normalizing a large archive.
    import pyarrow  # noqa: F401
    args.report_root.mkdir(parents=True, exist_ok=True)
    receipt_path = args.report_root / 'run.json'
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with args.db.with_suffix('.acquisition.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate_existing_inputs(args, receipt_path)
        receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {
            'schema_version': 'placsp_acquisition_batch_v1', 'contract': contract, 'attempts': []}
        if receipt['contract'] != contract:
            raise ValueError('report directory belongs to a different acquisition contract')
        for name, command in stages:
            attempt = {'stage': name, 'started_at': datetime.now(timezone.utc).isoformat(),
                'command': ['python'] + command, 'state': 'running'}
            receipt['attempts'].append(attempt)
            receipt['state'] = 'running'
            save(receipt_path, receipt)
            started = time.monotonic()
            with (args.report_root / f'{name}.log').open('w') as log:
                result = subprocess.run([sys.executable] + command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            attempt.update(elapsed_seconds=round(time.monotonic() - started, 3),
                returncode=result.returncode, state='passed' if result.returncode == 0 else 'failed')
            try:
                if result.returncode:
                    raise RuntimeError(f'{name} command failed')
                if name == 'download':
                    report = json.loads((args.report_root / 'download.json').read_text())
                    if report['archive_queue']['unfinished_total'] or report['archive_queue']['state_counts']['dead']:
                        raise RuntimeError('archive queue is not successfully terminal')
                if name == 'normalize':
                    report = json.loads((args.report_root / 'normalize.json').read_text())
                    if not report['analytical_ingest_gate_passed']:
                        raise RuntimeError('normalization gate failed; preserve checkpoints and stop')
                    with sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True) as conn:
                        if conn.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                            raise RuntimeError('SQLite integrity failed')
                        if conn.execute('PRAGMA foreign_key_check').fetchone() is not None:
                            raise RuntimeError('foreign key check failed')
            except (RuntimeError, OSError, ValueError, sqlite3.Error, KeyError) as exc:
                attempt.update(state='failed', error=str(exc))
                receipt['state'] = 'blocked'
                save(receipt_path, receipt)
                print(str(exc), file=sys.stderr)
                return 1
            (args.report_root / f'{name}.log').unlink(missing_ok=True)
            save(receipt_path, receipt)
        receipt.update(state='local_export_validated_not_published',
            database_bytes=args.db.stat().st_size, free_bytes=shutil.disk_usage(args.db.parent).free,
            manifest_sha256=hashlib.sha256((args.report_root / 'manifest.json').read_bytes()).hexdigest())
        save(receipt_path, receipt)
        print(json.dumps({'state': receipt['state'], 'receipt': relative(receipt_path)}))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--period', required=True)
    p.add_argument('--snapshot-date', required=True)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--pipeline-id', required=True)
    p.add_argument('--output-root', type=Path, required=True)
    p.add_argument('--report-root', type=Path, required=True)
    p.add_argument('--min-free-bytes', type=int, default=15 * 1024**3)
    p.add_argument('--max-archive-bytes', type=int, default=512 * 1024**2)
    p.add_argument('--plan-only', action='store_true')
    return run(p.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
