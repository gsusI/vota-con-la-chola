"""Coverage accounting against captured official catalogs, without network."""
from datetime import date
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import sqlite3

from publicdata_connectors_es.money.placsp_catalog import build_catalog_report
from scripts.report_placsp_acquisition_inventory import build_inventory, probe_archive_sizes
from scripts.run_placsp_acquisition_batch import plan, validate_existing_inputs

EVIDENCE = Path(__file__).resolve().parents[1] / 'docs/etl/sprints/DINERO-NACIONAL-20260926/evidence'


class AcquisitionInventoryTests(unittest.TestCase):
    def test_official_families_have_separate_period_universes(self):
        for family, first_year, expected_count in [('main', 2012, 23), ('minor', 2018, 17), ('aggregated', 2016, 19)]:
            with self.subTest(family=family):
                saved = json.loads((EVIDENCE / f'catalog-{family}.json').read_text())
                report = build_catalog_report(
                    (EVIDENCE / f'catalog-{family}.html').read_bytes(),
                    catalog_url=saved['catalog_url'], family=family,
                    as_of_date=date(2026, 9, 26))
                self.assertEqual(report['status'], 'ok')
                self.assertEqual(len(report['archives']), expected_count)
                self.assertEqual(report['archives'][0]['period'], str(first_year))
                self.assertNotIn('2026', [r['period'] for r in report['archives']])
                self.assertEqual(report['catalog_content_sha256'], saved['catalog_content_sha256'])

    def test_wrong_family_does_not_claim_archive_coverage(self):
        report = build_catalog_report((EVIDENCE / 'catalog-minor.html').read_bytes(),
            catalog_url='https://www.hacienda.gob.es/', family='main', as_of_date=date(2026, 9, 26))
        self.assertEqual(report['status'], 'degraded')
        self.assertEqual(report['archives'], [])

    def test_inventory_preserves_unknowns_and_open_months(self):
        paths = [EVIDENCE / f'catalog-{f}.json' for f in ('main', 'minor', 'aggregated')]
        report = build_inventory(paths, [])
        self.assertEqual(len(report['archives']), 59)
        self.assertEqual(report['capacity']['sized_archives'], 0)
        self.assertIsNone(report['national_record_denominator'])
        self.assertEqual(sum(not r['period_closed'] for r in report['archives']), 3)
        self.assertTrue(all(not r['local_captures'] for r in report['archives']))
        with self.assertRaisesRegex(ValueError, 'duplicate family'):
            build_inventory(paths + paths[:1], [])

    def test_family_start_year_is_not_silently_extended(self):
        with self.assertRaisesRegex(ValueError, '2018'):
            build_catalog_report((EVIDENCE / 'catalog-minor.html').read_bytes(),
                catalog_url='https://www.hacienda.gob.es/', family='minor',
                start_year=2012, as_of_date=date(2026, 9, 26))

    def test_unsupported_sizing_stops_instead_of_probing_entire_history(self):
        rows = json.loads((EVIDENCE / 'catalog-main.json').read_text())['archives']
        def unknown(row):
            return dict(row, remote={'http_status': 200, 'bytes': None})
        with patch('scripts.report_placsp_acquisition_inventory.probe_archive', side_effect=unknown) as probe:
            result = probe_archive_sizes(rows)
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(len(result), len(rows))
        self.assertIn('not_probed_reason', result[-1]['remote'])

    def test_batch_plan_binds_official_family_and_keeps_publication_separate(self):
        args = SimpleNamespace(catalog=EVIDENCE / 'catalog-minor.json', period='202608',
            snapshot_date='2026-09-26', db=Path('etl/data/staging/test-plan.db'),
            pipeline_id='minor-plan', output_root=Path('etl/data/published/test-plan'),
            report_root=EVIDENCE / 'test-plan', min_free_bytes=15 * 1024**3,
            max_archive_bytes=512 * 1024**2)
        contract, stages = plan(args)
        self.assertEqual(contract['family'], 'minor')
        self.assertIn('sindicacion_1143', contract['source_url'])
        self.assertEqual([name for name, _ in stages], ['enqueue', 'download', 'normalize', 'export', 'validate'])
        self.assertTrue(all('/Users/' not in json.dumps(command) for _, command in stages))
        args.period = '190001'
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            plan(args)

    def test_runner_refuses_mixed_database_and_unowned_export(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = SimpleNamespace(db=root / 'source.db', output_root=root / 'export', pipeline_id='requested')
            with sqlite3.connect(args.db) as conn:
                conn.execute('CREATE TABLE placsp_bulk_runs (pipeline_id TEXT)')
                conn.execute("INSERT INTO placsp_bulk_runs VALUES ('another-cohort')")
            with self.assertRaisesRegex(ValueError, 'dedicated cohort'):
                validate_existing_inputs(args, root / 'run.json')
            args.output_root.mkdir()
            (args.output_root / 'unrelated.txt').write_text('preserve')
            with self.assertRaisesRegex(ValueError, 'existing export'):
                validate_existing_inputs(args, root / 'run.json')
            self.assertEqual((args.output_root / 'unrelated.txt').read_text(), 'preserve')
            args.db.unlink()
            (root / 'run.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'restore the archived'):
                validate_existing_inputs(args, root / 'run.json')


if __name__ == '__main__':
    unittest.main()
