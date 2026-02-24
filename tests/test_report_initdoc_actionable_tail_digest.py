from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_initdoc_actionable_tail_digest import build_digest, main


class TestInitdocActionableTailDigest(unittest.TestCase):
    def test_build_digest_ok_when_queue_empty(self) -> None:
        contract = {
            "generated_at": "2026-02-22T23:00:00+00:00",
            "initiative_source_ids": ["senado_iniciativas"],
            "total_missing": 119,
            "redundant_missing": 119,
            "actionable_missing": 0,
            "actionable_missing_pct": 0.0,
        }
        digest = build_digest(
            contract,
            max_actionable_missing=0,
            max_actionable_missing_pct=0.0,
        )
        self.assertEqual(str(digest["status"]), "ok")
        self.assertEqual(int(digest["totals"]["actionable_missing"]), 0)
        self.assertEqual(digest["strict_fail_reasons"], [])
        self.assertEqual(bool(digest["checks"]["actionable_queue_empty"]), True)

    def test_build_digest_degraded_when_threshold_allows_nonempty(self) -> None:
        contract = {
            "generated_at": "2026-02-22T23:00:00+00:00",
            "initiative_source_ids": ["senado_iniciativas"],
            "total_missing": 10,
            "redundant_missing": 8,
            "actionable_missing": 2,
            "actionable_missing_pct": 0.2,
        }
        digest = build_digest(
            contract,
            max_actionable_missing=2,
            max_actionable_missing_pct=0.2,
        )
        self.assertEqual(str(digest["status"]), "degraded")
        self.assertEqual(digest["strict_fail_reasons"], [])
        self.assertEqual(bool(digest["checks"]["actionable_queue_empty"]), False)
        self.assertEqual(bool(digest["checks"]["actionable_missing_within_threshold"]), True)
        self.assertEqual(bool(digest["checks"]["actionable_missing_pct_within_threshold"]), True)

    def test_main_strict_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            contract_path = td_path / "contract.json"
            contract_payload = {
                "generated_at": "2026-02-22T23:00:00+00:00",
                "initiative_source_ids": ["senado_iniciativas"],
                "total_missing": 10,
                "redundant_missing": 8,
                "actionable_missing": 2,
                "actionable_missing_pct": 0.2,
            }
            contract_path.write_text(json.dumps(contract_payload), encoding="utf-8")

            fail_out = td_path / "digest_fail.json"
            rc_fail = main(
                [
                    "--contract-json",
                    str(contract_path),
                    "--max-actionable-missing",
                    "0",
                    "--max-actionable-missing-pct",
                    "0.0",
                    "--strict",
                    "--out",
                    str(fail_out),
                ]
            )
            self.assertEqual(rc_fail, 4)
            fail_digest = json.loads(fail_out.read_text(encoding="utf-8"))
            self.assertEqual(str(fail_digest["status"]), "failed")
            self.assertGreater(len(list(fail_digest["strict_fail_reasons"])), 0)

            pass_out = td_path / "digest_pass.json"
            rc_pass = main(
                [
                    "--contract-json",
                    str(contract_path),
                    "--max-actionable-missing",
                    "2",
                    "--max-actionable-missing-pct",
                    "0.2",
                    "--strict",
                    "--out",
                    str(pass_out),
                ]
            )
            self.assertEqual(rc_pass, 0)
            pass_digest = json.loads(pass_out.read_text(encoding="utf-8"))
            self.assertEqual(str(pass_digest["status"]), "degraded")
            self.assertEqual(pass_digest["strict_fail_reasons"], [])


if __name__ == "__main__":
    unittest.main()
