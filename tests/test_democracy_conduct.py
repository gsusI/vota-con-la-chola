"""Democratic-conduct ledger: validator rules, exporter output and the composite publication rule.

    python3 -m unittest tests.test_democracy_conduct
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts import export_public_viz_democracy_parties as exp
from scripts import validate_democracy_conduct as val

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "ui/site/public/visualizaciones/data/democracia-partidos.json"

GOOD = {
    "event_id": "stc-1-2020-test",
    "title": "STC 1/2020: prueba",
    "body": "Tribunal Constitucional",
    "act": "Artículo 1 de la Ley X",
    "finding_type": "court_annulment_partial",
    "indicator": "contrapesos",
    "severity": 2,
    "date": "2020-01-10",
    "act_date": "2019-05-01",
    "status": "firme",
    "attributions": [{"party_id": "pp", "role": "national_government", "attribution": "government_act", "lineage": "same", "power_only": True, "note": ""}],
    "source": {"url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2020-1", "title": "t", "retrieved": "2026-11-11", "quote": "Declarar inconstitucional y nulo el artículo 1", "quote_lang": "es", "locator": "fallo"},
    "extra_sources": [],
}


class ValidatorTest(unittest.TestCase):
    def errs(self, ev):
        return val.check_event(ev, "t", "2026-11-11")

    def test_good_event_passes(self):
        self.assertEqual(self.errs(GOOD), [])

    def test_severity_must_follow_finding_type(self):
        ev = copy.deepcopy(GOOD)
        ev["severity"] = 3
        self.assertTrue(any("severity" in e for e in self.errs(ev)))

    def test_quote_limit_and_official_host(self):
        ev = copy.deepcopy(GOOD)
        ev["source"]["quote"] = " ".join(["palabra"] * 16)
        ev["source"]["url"] = "https://www.elpais.com/x"
        errs = self.errs(ev)
        self.assertTrue(any("max 15" in e for e in errs))
        self.assertTrue(any("allow-list" in e for e in errs))

    def test_party_role_indicator_and_window(self):
        ev = copy.deepcopy(GOOD)
        ev["attributions"][0]["party_id"] = "ucd"
        ev["attributions"][0]["role"] = "king"
        ev["indicator"] = "populismo"
        ev["date"] = "2010-01-01"
        errs = " ".join(self.errs(ev))
        for needle in ("party", "role", "indicator", "outside window"):
            self.assertIn(needle, errs)

    def test_lineage_list_needs_note(self):
        ev = copy.deepcopy(GOOD)
        ev["attributions"][0]["lineage"] = "list"
        self.assertTrue(any("needs a note" in e for e in self.errs(ev)))

    def test_committed_ledger_is_valid(self):
        self.assertEqual(val.main([]), 0)


class SensitivityTest(unittest.TestCase):
    def seed(self):
        return {
            "parties": [{"party_id": p} for p in ("a", "b")],
            "codebook": {"indicators": [{"id": i} for i in val.INDICATORS]},
        }

    def ev(self, pid, sev, ind, power):
        return {"severity": sev, "indicator": ind, "coverage": {"type": "census", "family": "x"},
                "attributions": [{"party_id": pid, "lineage": "same", "power_only": power, "role": "opposition"}]}

    def test_reversal_blocks_composite(self):
        # a: one severe power-only act; b: two mild acts not needing power. W1 a=3 > b=2; W5 a=0 < b=2 -> reversal.
        events = [self.ev("a", 3, "contrapesos", True), self.ev("b", 1, "violencia", False), self.ev("b", 1, "violencia", False)]
        votes = {"summary": {}}
        s = exp.sensitivity(self.seed(), events, votes, {})
        self.assertFalse(s["publish_composite"])
        self.assertGreater(s["reversal_count"], 0)

    def test_stable_order_publishes(self):
        events = [self.ev("a", 3, "violencia", False), self.ev("a", 3, "contrapesos", False), self.ev("b", 1, "reglas", False), self.ev("b", 1, "justicia", False)]
        s = exp.sensitivity(self.seed(), events, {"summary": {}}, {})
        self.assertTrue(s["publish_composite"], s["reversals"])


class OutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(OUT.read_text(encoding="utf-8"))

    def test_every_event_links_a_source_and_counted_party(self):
        parties = {p["party_id"] for p in self.data["parties"]}
        for ev in self.data["events"]:
            self.assertTrue(ev["source"]["url"].startswith("https://"), ev["event_id"])
            self.assertTrue(all(a["party_id"] in parties for a in ev["attributions"]))

    def test_matrix_counts_match_events(self):
        cells = [c[s] for p in self.data["matrix"].values() for c in p.values() for s in ("gobierno", "fuera")]
        counted = [(e, a) for e in self.data["events"] for a in e["attributions"] if a["lineage"] != "predecessor"]
        self.assertEqual(sum(c["n"] for c in cells), sum(1 for e, _a in counted if e["coverage"]["type"] == "census"))
        self.assertEqual(sum(c["selection"] for c in cells), sum(1 for e, _a in counted if e["coverage"]["type"] == "selection"))

    def test_every_event_says_census_or_selection(self):
        fams = {f["family"]: f for f in self.data["census"]["families"]}
        for e in self.data["events"]:
            self.assertIn(e["coverage"]["type"], ("census", "selection"), e["event_id"])
            self.assertIn(e["coverage"]["family"], fams, e["event_id"])
            self.assertEqual(fams[e["coverage"]["family"]]["type"], e["coverage"]["type"])
        for f in fams.values():
            if f["type"] == "census":
                self.assertEqual(f["n_in_scope"], sum(1 for r in f["rows"] if r["in_scope"]))
                self.assertTrue(f["list_source"]["url"].startswith("https://"))

    def test_sensitivity_uses_census_only(self):
        n = sum(1 for e in self.data["events"] if e["coverage"]["type"] == "census")
        self.assertEqual(self.data["sensitivity"]["events_used"], n)

    def test_csv_carries_coverage(self):
        head = (REPO / "ui/site/public/visualizaciones/data/democracia-partidos.csv").read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(head.startswith("event_id,review,coverage,coverage_family"))

    def test_composite_only_when_no_reversal(self):
        s = self.data["sensitivity"]
        self.assertEqual(s["publish_composite"], s["reversal_count"] == 0 and len(s["parties_with_items"]) >= 2)
        if not s["publish_composite"]:
            self.assertIsNone(s["composite"])

    def test_vote_scores_bounded_and_roles(self):
        for pid, legs in self.data["votes"]["summary"].items():
            for leg, row in legs.items():
                self.assertEqual(row["role"] == "gobierno", pid in exp.LEG_GOVERNMENT[leg])
                for cat in ("estructural_vinculante", "estructural_declarativa", "escrutinio"):
                    sc = row[cat]["score"]
                    self.assertTrue(sc is None or -1 <= sc <= 1)

    def test_decree_series_zero_based_and_complete(self):
        d = self.data["decrees"]
        self.assertTrue(d["available"])
        years = [s["year"] for s in d["series"]]
        self.assertEqual(years, list(range(1979, years[-1] + 1)))
        self.assertTrue(all(s["rdl"] >= 0 for s in d["series"]))
        self.assertEqual(sum(s["rdl"] for s in d["series"]), sum(g["rdl"] for g in d["by_government"]))

    def test_every_published_item_verified(self):
        items = self.data["events"] + self.data["pending"]
        bad = [x.get("event_id") or x.get("pending_id") for x in items if x["review"]["status"] != "verified"]
        self.assertEqual(bad, [], "items without an independent verified review")
        self.assertEqual(self.data["meta"]["review"]["verified"], len(items))

    def test_size_budget(self):
        self.assertLess(OUT.stat().st_size, 1_500_000)


if __name__ == "__main__":
    unittest.main()
