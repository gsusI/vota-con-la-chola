#!/usr/bin/env python3
"""Reconcile physical PLACSP holdings and immutable publication, without database writes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def report(db, release_path, catalog_path):
    release = json.loads(release_path.read_text())
    public = ROOT / 'ui/gh-pages-next/public/spending/launch' / release['release']
    audit = json.loads((public / 'audit.json').read_text())
    catalog = json.loads(catalog_path.read_text())
    with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as c:
        c.row_factory = sqlite3.Row
        physical = dict(c.execute('''SELECT count(*) versions,
            count(DISTINCT stable_contract_id) distinct_contract_ids,
            min(entry_updated_at) first_update, max(entry_updated_at) last_update
            FROM money_contract_records''').fetchone())
        awards = dict(c.execute('SELECT result_code,count(*) FROM money_contract_award_results GROUP BY result_code').fetchall())
        physical_result_count = c.execute('SELECT count(*) FROM money_contract_award_results').fetchone()[0]
        archives = [dict(r) for r in c.execute('''SELECT period,source_url,content_sha256,bytes,
            members_total,status,fetched_at FROM placsp_bulk_archives ORDER BY period''')]
        # Same latest-unambiguous-version rule as the launch. No date or eligibility filtering here.
        latest = [dict(r) for r in c.execute('''WITH newest AS (
            SELECT stable_contract_id,max(coalesce(entry_updated_at,'')) stamp
            FROM money_contract_records GROUP BY stable_contract_id
        ), winners AS (
            SELECT r.stable_contract_id,min(r.source_record_pk) pk,count(*) n
            FROM money_contract_records r JOIN newest n ON r.stable_contract_id=n.stable_contract_id
            AND coalesce(r.entry_updated_at,'')=n.stamp GROUP BY r.stable_contract_id
        ) SELECT a.result_code,count(*) results,
            sum(CASE WHEN a.supplier_name IS NOT NULL AND a.award_date IS NOT NULL
                AND a.amount_eur_decimal IS NOT NULL AND a.currency='EUR' THEN 1 ELSE 0 END) with_basic_fields
            FROM winners w JOIN money_contract_award_results a ON a.source_record_pk=w.pk
            WHERE w.n=1 GROUP BY a.result_code ORDER BY a.result_code''')]
    exclusions = audit['selection_exclusions']
    award_facts = audit['corpus_fact_kinds']['contract_award']
    balanced = audit['selected_rows'] + sum(exclusions.values()) == award_facts
    checks = {
        'frozen_award_selection_balances': balanced,
        'release_matches_audit_count': release['rows'] == audit['selected_rows'],
        'release_matches_audit_amount': release['amount_cents'] == audit['amount_cents'],
        'physical_result_count_matches_codes': sum(awards.values()) == physical_result_count,
    }
    return {
        'schema_version': 'spending_coverage_v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'partial_coverage',
        'checks': checks,
        'source_db': db.name,
        'physical': {**physical, 'result_rows_all_versions': sum(awards.values()),
                     'results_by_source_code_all_versions': awards,
                     'latest_unambiguous_results_by_source_code': latest},
        'acquired_archives': archives,
        'official_catalog': {k: catalog[k] for k in ('catalog_url','as_of_date','expected','missing','archives')},
        'publication': {'release': release['release'], 'rows': release['rows'],
                        'date_min_normalized': release['date_min'], 'date_max_normalized': release['date_max'],
                        'frozen_award_facts': award_facts, 'exclusions': exclusions,
                        'source_result_codes_selected': ['8']},
        'national_coverage_ratio': None,
        'limitations': [
            'Archive periods describe publications/updates, not exhaustive award-date coverage.',
            'Catalog links are expected archive containers, not a national record denominator.',
            'Physical result rows include versions and unsuccessful outcomes; they are not unique awards.',
            'Latest result counts have not passed amount, identity, tombstone or source-parity gates.',
            'Current release accepts TenderResult code 8 only; code 9 formalizations require inclusion review.',
            'Formalizations must retain their stage and must never be counted as payments.',
            'Regional, local, sectoral and TED overlaps remain unenumerated.',
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--release', type=Path, default=ROOT/'infra/cloudflare/spending-api/src/release.json')
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = report(a.db, a.release, a.catalog)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'checks': result['checks'], 'physical': result['physical']}))
    if not all(result['checks'].values()):
        raise SystemExit('Coverage reconciliation failed')


if __name__ == '__main__':
    main()
