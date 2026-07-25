import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/export_andalucia_2026_water_commitment_receipt.py"
SPEC = importlib.util.spec_from_file_location("water_receipt_exporter", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AndaluciaWaterReceiptExporterTest(unittest.TestCase):
    def setUp(self):
        self.seed = json.loads(MODULE.DEFAULT_SEED.read_text(encoding="utf-8"))

    def test_builds_three_conservative_commitments(self):
        payload = MODULE.build_receipt(self.seed)

        self.assertEqual(
            payload["schema_version"],
            "andalucia_water_commitment_receipt_v1",
        )
        self.assertEqual(payload["summary"]["commitments_total"], 3)
        self.assertEqual(payload["summary"]["declared_only_total"], 3)
        self.assertEqual(payload["summary"]["post_investiture_actions_total"], 0)
        self.assertEqual(
            {item["status"] for item in payload["commitments"]},
            {"declarado"},
        )

    def test_reiteration_does_not_count_as_progress(self):
        payload = MODULE.build_receipt(self.seed)
        irrigation = payload["commitments"][0]

        self.assertEqual(irrigation["status"], "declarado")
        self.assertEqual(
            irrigation["post_investiture_evidence"][0]["evidence_kind"],
            "reiteration",
        )
        self.assertIs(
            irrigation["post_investiture_evidence"][0]["counts_as_progress"],
            False,
        )

    def test_rejects_non_official_source(self):
        self.seed["sources"][0]["url"] = "https://example.com/promise"

        with self.assertRaisesRegex(ValueError, "official Andalucía host"):
            MODULE.build_receipt(self.seed)

    def test_rejects_advanced_status_without_progress_evidence(self):
        self.seed["commitments"][1]["status"] = "acto_oficial"

        with self.assertRaisesRegex(ValueError, "needs evidence"):
            MODULE.build_receipt(self.seed)

    def test_exports_identical_bounded_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "published.json"
            second = Path(temp_dir) / "public.json"

            MODULE.export_receipt(MODULE.DEFAULT_SEED, [first, second])

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertLess(first.stat().st_size, MODULE.MAX_PUBLIC_BYTES)


if __name__ == "__main__":
    unittest.main()
