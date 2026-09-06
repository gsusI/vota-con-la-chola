"""Independent checks against the real, immutable launch fixture."""
import importlib.util
import json
import gzip
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reproduce',ROOT/'docs/examples/placsp-launch/reproduce.py')
reproduce=importlib.util.module_from_spec(spec);spec.loader.exec_module(reproduce)
build_spec=importlib.util.spec_from_file_location('build_placsp_launch',ROOT/'scripts/build_placsp_launch.py')
build_launch=importlib.util.module_from_spec(build_spec);build_spec.loader.exec_module(build_launch)
PUBLIC=ROOT/'ui/gh-pages-next/public/spending/launch'

def public_bytes(root, release, name):
    compressed = release.get('file_encodings', {}).get(name) == 'gzip' or (release.get('compressed_xml') and name.endswith('.xml'))
    parts = release.get('file_parts', {}).get(name)
    if parts:
        chunks = []
        for part in parts:
            chunk = (root/part['path']).read_bytes()
            if len(chunk) != part['bytes'] or reproduce.sha(chunk) != part['sha256']:
                raise ValueError('Transport part mismatch')
            chunks.append(chunk)
        data = b''.join(chunks)
    else:
        data = (root/(name+('.gz' if compressed else ''))).read_bytes()
    return gzip.decompress(data) if compressed else data

class LaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release=json.loads((PUBLIC/'latest.json').read_text())
        cls.root=PUBLIC/cls.release['release']
        cls.tmp=tempfile.TemporaryDirectory()
        cls.bundle=Path(cls.tmp.name)/'bundle';cls.bundle.mkdir()
        reproduce.unpack_verified(public_bytes(cls.root,cls.release,'placsp-launch.zip'),cls.release['archive_sha256'],cls.bundle)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_three_queries_and_filtered_totals(self):
        c,rows=reproduce.load_verified(self.bundle)
        for params in [dict(authority='',supplier='',start='2025-01-01',end='2025-01-31'),dict(authority=rows[0]['authority'],supplier='',start='2025-01-01',end='2025-01-31'),dict(authority='',supplier='',start='2026-01-01',end='2026-01-31')]:
            result=reproduce.reproduce(self.bundle,params)
            expected=[r for r in rows if (not params['authority'] or r['authority']==params['authority']) and params['start']<=r['decision_date']<=params['end']]
            self.assertEqual(len(result['records']),len(expected))
            self.assertEqual(sum(r['amount_cents'] for r in result['by-supplier']),sum(r['amount_cents'] for r in expected))
        c.close()
    def test_galasa_full_history_and_january_regression(self):
        rows=json.loads((self.bundle/'awards.json').read_text())
        galasa=[r for r in rows if r['authority_id']=='A04107272' and '1999-01-01' <= r['decision_date'] <= '2027-12-31']
        self.assertEqual(len(galasa),8)
        self.assertEqual(sum(r['amount_cents'] for r in galasa),550596594)
        january=[r for r in galasa if '2025-01-01' <= r['decision_date'] <= '2025-01-31']
        self.assertEqual(len(january),1)
        self.assertEqual(january[0]['amount_cents'],754648)
        audit=json.loads((self.bundle/'audit.json').read_text())
        self.assertEqual(audit['selection_mode'],'complete_available_history')
        self.assertNotIn('outside_january_2025',audit['selection_exclusions'])

    def test_original_xml_amount_and_supplier(self):
        rows=json.loads((self.bundle/'awards.json').read_text())
        def child(node,name):return next((x for x in node if x.tag.rsplit('}',1)[-1]==name),None)
        def path(node,*names):
            for name in names:
                node=child(node,name)
                if node is None:return None
            return node
        for row in rows:
            entry=ET.parse(self.bundle/row['capture_path']).getroot()
            status=child(entry,'ContractFolderStatus')
            awards=[n for n in status if n.tag.rsplit('}',1)[-1]=='TenderResult']
            award=awards[row['award_ordinal']]
            amount=path(award,'AwardedTenderedProject','LegalMonetaryTotal','TaxExclusiveAmount')
            supplier=path(award,'WinningParty','PartyName','Name')
            self.assertIsNotNone(amount)
            self.assertEqual(Decimal(amount.text)*100,row['amount_cents'])
            self.assertEqual(''.join(supplier.itertext()),row['supplier_source_text'])
            self.assertTrue(row['supplier'])
    def test_name_normalization_merges_punctuation_aliases_without_losing_source(self):
        rows=[
            {'authority_id':'A1','authority_source_text':'Órgano  Uno','supplier_id_scheme':'NIF','supplier_id':'A123',
             'supplier_source_text':'GAS NATURAL COMERCIALIZADORA, S.A'},
            {'authority_id':'A1','authority_source_text':'Órgano Uno','supplier_id_scheme':'OTROS','supplier_id':'A123',
             'supplier_source_text':'GAS NATURAL COMERCIALIZADORA, S.A.'},
        ]
        aliases,stats=build_launch.normalize_party_names(rows)
        self.assertEqual({row['supplier'] for row in rows},{'GAS NATURAL COMERCIALIZADORA, S.A.'})
        self.assertEqual(rows[0]['supplier_source_text'],'GAS NATURAL COMERCIALIZADORA, S.A')
        self.assertEqual(stats['supplier']['groups_with_multiple_source_names'],1)
        supplier_alias=next(row for row in aliases if row['entity_type']=='supplier')
        self.assertEqual({row['name'] for row in supplier_alias['source_names']},{
            'GAS NATURAL COMERCIALIZADORA, S.A','GAS NATURAL COMERCIALIZADORA, S.A.'})
    def test_tampered_download_rejected(self):
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            reproduce.unpack_verified(public_bytes(self.root,self.release,'placsp-launch.zip')+b'x',self.release['archive_sha256'],Path(self.tmp.name)/'tampered')
    def test_public_files_match_verified_download(self):
        manifest=json.loads((self.bundle/'manifest.json').read_text())
        for name,expected in manifest['files'].items():
            self.assertEqual(reproduce.sha(public_bytes(self.root,self.release,name)),expected['sha256'])
        self.assertEqual(reproduce.sha((self.root/'manifest.json').read_bytes()),self.release['release'])
    def test_manifest_and_json_agree(self):
        c,rows=reproduce.load_verified(self.bundle);c.close()
        self.assertEqual(len(rows),self.release['rows'])
        self.assertEqual(sum(r['amount_cents'] for r in rows),self.release['amount_cents'])

if __name__=='__main__':unittest.main()
