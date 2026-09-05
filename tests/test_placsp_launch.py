"""Independent checks against the real, immutable launch fixture."""
import importlib.util
import json
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

class LaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release=json.loads((PUBLIC/'latest.json').read_text())
        cls.root=PUBLIC/cls.release['release']
        cls.tmp=tempfile.TemporaryDirectory()
        cls.bundle=Path(cls.tmp.name)/'bundle';cls.bundle.mkdir()
        reproduce.unpack_verified((cls.root/'placsp-launch.zip').read_bytes(),cls.release['archive_sha256'],cls.bundle)
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
            reproduce.unpack_verified((self.root/'placsp-launch.zip').read_bytes()+b'x',self.release['archive_sha256'],Path(self.tmp.name)/'tampered')
    def test_public_files_match_verified_download(self):
        manifest=json.loads((self.bundle/'manifest.json').read_text())
        for name,expected in manifest['files'].items():
            self.assertEqual(reproduce.sha((self.root/name).read_bytes()),expected['sha256'])
        self.assertEqual(reproduce.sha((self.root/'manifest.json').read_bytes()),self.release['release'])
    def test_manifest_and_json_agree(self):
        c,rows=reproduce.load_verified(self.bundle);c.close()
        self.assertEqual(len(rows),self.release['rows'])
        self.assertEqual(sum(r['amount_cents'] for r in rows),self.release['amount_cents'])

if __name__=='__main__':unittest.main()
