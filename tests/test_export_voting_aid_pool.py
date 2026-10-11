from __future__ import annotations

import json
import re
import sqlite3
import unittest
from pathlib import Path

from scripts import export_voting_aid_pool as pool

REPO = Path(__file__).resolve().parent.parent
PUBLISHED = REPO / "ui/gh-pages-next/public/citizen/data/voting_aid_pool_v1.json"
PARTY_NAMES = re.compile(r"Grupo Parlamentario|Socialista|Popular en el|\bVOX\b|SUMAR|Junts|Republicano|Bildu|EAJ-PNV|Sra?\. [A-ZÁÉÍÓÚ]")


class TestAnonymizeTitle(unittest.TestCase):
    def test_removes_group_and_keeps_subject(self) -> None:
        cases = [
            (
                "Proposición de Ley del Grupo Parlamentario Popular en el Congreso, Orgánica contra la ocupación ilegal de inmuebles.",
                "toma",
                "Proposición de ley orgánica contra la ocupación ilegal de inmuebles.",
                "Grupo Parlamentario Popular en el Congreso",
            ),
            (
                "Moción consecuencia de interpelación urgente del Grupo Parlamentario Mixto (Sra. Belarra Urteaga), referida a la política educativa.",
                "mocion",
                "Moción referida a la política educativa.",
                "Grupo Parlamentario Mixto (Sra. Belarra Urteaga)",
            ),
            (
                "Del Grupo Parlamentario VOX, sobre la asistencia sanitaria.",
                "mocion",
                "Moción sobre la asistencia sanitaria.",
                "Grupo Parlamentario VOX",
            ),
            (
                "Proposición de Ley del Grupo Parlamentario Socialista sobre programa de cribado neonatal.",
                "toma",
                "Proposición de ley sobre programa de cribado neonatal.",
                "Grupo Parlamentario Socialista",
            ),
            (
                "Proposición no de Ley del Grupo Parlamentario Republicano, relativa a la vivienda. Se vota en los términos de la enmienda transaccional.",
                "pnl",
                "Proposición no de ley relativa a la vivienda.",
                "Grupo Parlamentario Republicano",
            ),
        ]
        for text, kind, title, proposer in cases:
            with self.subTest(text=text):
                self.assertEqual(pool.anonymize_title(text, kind), (title, proposer))

    def test_safety_net_masks_remaining_group_mentions(self) -> None:
        title, proposer = pool.anonymize_title("Ley el Grupo Parlamentario Vasco (EAJ-PNV), de modificación de la Ley 11/2002.", "toma")
        self.assertNotIn("Grupo Parlamentario", title)
        self.assertIsNone(proposer)

    def test_strips_expediente_note_and_final_prefix(self) -> None:
        title, _ = pool.anonymize_title(
            "Votación de conjunto del texto del Proyecto de Ley por la que se modifica la Ley 28/1990 (corresponde al número de expediente 121/0001).",
            "final",
        )
        self.assertEqual(title, "Proyecto de Ley por la que se modifica la Ley 28/1990.")


class TestThemeAndClassify(unittest.TestCase):
    def test_theme_uses_word_starts(self) -> None:
        self.assertEqual(pool.theme_for("Proposición no de ley relativa a la prioridad nacional"), "Otros")
        self.assertEqual(pool.theme_for("Rebaja del IVA de los alimentos"), "Impuestos y economía")
        self.assertEqual(pool.theme_for("Medidas fiscales contra la especulación inmobiliaria"), "Vivienda")
        self.assertEqual(pool.theme_for("Sistema para la Autonomía y Atención a la Dependencia"), "Servicios sociales")

    def test_classify(self) -> None:
        self.assertEqual(pool.classify("Toma en consideración de Proposiciones de Ley.", "x", ""), "toma")
        self.assertIsNone(pool.classify("Toma en consideración de Proposiciones de Ley.", "x", "Votación separada"))
        self.assertEqual(pool.classify("Convalidación o derogación de Reales Decretos-leyes.", "Real Decreto-ley 1/2026", ""), "rdl")
        self.assertIsNone(pool.classify("Convalidación o derogación de Reales Decretos-leyes.", "Tramitación como proyecto", ""))
        self.assertEqual(pool.classify("Dictámenes de Comisiones.", "Ley X", "Votación de conjunto."), "final")


class TestBuildPool(unittest.TestCase):
    def _db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            CREATE TABLE parl_vote_events (vote_event_id TEXT PRIMARY KEY, source_id TEXT, legislature TEXT, vote_date TEXT,
              title TEXT, expediente_text TEXT, subgroup_title TEXT, source_url TEXT, totals_yes INT, totals_no INT, totals_abstain INT);
            CREATE TABLE parl_vote_member_votes (vote_event_id TEXT, member_name TEXT, group_code TEXT, vote_choice TEXT);
            CREATE TABLE parl_vote_event_initiatives (vote_event_id TEXT, initiative_id TEXT);
            CREATE TABLE parl_initiatives (initiative_id TEXT, links_bocg_json TEXT);
            """
        )
        events = [
            ("e1", "2025-01-01", "Toma en consideración de Proposiciones de Ley.", "Proposición de Ley del Grupo Parlamentario Socialista, sobre algo.", ""),
            ("e2", "2025-01-02", "Toma en consideración de Proposiciones de Ley.", "Proposición de Ley del Grupo Parlamentario Popular en el Congreso, sobre todos de acuerdo.", ""),
            ("e3", "2025-01-03", "Enmiendas.", "Otra cosa", ""),
            ("curated", "2025-01-04", "Toma en consideración de Proposiciones de Ley.", "Proposición de Ley del Grupo Parlamentario Socialista, sobre ya usada.", ""),
        ]
        for vid, date, title, exp, sg in events:
            conn.execute(
                "INSERT INTO parl_vote_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (vid, "congreso_votaciones", "15", date, title, exp, sg, f"https://example.invalid/{vid}", 2, 1, 0),
            )
        votes = [("e1", "a", "GA", "Sí"), ("e1", "b", "GB", "No"), ("e2", "a", "GA", "Sí"), ("e2", "b", "GB", "Sí"),
                 ("e3", "a", "GA", "Sí"), ("e3", "b", "GB", "No"), ("curated", "a", "GA", "Sí"), ("curated", "b", "GB", "No")]
        conn.executemany("INSERT INTO parl_vote_member_votes VALUES (?,?,?,?)", votes)
        conn.execute("INSERT INTO parl_vote_event_initiatives VALUES ('e1','i1')")
        conn.execute("INSERT INTO parl_initiatives VALUES ('i1', ?)", (json.dumps(["https://x/BOCG-15-B-1-2.PDF", "https://x/BOCG-15-B-1-1.PDF#page=1"]),))
        conn.commit()
        return conn

    def test_keeps_only_divisive_new_votes(self) -> None:
        seed = {
            "parties": [{"party_id": "psoe", "label": "A", "group_codes": ["GA"]}, {"party_id": "pp", "label": "B", "group_codes": ["GB"]}],
            "statements": [{"votes": [{"vote_event_id": "curated"}]}],
        }
        out = pool.build_pool(self._db(), seed, legislature="15", generated_at="x")
        self.assertEqual([it["vote_event_id"] for it in out["items"]], ["e1"])
        item = out["items"][0]
        self.assertEqual(item["positions"], {"psoe": "agree", "pp": "disagree"})
        self.assertEqual(item["counts"]["psoe"], [1, 0, 0])
        self.assertEqual((item["title"], item["proposer"]), ("Proposición de ley sobre algo.", "Grupo Parlamentario Socialista"))
        self.assertEqual(item["text_url"], "https://x/BOCG-15-B-1-1.PDF")
        self.assertEqual((item["side"], item["tier"]), ("psoe", "lone"))


class TestPublishedPool(unittest.TestCase):
    def test_published_pool_hides_proposers_and_is_large(self) -> None:
        data = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        items = data["items"]
        self.assertGreaterEqual(len(items), 200)
        self.assertEqual(len({it["id"] for it in items}), len(items))
        for it in items:
            self.assertIsNone(PARTY_NAMES.search(it["title"]), it["title"])
            positions = set(it["positions"].values())
            self.assertIn("agree", positions)
            self.assertIn("disagree", positions)


if __name__ == "__main__":
    unittest.main()
