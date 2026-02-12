from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors


class TestSenadoVotacionesSamplesE2E(unittest.TestCase):
    def test_senado_votaciones_sample_is_idempotent(self) -> None:
        connectors = get_connectors()
        connector = connectors["senado_votaciones"]
        snapshot_date = "2026-02-12"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                sample_path = Path(PARL_SOURCE_CONFIG["senado_votaciones"]["fallback_file"])
                self.assertTrue(sample_path.exists(), f"Missing sample: {sample_path}")

                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )

                ev1 = int(conn.execute("SELECT COUNT(*) AS c FROM parl_vote_events").fetchone()["c"])
                mv1 = int(
                    conn.execute("SELECT COUNT(*) AS c FROM parl_vote_member_votes").fetchone()["c"]
                )
                self.assertEqual(ev1, 1)
                self.assertEqual(mv1, 0)

                title = conn.execute("SELECT title FROM parl_vote_events LIMIT 1").fetchone()["title"]
                self.assertIsNotNone(title)
                self.assertIn("Votación", str(title))

                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )

                ev2 = int(conn.execute("SELECT COUNT(*) AS c FROM parl_vote_events").fetchone()["c"])
                mv2 = int(
                    conn.execute("SELECT COUNT(*) AS c FROM parl_vote_member_votes").fetchone()["c"]
                )
                self.assertEqual(ev1, ev2)
                self.assertEqual(mv1, mv2)
            finally:
                conn.close()

    def test_senado_votaciones_with_manual_session_detail(self) -> None:
        connectors = get_connectors()
        connector = connectors["senado_votaciones"]
        snapshot_date = "2026-02-12"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            raw_dir = Path(td) / "raw"
            detail_dir = Path(td) / "senado_details"
            detail_dir.mkdir(parents=True, exist_ok=True)

            # Synthetic detail file for session 10 matching sample vote:
            # expediente 600/000001 + title "Votación final sobre el conjunto".
            (detail_dir / "ses_10.xml").write_text(
                """<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<main>
  <sesion>
    <num_sesion>10</num_sesion>
    <fecha_sesion>25/01/2024</fecha_sesion>
    <diario_sesiones>13</diario_sesiones>
  </sesion>
  <votacion>
    <num_vot>52</num_vot>
    <CodVotacion>1052</CodVotacion>
    <num_exp>600/000001</num_exp>
    <tit_vot>Votación final sobre el conjunto</tit_vot>
    <tit_sec>Votación final sobre el conjunto</tit_sec>
    <fecha_v>25-ENE-2024</fecha_v>
    <hora_vot>12:00</hora_vot>
    <tot_presentes>3</tot_presentes>
    <tot_afirmativos>2</tot_afirmativos>
    <tot_negativos>1</tot_negativos>
    <tot_abstenciones>0</tot_abstenciones>
    <tot_novotan>0</tot_novotan>
    <tot_nulos>0</tot_nulos>
    <tot_ausentes>1</tot_ausentes>
    <resultado>
      <VotoSenador>
        <escano>10</escano>
        <grupo>GRUPO A</grupo>
        <nombre>SENADOR UNO</nombre>
        <voto>SI</voto>
      </VotoSenador>
      <VotoSenador>
        <escano>11</escano>
        <grupo>GRUPO B</grupo>
        <nombre>SENADOR DOS</nombre>
        <voto>NO</voto>
      </VotoSenador>
      <VotoSenador>
        <escano>12</escano>
        <grupo>GRUPO C</grupo>
        <nombre>SENADOR TRES</nombre>
        <voto>SI</voto>
      </VotoSenador>
    </resultado>
    <ausentes>
      <ausencia>
        <escano>13</escano>
        <grupo>GRUPO D</grupo>
        <nombre>SENADOR CUATRO</nombre>
      </ausencia>
    </ausentes>
  </votacion>
</main>
""",
                encoding="utf-8",
            )

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                sample_path = Path(PARL_SOURCE_CONFIG["senado_votaciones"]["fallback_file"])
                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={"senado_detail_dir": str(detail_dir)},
                )

                event = conn.execute(
                    """
                    SELECT totals_present, totals_yes, totals_no, totals_abstain, totals_no_vote, vote_date
                    FROM parl_vote_events
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(event)
                self.assertEqual(int(event["totals_present"]), 3)
                self.assertEqual(int(event["totals_yes"]), 2)
                self.assertEqual(int(event["totals_no"]), 1)
                self.assertEqual(int(event["totals_abstain"]), 0)
                self.assertEqual(int(event["totals_no_vote"]), 0)
                self.assertEqual(str(event["vote_date"]), "2024-01-25")

                mv = int(conn.execute("SELECT COUNT(*) AS c FROM parl_vote_member_votes").fetchone()["c"])
                self.assertEqual(mv, 4)

                absent = conn.execute(
                    "SELECT COUNT(*) AS c FROM parl_vote_member_votes WHERE vote_choice = 'AUSENTE'"
                ).fetchone()
                self.assertEqual(int(absent["c"]), 1)
            finally:
                conn.close()

    def test_parse_helpers_handle_empty_and_html_payloads(self) -> None:
        import etl.parlamentario_es.connectors.senado_votaciones as conn_mod

        tipo9 = conn_mod._tipo12_urls_from_tipo9_xml(b"")
        self.assertEqual(tipo9, [])

        ses = conn_mod._parse_sesion_vote_xml(b"")
        self.assertEqual(ses["votes"], [])
        self.assertIsNone(ses["session_date"])

        with self.assertRaises(RuntimeError) as ctx:
            conn_mod._parse_sesion_vote_xml(b"<!doctype html><html><body>blocked</body></html>")
        self.assertIn("HTML", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx2:
            conn_mod._records_from_tipo12_xml(
                b"<!doctype html><html><body>blocked</body></html>",
                "https://www.senado.es/fake",
            )
        self.assertIn("HTML", str(ctx2.exception))


if __name__ == "__main__":
    unittest.main()
