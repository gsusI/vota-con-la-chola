from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import export_voting_aid_snapshot as va

REPO = Path(__file__).resolve().parent.parent
PUBLISHED = REPO / "ui/gh-pages-next/public/citizen/data/voting_aid_generales_v1.json"


def _seed(**overrides):
    seed = {
        "schema_version": va.SEED_SCHEMA_VERSION,
        "election": "generales",
        "legislature": "15",
        "parties": [
            {"party_id": "a", "label": "A", "group_codes": ["GA"]},
            {"party_id": "b", "label": "B", "group_codes": ["GB"]},
            {"party_id": "c", "label": "C", "members": ["Persona C"]},
        ],
        "statements": [
            {
                "statement_id": "s1",
                "concern_id": "vivienda",
                "text": "Afirmación uno",
                "votes": [{"vote_event_id": "v1", "agree_vote": "Sí"}],
            },
            {
                "statement_id": "s2",
                "concern_id": None,
                "text": "Afirmación dos",
                "votes": [{"vote_event_id": "v1", "agree_vote": "No"}, {"vote_event_id": "v2", "agree_vote": "Sí"}],
            },
        ],
    }
    seed.update(overrides)
    return seed


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE parl_vote_events (
          vote_event_id TEXT PRIMARY KEY, vote_date TEXT, expediente_text TEXT, subgroup_title TEXT,
          subgroup_text TEXT, source_url TEXT, totals_yes INTEGER, totals_no INTEGER, totals_abstain INTEGER
        );
        CREATE TABLE parl_vote_member_votes (
          vote_event_id TEXT, member_name TEXT, group_code TEXT, vote_choice TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO parl_vote_events VALUES (?,?,?,?,?,?,?,?,?)",
        [
            ("v1", "2025-01-01", "Ley uno", "", "", "https://example.invalid/v1", 3, 2, 0),
            ("v2", "2025-02-01", "Ley dos", "", "", "https://example.invalid/v2", 2, 2, 1),
        ],
    )
    rows = [
        # v1: A yes (2-1), B no, C (in group GB but mapped by name) yes.
        ("v1", "a1", "GA", "Sí"), ("v1", "a2", "GA", "Sí"), ("v1", "a3", "GA", "No"),
        ("v1", "b1", "GB", "No"), ("v1", "Persona C", "GB", "Sí"),
        ("v1", "Sin partido", "GX", "Sí"),
        # v2: A abstains, B tie (no clear position), C absent.
        ("v2", "a1", "GA", "Abstención"), ("v2", "a2", "GA", "Abstención"),
        ("v2", "b1", "GB", "Sí"), ("v2", "b2", "GB", "No"), ("v2", "b3", "GB", "No vota"),
    ]
    conn.executemany("INSERT INTO parl_vote_member_votes VALUES (?,?,?,?)", rows)
    conn.commit()  # backup() retries forever while the source holds an open write transaction
    return conn


class TestVotingAidSnapshot(unittest.TestCase):
    def test_positions_follow_majority_and_agree_vote(self) -> None:
        snap = va.build_snapshot(_db(), _seed(), generated_at="2026-10-11T00:00:00+00:00")
        s1, s2 = snap["statements"]
        self.assertEqual({p: c["position"] for p, c in s1["cells"].items()}, {"a": "agree", "b": "disagree", "c": "agree"})
        # s2: v1 with agree_vote=No flips; v2 gives A abstain, B tie (no_data), C absent (no_data).
        self.assertEqual(s2["cells"]["a"]["position"], "mixed")
        self.assertEqual(s2["cells"]["b"], {"position": "agree", "votes_with_data": 1, "votes_total": 2})
        self.assertEqual(s2["cells"]["c"]["position"], "disagree")
        v2_b = s2["votes"][1]["party_votes"]["b"]
        self.assertEqual((v2_b["choice"], v2_b["position"], v2_b["not_voting"]), (None, "no_data", 1))
        self.assertEqual(snap["meta"]["quality"]["unmapped_member_votes"], {"Sin partido": 1})
        self.assertEqual(snap["meta"]["quality"]["votes_missing"], [])
        self.assertIn("parl_vote_member_votes", s1["votes"][0]["explorer_member_votes"])

    def test_statement_without_any_vote_data_is_no_data(self) -> None:
        self.assertEqual(va.combine_positions(["no_data", "no_data"]), "no_data")
        self.assertEqual(va.combine_positions(["agree", "no_data", "agree"]), "agree")

    def test_missing_vote_is_reported(self) -> None:
        seed = _seed()
        seed["statements"][0]["votes"].append({"vote_event_id": "v404", "agree_vote": "Sí"})
        snap = va.build_snapshot(_db(), seed, generated_at="x")
        self.assertEqual(snap["meta"]["quality"]["votes_missing"], ["v404"])
        self.assertFalse(snap["statements"][0]["votes"][1]["found"])

    def test_validate_seed_rejects_bad_input(self) -> None:
        seed = _seed()
        seed["parties"].append({"party_id": "d", "label": "D", "group_codes": ["GA"]})
        seed["statements"][0]["votes"][0]["agree_vote"] = "Abstención"
        seed["statements"][1]["concern_id"] = "inexistente"
        errors = va.validate_seed(seed, concern_ids={"vivienda"})
        self.assertTrue(any("GA" in e for e in errors))
        self.assertTrue(any("agree_vote" in e for e in errors))
        self.assertTrue(any("inexistente" in e for e in errors))

    def test_main_fails_on_missing_votes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "v.db"
            disk = sqlite3.connect(db_path)
            _db().backup(disk)
            disk.close()
            seed = _seed()
            seed["statements"][0]["votes"].append({"vote_event_id": "v404", "agree_vote": "Sí"})
            seed_path = Path(td) / "seed.json"
            seed_path.write_text(json.dumps(seed), encoding="utf-8")
            out = Path(td) / "out.json"
            base = ["--db", str(db_path), "--seed", str(seed_path), "--out", str(out)]
            self.assertEqual(va.main(base), 3)
            self.assertFalse(out.exists())
            self.assertEqual(va.main(base + ["--allow-missing-votes"]), 0)
            self.assertTrue(out.exists())

    def test_committed_seed_is_valid_and_matches_published_snapshot(self) -> None:
        seed = json.loads(va.DEFAULT_SEED.read_text(encoding="utf-8"))
        concerns = json.loads(va.DEFAULT_CONCERNS.read_text(encoding="utf-8"))
        self.assertEqual(va.validate_seed(seed, concern_ids={c["id"] for c in concerns["concerns"]}), [])
        published = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        self.assertEqual(
            [s["statement_id"] for s in published["statements"]],
            [s["statement_id"] for s in seed["statements"]],
        )
        self.assertEqual(published["meta"]["quality"]["votes_missing"], [])
        for st in published["statements"]:
            self.assertEqual(set(st["cells"]), {p["party_id"] for p in seed["parties"]})


if __name__ == "__main__":
    unittest.main()
