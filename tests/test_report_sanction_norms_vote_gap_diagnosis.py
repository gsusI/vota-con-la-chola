from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.report_sanction_norms_vote_gap_diagnosis import build_report


def _seed_minimal_lisos_responsibilities(conn, *, ts: str) -> tuple[int, int]:
    for sid, name in [
        ("senado_iniciativas", "Senado iniciativas"),
        ("senado_votaciones", "Senado votaciones"),
    ]:
        conn.execute(
            """
            INSERT INTO sources (
              source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO NOTHING
            """,
            (sid, name, "nacional", "https://example.org", "json", 1, ts, ts),
        )

    conn.execute(
        """
        INSERT INTO legal_norms (
          norm_id, boe_id, title, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "es:boe-a-2000-15060",
            "BOE-A-2000-15060",
            "Texto refundido de la Ley sobre infracciones y sanciones en el orden social",
            "{}",
            ts,
            ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO legal_norm_fragments (
          fragment_id, norm_id, fragment_type, fragment_label, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "es:boe-a-2000-15060:fragment:articulo:bloque-principal",
            "es:boe-a-2000-15060",
            "articulo",
            "Bloque principal",
            "{}",
            ts,
            ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO sanction_norm_catalog (
          norm_id, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?)
        """,
        ("es:boe-a-2000-15060", "{}", ts, ts),
    )
    conn.execute(
        """
        INSERT INTO sanction_norm_fragment_links (
          norm_id, fragment_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?)
        """,
        (
            "es:boe-a-2000-15060",
            "es:boe-a-2000-15060:fragment:articulo:bloque-principal",
            ts,
            ts,
        ),
    )

    conn.execute(
        """
        INSERT INTO legal_fragment_responsibilities (
          fragment_id, role, actor_label, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "es:boe-a-2000-15060:fragment:articulo:bloque-principal",
            "approve",
            "Cortes Generales",
            "{}",
            ts,
            ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO legal_fragment_responsibilities (
          fragment_id, role, actor_label, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "es:boe-a-2000-15060:fragment:articulo:bloque-principal",
            "enforce",
            "Inspección de Trabajo y Seguridad Social",
            "{}",
            ts,
            ts,
        ),
    )
    approve_id = conn.execute(
        """
        SELECT responsibility_id
        FROM legal_fragment_responsibilities
        WHERE fragment_id = ? AND role = 'approve'
        """,
        ("es:boe-a-2000-15060:fragment:articulo:bloque-principal",),
    ).fetchone()
    enforce_id = conn.execute(
        """
        SELECT responsibility_id
        FROM legal_fragment_responsibilities
        WHERE fragment_id = ? AND role = 'enforce'
        """,
        ("es:boe-a-2000-15060:fragment:articulo:bloque-principal",),
    ).fetchone()
    assert approve_id is not None
    assert enforce_id is not None

    for rid in [int(approve_id["responsibility_id"]), int(enforce_id["responsibility_id"])]:
        payload = {
            "record_kind": "sanction_norm_parliamentary_evidence_backfill",
            "initiative_id": "senado:leg5:exp:621/000026",
            "boe_id": "BOE-A-2000-15060",
        }
        conn.execute(
            """
            INSERT INTO legal_fragment_responsibility_evidence (
              responsibility_id, evidence_type, source_id, source_url, evidence_date,
              evidence_quote, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                "senado_diario",
                "senado_iniciativas",
                "http://www.senado.es/legis5/expedientes/621/xml/INI-3-621000026.xml",
                "2000-08-08",
                "Ley sobre infracciones y sanciones en el orden social.",
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ts,
                ts,
            ),
        )
    conn.commit()
    return int(approve_id["responsibility_id"]), int(enforce_id["responsibility_id"])


class TestReportSanctionNormsVoteGapDiagnosis(unittest.TestCase):
    def test_diagnosis_marks_no_vote_event_link_for_parliamentary_initiatives(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "vote_gap_diag_no_vote_link.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                _seed_minimal_lisos_responsibilities(conn, ts="2026-02-24T00:00:00+00:00")
                got = build_report(conn, roles=["approve", "enforce"])
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertEqual(int(got["totals"]["responsibilities_missing_vote_total"]), 2)
        self.assertEqual(int(got["totals"]["missing_with_vote_title_candidates_total"]), 0)
        self.assertEqual(
            int(got["totals"]["missing_with_parliamentary_initiatives_with_vote_link_total"]), 0
        )
        self.assertEqual(int(got["totals"]["unreachable_missing_total"]), 2)
        reasons = {str(r["diagnosis_reason"]) for r in got["missing_vote_responsibilities"]}
        self.assertEqual(reasons, {"no_vote_event_link_for_parliamentary_initiatives"})

    def test_diagnosis_marks_candidate_present_when_vote_title_matches_rule(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "vote_gap_diag_candidate_present.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                _seed_minimal_lisos_responsibilities(conn, ts="2026-02-24T00:00:00+00:00")

                ts = "2026-02-24T00:00:00+00:00"
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, vote_date, title, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "vote:senado:test:0001",
                        "2026-02-24",
                        "Proyecto ligado al Real Decreto Legislativo 5/2000 sobre infracciones en el orden social.",
                        "senado_votaciones",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, source_id, title, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:leg15:exp:621/999999",
                        "senado_iniciativas",
                        "Proyecto en materia de infracciones y sanciones en el orden social",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_initiatives (
                      vote_event_id, initiative_id, link_method, confidence, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "vote:senado:test:0001",
                        "senado:leg15:exp:621/999999",
                        "manual",
                        1.0,
                        ts,
                        ts,
                    ),
                )
                conn.commit()
                got = build_report(conn, roles=["approve", "enforce"])
            finally:
                conn.close()

        self.assertEqual(int(got["totals"]["responsibilities_missing_vote_total"]), 2)
        self.assertEqual(int(got["totals"]["missing_with_vote_title_candidates_total"]), 2)
        reasons = {str(r["diagnosis_reason"]) for r in got["missing_vote_responsibilities"]}
        self.assertEqual(reasons, {"candidate_present_needs_rule_or_bridge"})


if __name__ == "__main__":
    unittest.main()
