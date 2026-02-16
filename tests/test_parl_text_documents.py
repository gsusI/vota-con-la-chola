from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.text_documents import backfill_text_documents_from_topic_evidence
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes


class TestParlTextDocuments(unittest.TestCase):
    def test_backfill_text_documents_from_topic_evidence_reads_file_url_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "text-docs.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            html_path = td_path / "texto_integro.html"
            html_path.write_text(
                (
                    "<html><body>"
                    "<div class='textoIntegro'>"
                    "<p style='text-align:center'><a name='(Página22)'><b>Página 22</b></a></p>"
                    "<p class='textoCompleto'>Hola <b>mundo</b>. Intervención X.</p>"
                    "<p style='text-align:center'><a name='(Página23)'><b>Página 23</b></a></p>"
                    "<p class='textoCompleto'>Otra página.</p>"
                    "</div>"
                    "</body></html>"
                ),
                encoding="utf-8",
            )

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
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )

                sr_payload = '{"kind":"intervention","id":"test"}'
                sr_sha = sha256_bytes(sr_payload.encode("utf-8"))
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "test:1", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "test:1"),
                    ).fetchone()["source_record_pk"]
                )

                # Minimal evidence row: we only need source_url + source_record_pk.
                file_url = f"file://{html_path}#(Página22)"
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
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, NULL,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', ?, ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, file_url, sr_pk, now, now),
                )
                conn.commit()

                result1 = backfill_text_documents_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    raw_dir=raw_dir,
                    timeout=5,
                    limit=50,
                    only_missing=True,
                    strict_network=True,
                    dry_run=False,
                )
                self.assertEqual(result1["failures"], [])
                self.assertGreaterEqual(int(result1.get("upserted", 0)), 1)
                excerpt = conn.execute(
                    "SELECT text_excerpt FROM text_documents WHERE source_record_pk = ?",
                    (sr_pk,),
                ).fetchone()["text_excerpt"]
                self.assertIn("Intervención X", excerpt)
                # Ensure we extracted only the requested page, not the next one.
                self.assertNotIn("Otra página", excerpt)

                ev_excerpt = conn.execute(
                    "SELECT excerpt FROM topic_evidence WHERE source_record_pk = ?",
                    (sr_pk,),
                ).fetchone()["excerpt"]
                self.assertIn("Intervención X", ev_excerpt)

                # Re-run: should be idempotent (no extra rows).
                result2 = backfill_text_documents_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    raw_dir=raw_dir,
                    timeout=5,
                    limit=50,
                    only_missing=True,
                    strict_network=True,
                    dry_run=False,
                )
                self.assertEqual(result2["failures"], [])
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) AS c FROM text_documents").fetchone()["c"]),
                    1,
                )

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
