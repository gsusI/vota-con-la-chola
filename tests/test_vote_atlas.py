from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

from scripts import export_vote_atlas as ex
from scripts import vote_atlas as va

REPO = Path(__file__).resolve().parent.parent
PUBLISHED = REPO / "ui/site/public/citizen/data"

SEED = {
    "parties": [
        {"party_id": "a", "label": "A", "group_codes": ["GA"]},
        {"party_id": "b", "label": "B", "group_codes": ["GB"]},
    ],
}
SEED_PSOE = {
    "parties": [
        {"party_id": "psoe", "label": "PSOE", "group_codes": ["GA"]},
        {"party_id": "b", "label": "B", "group_codes": ["GB"]},
    ],
}
AXES = {
    "topics": [{"topic_id": "t", "label": "Tema", "concern_id": None}],
    "axes": [
        {"axis_id": "x", "topic_id": "t", "label": "Eje X", "pos": "más", "neg": "menos", "pos_short": "Más", "neg_short": "Menos"},
        {"axis_id": "y", "topic_id": "t", "label": "Eje Y", "pos": "sí", "neg": "no", "pos_short": "Sí", "neg_short": "No"},
    ],
    "null_reasons": {"procedimiento": "trámite"},
}
MOTION = "Moción consecuencia de interpelación urgente del Grupo Parlamentario A, sobre algo."


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE parl_vote_events (vote_event_id TEXT PRIMARY KEY, legislature TEXT, session_number INTEGER,
          vote_number INTEGER, vote_date TEXT, title TEXT, expediente_text TEXT, subgroup_title TEXT, subgroup_text TEXT,
          totals_yes INTEGER, totals_no INTEGER, totals_abstain INTEGER, totals_no_vote INTEGER, source_url TEXT,
          source_id TEXT);
        CREATE TABLE parl_vote_member_votes (vote_event_id TEXT, member_name TEXT, person_id INTEGER, group_code TEXT,
          vote_choice TEXT);
        """
    )
    events = [
        # Two points of one motion (share one unit of weight), one bill, one amendment.
        ("p1", 1, "2024-01-10", "Mociones consecuencia de interpelaciones urgentes.", MOTION, "Votación separada por puntos.", "Punto 1."),
        ("p2", 2, "2024-01-10", "Mociones consecuencia de interpelaciones urgentes.", MOTION, "Votación separada por puntos.", "Punto 2."),
        ("law", 3, "2024-02-01", "Toma en consideración de Proposiciones de Ley.", "Proposición de Ley de algo.", "", ""),
        ("amd", 4, "2024-03-01", "Dictámenes de Comisiones sobre iniciativas legislativas.", "Proyecto de Ley de algo.",
         "Enmiendas presentadas por el Grupo Parlamentario B", "Enmienda 3."),
    ]
    for vid, n, date, title, exp, sgt, sgx in events:
        conn.execute(
            "INSERT INTO parl_vote_events VALUES (?, '15', 1, ?, ?, ?, ?, ?, ?, 2, 1, 0, 0, ?, 'congreso_votaciones')",
            (vid, n, date, title, exp, sgt, sgx, f"https://example.invalid/{vid}.json"),
        )
    # A1, A2 in party A; B1 in party B. A2 breaks with A on the bill.
    votes = {
        "p1": {"A1": "Sí", "A2": "Sí", "B1": "No"},
        "p2": {"A1": "Sí", "A2": "Sí", "B1": "Sí"},
        "law": {"A1": "No", "A2": "Sí", "B1": "Sí"},
        "amd": {"A1": "No", "A2": "No", "B1": "Sí"},
    }
    for vid, by in votes.items():
        for name, choice in by.items():
            conn.execute("INSERT INTO parl_vote_member_votes VALUES (?, ?, NULL, ?, ?)", (vid, name, "GA" if name[0] == "A" else "GB", choice))
    return conn


CLS = {
    "schema_version": ex.CLASSIFICATIONS_SCHEMA_VERSION,
    "votes": {
        "p1": {"axes": [{"axis_id": "x", "yes_pushes": "+", "confidence": "alta"}], "summary_yes": "Uno"},
        "p2": {"axes": [{"axis_id": "x", "yes_pushes": "-", "confidence": "media"}], "summary_yes": "Dos"},
        "law": {"axes": [{"axis_id": "x", "yes_pushes": "+", "confidence": "alta"}, {"axis_id": "y", "yes_pushes": "+", "confidence": "baja"}], "summary_yes": "Ley"},
    },
}


class VoteKindTest(unittest.TestCase):
    def test_kinds(self) -> None:
        k = va.vote_kind
        self.assertEqual(k("Mociones consecuencia de interpelaciones urgentes.", "Votación separada por puntos.", "Punto 1.", MOTION), "mocion_punto")
        self.assertEqual(k("Proposiciones no de Ley.", "", "", "Proposición no de Ley de X."), "pnl")
        self.assertEqual(k("Enmiendas del Senado.", "Votación separada de las enmiendas", "Enmienda al artículo 3.", ""), "enmienda_senado")
        self.assertEqual(k("Debates de totalidad de iniciativas legislativas.", "", "", "Enmiendas de totalidad de devolución."), "totalidad")
        self.assertEqual(k("Convalidación o derogación de Reales Decretos-leyes.", "", "", "Real Decreto-ley 1/2024."), "rdl")
        self.assertEqual(k("Convalidación o derogación de Reales Decretos-leyes.", "", "", "Tramitación como Proyecto de Ley del Real Decreto-ley 1/2024."), "rdl_tramitacion")
        self.assertEqual(k("Dictámenes de Comisiones sobre iniciativas legislativas.", "Enmiendas presentadas por el Grupo X", "Enmienda 2.", ""), "enmienda")
        self.assertEqual(k("Dictámenes de Comisiones sobre iniciativas legislativas.", "Votación de conjunto.", "", ""), "final")
        self.assertEqual(k("Solicitud de prórroga de Subcomisiones.", "", "", ""), "procedimiento")

    def test_point_numbers(self) -> None:
        self.assertEqual(va.point_numbers("Punto 3."), [3])
        self.assertEqual(va.point_numbers("Puntos 1 y 4"), [1, 4])
        self.assertEqual(va.point_numbers("Sexto guion."), [6])
        self.assertEqual(va.point_numbers("Resto de la moción."), [])

    def test_point_text_locates_points(self) -> None:
        text = {"points": [{"n": "1", "text": "Uno"}, {"n": "2", "text": "Dos"}]}
        self.assertEqual(va.point_text(text, "Punto 2.")[0], [{"n": "2", "text": "Dos"}])
        self.assertEqual(va.point_text(text, "Punto 7.")[1], "punto_no_encontrado")
        self.assertEqual(va.point_text(None, "Punto 1.")[1], "sin_texto_mocion")


class AgreementTest(unittest.TestCase):
    def test_agreement_counts_axis_and_sign(self) -> None:
        main = {
            "v1": {"axes": [{"axis_id": "x", "yes_pushes": "+", "confidence": "alta"}]},
            "v2": {"axes": [{"axis_id": "x", "yes_pushes": "+", "confidence": "media"}]},
            "v3": {"axes": [], "null_reason": "procedimiento"},
        }
        second = {
            "v1": {"axes": [{"axis_id": "x", "yes_pushes": "+"}]},
            "v2": {"axes": [{"axis_id": "y", "yes_pushes": "+"}]},
            "v3": {"axes": []},
        }
        r = va.agreement(main, second)
        self.assertEqual(r["votes_compared"], 3)
        self.assertEqual(r["same_has_axis"], 1.0)
        self.assertEqual(r["same_primary_axis"], 0.5)
        self.assertEqual(r["scored_primary_axis_found_in_second"], 0.5)
        self.assertEqual([d["type"] for d in r["disagreements"]], ["axis"])


class ExportTest(unittest.TestCase):
    def setUp(self) -> None:
        conn = _db()
        self.addCleanup(conn.close)
        self.atlas, self.people, self.ctx = ex.build(conn, SEED, AXES, CLS, {}, legislature="15", generated_at="t")

    def test_validation(self) -> None:
        self.assertEqual(ex.validate_classifications(CLS, AXES), [])
        bad = {"schema_version": ex.CLASSIFICATIONS_SCHEMA_VERSION, "votes": {"v": {"axes": [{"axis_id": "z", "yes_pushes": "?", "confidence": "alta"}]}}}
        errors = ex.validate_classifications(bad, AXES)
        self.assertTrue(any("eje desconocido" in e for e in errors))
        self.assertTrue(any("yes_pushes" in e for e in errors))

    def test_party_scores_weight_motion_points_as_one(self) -> None:
        # Party A: p1 Sí(+) -> +1, p2 Sí(-) -> -1 (each weight 1/2), law A1 No / A2 Sí -> 0 (weight 1) => 0.
        # Party B: p1 No(+) -> -1, p2 Sí(-) -> -1 (weights 1/2), law Sí(+) -> +1 => 0.
        a = self.atlas["party_axes"]["a"]["x"]
        b = self.atlas["party_axes"]["b"]["x"]
        self.assertAlmostEqual(a["score"], 0.0)
        self.assertAlmostEqual(b["score"], 0.0)
        self.assertEqual(a["votes"], 3)
        self.assertEqual(a["initiatives"], 2)
        # Low-confidence axes are listed but never scored.
        self.assertNotIn("y", self.atlas["party_axes"]["a"])

    def test_coverage_and_votes(self) -> None:
        cov = self.atlas["meta"]["coverage"]
        self.assertEqual(cov["by_status"]["enmienda_sin_texto"], 1)
        self.assertEqual(cov["scored_votes"], 3)
        law = next(v for v in self.atlas["votes"] if v["summary_yes"] == "Ley")
        self.assertEqual(law["parties"], "=S")  # A tied 1-1, B voted Sí

    def test_people_loyalty_and_rebels(self) -> None:
        by_name = {p["name"]: p for p in self.people["people"]}
        self.assertEqual(by_name["A1"]["votes"], "SSNN")
        # A is tied on the bill: no majority, so it does not count for loyalty.
        self.assertEqual(by_name["A2"]["rebels"], [])
        self.assertEqual(by_name["A2"]["loyalty_votes"], 3)
        self.assertEqual(by_name["B1"]["axes"]["x"][1], 3)

    def test_voting_aid_statements(self) -> None:
        aid_seed = {"schema_version": ex.AID_SEED_SCHEMA_VERSION, "min_votes": 1,
                    "statements": [{"statement_id": "s-x", "axis_id": "x", "pole": "-", "text": "Menos X"},
                                   {"statement_id": "s-y", "axis_id": "y", "pole": "+", "text": "Más Y"}]}
        aid = ex.build_voting_aid(self.ctx, SEED, aid_seed, AXES, {}, self.atlas["meta"], generated_at="t")
        self.assertEqual([s["statement_id"] for s in aid["statements"]], ["s-x"])  # y has no primary scored votes
        self.assertEqual(aid["meta"]["quality"]["statements_skipped"], [{"statement_id": "s-y", "votes": 0}])
        st = aid["statements"][0]
        self.assertEqual(st["votes_total"], 3)
        self.assertEqual(st["initiatives_total"], 2)
        # Pole "-": a Sí on p1 (pushes +) disagrees with the statement.
        p1 = next(v for v in st["votes"] if v["summary_yes"] == "Uno")
        self.assertEqual(p1["agree_vote"], "No")
        self.assertEqual(st["cells"]["a"]["position"], "mixed")

    def test_score_position_bands(self) -> None:
        self.assertEqual(ex.score_position(None), "no_data")
        self.assertEqual(ex.score_position(0.5), "agree")
        self.assertEqual(ex.score_position(-0.4), "disagree")
        self.assertEqual(ex.score_position(0.1), "mixed")


class EarlierLegislatureTest(unittest.TestCase):
    def test_xiv_votes_count_for_deputies_not_parties(self) -> None:
        conn = _db()
        self.addCleanup(conn.close)
        conn.execute(
            "INSERT INTO parl_vote_events VALUES ('old', '14', 1, 1, '2022-11-01', 'Proposiciones no de Ley.', "
            "'Proposición no de Ley de algo viejo.', '', '', 1, 2, 0, 0, 'https://example.invalid/old.json', 'congreso_votaciones')"
        )
        conn.execute(
            "INSERT INTO parl_vote_events VALUES ('older', '14', 1, 1, '2020-01-01', 'Proposiciones no de Ley.', "
            "'Proposición no de Ley fuera de rango.', '', '', 1, 2, 0, 0, 'https://example.invalid/older.json', 'congreso_votaciones')"
        )
        # Same person as A1 (accents/case aside), then in group GS; X2 only sat in the XIV, in the Plural group.
        for name, group, choice in (("a1", "GS", "Sí"), ("Otro GS", "GS", "No"), ("Otro GS 2", "GS", "No"), ("X2", "GPlu", "No")):
            conn.execute("INSERT INTO parl_vote_member_votes VALUES ('old', ?, NULL, ?, ?)", (name, group, choice))
        cls = {**CLS, "votes": {**CLS["votes"], "old": {"axes": [{"axis_id": "x", "yes_pushes": "+", "confidence": "alta"}], "summary_yes": "Viejo"}}}
        atlas, people, ctx = ex.build(conn, SEED_PSOE, AXES, cls, {}, legislature="15", generated_at="t", earlier=[("14", "2022-10-01")])
        # Parties and the voting aid only see the current legislature.
        self.assertEqual(atlas["party_axes"]["psoe"]["x"]["votes"], 3)
        self.assertEqual([e["vote_event_id"] for e in ctx["events"]], ["p1", "p2", "law", "amd"])
        self.assertEqual(people["votes"][0][-1], "14")
        self.assertEqual(len(people["votes"]), 5)  # 'older' is before the cut-off date
        by_name = {p["name"]: p for p in people["people"]}
        a1 = by_name.get("A1") or by_name["a1"]
        self.assertEqual(a1["legislatures"], ["14", "15"])
        self.assertEqual(a1["rebels"][0], [0, "N"])  # voted Sí against the GS majority in the XIV
        self.assertEqual(a1["loyalty_by_leg"]["14"], [0.0, 1])
        self.assertEqual(a1["axes"]["x"][1], 4)  # the XIV vote adds to the deputy's own direction
        self.assertIsNone(by_name["X2"]["party_id"])
        self.assertEqual(by_name["X2"]["loyalty_votes"], 0)  # Plural group: no single-party majority
        old = next(v for v in atlas["votes"] if v.get("leg") == "14")
        self.assertEqual(old["parties"], "N?")  # PSOE through its XIV group; party B has no XIV group


class PublishedTest(unittest.TestCase):
    def test_published_files_are_consistent(self) -> None:
        atlas = json.loads((PUBLISHED / "vote_atlas_v1.json").read_text(encoding="utf-8"))
        aid = json.loads((PUBLISHED / "voting_aid_generales_v2.json").read_text(encoding="utf-8"))
        axis_ids = {a["axis_id"] for a in atlas["axes"]}
        for v in atlas["votes"]:
            self.assertTrue(all(a[0] in axis_ids for a in v["axes"]))
            self.assertEqual(len(v["parties"]), len(atlas["parties"]))
        balance = aid["meta"]["quality"]["direction_balance"]["agree_sides_only_with"]
        self.assertLessEqual(abs(balance["psoe"] - balance["pp"]), 3, "responder siempre «de acuerdo» no debe favorecer a un bloque")
        for st in aid["statements"]:
            self.assertGreaterEqual(st["votes_total"], 4)
            self.assertIn(st["axis_id"], axis_ids)


if __name__ == "__main__":
    unittest.main()
