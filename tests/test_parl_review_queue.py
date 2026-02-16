from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.review_queue import (
    apply_topic_evidence_review_decision,
    build_topic_evidence_review_report,
)
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes


class TestParlReviewQueue(unittest.TestCase):
    def test_review_decision_resolve_and_ignore(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "review-queue.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                ckey = canonical_key(full_name="Persona Demo", birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Persona Demo", ckey, now, now),
                )
                person_id = int(
                    conn.execute("SELECT person_id FROM persons WHERE canonical_key = ?", (ckey,)).fetchone()["person_id"]
                )

                conn.execute(
                    """
                    INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
                    VALUES ('demo_topic', 'Demo topic', NULL, NULL, ?, ?)
                    """,
                    (now, now),
                )
                topic_id = int(conn.execute("SELECT topic_id FROM topics WHERE canonical_key='demo_topic'").fetchone()["topic_id"])

                sr_payload = '{"kind":"intervention","id":"test"}'
                sr_sha = sha256_bytes(sr_payload.encode("utf-8"))
                for rid in ("test:1", "test:2"):
                    conn.execute(
                        """
                        INSERT INTO source_records (
                          source_id, source_record_id, source_snapshot_date,
                          raw_payload, content_sha256, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("congreso_intervenciones", rid, "2026-02-12", sr_payload, sr_sha, now, now),
                    )

                sr_pk_1 = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id=? AND source_record_id='test:1'",
                        ("congreso_intervenciones",),
                    ).fetchone()["source_record_pk"]
                )
                sr_pk_2 = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id=? AND source_record_id='test:2'",
                        ("congreso_intervenciones",),
                    ).fetchone()["source_record_pk"]
                )

                for idx, sr_pk in enumerate((sr_pk_1, sr_pk_2), start=1):
                    conn.execute(
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
                          ?, NULL,
                          ?, NULL,
                          NULL, NULL, NULL,
                          'declared:intervention', '2026-02-12', NULL, ?,
                          'unclear', 0, 0.5, 0.2,
                          NULL, 'intervention_metadata',
                          NULL, NULL,
                          'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                          '{}', ?, ?
                        )
                        """,
                        (topic_id, person_id, f"excerpt-{idx}", sr_pk, now, now),
                    )

                ev_ids = [
                    int(r["evidence_id"])
                    for r in conn.execute(
                        "SELECT evidence_id FROM topic_evidence ORDER BY evidence_id ASC"
                    ).fetchall()
                ]

                conn.execute(
                    """
                    INSERT INTO topic_evidence_reviews (
                      evidence_id, source_id, source_record_pk, review_reason, status,
                      suggested_stance, suggested_polarity, suggested_confidence, extractor_version, note,
                      created_at, updated_at
                    ) VALUES (?, 'congreso_intervenciones', ?, 'low_confidence', 'pending', 'support', 1, 0.58, 'declared:regex_v2', '', ?, ?)
                    """,
                    (ev_ids[0], sr_pk_1, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO topic_evidence_reviews (
                      evidence_id, source_id, source_record_pk, review_reason, status,
                      suggested_stance, suggested_polarity, suggested_confidence, extractor_version, note,
                      created_at, updated_at
                    ) VALUES (?, 'congreso_intervenciones', ?, 'no_signal', 'pending', NULL, NULL, NULL, 'declared:regex_v2', '', ?, ?)
                    """,
                    (ev_ids[1], sr_pk_2, now, now),
                )
                conn.commit()

                report_1 = build_topic_evidence_review_report(
                    conn,
                    source_id="congreso_intervenciones",
                    status="pending",
                    limit=20,
                    offset=0,
                )
                self.assertEqual(int(report_1["summary"]["pending"]), 2)
                self.assertEqual(int(report_1["page"]["returned"]), 2)

                dry = apply_topic_evidence_review_decision(
                    conn,
                    evidence_ids=(ev_ids[0],),
                    status="resolved",
                    final_stance="oppose",
                    final_confidence=0.91,
                    note="manual review",
                    source_id="congreso_intervenciones",
                    dry_run=True,
                )
                self.assertEqual(int(dry["review_rows_updated"]), 1)
                self.assertEqual(int(dry["evidence_rows_updated"]), 1)
                # Dry-run: evidence unchanged.
                ev_row_dry = conn.execute(
                    "SELECT stance, stance_method FROM topic_evidence WHERE evidence_id = ?",
                    (ev_ids[0],),
                ).fetchone()
                self.assertEqual(str(ev_row_dry["stance"]), "unclear")
                self.assertEqual(str(ev_row_dry["stance_method"]), "intervention_metadata")

                applied = apply_topic_evidence_review_decision(
                    conn,
                    evidence_ids=(ev_ids[0],),
                    status="resolved",
                    final_stance="oppose",
                    final_confidence=0.91,
                    note="manual review",
                    source_id="congreso_intervenciones",
                    dry_run=False,
                )
                self.assertEqual(int(applied["review_rows_updated"]), 1)
                self.assertEqual(int(applied["evidence_rows_updated"]), 1)

                ev_row = conn.execute(
                    "SELECT stance, polarity, confidence, stance_method FROM topic_evidence WHERE evidence_id = ?",
                    (ev_ids[0],),
                ).fetchone()
                self.assertEqual(str(ev_row["stance"]), "oppose")
                self.assertEqual(int(ev_row["polarity"]), -1)
                self.assertEqual(str(ev_row["stance_method"]), "declared:manual_review_v1")
                self.assertGreater(float(ev_row["confidence"]), 0.9 - 1e-9)

                rv_row = conn.execute(
                    "SELECT status, suggested_stance, suggested_polarity FROM topic_evidence_reviews WHERE evidence_id = ?",
                    (ev_ids[0],),
                ).fetchone()
                self.assertEqual(str(rv_row["status"]), "resolved")
                self.assertEqual(str(rv_row["suggested_stance"]), "oppose")
                self.assertEqual(int(rv_row["suggested_polarity"]), -1)

                ignored = apply_topic_evidence_review_decision(
                    conn,
                    evidence_ids=(ev_ids[1],),
                    status="ignored",
                    note="sin señal",
                    source_id="congreso_intervenciones",
                    dry_run=False,
                )
                self.assertEqual(int(ignored["review_rows_updated"]), 1)
                self.assertEqual(int(ignored["evidence_rows_updated"]), 0)

                rv2 = conn.execute(
                    "SELECT status FROM topic_evidence_reviews WHERE evidence_id = ?",
                    (ev_ids[1],),
                ).fetchone()
                self.assertEqual(str(rv2["status"]), "ignored")

                report_2 = build_topic_evidence_review_report(
                    conn,
                    source_id="congreso_intervenciones",
                    status="all",
                    limit=20,
                    offset=0,
                )
                self.assertEqual(int(report_2["summary"]["pending"]), 0)
                self.assertEqual(int(report_2["summary"]["resolved"]), 1)
                self.assertEqual(int(report_2["summary"]["ignored"]), 1)

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

