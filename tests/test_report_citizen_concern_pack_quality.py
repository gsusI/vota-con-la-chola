from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_concern_pack_quality import main


class TestReportCitizenConcernPackQuality(unittest.TestCase):
    def _write_snapshot(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "meta": {"quality": {"unknown_pct": 0.2}},
                    "parties": [
                        {"party_id": 1, "name": "A"},
                        {"party_id": 2, "name": "B"},
                    ],
                    "topics": [
                        {"topic_id": 101, "label": "T1", "concern_ids": ["a"], "is_high_stakes": True},
                        {"topic_id": 102, "label": "T2", "concern_ids": ["b"], "is_high_stakes": False},
                        {"topic_id": 103, "label": "T3", "concern_ids": ["c"], "is_high_stakes": False},
                    ],
                    "party_topic_positions": [
                        {"topic_id": 101, "party_id": 1, "stance": "support", "confidence": 0.9},
                        {"topic_id": 101, "party_id": 2, "stance": "oppose", "confidence": 0.9},
                        {"topic_id": 102, "party_id": 1, "stance": "support", "confidence": 0.8},
                        {"topic_id": 102, "party_id": 2, "stance": "support", "confidence": 0.8},
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_concerns(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "version": "v1",
                    "normalization": {"lowercase": True, "strip_diacritics": True},
                    "concerns": [
                        {"id": "a", "label": "A", "description": "A", "keywords": ["a"]},
                        {"id": "b", "label": "B", "description": "B", "keywords": ["b"]},
                        {"id": "c", "label": "C", "description": "C", "keywords": ["c"]},
                    ],
                    "packs": [
                        {
                            "id": "pack_ok",
                            "label": "Pack OK",
                            "concern_ids": ["a", "b"],
                            "tradeoff": "x",
                        },
                        {
                            "id": "pack_weak",
                            "label": "Pack weak",
                            "concern_ids": ["c"],
                            "tradeoff": "y",
                        },
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_main_reports_pack_quality_and_passes_within_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            snapshot = td_path / "citizen.json"
            concerns = td_path / "concerns.json"
            out = td_path / "out.json"
            self._write_snapshot(snapshot)
            self._write_concerns(concerns)

            rc = main(
                [
                    "--snapshot",
                    str(snapshot),
                    "--concerns-config",
                    str(concerns),
                    "--min-topics-per-pack",
                    "2",
                    "--min-clear-cells-pct",
                    "0.6",
                    "--max-unknown-cells-pct",
                    "0.4",
                    "--min-confidence-avg-signal",
                    "0.6",
                    "--min-high-stakes-share",
                    "0.0",
                    "--max-weak-packs",
                    "1",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "ok")
            self.assertEqual(int(got["summary"]["packs_total"]), 2)
            self.assertEqual(int(got["summary"]["weak_packs_total"]), 1)
            by_id = {str(r.get("pack_id")): r for r in got.get("packs") or []}
            self.assertIn("pack_ok", by_id)
            self.assertIn("pack_weak", by_id)
            self.assertFalse(bool(by_id["pack_ok"]["weak"]))
            self.assertTrue(bool(by_id["pack_weak"]["weak"]))
            self.assertIn("topics_below_min", set(by_id["pack_weak"]["weak_reasons"]))

    def test_main_strict_fails_when_weak_packs_exceed_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            snapshot = td_path / "citizen.json"
            concerns = td_path / "concerns.json"
            out = td_path / "out_failed.json"
            self._write_snapshot(snapshot)
            self._write_concerns(concerns)

            rc = main(
                [
                    "--snapshot",
                    str(snapshot),
                    "--concerns-config",
                    str(concerns),
                    "--min-topics-per-pack",
                    "2",
                    "--min-clear-cells-pct",
                    "0.6",
                    "--max-unknown-cells-pct",
                    "0.4",
                    "--min-confidence-avg-signal",
                    "0.6",
                    "--min-high-stakes-share",
                    "0.0",
                    "--max-weak-packs",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("weak_packs_above_threshold", set(got.get("failure_reasons") or []))
            self.assertEqual(int(got["summary"]["weak_packs_total"]), 1)


if __name__ == "__main__":
    unittest.main()
