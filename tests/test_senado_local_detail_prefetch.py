from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources
from etl.parlamentario_es.pipeline import backfill_senado_vote_details
from publicdata_connectors_es.parliamentary.senado_votaciones import (
    _find_local_session_xml,
    _load_session_vote_info as reusable_load_session_vote_info,
)


class TestSenadoLocalDetailPrefetch(unittest.TestCase):
    def test_local_cache_lookup_never_crosses_legislatures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            detail_dir = Path(temp_dir)
            (detail_dir / "legis14").mkdir()
            (detail_dir / "legis15").mkdir()
            wrong = detail_dir / "legis14" / "ses_9.xml"
            wrong.write_text("<main/>", encoding="utf-8")
            found = _find_local_session_xml(
                detail_dir,
                9,
                None,
                session_url="https://www.senado.es/legis15/votaciones/ses_9.xml",
            )
            self.assertIsNone(found)

    def test_local_only_loader_never_calls_http_on_cache_miss(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch(
                "publicdata_connectors_es.parliamentary.senado_votaciones."
                "http_get_bytes"
            ) as fetch:
                result = reusable_load_session_vote_info(
                    "https://www.senado.es/legis15/votaciones/ses_999.xml",
                    timeout=1,
                    detail_dir=Path(temp_dir),
                    session_id=999,
                    vote_id=None,
                    detail_cookie=None,
                    local_only=True,
                )
            fetch.assert_not_called()
            self.assertEqual(result["error"], "local-cache-only: miss")

    def test_session_file_is_parsed_once_for_multiple_vote_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "votes.db"
            detail_dir = root / "details"
            legislature_dir = detail_dir / "legis15"
            legislature_dir.mkdir(parents=True)
            legislature_dir.joinpath("ses_1.xml").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<main><sesion><legislatura>15</legislatura><num_sesion>1</num_sesion>
<fecha_sesion>01/01/2026</fecha_sesion>
<votacion><num_vot>100</num_vot><CodVotacion>1</CodVotacion>
<num_exp>100/000001</num_exp><tit_vot>Vote one</tit_vot>
<tot_presentes>1</tot_presentes><tot_afirmativos>1</tot_afirmativos>
<tot_negativos>0</tot_negativos><tot_abstenciones>0</tot_abstenciones>
<tot_novotan>0</tot_novotan><tot_ausentes>0</tot_ausentes>
<Resultado><VotoSenador><escano>1</escano><grupo>G</grupo>
<nombre>Ana</nombre><apellidos>Uno</apellidos><voto>SI</voto></VotoSenador></Resultado>
</votacion>
<votacion><num_vot>101</num_vot><CodVotacion>2</CodVotacion>
<num_exp>100/000002</num_exp><tit_vot>Vote two</tit_vot>
<tot_presentes>1</tot_presentes><tot_afirmativos>0</tot_afirmativos>
<tot_negativos>1</tot_negativos><tot_abstenciones>0</tot_abstenciones>
<tot_novotan>0</tot_novotan><tot_ausentes>0</tot_ausentes>
<Resultado><VotoSenador><escano>2</escano><grupo>G</grupo>
<nombre>Beto</nombre><apellidos>Dos</apellidos><voto>NO</voto></VotoSenador></Resultado>
</votacion></sesion></main>""",
                encoding="utf-8",
            )
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                now = "2026-08-10T00:00:00Z"
                for vote_id, title, expediente in (
                    (1, "Vote one", "000001"),
                    (2, "Vote two", "000002"),
                ):
                    event_id = (
                        "url:https://www.senado.es/legis15/votaciones/"
                        f"ses_1_{vote_id}.xml"
                    )
                    payload = {
                        "legislature": "15",
                        "session_id": 1,
                        "vote_id": vote_id,
                        "tipo_expediente": "100",
                        "numero_expediente": expediente,
                        "vote_title": title,
                        "vote_file_url": event_id.removeprefix("url:"),
                    }
                    raw_payload = json.dumps(payload, sort_keys=True)
                    cursor = conn.execute(
                        """
                        INSERT INTO source_records (
                          source_id, source_record_id, source_snapshot_date,
                          raw_payload, content_sha256, created_at, updated_at
                        ) VALUES ('senado_votaciones', ?, '2026-02-12', ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            raw_payload,
                            hashlib.sha256(raw_payload.encode()).hexdigest(),
                            now,
                            now,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO parl_vote_events (
                          vote_event_id, legislature, session_number, vote_number,
                          title, source_id, source_url, source_record_pk,
                          source_snapshot_date, raw_payload, created_at, updated_at
                        ) VALUES (?, '15', 1, ?, ?, 'senado_votaciones', ?, ?,
                                  '2026-02-12', ?, ?, ?)
                        """,
                        (
                            event_id,
                            vote_id,
                            title,
                            event_id.removeprefix("url:"),
                            int(cursor.lastrowid),
                            raw_payload,
                            now,
                            now,
                        ),
                    )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized,
                      vote_choice, source_id, source_url, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, '999', 'Stale Person', 'stale person', 'NO',
                              'senado_votaciones', ?, '2026-02-12', '{}', ?, ?)
                    """,
                    (event_id, event_id.removeprefix("url:"), now, now),
                )
                conn.commit()
                with mock.patch(
                    "etl.parlamentario_es.connectors.senado_votaciones."
                    "_load_session_vote_info",
                    wraps=reusable_load_session_vote_info,
                ) as loader:
                    report = backfill_senado_vote_details(
                        conn,
                        timeout=1,
                        snapshot_date="2026-02-12",
                        include_existing=True,
                        only_reingest_when_member_votes=True,
                        senado_detail_dir=str(detail_dir),
                        detail_workers=2,
                    )
                self.assertEqual(loader.call_count, 1)
                self.assertEqual(report["detail_urls_total"], 2)
                self.assertEqual(report["detail_prefetch_jobs_total"], 1)
                self.assertEqual(report["detail_local_cache_groups_total"], 1)
                self.assertEqual(report["events_reingested"], 2, report)
                self.assertEqual(report["member_votes_loaded"], 2)
                self.assertEqual(report["stale_member_votes_removed"], 1)
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM parl_vote_member_votes").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT SUM(totals_absent) FROM parl_vote_events"
                    ).fetchone()[0],
                    0,
                )
            finally:
                conn.close()

    def test_local_cache_only_skips_uncached_event_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "votes.db"
            detail_dir = root / "details"
            detail_dir.mkdir()
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                now = "2026-08-10T00:00:00Z"
                event_id = "url:https://www.senado.es/legis15/votaciones/ses_999_1.xml"
                payload = json.dumps(
                    {
                        "legislature": "15",
                        "session_id": 999,
                        "vote_id": 1,
                        "vote_file_url": event_id.removeprefix("url:"),
                    },
                    sort_keys=True,
                )
                cursor = conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES ('senado_votaciones', ?, '2026-02-12', ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        payload,
                        hashlib.sha256(payload.encode()).hexdigest(),
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, session_number, vote_number,
                      source_id, source_url, source_record_pk,
                      source_snapshot_date, raw_payload, created_at, updated_at
                    ) VALUES (?, '15', 999, 1, 'senado_votaciones', ?, ?,
                              '2026-02-12', ?, ?, ?)
                    """,
                    (
                        event_id,
                        event_id.removeprefix("url:"),
                        int(cursor.lastrowid),
                        payload,
                        now,
                        now,
                    ),
                )
                conn.commit()
                with mock.patch(
                    "etl.parlamentario_es.connectors.senado_votaciones."
                    "_load_session_vote_info"
                ) as loader:
                    report = backfill_senado_vote_details(
                        conn,
                        timeout=1,
                        snapshot_date="2026-02-12",
                        include_existing=True,
                        senado_detail_dir=str(detail_dir),
                        senado_local_cache_only=True,
                        detail_workers=2,
                    )
                loader.assert_not_called()
                self.assertEqual(report["events_considered"], 0)
                self.assertEqual(report["events_skipped_no_local_cache"], 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
