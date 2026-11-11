"""/visualizaciones/democracia/: seed, raw payloads and published artifact stay consistent."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import export_public_viz_democracy as exp  # noqa: E402
import validate_democracy_safeguards as val  # noqa: E402


class TestDemocracySafeguards(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = exp.load_seed()

    def test_raw_payloads_match_manifest(self) -> None:
        for name in exp.load_manifest():
            exp.read_raw(name)  # raises on sha256 mismatch

    def test_decree_law_counts_equal_official_numbering(self) -> None:
        series = exp.decree_law_series(self.seed)
        gaps = {row["year"]: row["numbering_gap"] for row in series["annual"] if row["numbering_gap"]}
        self.assertEqual(gaps, {}, "a year's count differs from its highest official number")
        self.assertEqual(series["annual"][0]["year"], exp.FIRST_YEAR)

    def test_every_norm_falls_in_a_legislature_and_a_government(self) -> None:
        inv = exp.eli_inventory()
        for row in inv["norms"]:
            if row["date"] >= "1979-03-23":
                self.assertIsNotNone(exp.legislature_of(row["date"], self.seed["legislatures"]), row)
            if row["date"] >= "1979-01-01":
                self.assertIsNotNone(exp.government_at(row["date"], self.seed["governments"]), row)

    def test_governments_and_legislatures_are_contiguous(self) -> None:
        for key in ("governments", "legislatures"):
            rows = self.seed[key]
            for a, b in zip(rows, rows[1:]):
                self.assertEqual(a["end"], b["start"], f"{key}: gap between {a['id']} and {b['id']}")
            self.assertIsNone(rows[-1]["end"])

    def test_budget_status_is_consistent(self) -> None:
        budgets = exp.budget_series(self.seed)
        for row in budgets["years"]:
            if row["status"] == "a_tiempo":
                self.assertLess(row["law"]["published"], f"{row['year']}-01-01")
            if row["status"] == "tarde":
                self.assertGreaterEqual(row["law"]["published"], f"{row['year']}-01-01")
            if row["status"] == "prorrogado":
                self.assertNotIn("law", row)

    def test_published_safeguards_validate(self) -> None:
        self.assertEqual(val.main(["--published"]), 0)

    def test_published_artifact_is_reproducible(self) -> None:
        if not exp.OUT_JSON.exists():
            self.skipTest("published JSON not built")
        published = json.loads(exp.OUT_JSON.read_text())
        rebuilt = json.loads(json.dumps(exp.build_payload(self.seed), ensure_ascii=False))
        for key in exp.REPRODUCIBLE_KEYS:
            self.assertEqual(published[key], rebuilt[key], key)
        self.assertEqual(published["safeguards"], rebuilt["safeguards"])


if __name__ == "__main__":
    unittest.main()
