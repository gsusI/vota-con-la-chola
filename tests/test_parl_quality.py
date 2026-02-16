from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.linking import link_congreso_votes_to_initiatives, link_senado_votes_to_initiatives
from etl.parlamentario_es.pipeline import backfill_vote_member_person_ids, ingest_one_source as ingest_parl_source
from etl.politicos_es.util import canonical_key, now_utc_iso
from etl.parlamentario_es.quality import (
    DEFAULT_VOTE_QUALITY_THRESHOLDS,
    compute_vote_quality_kpis,
    evaluate_vote_quality_gate,
)
from etl.parlamentario_es.registry import get_connectors


class TestParlVoteQuality(unittest.TestCase):
    def test_compute_kpis_is_deterministic_with_samples_and_linking(self) -> None:
        connectors = get_connectors()
        snapshot_date = "2026-02-12"
        ingest_sources = [
            "congreso_votaciones",
            "congreso_iniciativas",
            "senado_iniciativas",
            "senado_votaciones",
        ]

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                for sid in ingest_sources:
                    connector = connectors[sid]
                    sample_path = Path(PARL_SOURCE_CONFIG[sid]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing sample for {sid}: {sample_path}")
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

                link_congreso_votes_to_initiatives(conn, dry_run=False)
                link_senado_votes_to_initiatives(conn, dry_run=False)

                kpis_1 = compute_vote_quality_kpis(conn)
                kpis_2 = compute_vote_quality_kpis(conn)
                self.assertEqual(kpis_1, kpis_2)

                self.assertGreater(int(kpis_1["events_total"]), 0)
                self.assertGreaterEqual(int(kpis_1["events_with_nominal_vote"]), 0)
                self.assertGreaterEqual(int(kpis_1["member_votes_total"]), 0)
                self.assertIn("events_with_initiative_link", kpis_1)
                self.assertIn("events_with_initiative_link_pct", kpis_1)
                self.assertIn("events_with_initiative_link", kpis_1["by_source"]["congreso_votaciones"])
                self.assertIn(
                    "events_with_initiative_link_pct",
                    kpis_1["by_source"]["congreso_votaciones"],
                )
                self.assertLessEqual(
                    int(kpis_1["member_votes_with_person_id"]),
                    int(kpis_1["member_votes_total"]),
                )
                self.assertIn("congreso_votaciones", kpis_1["by_source"])
                self.assertIn("senado_votaciones", kpis_1["by_source"])

                by_source = kpis_1["by_source"]
                self.assertEqual(
                    int(kpis_1["events_total"]),
                    int(by_source["congreso_votaciones"]["events_total"])
                    + int(by_source["senado_votaciones"]["events_total"]),
                )

                pass_gate = evaluate_vote_quality_gate(
                    kpis_1,
                    thresholds={metric: 0.0 for metric in DEFAULT_VOTE_QUALITY_THRESHOLDS},
                )
                self.assertTrue(bool(pass_gate["passed"]))
                self.assertEqual(pass_gate["failures"], [])

                fail_gate = evaluate_vote_quality_gate(
                    kpis_1,
                    thresholds={metric: 1.01 for metric in DEFAULT_VOTE_QUALITY_THRESHOLDS},
                )
                self.assertFalse(bool(fail_gate["passed"]))
                self.assertEqual(len(fail_gate["failures"]), len(DEFAULT_VOTE_QUALITY_THRESHOLDS))
            finally:
                conn.close()

    def test_evaluate_gate_default_and_custom_thresholds(self) -> None:
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["events_with_date_pct"], 0.95)
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["events_with_theme_pct"], 0.95)
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["events_with_totals_pct"], 0.95)
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["events_with_initiative_link_pct"], 0.95)
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["member_votes_with_person_id_pct"], 0.90)

        kpis = {
            "events_with_date_pct": 0.96,
            "events_with_theme_pct": 0.94,
            "events_with_totals_pct": 0.97,
            "events_with_initiative_link_pct": 0.96,
            "member_votes_with_person_id_pct": 0.91,
        }

        default_gate = evaluate_vote_quality_gate(kpis)
        self.assertFalse(bool(default_gate["passed"]))
        self.assertEqual(len(default_gate["failures"]), 1)
        self.assertEqual(default_gate["failures"][0]["metric"], "events_with_theme_pct")

        custom_gate = evaluate_vote_quality_gate(
            kpis,
            thresholds={"events_with_theme_pct": 0.94},
        )
        self.assertTrue(bool(custom_gate["passed"]))


class TestParlBackfillMemberIds(unittest.TestCase):
    def _seed_institution(self, conn: sqlite3.Connection, *, name: str = "Congreso") -> int:
        row = conn.execute(
            "SELECT institution_id FROM institutions WHERE name = ? AND level = ? AND territory_code = ''",
            (name, "nacional"),
        ).fetchone()
        if row is not None:
            return int(row["institution_id"])

        now = now_utc_iso()
        conn.execute(
            """
            INSERT INTO institutions (
                name, level, territory_code, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (name, "nacional", "", now, now),
        )
        return int(
            conn.execute(
                "SELECT institution_id FROM institutions WHERE name = ? AND level = ?",
                (name, "nacional"),
            ).fetchone()["institution_id"]
        )

    def _seed_source_if_missing(
        self,
        conn: sqlite3.Connection,
        source_id: str,
        *,
        name: str,
        scope: str = "nacional",
        default_url: str = "",
        data_format: str = "json",
    ) -> None:
        exists = conn.execute(
            "SELECT 1 FROM sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if exists is not None:
            return
        now = now_utc_iso()
        conn.execute(
            """
            INSERT INTO sources (source_id, name, scope, default_url, data_format, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (source_id, name, scope, default_url, data_format, now, now),
        )

    def _seed_person_and_mandate(
        self,
        conn: sqlite3.Connection,
        *,
        full_name: str,
        given_name: str | None,
        family_name: str | None,
        source_id: str,
        is_active: int,
        start_date: str | None = None,
        end_date: str | None = None,
        source_record_id: str,
    ) -> int:
        now = now_utc_iso()
        institution_id = self._seed_institution(conn)
        ckey = canonical_key(full_name=full_name, birth_date=None, territory_code="")

        cur = conn.execute(
            """
            INSERT INTO persons (
                full_name, given_name, family_name, canonical_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (full_name, given_name, family_name, ckey, now, now),
        )
        person_id = int(cur.lastrowid)

        conn.execute(
            """
            INSERT INTO mandates (
              person_id, institution_id, role_title, level, territory_code,
              start_date, end_date, is_active, source_id, source_record_id,
              first_seen_at, last_seen_at, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id,
                institution_id,
                "Diputado",
                "nacional",
                "",
                start_date,
                end_date,
                is_active,
                source_id,
                source_record_id,
                now,
                now,
                "{}",
            ),
        )
        return person_id

    def _seed_mandate_for_person(
        self,
        conn: sqlite3.Connection,
        *,
        person_id: int,
        source_id: str,
        is_active: int,
        start_date: str | None = None,
        end_date: str | None = None,
        source_record_id: str,
    ) -> None:
        now = now_utc_iso()
        institution_id = self._seed_institution(conn)
        conn.execute(
            """
            INSERT INTO mandates (
              person_id, institution_id, role_title, level, territory_code,
              start_date, end_date, is_active, source_id, source_record_id,
              first_seen_at, last_seen_at, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id,
                institution_id,
                "Diputado",
                "nacional",
                "",
                start_date,
                end_date,
                is_active,
                source_id,
                source_record_id,
                now,
                now,
                "{}",
            ),
        )

    def test_backfill_vote_member_ids_matches_on_name_and_legislature(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_source_if_missing(conn, "congreso_diputados", name="Congreso de los Diputados")
                self._seed_source_if_missing(conn, "senado_senadores", name="Senado de España")

                person_same_leg = self._seed_person_and_mandate(
                    conn,
                    full_name="Ana Torres",
                    given_name="Ana",
                    family_name="Torres",
                    source_id="congreso_diputados",
                    is_active=1,
                    start_date="2025-01-01",
                    source_record_id="m-cong-same-leg",
                )
                self._seed_mandate_for_person(
                    conn,
                    person_id=person_same_leg,
                    source_id="congreso_diputados",
                    is_active=1,
                    start_date="2023-01-01",
                    source_record_id="m-cong-other-leg",
                )
                person_senado = self._seed_person_and_mandate(
                    conn,
                    full_name="Luis Pérez",
                    given_name="Luis",
                    family_name="Pérez",
                    source_id="senado_senadores",
                    is_active=1,
                    start_date="2024-01-01",
                    source_record_id="m-sen-old",
                )

                now = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-cong", "XV", "2026-01-15", "congreso_votaciones", "{}", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-sen", "15", "2024-03-10", "senado_votaciones", "{}", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized, vote_choice, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-cong", "s1", "Torres, Ana", "ana torres", "SI", "congreso_votaciones", "{}", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized, vote_choice, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-sen", "s2", "Luis Pérez", "luis perez", "NO", "senado_votaciones", "{}", now, now),
                )
                conn.commit()

                report = backfill_vote_member_person_ids(conn, vote_source_ids=("congreso_votaciones", "senado_votaciones"))
                self.assertEqual(report.get("total_checked"), 2)
                self.assertEqual(report.get("total_updated"), 2)
                self.assertEqual(report.get("total_unmatched"), 0)

                rows = conn.execute(
                    """
                    SELECT person_id FROM parl_vote_member_votes
                    ORDER BY seat
                    """
                ).fetchall()
                self.assertEqual(int(rows[0]["person_id"]), person_same_leg)
                self.assertEqual(int(rows[1]["person_id"]), person_senado)
            finally:
                conn.close()

    def test_backfill_vote_member_ids_dry_run_does_not_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-backfill-dry.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_source_if_missing(conn, "senado_senadores", name="Senado de España")

                self._seed_person_and_mandate(
                    conn,
                    full_name="María Rojas",
                    given_name="María",
                    family_name="Rojas",
                    source_id="senado_senadores",
                    is_active=0,
                    source_record_id="m-sen-dry",
                )

                now = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-sen-2", "14", "2024-04-10", "senado_votaciones", "{}", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized, vote_choice, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-sen-2", "s1", "María Rojas", "maria rojas", "ABST", "senado_votaciones", "{}", now, now),
                )
                conn.commit()

                report = backfill_vote_member_person_ids(
                    conn,
                    vote_source_ids=("senado_votaciones",),
                    dry_run=True,
                )
                self.assertEqual(report.get("total_checked"), 1)
                self.assertEqual(report.get("total_updated"), 1)
                self.assertEqual(report.get("total_unmatched"), 0)

                row = conn.execute(
                    "SELECT person_id FROM parl_vote_member_votes WHERE vote_event_id = ?",
                    ("ev-sen-2",),
                ).fetchone()
                self.assertIsNone(row["person_id"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
