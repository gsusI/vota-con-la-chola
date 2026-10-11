"""Keep formalized awards visible without admitting failed or deleted results."""
import unittest
from scripts.build_placsp_launch import successful_result_stage, published_supplier_identifier


class ResultStageTests(unittest.TestCase):
    def test_codice_successful_stages(self):
        self.assertEqual(successful_result_stage('8'), 'awarded')
        self.assertEqual(successful_result_stage('9'), 'formalized')

    def test_unsuccessful_or_unknown_results_stay_excluded(self):
        for code in ('2', '3', '4', '5', '', None, '99'):
            with self.subTest(code=code):
                self.assertIsNone(successful_result_stage(code))

    def test_tombstone_overrides_successful_stage(self):
        for code in ('8', '9'):
            self.assertIsNone(successful_result_stage(code, tombstone=True))

    def test_publisher_identifier_canonicalization_preserves_identity(self):
        self.assertEqual(published_supplier_identifier(' b04310322 '), 'B04310322')
        self.assertEqual(published_supplier_identifier('B04310323'), 'B04310323')
        self.assertIsNone(published_supplier_identifier(None))
        self.assertIsNone(published_supplier_identifier('  '))


if __name__ == '__main__':
    unittest.main()
