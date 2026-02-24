from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes
from scripts.report_declared_source_status import build_report


class TestDeclaredSourceStatusReport(unittest.TestCase):
    def test_build_report_programas_like_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "report-declared-source-status.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                ckey = canonical_key(full_name="Partido Demo", birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Partido Demo", ckey, now, now),
                )
                person_id = int(
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )
                conn.execute(
                    """
                    INSERT INTO person_identifiers (person_id, namespace, value, created_at)
                    VALUES (?, 'party_id', ?, ?)
                    """,
                    (person_id, "999", now),
                )

                conn.execute(
                    """
                    INSERT INTO topic_sets (name, description, institution_id, admin_level_id, territory_id, legislature, valid_from, valid_to, is_active, created_at, updated_at)
                    VALUES (?, NULL, NULL, NULL, NULL, 'XV', NULL, NULL, 1, ?, ?)
                    """,
                    ("Programas 2023", now, now),
                )
                topic_set_id = int(conn.execute("SELECT topic_set_id FROM topic_sets").fetchone()["topic_set_id"])
                conn.execute(
                    """
                    INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
                    VALUES (?, ?, NULL, NULL, ?, ?)
                    """,
                    ("vivienda", "Vivienda", now, now),
                )
                topic_id = int(conn.execute("SELECT topic_id FROM topics WHERE canonical_key = ?", ("vivienda",)).fetchone()["topic_id"])

                raw_payload = '{"party_id":999,"kind":"programa"}'
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "programas_partidos",
                        "programas_partidos:es_generales_2023:999:programa",
                        "2026-02-22",
                        raw_payload,
                        sha256_bytes(raw_payload.encode("utf-8")),
                        now,
                        now,
                    ),
                )
                source_record_pk = int(
                    conn.execute(
                        """
                        SELECT source_record_pk
                        FROM source_records
                        WHERE source_id = 'programas_partidos'
                        """,
                    ).fetchone()["source_record_pk"]
                )
                conn.execute(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk,
                      fetched_at, content_type, content_sha256, bytes, raw_path,
                      text_excerpt, text_chars, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "programas_partidos",
                        "https://example.invalid/programa.html",
                        source_record_pk,
                        now,
                        "text/html",
                        "sha-doc",
                        123,
                        "raw/programa.html",
                        "Texto programa",
                        13,
                        now,
                        now,
                    ),
                )

                conn.executemany(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      ?, ?,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:programa', '2026-02-22', ?, ?,
                      ?, 0, 0.5, 0.6,
                      'programa:concern:v1', 'programa_metadata',
                      NULL, NULL,
                      'programas_partidos', 'https://example.invalid/programa.html', ?, '2026-02-22',
                      '{}', ?, ?
                    )
                    """,
                    [
                        (topic_id, topic_set_id, person_id, "Prog Vivienda +", "Construiremos vivienda.", "support", source_record_pk, now, now),
                        (topic_id, topic_set_id, person_id, "Prog Vivienda -", "No apoyamos esta medida.", "oppose", source_record_pk, now, now),
                    ],
                )
                evidence_rows = conn.execute(
                    """
                    SELECT evidence_id, stance
                    FROM topic_evidence
                    WHERE source_id = 'programas_partidos'
                    ORDER BY evidence_id
                    """
                ).fetchall()
                ev_support = int(evidence_rows[0]["evidence_id"])
                ev_oppose = int(evidence_rows[1]["evidence_id"])

                conn.executemany(
                    """
                    INSERT INTO topic_evidence_reviews (
                      evidence_id, source_id, source_record_pk, review_reason, status,
                      suggested_stance, suggested_polarity, suggested_confidence,
                      extractor_version, note, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (ev_support, "programas_partidos", source_record_pk, "low_confidence", "pending", "support", 1, 0.61, "declared:regex_v2", "", now, now),
                        (ev_oppose, "programas_partidos", source_record_pk, "no_signal", "ignored", None, None, None, "declared:regex_v2", "manual", now, now),
                    ],
                )

                conn.execute(
                    """
                    INSERT INTO topic_positions (
                      topic_id, topic_set_id, person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      as_of_date, window_days, stance, score, confidence,
                      evidence_count, last_evidence_date, computed_method,
                      computed_version, computed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, NULL, NULL, NULL, NULL, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        topic_set_id,
                        person_id,
                        "2026-02-22",
                        "support",
                        0.75,
                        0.75,
                        2,
                        "2026-02-22",
                        "declared",
                        "declared:v1",
                        now,
                        now,
                        now,
                    ),
                )
                conn.commit()

                got = build_report(conn, source_id="programas_partidos")
                self.assertEqual(int(got["source_records"]), 1)
                self.assertEqual(int(got["text_documents"]), 1)
                self.assertEqual(int(got["topic_evidence_total"]), 2)
                self.assertEqual(int(got["topic_sets_touched"]), 1)
                self.assertEqual(int(got["review_total"]), 2)
                self.assertEqual(int(got["review_pending"]), 1)
                self.assertEqual(int(got["review_ignored"]), 1)
                self.assertEqual(int(got["declared_positions_total"]), 1)
                self.assertEqual(str(got["declared_positions_latest_as_of_date"]), "2026-02-22")
                self.assertEqual(int(got["party_proxy_count"]), 1)
                self.assertEqual(int(got["topic_evidence_by_stance"]["support"]), 1)
                self.assertEqual(int(got["topic_evidence_by_stance"]["oppose"]), 1)
                self.assertEqual(int(got["declared_positions_by_stance"]["support"]), 1)
                self.assertEqual(int(got["review_pending_by_reason"]["low_confidence"]), 1)
                self.assertEqual(got["source_snapshot_dates"], ["2026-02-22"])
            finally:
                conn.close()

    def test_build_report_unknown_source_returns_zeroes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "report-declared-source-status-empty.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                got = build_report(conn, source_id="source_does_not_exist")
                self.assertEqual(int(got["source_records"]), 0)
                self.assertEqual(int(got["text_documents"]), 0)
                self.assertEqual(int(got["topic_evidence_total"]), 0)
                self.assertEqual(int(got["review_total"]), 0)
                self.assertEqual(int(got["declared_positions_total"]), 0)
                self.assertEqual(got["topic_evidence_by_stance"], {})
                self.assertEqual(got["declared_positions_by_stance"], {})
                self.assertEqual(got["source_snapshot_dates"], [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
