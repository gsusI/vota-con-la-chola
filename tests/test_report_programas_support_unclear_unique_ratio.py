from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.report_programas_support_unclear_unique_ratio import build_report, main


class TestReportProgramasSupportUnclearUniqueRatio(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE persons (
              person_id INTEGER PRIMARY KEY,
              full_name TEXT
            );
            CREATE TABLE topic_evidence (
              evidence_id INTEGER PRIMARY KEY,
              person_id INTEGER,
              source_id TEXT,
              source_url TEXT,
              excerpt TEXT,
              stance TEXT
            );
            """
        )
        return conn

    def test_build_report_ok_when_ratio_meets_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "ratio_ok.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO persons(person_id, full_name) VALUES (?, ?)",
                    [(1, "BNG"), (2, "VOX")],
                )
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, excerpt, stance)
                    VALUES (?, ?, 'programas_partidos', ?, ?, ?)
                    """,
                    [
                        (1, 1, "https://bng/eu.pdf", "a b c", "unclear"),
                        (2, 1, "https://bng/eu.pdf", "a   b   c", "unclear"),
                        (3, 1, "https://bng/eu.pdf", "x y z", "support"),
                        (4, 1, "https://bng/eu.pdf", "k l m", "support"),
                        (5, 2, "https://vox/web.pdf", "p q r", "unclear"),
                        (6, 2, "https://vox/web.pdf", "p q r", "unclear"),
                        (7, 2, "https://vox/web.pdf", "u v w", "support"),
                    ],
                )
                conn.commit()

                report = build_report(
                    conn,
                    source_id="programas_partidos",
                    parties=["BNG", "VOX"],
                    min_ratio=1.0,
                )
                self.assertEqual(str(report["status"]), "ok")
                self.assertEqual(int(report["rows_total"]), 2)
                by_party = {str(r["party_name"]): r for r in list(report["rows"])}
                self.assertAlmostEqual(float(by_party["BNG"]["support_to_unclear_unique_ratio"]), 1.0, places=6)
                self.assertAlmostEqual(float(by_party["VOX"]["support_to_unclear_unique_ratio"]), 1.0, places=6)
            finally:
                conn.close()

    def test_main_strict_fails_when_ratio_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "ratio_fail.db"
            out_json = td_path / "report.json"

            conn = self._open_db(db_path)
            try:
                conn.execute("INSERT INTO persons(person_id, full_name) VALUES (1, 'BNG')")
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, excerpt, stance)
                    VALUES (?, 1, 'programas_partidos', 'https://bng/eu.pdf', ?, ?)
                    """,
                    [
                        (10, "texto 1", "unclear"),
                        (11, "texto 2", "unclear"),
                        (12, "texto 3", "support"),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--source-id",
                    "programas_partidos",
                    "--parties",
                    "BNG",
                    "--min-support-unclear-unique-ratio",
                    "2.0",
                    "--out",
                    str(out_json),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(payload["status"]), "degraded")
            self.assertIn("ratio_below_threshold", list(payload["strict_fail_reasons"]))

    def test_build_report_collapses_near_duplicates_for_unclear(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "ratio_near_dup.db"
            conn = self._open_db(db_path)
            try:
                conn.execute("INSERT INTO persons(person_id, full_name) VALUES (1, 'BNG')")
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, excerpt, stance)
                    VALUES (?, 1, 'programas_partidos', 'https://bng/eu.pdf', ?, ?)
                    """,
                    [
                        (
                            1,
                            "aumento cotas hipotecarias familias tecido produtivo "
                            "entidades financeiras record lucros union europea non quixo despregar "
                            "medida efectiva combater carestia vida",
                            "unclear",
                        ),
                        (
                            2,
                            "entidades financeiras record lucros union europea non quixo despregar "
                            "medida efectiva combater carestia vida empobrecemento social "
                            "reformas gobernanza economica",
                            "unclear",
                        ),
                        (3, "proponemos mellorar o emprego", "support"),
                        (4, "impulsaremos vivenda asequible", "support"),
                    ],
                )
                conn.commit()
                report = build_report(
                    conn,
                    source_id="programas_partidos",
                    parties=["BNG"],
                    min_ratio=2.0,
                )
                self.assertEqual(str(report["status"]), "ok")
                self.assertEqual(int(report["rows_total"]), 1)
                row = list(report["rows"])[0]
                self.assertEqual(int(row["unclear_unique_exact_excerpt_rows"]), 2)
                self.assertEqual(int(row["unclear_unique_excerpt_rows"]), 1)
                self.assertEqual(int(row["unclear_near_duplicate_collapsed_rows"]), 1)
                self.assertAlmostEqual(float(row["support_to_unclear_unique_ratio"]), 2.0, places=6)
            finally:
                conn.close()

    def test_build_report_can_disable_near_duplicate_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "ratio_disable_near_dup.db"
            conn = self._open_db(db_path)
            try:
                conn.execute("INSERT INTO persons(person_id, full_name) VALUES (1, 'BNG')")
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, excerpt, stance)
                    VALUES (?, 1, 'programas_partidos', 'https://bng/eu.pdf', ?, ?)
                    """,
                    [
                        (
                            1,
                            "aumento cotas hipotecarias familias tecido produtivo "
                            "entidades financeiras record lucros union europea non quixo despregar "
                            "medida efectiva combater carestia vida",
                            "unclear",
                        ),
                        (
                            2,
                            "entidades financeiras record lucros union europea non quixo despregar "
                            "medida efectiva combater carestia vida empobrecemento social "
                            "reformas gobernanza economica",
                            "unclear",
                        ),
                        (3, "proponemos mellorar o emprego", "support"),
                        (4, "impulsaremos vivenda asequible", "support"),
                    ],
                )
                conn.commit()
                report = build_report(
                    conn,
                    source_id="programas_partidos",
                    parties=["BNG"],
                    min_ratio=2.0,
                    near_duplicate_dedupe_enabled=False,
                )
                self.assertEqual(str(report["status"]), "degraded")
                row = list(report["rows"])[0]
                self.assertEqual(int(row["unclear_unique_exact_excerpt_rows"]), 2)
                self.assertEqual(int(row["unclear_unique_excerpt_rows"]), 2)
                self.assertAlmostEqual(float(row["support_to_unclear_unique_ratio"]), 1.0, places=6)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
