from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.report_programas_empleo_fiscal_snippets_audit import build_report, main


class TestReportProgramasEmpleoFiscalSnippetsAudit(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE persons (
              person_id INTEGER PRIMARY KEY,
              full_name TEXT
            );
            CREATE TABLE topics (
              topic_id INTEGER PRIMARY KEY,
              canonical_key TEXT
            );
            CREATE TABLE topic_evidence (
              evidence_id INTEGER PRIMARY KEY,
              person_id INTEGER,
              topic_id INTEGER,
              source_id TEXT,
              source_url TEXT,
              excerpt TEXT,
              stance TEXT,
              stance_method TEXT
            );
            """
        )
        return conn

    def test_build_report_ok_for_bng_with_employment_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "audit_ok.db"
            conn = self._open_db(db_path)
            try:
                conn.execute("INSERT INTO persons(person_id, full_name) VALUES (1, 'BNG')")
                conn.execute("INSERT INTO topics(topic_id, canonical_key) VALUES (1, 'concern:v1:empleo')")
                conn.execute(
                    """
                    INSERT INTO topic_evidence(
                      evidence_id, person_id, topic_id, source_id, source_url, excerpt, stance, stance_method
                    ) VALUES (100, 1, 1, 'programas_partidos', 'https://bng/pg.pdf', ?, 'support', 'declared:regex_v3')
                    """,
                    ("Minorando a tributacion polos ingresos do traballo e o imposto de sociedades",),
                )
                conn.commit()

                report = build_report(
                    conn,
                    source_id="programas_partidos",
                    topic_key="concern:v1:empleo",
                    parties=["BNG"],
                    fiscal_terms=["imposto de sociedades", "tribut"],
                    employment_anchor_terms=["traballo", "emple"],
                    max_suspicious_support_rows=0,
                )
                self.assertEqual(str(report["status"]), "ok")
                self.assertEqual(int(report["rows_total"]), 1)
                self.assertEqual(int(report["suspicious_support_rows"]), 0)
            finally:
                conn.close()

    def test_build_report_flags_suspicious_support_without_employment_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "audit_degraded.db"
            conn = self._open_db(db_path)
            try:
                conn.execute("INSERT INTO persons(person_id, full_name) VALUES (1, 'Compromis')")
                conn.execute("INSERT INTO topics(topic_id, canonical_key) VALUES (1, 'concern:v1:empleo')")
                conn.execute(
                    """
                    INSERT INTO topic_evidence(
                      evidence_id, person_id, topic_id, source_id, source_url, excerpt, stance, stance_method
                    ) VALUES (200, 1, 1, 'programas_partidos', 'https://compromis/50.pdf', ?, 'support', 'declared:regex_v3')
                    """,
                    ("Incloent la fiscalitat verda per a impulsar una transicio ecologica",),
                )
                conn.commit()

                report = build_report(
                    conn,
                    source_id="programas_partidos",
                    topic_key="concern:v1:empleo",
                    parties=["Compromis"],
                    fiscal_terms=["fiscalitat", "impost"],
                    employment_anchor_terms=["emple", "trabaj", "traballo"],
                    max_suspicious_support_rows=0,
                )
                self.assertEqual(str(report["status"]), "degraded")
                self.assertEqual(int(report["rows_total"]), 1)
                self.assertEqual(int(report["suspicious_support_rows"]), 1)
                self.assertIn("suspicious_support_rows_above_threshold", list(report["strict_fail_reasons"]))
            finally:
                conn.close()

    def test_main_strict_returns_4_on_suspicious_support(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "audit_strict.db"
            out_json = td_path / "audit.json"
            out_csv = td_path / "audit.csv"

            conn = self._open_db(db_path)
            try:
                conn.execute("INSERT INTO persons(person_id, full_name) VALUES (1, 'Compromis')")
                conn.execute("INSERT INTO topics(topic_id, canonical_key) VALUES (1, 'concern:v1:empleo')")
                conn.execute(
                    """
                    INSERT INTO topic_evidence(
                      evidence_id, person_id, topic_id, source_id, source_url, excerpt, stance, stance_method
                    ) VALUES (300, 1, 1, 'programas_partidos', 'https://compromis/50.pdf', ?, 'support', 'declared:regex_v3')
                    """,
                    ("Fiscalitat verda per a la transicio ecologica",),
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
                    "--topic-key",
                    "concern:v1:empleo",
                    "--parties",
                    "Compromis",
                    "--fiscal-terms",
                    "fiscalitat",
                    "--employment-anchor-terms",
                    "emple,trabaj",
                    "--max-suspicious-support-rows",
                    "0",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(payload["status"]), "degraded")
            self.assertEqual(int(payload["suspicious_support_rows"]), 1)
            self.assertTrue(out_csv.exists())


if __name__ == "__main__":
    unittest.main()
