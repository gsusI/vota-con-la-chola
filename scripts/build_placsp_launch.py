#!/usr/bin/env python3
"""Build a bounded, checksum-bound PLACSP launch from the public frozen corpus."""
import argparse
import csv
import hashlib
import html
import json
import re
import sqlite3
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from publicdata_connectors_es.money.placsp_bulk import _parse_entry

RELEASE = '5d9ce557ed864de56f677a9f82c999a4ec0dfc494c086b1bfca0bb2e461272dd'
MANIFEST_SHA = 'b225f167d1fad027a0f8d3bac336ec96f9a5e06770f32db8c2f2af53810dda4b'
BASE = f'https://huggingface.co/datasets/JesusIC/vota-con-la-chola-data/resolve/main/scale/snapshots/2026-08-19/{RELEASE}/'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, default=str) + '\n')

def clean_party_name(value):
    text = unicodedata.normalize('NFKC', html.unescape(value or '')).replace('\u00a0', ' ')
    text = ' '.join(text.split())
    return re.sub(r'\s+([,.;:])', r'\1', text)

def party_name_key(value):
    return clean_party_name(value).rstrip(' .,:;').casefold()

def party_identity(row, kind):
    if kind == 'authority':
        identifier = re.sub(r'[\s.\-]', '', row.get('authority_id') or '').upper()
        return ('id', identifier) if identifier else ('name', party_name_key(row['authority_source_text']))
    identifier = re.sub(r'[\s.\-]', '', row.get('supplier_id') or '').upper()
    return ('id', identifier) if identifier else ('name', party_name_key(row['supplier_source_text']))

def normalize_party_names(rows):
    aliases = []
    stats = {}
    for kind in ('authority', 'supplier'):
        source_field = kind + '_source_text'
        variants = defaultdict(Counter)
        for row in rows:
            variants[party_identity(row, kind)][clean_party_name(row[source_field])] += 1
        canonical = {
            identity: min(counts, key=lambda name: (-counts[name], -len(name), name.casefold(), name))
            for identity, counts in variants.items()
        }
        changed = 0
        for row in rows:
            label = canonical[party_identity(row, kind)]
            changed += label != clean_party_name(row[source_field])
            row[kind] = label
        merged = 0
        for identity, counts in variants.items():
            if len(counts) < 2:
                continue
            merged += 1
            aliases.append({
                'entity_type': kind,
                'identity_basis': identity[0],
                'identity_key': '|'.join(identity[1:]),
                'canonical_name': canonical[identity],
                'source_names': [
                    {'name': name, 'rows': count}
                    for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold(), item[0]))
                ],
            })
        stats[kind] = {
            'canonical_entities': len(variants),
            'groups_with_multiple_source_names': merged,
            'rows_using_canonical_alias': changed,
        }
    aliases.sort(key=lambda row: (row['entity_type'], row['canonical_name'].casefold(), row['identity_key']))
    return aliases, stats

def retain_literal_labels(rows, out):
    def child(node, name):
        return next((x for x in node if x.tag.rsplit('}', 1)[-1] == name), None)
    def path(node, *names):
        for name in names:
            node = child(node, name)
            if node is None:
                raise ValueError('Missing source identity element')
        return node
    entries = {}
    for row in rows:
        capture = row['capture_path']
        if capture not in entries:
            entry = ET.parse(out/capture).getroot()
            status = child(entry, 'ContractFolderStatus')
            entries[capture] = (
                ''.join(path(status, 'LocatedContractingParty', 'Party', 'PartyName', 'Name').itertext()),
                [award for award in status if award.tag.rsplit('}', 1)[-1] == 'TenderResult'],
                {},
            )
        authority, awards, suppliers = entries[capture]
        ordinal = row['award_ordinal']
        if ordinal not in suppliers:
            suppliers[ordinal] = ''.join(path(awards[ordinal], 'WinningParty', 'PartyName', 'Name').itertext())
        row['authority_source_text'] = authority
        row['supplier_source_text'] = suppliers[ordinal]


def build(corpus, db, out, limit=None):
    import pyarrow as pa
    import pyarrow.parquet as pq
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output must be empty; retained releases are immutable')
    out.mkdir(parents=True, exist_ok=True)
    manifest_bytes = (corpus/'manifest.json').read_bytes()
    if sha(manifest_bytes) != MANIFEST_SHA:
        raise ValueError('Frozen manifest hash mismatch')
    manifest = json.loads(manifest_bytes)
    all_rows = []
    for partition in manifest['partitions']:
        for f in partition['files']:
            p = corpus/'data'/f['path']
            b = p.read_bytes()
            if len(b) != f['bytes'] or sha(b) != f['sha256']:
                raise ValueError('Parquet checksum mismatch')
            rows = pq.ParquetFile(p).read().to_pylist()
            if len(rows) != f['rows']:
                raise ValueError('Parquet row mismatch')
            all_rows.extend(rows)
    if len(all_rows) != manifest['totals']['rows']:
        raise ValueError('Corpus balance mismatch')
    c = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    pks = {r['source_record_pk'] for r in all_rows}
    contracts = {r['source_record_pk']:dict(r) for r in c.execute('SELECT source_record_pk,source_record_id,stable_contract_id,entry_updated_at FROM money_contract_records') if r['source_record_pk'] in pks}
    if len(contracts) != len(pks):
        raise ValueError('Frozen records missing from source database')
    # Select latest captured version inside this frozen corpus, never today's DB.
    versions = defaultdict(list)
    for r in contracts.values():
        versions[r['stable_contract_id'] or 'source:'+r['source_record_id']].append(r)
    latest = set()
    ambiguous = 0
    for group in versions.values():
        stamps = [r['entry_updated_at'] or '' for r in group]
        top = max(stamps)
        winners = [r for r in group if (r['entry_updated_at'] or '') == top]
        if len(winners) != 1:
            ambiguous += 1
            continue
        latest.add(winners[0]['source_record_pk'])
    excluded = Counter()
    candidates = []
    for r in all_rows:
        if r['fact_kind'] != 'contract_award':
            continue
        if r['source_record_pk'] not in latest:
            excluded['older_or_ambiguous_version'] += 1
            continue
        if not '2025-01-01' <= (r['effective_date'] or '') <= '2025-01-31':
            excluded['outside_january_2025'] += 1
            continue
        date.fromisoformat(r['effective_date'])
        if not r['public_authority'] or not r['counterparty_name'] or r['currency'] != 'EUR' or r['amount_eur'] is None:
            excluded['missing_identity_or_eur_amount'] += 1
            continue
        value = Decimal(r['amount_eur'])
        if not value.is_finite() or value < 0 or value * 100 != (value * 100).to_integral_value():
            excluded['amount_not_nonnegative_exact_cents'] += 1
            continue
        candidates.append(r)
    candidates.sort(key=lambda r:(r['effective_date'],r['source_record_id'],r['money_fact_id']))
    selected = []
    selected_keys = set()
    source_payloads = {}
    for r in candidates:
        source = c.execute('SELECT raw_payload,content_sha256 FROM source_records WHERE source_record_pk=?',(r['source_record_pk'],)).fetchone()
        payload = json.loads(source['raw_payload'])
        award_id = int(r['money_fact_id'].split(':')[1])
        award = dict(c.execute('SELECT * FROM money_contract_award_results WHERE contract_award_result_id=?',(award_id,)).fetchone())
        a = payload['awards'][award['award_ordinal']]
        rec = payload['record']
        if payload['record'].get('tombstone') or a.get('result_code') != '8':
            excluded['not_awarded_or_tombstone'] += 1
            continue
        expected = [rec.get('contracting_authority'),a.get('supplier_name'),a.get('supplier_identifier'),a.get('award_date'),a.get('currency'),a.get('lot_id')]
        observed = [r['public_authority'],r['counterparty_name'],r['counterparty_identifier'],r['effective_date'],r['currency'],r['secondary_reference_id']]
        if expected != observed or Decimal(a['amount_eur_decimal']) != r['amount_eur'] or source['content_sha256'] != payload['entry_content_sha256']:
            excluded['source_parquet_semantic_mismatch'] += 1
            continue
        identity = rec['stable_contract_id'] + '#' + str(a['award_ordinal'])
        if identity in selected_keys:
            raise ValueError('Duplicate award version')
        selected_keys.add(identity)
        source_payloads[r['source_record_pk']] = payload
        selected.append(dict(
            award_key=identity, money_fact_id=r['money_fact_id'], source_record_id=r['source_record_id'],
            authority_id=rec.get('authority_identifier') or '', authority=r['public_authority'],
            supplier_id=a.get('supplier_identifier') or '', supplier=r['counterparty_name'],
            supplier_id_scheme=a.get('supplier_identifier_scheme') or '',
            contract_id=r['primary_reference_id'] or '', lot_id=a.get('lot_id') or '',
            award_ordinal=a['award_ordinal'], decision_date=r['effective_date'],
            amount_decimal=a['amount_eur_decimal'], amount_cents=int(r['amount_eur']*100),currency='EUR',
            title=rec.get('title') or '', source_url=r['source_url'],
            source_snapshot_date=r['source_snapshot_date'], entry_updated_at=rec['entry_updated_at'],
            entry_sha256=source['content_sha256'], capture_path='evidence/'+source['content_sha256']+'.xml',
        ))
        if limit is not None and len(selected) == limit:
            break
    if limit is not None and len(selected) != limit:
        raise ValueError('Insufficient eligible source rows')
    if not selected:
        raise ValueError('No eligible source rows')
    # Rehash original archives and members; recover exact ET-serialized entries used by ingest.
    targets = defaultdict(dict)
    target_metadata = {}
    lineage = []
    for pk, payload in source_payloads.items():
        row = c.execute('''SELECT m.member_name,m.content_sha256 member_sha256,a.raw_path,
          a.content_sha256 archive_sha256,a.source_url,a.fetched_at,a.bytes
          FROM placsp_bulk_record_sightings s JOIN placsp_bulk_members m USING(placsp_bulk_member_id)
          JOIN placsp_bulk_archives a USING(placsp_bulk_archive_id)
          WHERE s.source_record_pk=? ORDER BY s.placsp_bulk_record_sighting_id LIMIT 1''',(pk,)).fetchone()
        if not row:
            raise ValueError('Missing original capture')
        targets[(row['raw_path'],row['member_name'])][payload['entry_content_sha256']] = payload
        target_metadata[(row['raw_path'],row['member_name'])] = dict(row)
        lineage.append({k:row[k] for k in ('member_name','member_sha256','archive_sha256','source_url','fetched_at','bytes')} | {'entry_sha256':payload['entry_content_sha256']})
    (out/'evidence').mkdir()
    checked_archives = set()
    recovered = set()
    for (raw_path, member), payloads in targets.items():
        line = target_metadata[(raw_path, member)]
        archive = ROOT/raw_path
        if raw_path not in checked_archives:
            h = hashlib.sha256()
            with archive.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
            if h.hexdigest()!=line['archive_sha256'] or archive.stat().st_size!=line['bytes']:
                raise ValueError('Original archive checksum mismatch')
            checked_archives.add(raw_path)
        with zipfile.ZipFile(archive) as z:
            member_bytes=z.read(member)
        if sha(member_bytes)!=line['member_sha256']:
            raise ValueError('Original member checksum mismatch')
        import io
        for _, element in ET.iterparse(io.BytesIO(member_bytes), events=('end',)):
            if element.tag.rsplit('}',1)[-1] not in ('entry','deleted-entry'):continue
            b=ET.tostring(element,encoding='utf-8'); digest=sha(b)
            if digest in payloads:
                parsed=_parse_entry(element,digest,max_documents=10000)
                if parsed.record!=payloads[digest]['record'] or list(parsed.awards)!=payloads[digest]['awards']:
                    raise ValueError('Original XML replay differs from normalized source')
                (out/'evidence'/f'{digest}.xml').write_bytes(b)
                recovered.add(digest)
            element.clear()
    if recovered != {p['entry_content_sha256'] for p in source_payloads.values()}:
        raise ValueError('Incomplete original XML recovery')
    c.close()
    retain_literal_labels(selected, out)
    aliases, normalization = normalize_party_names(selected)
    dump(out/'name-aliases.json', aliases)
    dump(out/'awards.json',selected)
    with (out/'awards.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(selected[0]));writer.writeheader();writer.writerows(selected)
    pq.write_table(pa.Table.from_pylist(selected),out/'awards.parquet',compression='zstd')
    dump(out/'lineage.json',lineage)
    (out/'source-manifest.json').write_bytes(manifest_bytes)
    counts=Counter(r['fact_kind'] for r in all_rows)
    audit=dict(schema_version='placsp-launch-v2', upstream_release=RELEASE, upstream_base_url=BASE,
        upstream_manifest_sha256=MANIFEST_SHA, manifest_snapshot_label=manifest['snapshot_date'],
        observed_source_snapshot_dates=sorted({r['source_snapshot_date'] for r in all_rows}),
        corpus_rows=len(all_rows),corpus_fact_kinds=dict(counts),
        scope='Complete eligible January 2025 award-result cohort inside the frozen corpus; latest unambiguous version only. Not complete procurement coverage outside this month or snapshot.',
        selection_mode='complete_month',selection_limit=limit,selected_rows=len(selected),eligible_january_rows_before_source_result_check=len(candidates),
        selection_exclusions=dict(excluded),ambiguous_contract_version_groups=ambiguous,
        name_normalization=dict(method='NFKC, HTML entity decoding, whitespace/punctuation cleanup, case-insensitive terminal-punctuation key; published identifiers group variants even when the identifier scheme label differs; literal XML labels retained per row', **normalization),
        capture_entries=len(recovered),original_archives_rehashed=len(checked_archives),original_members_rehashed=len(targets),
        amount_cents=sum(r['amount_cents'] for r in selected),
        decision_date_min=min(r['decision_date'] for r in selected),decision_date_max=max(r['decision_date'] for r in selected),
        unit='award result, identified by source stable contract and award ordinal; not unique contract, lot, invoice or payment',
        amount_semantics='EUR tax-exclusive awarded amount; integer cents for aggregation; lexical source decimal retained',
        identity='Names and identifiers retained as published; no name-only entity resolution',
        rights_url='https://github.com/gsusI/vota-con-la-chola/blob/main/docs/legal/data-rights.md',
        evidence_serialization='ET UTF-8 serialization of original captured Atom entry, matching ingest SHA-256; archive and member lineage retained',
        community_validation=dict(journey_testers=0,query_reproducers=0,status='pending'),status='technical_alpha')
    dump(out/'audit.json',audit)
    print(json.dumps({k:audit[k] for k in ('selected_rows','capture_entries','original_archives_rehashed','original_members_rehashed','amount_cents','decision_date_min','decision_date_max')}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',type=Path,required=True);p.add_argument('--source-db',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--limit',type=int,default=0,help='Development-only cap; zero validates the complete January cohort')
    a=p.parse_args();build(a.corpus,a.source_db,a.out,a.limit or None)
