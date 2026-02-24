from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from typing import Any

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.politicos_es.util import canonical_key, now_utc_iso
from scripts import graph_ui_server as g


class TestGraphUiServerCoherenceApi(unittest.TestCase):
    def _seed_fixture(self, db_path: Path) -> dict[str, Any]:
        conn = open_db(db_path)
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            seed_parl_sources(conn)
            now_iso = now_utc_iso()
            as_of_date = "2026-02-12"

            conn.execute(
                """
                INSERT INTO admin_levels (code, label, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                  label = excluded.label,
                  updated_at = excluded.updated_at
                """,
                ("nacional", "Nacional", now_iso, now_iso),
            )
            admin_level_id = int(
                conn.execute(
                    "SELECT admin_level_id FROM admin_levels WHERE code = 'nacional'"
                ).fetchone()["admin_level_id"]
            )

            conn.execute(
                """
                INSERT INTO topic_sets (
                  name, description, institution_id, admin_level_id, territory_id,
                  legislature, valid_from, valid_to, is_active, created_at, updated_at
                ) VALUES (?, ?, NULL, ?, NULL, ?, NULL, NULL, 1, ?, ?)
                """,
                ("Set Coherence Demo", "fixture", admin_level_id, "XV", now_iso, now_iso),
            )
            topic_set_id = int(conn.execute("SELECT topic_set_id FROM topic_sets").fetchone()["topic_set_id"])

            conn.execute(
                """
                INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
                VALUES ('demo_coherence', 'Demo coherence topic', NULL, NULL, ?, ?)
                """,
                (now_iso, now_iso),
            )
            topic_id = int(
                conn.execute(
                    "SELECT topic_id FROM topics WHERE canonical_key = 'demo_coherence'"
                ).fetchone()["topic_id"]
            )

            person_ids: dict[str, int] = {}
            for person_name in ("Persona Incoherente", "Persona Coherente"):
                ckey = canonical_key(full_name=person_name, birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (person_name, ckey, now_iso, now_iso),
                )
                person_ids[person_name] = int(
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )

            conn.execute(
                """
                INSERT INTO parties (name, acronym, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                ("Partido Incoherente", "PI", now_iso, now_iso),
            )
            conn.execute(
                """
                INSERT INTO parties (name, acronym, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                ("Partido Coherente", "PC", now_iso, now_iso),
            )
            party_ids = {
                "Persona Incoherente": int(
                    conn.execute("SELECT party_id FROM parties WHERE name = 'Partido Incoherente'").fetchone()["party_id"]
                ),
                "Persona Coherente": int(
                    conn.execute("SELECT party_id FROM parties WHERE name = 'Partido Coherente'").fetchone()["party_id"]
                ),
            }

            conn.execute(
                """
                INSERT INTO institutions (name, level, admin_level_id, territory_code, created_at, updated_at)
                VALUES (?, ?, ?, '', ?, ?)
                """,
                ("Congreso Demo", "nacional", admin_level_id, now_iso, now_iso),
            )
            institution_id = int(
                conn.execute(
                    "SELECT institution_id FROM institutions WHERE name = 'Congreso Demo'"
                ).fetchone()["institution_id"]
            )

            for person_name, person_id in person_ids.items():
                conn.execute(
                    """
                    INSERT INTO mandates (
                      person_id, institution_id, party_id, role_title, level, admin_level_id,
                      source_id, source_record_id, source_snapshot_date,
                      first_seen_at, last_seen_at, raw_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(person_id),
                        institution_id,
                        int(party_ids[person_name]),
                        "Diputado",
                        "nacional",
                        admin_level_id,
                        "congreso_votaciones",
                        f"fixture-mandate:{person_id}",
                        as_of_date,
                        now_iso,
                        now_iso,
                        "{}",
                    ),
                )

            def _insert_position(person_id: int, computed_method: str, stance: str, score: float) -> None:
                conn.execute(
                    """
                    INSERT INTO topic_positions (
                      topic_id, topic_set_id, person_id, admin_level_id,
                      as_of_date, stance, score, confidence, evidence_count, last_evidence_date,
                      computed_method, computed_version, computed_at,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        topic_set_id,
                        person_id,
                        admin_level_id,
                        as_of_date,
                        stance,
                        score,
                        0.9,
                        1,
                        as_of_date,
                        computed_method,
                        "v1",
                        now_iso,
                        now_iso,
                        now_iso,
                    ),
                )

            _insert_position(person_ids["Persona Incoherente"], "votes", "support", 1.0)
            _insert_position(person_ids["Persona Incoherente"], "declared", "oppose", -1.0)
            _insert_position(person_ids["Persona Coherente"], "votes", "support", 1.0)
            _insert_position(person_ids["Persona Coherente"], "declared", "support", 1.0)

            def _insert_evidence(
                *,
                person_id: int,
                evidence_type: str,
                stance: str,
                polarity: int,
                source_id: str,
                stance_method: str,
            ) -> None:
                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id, person_id, admin_level_id,
                      evidence_type, evidence_date, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      source_id, source_url, source_snapshot_date, raw_payload,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        topic_set_id,
                        person_id,
                        admin_level_id,
                        evidence_type,
                        as_of_date,
                        f"{evidence_type} for {person_id}",
                        stance,
                        polarity,
                        1.0,
                        0.9,
                        "fixture",
                        stance_method,
                        source_id,
                        "https://example.invalid/evidence",
                        as_of_date,
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )

            _insert_evidence(
                person_id=person_ids["Persona Incoherente"],
                evidence_type="revealed:vote",
                stance="support",
                polarity=1,
                source_id="congreso_votaciones",
                stance_method="vote_totals",
            )
            _insert_evidence(
                person_id=person_ids["Persona Incoherente"],
                evidence_type="declared:intervention",
                stance="oppose",
                polarity=-1,
                source_id="congreso_intervenciones",
                stance_method="declared:regex_v3",
            )
            _insert_evidence(
                person_id=person_ids["Persona Coherente"],
                evidence_type="revealed:vote",
                stance="support",
                polarity=1,
                source_id="congreso_votaciones",
                stance_method="vote_totals",
            )
            _insert_evidence(
                person_id=person_ids["Persona Coherente"],
                evidence_type="declared:intervention",
                stance="support",
                polarity=1,
                source_id="congreso_intervenciones",
                stance_method="declared:regex_v3",
            )
            conn.commit()

            fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
            self.assertEqual(fk_rows, [])

            return {
                "topic_set_id": topic_set_id,
                "topic_id": topic_id,
                "as_of_date": as_of_date,
                "incoherent_person_id": person_ids["Persona Incoherente"],
                "incoherent_party_id": party_ids["Persona Incoherente"],
                "coherent_party_id": party_ids["Persona Coherente"],
            }
        finally:
            conn.close()

    def _start_server(self, db_path: Path) -> tuple[ThreadingHTTPServer, threading.Thread]:
        handler = g.create_handler(g.AppConfig(db_path=db_path))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def _get_json(self, port: int, path: str) -> tuple[int, dict[str, Any]]:
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            body = response.read()
            payload = json.loads(body.decode("utf-8")) if body else {}
            return int(response.status), payload
        finally:
            conn.close()

    def test_topics_coherence_endpoint_groups_by_topic_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "coherence.db"
            fixture = self._seed_fixture(db_path)
            server, thread = self._start_server(db_path)
            try:
                port = int(server.server_address[1])
                status, payload = self._get_json(
                    port,
                    f"/api/topics/coherence?as_of_date={fixture['as_of_date']}",
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["meta"]["as_of_date"], fixture["as_of_date"])
                self.assertGreaterEqual(int(payload["summary"]["groups_total"]), 1)
                self.assertGreater(int(payload["summary"]["overlap_total"]), 0)
                groups = payload["groups"]
                self.assertTrue(groups)

                matches = [
                    row
                    for row in groups
                    if int(row["topic_set_id"] or 0) == int(fixture["topic_set_id"])
                    and int(row["topic_id"] or 0) == int(fixture["topic_id"])
                    and str(row["scope"] or "") == "nacional"
                ]
                self.assertEqual(len(matches), 1)
                row = matches[0]
                self.assertEqual(int(row["overlap_total"]), 2)
                self.assertEqual(int(row["explicit_total"]), 2)
                self.assertEqual(int(row["coherent_total"]), 1)
                self.assertEqual(int(row["incoherent_total"]), 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_topics_coherence_evidence_endpoint_filters_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "coherence.db"
            fixture = self._seed_fixture(db_path)
            server, thread = self._start_server(db_path)
            try:
                port = int(server.server_address[1])
                query = (
                    "/api/topics/coherence/evidence"
                    f"?bucket=incoherent&as_of_date={fixture['as_of_date']}"
                    f"&topic_set_id={fixture['topic_set_id']}"
                    f"&topic_id={fixture['topic_id']}"
                    "&scope=nacional"
                )
                status, payload = self._get_json(port, query)
                self.assertEqual(status, 200)
                self.assertEqual(int(payload["summary"]["pairs_total"]), 1)
                self.assertEqual(int(payload["summary"]["evidence_total"]), 2)
                self.assertEqual(int(payload["page"]["returned"]), 2)
                self.assertTrue(payload["rows"])
                self.assertEqual(
                    {int(r["person_id"]) for r in payload["rows"]},
                    {int(fixture["incoherent_person_id"])},
                )
                self.assertEqual(
                    {str(r["evidence_type"]) for r in payload["rows"]},
                    {"declared:intervention", "revealed:vote"},
                )

                bad_status, bad_payload = self._get_json(port, "/api/topics/coherence/evidence?bucket=unknown")
                self.assertEqual(bad_status, 400)
                self.assertIn("bucket", str(bad_payload.get("error", "")))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_topics_coherence_endpoints_filter_party_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "coherence.db"
            fixture = self._seed_fixture(db_path)
            server, thread = self._start_server(db_path)
            try:
                port = int(server.server_address[1])
                summary_query = (
                    "/api/topics/coherence"
                    f"?as_of_date={fixture['as_of_date']}"
                    f"&topic_set_id={fixture['topic_set_id']}"
                    f"&topic_id={fixture['topic_id']}"
                    "&scope=nacional"
                    f"&party_id={fixture['incoherent_party_id']}"
                )
                status, payload = self._get_json(port, summary_query)
                self.assertEqual(status, 200)
                self.assertEqual(int(payload["summary"]["overlap_total"]), 1)
                self.assertEqual(int(payload["summary"]["explicit_total"]), 1)
                self.assertEqual(int(payload["summary"]["coherent_total"]), 0)
                self.assertEqual(int(payload["summary"]["incoherent_total"]), 1)

                evidence_query = (
                    "/api/topics/coherence/evidence"
                    f"?bucket=incoherent&as_of_date={fixture['as_of_date']}"
                    f"&topic_set_id={fixture['topic_set_id']}"
                    f"&topic_id={fixture['topic_id']}"
                    "&scope=nacional"
                    f"&party_id={fixture['incoherent_party_id']}"
                )
                ev_status, ev_payload = self._get_json(port, evidence_query)
                self.assertEqual(ev_status, 200)
                self.assertEqual(int(ev_payload["summary"]["pairs_total"]), 1)
                self.assertEqual(int(ev_payload["summary"]["evidence_total"]), 2)
                self.assertEqual(
                    {int(r["person_id"]) for r in ev_payload["rows"]},
                    {int(fixture["incoherent_person_id"])},
                )
                self.assertEqual(
                    {int(r["party_id"] or 0) for r in ev_payload["rows"]},
                    {int(fixture["incoherent_party_id"])},
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_sources_status_coherence_as_of_uses_overlap_date(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "coherence-status.db"
            fixture = self._seed_fixture(db_path)

            conn = open_db(db_path)
            try:
                now_iso = now_utc_iso()
                admin_level_id = int(
                    conn.execute(
                        "SELECT admin_level_id FROM topic_sets WHERE topic_set_id = ?",
                        (fixture["topic_set_id"],),
                    ).fetchone()["admin_level_id"]
                    or 0
                )
                conn.execute(
                    """
                    INSERT INTO topic_positions (
                      topic_id, topic_set_id, person_id, admin_level_id,
                      as_of_date, stance, score, confidence, evidence_count, last_evidence_date,
                      computed_method, computed_version, computed_at,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(fixture["topic_id"]),
                        int(fixture["topic_set_id"]),
                        int(fixture["incoherent_person_id"]),
                        admin_level_id if admin_level_id > 0 else None,
                        "2026-02-16",
                        "support",
                        1.0,
                        0.9,
                        1,
                        "2026-02-16",
                        "declared",
                        "v1",
                        now_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            server, thread = self._start_server(db_path)
            try:
                port = int(server.server_address[1])
                status, payload = self._get_json(port, "/api/sources/status")
                self.assertEqual(status, 200)
                coherence = payload.get("analytics", {}).get("coherence", {})
                self.assertEqual(str(coherence.get("as_of_date") or ""), fixture["as_of_date"])
                self.assertGreater(int(coherence.get("overlap_total") or 0), 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
