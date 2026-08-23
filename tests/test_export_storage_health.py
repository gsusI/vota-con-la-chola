from __future__ import annotations

import json
import unittest
from pathlib import Path

from publicdata_publish.hf_snapshot import collect_published_files
from scripts.export_storage_health import StorageHealthError, build_report

BDNS_EVIDENCE = (
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "bdns-concessions-partitioned-real-s3-storage-preflight-20260812.json"
)
PLACSP_EVIDENCE = (
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "placsp-official-history-storage-preflight-20260811.json"
)
PUBLISHED_DIR = Path(__file__).resolve().parents[1] / "etl/data/published"


class ExportStorageHealthTests(unittest.TestCase):
    def test_real_preflights_reconcile_to_public_safe_blocker_status(self) -> None:
        report = build_report(
            [f"bdns_history={BDNS_EVIDENCE}", f"placsp_history={PLACSP_EVIDENCE}"]
        )
        self.assertEqual(report["status"], "blocked_storage")
        self.assertEqual(report["summary"]["lanes_total"], 2)
        self.assertEqual(report["summary"]["lanes_blocked_storage"], 2)
        self.assertEqual(
            report["summary"]["largest_additional_bytes_required"], 66_776_911_872
        )
        serialized = json.dumps(report)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("raw_root", serialized)
        self.assertNotIn("sqlite_root", serialized)

    def test_duplicate_real_lane_is_rejected(self) -> None:
        with self.assertRaises(StorageHealthError):
            build_report([f"history={BDNS_EVIDENCE}", f"history={PLACSP_EVIDENCE}"])

    def test_real_storage_health_is_in_the_next_snapshot_package(self) -> None:
        names = {
            path.name for path in collect_published_files(PUBLISHED_DIR, "1900-01-01")
        }
        self.assertIn("storage-health-latest.json", names)


if __name__ == "__main__":
    unittest.main()
