from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts import export_voting_aid_vote_impacts as vi

REPO = Path(__file__).resolve().parent.parent
SEED = REPO / "etl/data/seeds/voting_aid_vote_impacts_v1.json"
DATA = REPO / "ui/site/public/citizen/data"
DS = "https://www.congreso.es/public_oficiales/L15/CONG/DS/PL/DSCD-15-PL-62.PDF"

FIXTURE = {
    "meta": {"schema_version": vi.SEED_SCHEMA_VERSION},
    "facts": {
        "hogares": {"text": "El 16,7 % de los hogares vive de alquiler.", "period": "2025", "source": "INE", "url": "https://www.ine.es/jaxiT3/Tabla.htm?t=9996"},
    },
    "statements": {"eje": {"facts": ["hogares"]}},
    "votes": {
        "v1": {
            "facts": ["hogares"],
            "direct_effects": [{"actor": "Inquilinos", "text": "Podrían irse tras el primer mes.", "locator": "Artículo 11.2"}],
            "indirect_effects": [
                {"kind": "riesgo_senalado", "text": "Menos oferta para estudiantes.", "evidence": "debate", "source": "Debate", "locator": "pág. 12", "url": DS},
                {"kind": "beneficio_esperado", "text": "Más alquiler habitual.", "evidence": "organismo_publico", "source": "Banco de España", "locator": "pág. 29", "url": "https://www.bde.es/x.pdf"},
            ],
            "gaps": "No lleva memoria de impacto.",
            "review": {"status": "draft"},
        },
    },
}


class TestValidation(unittest.TestCase):
    def test_valid_fixture_passes_and_publishes(self) -> None:
        self.assertEqual(vi.validate_seed(FIXTURE, {"v1"}, {"eje"}), [])
        out = vi.build_payload(FIXTURE)
        self.assertEqual(out["facts"]["hogares"]["period"], "2025")
        self.assertEqual(out["by_statement"], {"eje": {"facts": ["hogares"]}})
        v = out["by_vote"]["v1"]
        # Expected benefits come first regardless of seed order.
        self.assertEqual([e["kind"] for e in v["indirect"]], ["beneficio_esperado", "riesgo_senalado"])
        self.assertEqual(v["direct"][0], {"actor": "Inquilinos", "text": "Podrían irse tras el primer mes.", "locator": "Artículo 11.2"})
        self.assertEqual(v["gaps"], "No lleva memoria de impacto.")
        self.assertEqual(out["meta"]["indirect_by_evidence"]["debate"], 1)

    def test_accepts_diary_supplement(self) -> None:
        seed = copy.deepcopy(FIXTURE)
        seed["votes"]["v1"]["indirect_effects"][0]["url"] = DS.replace("PL-62.PDF", "PL-163-C1.PDF")
        self.assertEqual(vi.validate_seed(seed, {"v1"}, {"eje"}), [])

    def test_rejects_ungrounded_one_sided_or_partisan(self) -> None:
        def ind(s, i=0):
            return s["votes"]["v1"]["indirect_effects"][i]

        cases = {
            "unknown fact": lambda s: s["votes"]["v1"]["facts"].append("inventado"),
            "no facts": lambda s: s["votes"]["v1"].__setitem__("facts", []),
            "fact without url": lambda s: s["facts"]["hogares"].__setitem__("url", ""),
            "fact without period": lambda s: s["facts"]["hogares"].__setitem__("period", " "),
            "one-sided": lambda s: s["votes"]["v1"]["indirect_effects"].pop(1),
            "bad kind": lambda s: ind(s).__setitem__("kind", "opinion"),
            "bad evidence": lambda s: ind(s).__setitem__("evidence", "intuicion"),
            "debate off diary": lambda s: ind(s).__setitem__("url", "https://www.congreso.es/es/notas-de-prensa"),
            "no page": lambda s: ind(s).__setitem__("locator", ""),
            "party in effect": lambda s: ind(s).__setitem__("text", "Según el PSOE, bajarán los precios."),
            "party in source": lambda s: ind(s).__setitem__("source", "Intervención del Grupo Parlamentario Popular"),
            "direct without locator": lambda s: s["votes"]["v1"]["direct_effects"][0].__setitem__("locator", ""),
            "too many direct": lambda s: s["votes"]["v1"].__setitem__("direct_effects", [{"actor": "A", "text": "x", "locator": "y"}] * 5),
            "unknown statement": lambda s: s["statements"].__setitem__("otro", {"facts": ["hogares"]}),
            "review": lambda s: s["votes"]["v1"].__setitem__("review", {}),
        }
        for name, mutate in cases.items():
            seed = copy.deepcopy(FIXTURE)
            mutate(seed)
            with self.subTest(name):
                self.assertTrue(vi.validate_seed(seed, {"v1"}, {"eje"}), name)

    def test_unknown_vote_is_rejected(self) -> None:
        self.assertTrue(vi.validate_seed(FIXTURE, {"v2"}, {"eje"}))


class TestParts(unittest.TestCase):
    def test_merge_reuses_facts_and_rejects_duplicates(self) -> None:
        part = {"facts": {"hogares": FIXTURE["facts"]["hogares"]}, "votes": {"v2": {"facts": ["hogares"], "review": {"status": "draft"}}}}
        merged, errors = vi.merge_parts(FIXTURE, [("a.json", part)])
        self.assertEqual(errors, [])
        self.assertEqual(sorted(merged["votes"]), ["v1", "v2"])
        changed = copy.deepcopy(part)
        changed["facts"]["hogares"]["text"] = "Otra cifra."
        self.assertTrue(vi.merge_parts(FIXTURE, [("a.json", changed)])[1])
        self.assertTrue(vi.merge_parts(FIXTURE, [("a.json", part), ("b.json", {"votes": part["votes"]})])[1])

    def test_coverage_counts_both_levels(self) -> None:
        cov = vi.coverage(FIXTURE, {"v1", "v2"}, {"eje", "otra"})
        self.assertEqual((cov["statements"], cov["votes"]), ([1, 2], [1, 2]))
        self.assertEqual((cov["missing_statements"], cov["missing_votes"]), (["otra"], ["v2"]))


class TestRealSeed(unittest.TestCase):
    def test_pilot_seed_is_publishable(self) -> None:
        seed, errors = vi.merge_parts(json.loads(SEED.read_text(encoding="utf-8")), vi.load_parts(vi.DEFAULT_PARTS))
        self.assertEqual(errors, [])
        snapshots = [json.loads((DATA / f"voting_aid_generales_{v}.json").read_text(encoding="utf-8")) for v in ("v1", "v2")]
        pool = json.loads((DATA / "voting_aid_pool_v1.json").read_text(encoding="utf-8"))
        votes, statements = vi.known_ids(snapshots, pool)
        self.assertEqual(vi.validate_seed(seed, votes, statements), [])
        self.assertGreaterEqual(len(seed["votes"]), 5)


if __name__ == "__main__":
    unittest.main()
