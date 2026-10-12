from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts import export_voting_aid_vote_bullets as vb

REPO = Path(__file__).resolve().parent.parent
SEED = REPO / "etl/data/seeds/voting_aid_vote_bullets_v1.json"
DATA = REPO / "ui/site/public/citizen/data"
SHA = "a" * 64

FIXTURE = {
    "meta": {"schema_version": vb.SEED_SCHEMA_VERSION},
    "votes": {
        "v1": {
            "status": "ok",
            "source": {"url": "https://www.boe.es/eli/es/rdl/2024/12/23/9", "sha256": SHA, "source": "BOE"},
            "bullets": [
                {"text": "Prorroga hasta 2025 la suspensión de desahucios de hogares vulnerables.", "locator": "Artículo 1"},
                {"text": "Sube las pensiones un 2,8 %.", "locator": "Disposición final segunda"},
            ],
            "review": {"status": "draft"},
        },
        "v2": {"status": "sin_texto_oficial", "bullets": [], "source": None, "review": {"status": "draft"}},
    },
}


class TestValidation(unittest.TestCase):
    def test_valid_fixture_passes_and_publishes(self) -> None:
        self.assertEqual(vb.validate_seed(FIXTURE, {"v1", "v2"}), [])
        out = vb.build_payload(FIXTURE)
        self.assertEqual(out["meta"]["with_bullets"], 1)
        self.assertEqual(out["meta"]["without_official_text"], 1)
        self.assertEqual(out["by_vote"]["v1"]["bullets"][1], {"text": "Sube las pensiones un 2,8 %.", "locator": "Disposición final segunda"})
        self.assertEqual(out["by_vote"]["v1"]["source"], "BOE")
        self.assertEqual(out["by_vote"]["v2"], {"status": "sin_texto_oficial", "review": "draft"})

    def test_rejects_ungrounded_or_biased_bullets(self) -> None:
        cases = {
            "7 bullets": lambda s: s["votes"]["v1"].__setitem__("bullets", [{"text": f"Punto {i}", "locator": f"Punto {i}"} for i in range(7)]),
            "no locator": lambda s: s["votes"]["v1"]["bullets"][0].__setitem__("locator", ""),
            "no url": lambda s: s["votes"]["v1"]["source"].__setitem__("url", ""),
            "no sha": lambda s: s["votes"]["v1"]["source"].__setitem__("sha256", None),
            "party": lambda s: s["votes"]["v1"]["bullets"][0].__setitem__("text", "Propuesta del Grupo Parlamentario Popular para bajar el IVA."),
            "invented": lambda s: s["votes"]["v2"].__setitem__("bullets", [{"text": "Algo", "locator": "Artículo 1"}]),
            "review": lambda s: s["votes"]["v1"].__setitem__("review", {}),
            "unknown review": lambda s: s["votes"]["v1"].__setitem__("review", {"status": "ok"}),
        }
        for name, mutate in cases.items():
            seed = copy.deepcopy(FIXTURE)
            mutate(seed)
            self.assertTrue(vb.validate_seed(seed, {"v1", "v2"}), name)
        self.assertTrue(vb.validate_seed(FIXTURE, {"v1"}))  # v2 is not a voting-aid vote

    def test_sha_must_match_published_highlights(self) -> None:
        hl = {"docs": {"k": {"url": "https://www.boe.es/eli/es/rdl/2024/12/23/9", "sha256": "b" * 64}}}
        self.assertTrue(any("sha256" in e for e in vb.validate_seed(FIXTURE, None, hl)))


class TestPublishedBullets(unittest.TestCase):
    def test_seed_validates_and_covers_every_question(self) -> None:
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        snapshot = json.loads((DATA / "voting_aid_generales_v1.json").read_text(encoding="utf-8"))
        pool = json.loads((DATA / "voting_aid_pool_v1.json").read_text(encoding="utf-8"))
        highlights = json.loads((DATA / "voting_aid_highlights_v1.json").read_text(encoding="utf-8"))
        ids = vb.question_vote_ids(snapshot, pool)
        self.assertEqual(vb.validate_seed(seed, ids, highlights), [])
        self.assertEqual(set(seed["votes"]), ids)
        published = json.loads((DATA / "voting_aid_vote_bullets_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(published["meta"]["schema_version"], vb.SCHEMA_VERSION)
        self.assertEqual(set(published["by_vote"]), ids)
        # Every vote with an official text has bullets; the rest say so explicitly.
        with_text = set(highlights["by_vote"])
        for vid, v in published["by_vote"].items():
            self.assertEqual(v["status"], "ok" if vid in with_text else "sin_texto_oficial", vid)


if __name__ == "__main__":
    unittest.main()
