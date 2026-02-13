from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.linking import link_congreso_votes_to_initiatives
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors
from etl.politicos_es.util import now_utc_iso


class TestParlLinkingCongreso(unittest.TestCase):
    def test_linking_by_expediente_regex(self) -> None:
        connectors = get_connectors()
        ini_connector = connectors["congreso_iniciativas"]
        snapshot_date = "2026-02-12"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                sample_path = Path(PARL_SOURCE_CONFIG["congreso_iniciativas"]["fallback_file"])
                ingest_parl_source(
                    conn=conn,
                    connector=ini_connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )

                exp = "121/000001/0000"
                init = conn.execute(
                    """
                    SELECT initiative_id
                    FROM parl_initiatives
                    WHERE legislature = '15' AND expediente = ?
                    """,
                    (exp,),
                ).fetchone()
                self.assertIsNotNone(init)
                initiative_id = str(init["initiative_id"])

                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, session_number, vote_number, vote_date,
                      title, expediente_text, subgroup_title, subgroup_text,
                      assentimiento,
                      totals_present, totals_yes, totals_no, totals_abstain, totals_no_vote,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "test:vote:1",
                        "15",
                        1,
                        1,
                        "2026-02-12",
                        "Test vote",
                        f"Expediente {exp} (synthetic)",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "congreso_votaciones",
                        "file://test",
                        None,
                        snapshot_date,
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()

                res1 = link_congreso_votes_to_initiatives(conn, dry_run=False)
                self.assertGreaterEqual(int(res1["links_written"]), 1)

                link = conn.execute(
                    """
                    SELECT vote_event_id, initiative_id, link_method
                    FROM parl_vote_event_initiatives
                    WHERE vote_event_id = 'test:vote:1'
                    """
                ).fetchone()
                self.assertIsNotNone(link)
                self.assertEqual(str(link["initiative_id"]), initiative_id)
                self.assertEqual(str(link["link_method"]), "expediente_regex")

                # Idempotent: running again should not increase row count.
                before = int(conn.execute("SELECT COUNT(*) AS c FROM parl_vote_event_initiatives").fetchone()["c"])
                link_congreso_votes_to_initiatives(conn, dry_run=False)
                after = int(conn.execute("SELECT COUNT(*) AS c FROM parl_vote_event_initiatives").fetchone()["c"])
                self.assertEqual(before, after)
            finally:
                conn.close()

    def test_linking_by_title_normalized_exact_unique(self) -> None:
        snapshot_date = "2026-02-12"
        title = "Proposición de Ley de Prueba Única para Trazabilidad Parlamentaria Avanzada"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente, title,
                      source_id, source_url, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:exp:121/123456/0000",
                        "15",
                        "121/123456/0000",
                        title,
                        "congreso_iniciativas",
                        "file://test",
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, session_number, vote_number, vote_date,
                      title, expediente_text, subgroup_title, subgroup_text,
                      assentimiento,
                      totals_present, totals_yes, totals_no, totals_abstain, totals_no_vote,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "test:title-exact:1",
                        "15",
                        1,
                        1,
                        "2026-02-12",
                        "Test vote",
                        "proposicion de ley de prueba unica para trazabilidad parlamentaria avanzada",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "congreso_votaciones",
                        "file://test",
                        None,
                        snapshot_date,
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()

                res = link_congreso_votes_to_initiatives(conn, dry_run=False)
                self.assertGreaterEqual(int(res["links_written"]), 1)

                link = conn.execute(
                    """
                    SELECT initiative_id, link_method
                    FROM parl_vote_event_initiatives
                    WHERE vote_event_id = 'test:title-exact:1'
                    """
                ).fetchone()
                self.assertIsNotNone(link)
                self.assertEqual(str(link["initiative_id"]), "congreso:leg15:exp:121/123456/0000")
                self.assertEqual(str(link["link_method"]), "title_norm_exact_unique")
            finally:
                conn.close()

    def test_linking_by_title_group_prefix_cleaning(self) -> None:
        snapshot_date = "2026-02-12"
        title = (
            "Proposición de Ley para la reducción de la duración máxima de la jornada ordinaria de trabajo a 35 horas semanales."
        )

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente, title,
                      source_id, source_url, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:exp:122/000241/0000",
                        "15",
                        "122/000241/0000",
                        title,
                        "congreso_iniciativas",
                        "file://test",
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, session_number, vote_number, vote_date,
                      title, expediente_text, subgroup_title, subgroup_text,
                      assentimiento,
                      totals_present, totals_yes, totals_no, totals_abstain, totals_no_vote,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "test:title-group-cleaning:1",
                        "15",
                        1,
                        1,
                        "2026-02-12",
                        "Toma en consideración de Proposiciones de Ley.",
                        (
                            "Proposición de Ley del Grupo Parlamentario Popular en el Congreso, "
                            "para la reducción de la duración máxima de la jornada ordinaria de trabajo a 35 horas semanales."
                        ),
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "congreso_votaciones",
                        "file://test",
                        None,
                        snapshot_date,
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()

                res = link_congreso_votes_to_initiatives(conn, dry_run=False)
                self.assertGreaterEqual(int(res["links_written"]), 1)

                link = conn.execute(
                    """
                    SELECT initiative_id, link_method
                    FROM parl_vote_event_initiatives
                    WHERE vote_event_id = 'test:title-group-cleaning:1'
                    """
                ).fetchone()
                self.assertIsNotNone(link)
                self.assertEqual(str(link["initiative_id"]), "congreso:leg15:exp:122/000241/0000")
                self.assertEqual(str(link["link_method"]), "title_norm_exact_unique")
            finally:
                conn.close()

    def test_linking_by_title_prefix_unique(self) -> None:
        snapshot_date = "2026-02-12"
        full_title = (
            "Proposición de Ley de Prueba Única para Trazabilidad Parlamentaria Avanzada "
            "con control reforzado de evidencia pública"
        )

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente, title,
                      source_id, source_url, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:exp:121/654321/0000",
                        "15",
                        "121/654321/0000",
                        full_title,
                        "congreso_iniciativas",
                        "file://test",
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, session_number, vote_number, vote_date,
                      title, expediente_text, subgroup_title, subgroup_text,
                      assentimiento,
                      totals_present, totals_yes, totals_no, totals_abstain, totals_no_vote,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "test:title-prefix:1",
                        "15",
                        1,
                        1,
                        "2026-02-12",
                        "Test vote",
                        "Proposición de Ley de Prueba Única para Trazabilidad Parlamentaria Avanzada...",
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "congreso_votaciones",
                        "file://test",
                        None,
                        snapshot_date,
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()

                res = link_congreso_votes_to_initiatives(conn, dry_run=False)
                self.assertGreaterEqual(int(res["links_written"]), 1)

                link = conn.execute(
                    """
                    SELECT initiative_id, link_method
                    FROM parl_vote_event_initiatives
                    WHERE vote_event_id = 'test:title-prefix:1'
                    """
                ).fetchone()
                self.assertIsNotNone(link)
                self.assertEqual(str(link["initiative_id"]), "congreso:leg15:exp:121/654321/0000")
                self.assertEqual(str(link["link_method"]), "title_norm_prefix_unique")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
