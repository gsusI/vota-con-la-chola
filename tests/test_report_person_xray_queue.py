from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.politicos_es.db import apply_schema, open_db
from scripts.report_person_xray_queue import build_report


class TestReportPersonXrayQueue(unittest.TestCase):
    def _insert_source(self, conn: object, source_id: str, scope: str, url: str) -> None:
        conn.execute(
            """
            INSERT INTO sources (
              source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'json', 1, ?, ?)
            """,
            (source_id, source_id, scope, url, "2026-02-24T00:00:00+00:00", "2026-02-24T00:00:00+00:00"),
        )

    def _seed_person_with_gaps(self, conn: object, *, include_party_proxy: bool = False) -> int:
        self._insert_source(conn, "congreso_diputados", "nacional", "https://www.congreso.es/")
        self._insert_source(conn, "congreso_votaciones", "nacional", "https://www.congreso.es/webpublica/opendata/votaciones/")
        self._insert_source(conn, "congreso_intervenciones", "nacional", "https://www.congreso.es/")

        conn.execute(
            """
            INSERT INTO institutions (
              name, level, territory_code, created_at, updated_at
            ) VALUES ('Congreso de los Diputados', 'nacional', 'es', ?, ?)
            """,
            ("2026-02-24T00:00:00+00:00", "2026-02-24T00:00:00+00:00"),
        )
        institution_id = int(
            conn.execute("SELECT institution_id FROM institutions ORDER BY institution_id DESC LIMIT 1").fetchone()["institution_id"]
        )

        canonical_key = "party:1" if include_party_proxy else "maria test|madrid"
        conn.execute(
            """
            INSERT INTO persons (
              full_name, given_name, family_name, gender, birth_date, territory_code, canonical_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Maria Test",
                "Maria",
                "Test",
                "",
                None,
                "madrid",
                canonical_key,
                "2026-02-24T00:00:00+00:00",
                "2026-02-24T00:00:00+00:00",
            ),
        )
        person_id = int(conn.execute("SELECT person_id FROM persons ORDER BY person_id DESC LIMIT 1").fetchone()["person_id"])

        conn.execute(
            """
            INSERT INTO mandates (
              person_id, institution_id, role_title, level, territory_code, start_date, end_date, is_active,
              source_id, source_record_id, source_snapshot_date, first_seen_at, last_seen_at, raw_payload
            ) VALUES (?, ?, 'Diputada', 'nacional', 'madrid', '2025-01-01', NULL, 1, 'congreso_diputados', ?, '2026-02-24', ?, ?, '{}')
            """,
            (
                person_id,
                institution_id,
                f"congreso:persona:{person_id}",
                "2026-02-24T00:00:00+00:00",
                "2026-02-24T00:00:00+00:00",
            ),
        )

        conn.execute(
            """
            INSERT INTO parl_vote_events (
              vote_event_id, vote_date, title, source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, '2026-02-24', 'Votacion de prueba', 'congreso_votaciones', 'https://www.congreso.es/voto/1', '{}', ?, ?)
            """,
            ("vote:test:1", "2026-02-24T00:00:00+00:00", "2026-02-24T00:00:00+00:00"),
        )
        conn.execute(
            """
            INSERT INTO parl_vote_events (
              vote_event_id, vote_date, title, source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, '2026-02-25', 'Votacion de prueba 2', 'congreso_votaciones', 'https://www.congreso.es/voto/2', '{}', ?, ?)
            """,
            ("vote:test:2", "2026-02-24T00:00:00+00:00", "2026-02-24T00:00:00+00:00"),
        )
        conn.execute(
            """
            INSERT INTO parl_vote_member_votes (
              vote_event_id, seat, member_name, member_name_normalized, person_id, group_code, vote_choice,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'GP', 'Si', 'congreso_votaciones', 'https://www.congreso.es/voto/1', '{}', ?, ?)
            """,
            ("vote:test:1", "A-1", "MARIA TEST", "maria test", person_id, "2026-02-24T00:00:00+00:00", "2026-02-24T00:00:00+00:00"),
        )
        conn.execute(
            """
            INSERT INTO parl_vote_member_votes (
              vote_event_id, seat, member_name, member_name_normalized, person_id, group_code, vote_choice,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'GP', 'No', 'congreso_votaciones', 'https://www.congreso.es/voto/2', '{}', ?, ?)
            """,
            ("vote:test:2", "A-2", "MARÍA TEST", "maría test", person_id, "2026-02-24T00:00:00+00:00", "2026-02-24T00:00:00+00:00"),
        )
        conn.commit()
        return person_id

    def test_detects_and_resolves_person_gap_queue(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "person_xray_queue.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                person_id = self._seed_person_with_gaps(conn)

                first = build_report(conn, person_id=person_id, enqueue=True, queue_limit=50)
                first_gap_codes = {str(row["gap_code"]) for row in (first.get("xray") or {}).get("detected_gaps", [])}
                self.assertIn("missing_birth_date_public_profile", first_gap_codes)
                self.assertIn("missing_gender_public_profile", first_gap_codes)
                self.assertIn("missing_declared_evidence", first_gap_codes)
                self.assertIn("missing_name_aliases_for_vote_variants", first_gap_codes)
                self.assertGreaterEqual(int(first["queue_totals"]["queue_pending_total"]), 4)

                conn.execute(
                    """
                    UPDATE persons
                    SET birth_date = '1980-01-01', gender = 'Femenino', updated_at = '2026-02-24T01:00:00+00:00'
                    WHERE person_id = ?
                    """,
                    (person_id,),
                )
                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      person_id, evidence_type, source_id, source_url, raw_payload, created_at, updated_at
                    ) VALUES (?, 'declared:intervention', 'congreso_intervenciones', 'https://www.congreso.es/intervencion/1', '{}', ?, ?)
                    """,
                    (person_id, "2026-02-24T01:00:00+00:00", "2026-02-24T01:00:00+00:00"),
                )
                conn.execute(
                    """
                    INSERT INTO person_name_aliases (
                      person_id, alias, canonical_alias, source_id, source_kind, source_url, confidence, note, created_at, updated_at
                    ) VALUES (?, 'MARÍA TEST', 'maría test', 'congreso_votaciones', 'official_vote_rollcall', 'https://www.congreso.es/voto/2', 0.9, 'seeded in test', ?, ?)
                    """,
                    (person_id, "2026-02-24T01:00:00+00:00", "2026-02-24T01:00:00+00:00"),
                )
                conn.commit()

                second = build_report(conn, person_id=person_id, enqueue=True, queue_limit=50)
                self.assertEqual(int(second["queue_totals"]["queue_pending_total"]), 0)
                self.assertEqual(int(second["queue_totals"]["queue_in_progress_total"]), 0)
                self.assertGreaterEqual(int(second["queue_totals"]["queue_resolved_total"]), 4)
                self.assertEqual(len((second.get("xray") or {}).get("detected_gaps", [])), 0)
            finally:
                conn.close()

    def test_party_proxy_excluded_by_default(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "person_xray_party_proxy.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                person_id = self._seed_person_with_gaps(conn, include_party_proxy=True)

                excluded = build_report(conn, person_id=person_id, enqueue=False, include_party_proxies=False, queue_limit=20)
                included = build_report(conn, person_id=person_id, enqueue=False, include_party_proxies=True, queue_limit=20)
            finally:
                conn.close()

        self.assertEqual(len((excluded.get("xray") or {}).get("detected_gaps", [])), 0)
        self.assertGreater(len((included.get("xray") or {}).get("detected_gaps", [])), 0)


if __name__ == "__main__":
    unittest.main()
