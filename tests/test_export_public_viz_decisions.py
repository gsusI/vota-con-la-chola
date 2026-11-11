"""Tests for scripts/export_public_viz_decisions.py: selection rule, vote recount, decisiveness and the validator."""

from __future__ import annotations

import unittest

from scripts import export_public_viz_decisions as dec


def counts(**parties):
    return {p: {"S": s, "N": n, "A": a, "no_vota": 0} for p, (s, n, a) in parties.items()}


class DecisivenessTest(unittest.TestCase):
    def test_simple_majority_pivot(self):
        result, d = dec.decisiveness(counts(a=(120, 0, 0), b=(40, 0, 0), c=(0, 150, 0)), False)
        self.assertTrue(result)  # 160 > 150
        self.assertTrue(d["a"]["if_absent"])
        self.assertTrue(d["b"]["if_absent"])  # 120 < 150 without b
        self.assertFalse(d["c"]["if_absent"])  # without c it still passes

    def test_tie_is_rejection(self):
        self.assertFalse(dec.passes(171, 171, False))

    def test_absolute_majority(self):
        result, d = dec.decisiveness(counts(a=(170, 0, 0), b=(7, 0, 0), c=(0, 100, 0)), True)
        self.assertTrue(result)  # 177 >= 176
        self.assertTrue(d["b"]["if_absent"])  # 170 < 176
        self.assertFalse(d["c"]["if_absent"])

    def test_stance_orientation(self):
        self.assertEqual(dec.stance("S", True), "backed")
        self.assertEqual(dec.stance("S", False), "opposed")  # Sí to an enmienda a la totalidad kills the bill
        self.assertEqual(dec.stance("A", False), "abstained")
        self.assertEqual(dec.stance("dividido", True), "split")


class SelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.votes = dec.Votes(dec.load(dec.ATLAS), dec.load(dec.PEOPLE))
        cls.worklist = dec.build_candidates(cls.votes)

    def test_rule_is_deterministic_and_covers_every_domain(self):
        again = dec.build_candidates(self.votes)
        self.assertEqual([c["candidate_key"] for c in again], [c["candidate_key"] for c in self.worklist])
        domains = {d for c in self.worklist for d in c["domains"]}
        self.assertEqual(domains, set(dec.DOMAINS))

    def test_only_binding_units(self):
        for c in self.worklist:
            self.assertIn(c["kind"], {"final", "rdl", "totalidad"})
            if c["kind"] == "totalidad":
                self.assertEqual(c["unit"], "contrafactual")

    def test_recount_matches_published_totals(self):
        for c in self.worklist:
            pc = self.votes.party_counts(c["main_vote_id"])
            yes = sum(v["S"] for v in pc.values())
            no = sum(v["N"] for v in pc.values())
            abst = sum(v["A"] for v in pc.values())
            self.assertEqual([yes, no, abst], c["totals"], c["candidate_key"])

    def test_keywords_do_not_catch_autonomous_communities(self):
        rule = dec.DOMAIN_RULES["autonomos"]["keywords"]
        import re
        self.assertIsNone(re.search(rule, "Ley del Concierto Económico con la Comunidad Autónoma del País Vasco", re.I))
        self.assertIsNotNone(re.search(rule, "medidas para los trabajadores autónomos", re.I))


class ValidatorTest(unittest.TestCase):
    def test_flags_bad_records(self):
        votes = dec.Votes(dec.load(dec.ATLAS), dec.load(dec.PEOPLE))
        worklist = dec.build_candidates(votes)
        key = worklist[0]["candidate_key"]
        bad = {
            "measure_id": "x", "candidate_key": key, "name": "X", "what_changes": "Gracias a esta ley se creó todo",
            "stated_goal": "y", "boe_url": "http://boe.es", "verdict": "positivo", "verdict_reason": "z", "retrieved": "2026-11-11",
            "ex_ante": [], "ex_post": [{"source": "s", "url": "https://a", "finding": "f", "grade": "C"}], "evidence_against": [],
        }
        errors = dec.validate({"measures": [bad]}, votes, worklist)
        text = "\n".join(errors)
        self.assertIn("boe_url must be an https URL", text)
        self.assertIn("needs at least one A/B", text)
        self.assertIn("causal wording", text)

    def test_unknown_candidate_rejected(self):
        votes = dec.Votes(dec.load(dec.ATLAS), dec.load(dec.PEOPLE))
        errors = dec.validate({"measures": [{"measure_id": "y", "candidate_key": "hand-picked"}]}, votes, dec.build_candidates(votes))
        self.assertTrue(any("not in worklist" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
