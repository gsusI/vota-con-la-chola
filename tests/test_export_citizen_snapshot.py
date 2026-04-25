from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema
from scripts import export_citizen_snapshot as citizen_snapshot
from scripts.export_citizen_snapshot import build_snapshot_freshness


def _seed_min_citizen_db(conn: sqlite3.Connection) -> None:
    ts = "2026-02-17T00:00:00Z"

    # Minimal source row for mandates FK.
    conn.execute(
        """
        INSERT INTO sources (source_id, name, scope, default_url, data_format, is_active, created_at, updated_at)
        VALUES ('test_source', 'Test Source', 'test', 'https://example.com', 'test', 1, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )

    # Institution id matches export default (institution_id=7).
    conn.execute(
        """
        INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
        VALUES (7, 'Congreso de los Diputados', 'nacional', '', ?, ?)
        ON CONFLICT(name, level, territory_code) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )

    # Parties (explicit ids for clarity).
    conn.execute(
        """
        INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
        VALUES (1, 'Partido A', 'PA', ?, ?)
        ON CONFLICT(party_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
        VALUES (2, 'Partido B', 'PB', ?, ?)
        ON CONFLICT(party_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )

    # Persons.
    conn.execute(
        """
        INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
        VALUES ('Alice Example', 'person:alice', ?, ?)
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
        VALUES ('Bob Example', 'person:bob', ?, ?)
        """,
        (ts, ts),
    )
    p1 = int(conn.execute("SELECT person_id FROM persons WHERE canonical_key='person:alice'").fetchone()[0])
    p2 = int(conn.execute("SELECT person_id FROM persons WHERE canonical_key='person:bob'").fetchone()[0])

    # Mandates: one active member per party (needed for party aggregation join).
    conn.execute(
        """
        INSERT INTO mandates (
          person_id, institution_id, party_id,
          role_title, level, territory_code,
          is_active,
          source_id, source_record_id,
          first_seen_at, last_seen_at,
          raw_payload
        ) VALUES (?, 7, 1, 'Diputada', 'nacional', '', 1, 'test_source', 'm1', ?, ?, '{}')
        """,
        (p1, ts, ts),
    )
    conn.execute(
        """
        INSERT INTO mandates (
          person_id, institution_id, party_id,
          role_title, level, territory_code,
          is_active,
          source_id, source_record_id,
          first_seen_at, last_seen_at,
          raw_payload
        ) VALUES (?, 7, 2, 'Diputado', 'nacional', '', 1, 'test_source', 'm2', ?, ?, '{}')
        """,
        (p2, ts, ts),
    )
    m1 = int(conn.execute("SELECT mandate_id FROM mandates WHERE source_record_id='m1'").fetchone()[0])
    m2 = int(conn.execute("SELECT mandate_id FROM mandates WHERE source_record_id='m2'").fetchone()[0])

    # Topic set id matches export default (topic_set_id=1).
    conn.execute(
        """
        INSERT INTO topic_sets (topic_set_id, name, institution_id, legislature, is_active, created_at, updated_at)
        VALUES (1, 'Test Topic Set', 7, '15', 1, ?, ?)
        ON CONFLICT(name, institution_id, admin_level_id, territory_id, legislature) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )

    # Topics: 2 concerns (vivienda, empleo) and an extra vivienda to test max-items-per-concern filtering.
    topics = [
        (101, "t:101", "Vivienda y alquiler"),
        (102, "t:102", "Empleo y salarios"),
        (103, "t:103", "Vivienda social"),
        (104, "t:104", "Administracion publica"),
    ]
    for tid, key, label in topics:
        conn.execute(
            """
            INSERT INTO topics (topic_id, canonical_key, label, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(tid), str(key), str(label), ts, ts),
        )

    # Topic set memberships and ordering.
    for tid, rank, high in ((101, 1, 1), (102, 2, 1), (103, 3, 0), (104, 4, 0)):
        conn.execute(
            """
            INSERT INTO topic_set_topics (topic_set_id, topic_id, stakes_rank, is_high_stakes, created_at, updated_at)
            VALUES (1, ?, ?, ?, ?, ?)
            """,
            (int(tid), int(rank), int(high), ts, ts),
        )

    # Topic positions for 2 topics only (the ones expected after filtering) in both methods.
    # as_of_date matches typical citizen export (YYYY-MM-DD).
    as_of_date = "2026-02-16"
    computed_at = ts
    rows = [
        # combined
        (101, p1, m1, "support", 0.8, 0.9, 3, "combined", "v1"),
        (101, p2, m2, "oppose", -0.7, 0.8, 2, "combined", "v1"),
        (102, p1, m1, "support", 0.6, 0.7, 2, "combined", "v1"),
        (102, p2, m2, "support", 0.6, 0.7, 2, "combined", "v1"),
        # votes
        (101, p1, m1, "support", 0.8, 0.9, 3, "votes", "v1"),
        (101, p2, m2, "oppose", -0.7, 0.8, 2, "votes", "v1"),
        (102, p1, m1, "support", 0.6, 0.7, 2, "votes", "v1"),
        (102, p2, m2, "support", 0.6, 0.7, 2, "votes", "v1"),
    ]
    for topic_id, person_id, mandate_id, stance, score, conf, evc, method, version in rows:
        conn.execute(
            """
            INSERT INTO topic_positions (
              topic_id, topic_set_id, person_id, mandate_id, institution_id,
              as_of_date, stance, score, confidence, evidence_count, last_evidence_date,
              computed_method, computed_version, computed_at, created_at, updated_at
            ) VALUES (?, 1, ?, ?, 7, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(topic_id),
                int(person_id),
                int(mandate_id),
                str(as_of_date),
                str(stance),
                float(score),
                float(conf),
                int(evc),
                str(as_of_date),
                str(method),
                str(version),
                str(computed_at),
                ts,
                ts,
            ),
        )

    conn.commit()


def _seed_scope_fallback_citizen_db(conn: sqlite3.Connection) -> None:
    ts = "2026-02-17T00:00:00Z"

    conn.execute(
        """
        INSERT INTO sources (source_id, name, scope, default_url, data_format, is_active, created_at, updated_at)
        VALUES ('test_source', 'Test Source', 'test', 'https://example.com', 'test', 1, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
        VALUES (1, 'Congreso de los Diputados', 'nacional', '', ?, ?)
        ON CONFLICT(name, level, territory_code) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
        VALUES (7, 'Ayuntamiento demo', 'municipal', 'ES', ?, ?)
        ON CONFLICT(name, level, territory_code) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
        VALUES (1, 'Partido A', 'PA', ?, ?)
        ON CONFLICT(party_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO persons (person_id, full_name, canonical_key, created_at, updated_at)
        VALUES (1, 'Alice Example', 'person:alice', ?, ?)
        ON CONFLICT(person_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO mandates (
          mandate_id, person_id, institution_id, party_id,
          role_title, level, territory_code,
          is_active,
          source_id, source_record_id,
          first_seen_at, last_seen_at,
          raw_payload
        ) VALUES (1, 1, 1, 1, 'Diputada', 'nacional', '', 1, 'test_source', 'm1', ?, ?, '{}')
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO topic_sets (topic_set_id, name, institution_id, legislature, is_active, created_at, updated_at)
        VALUES (1, 'Congreso / votos', 1, '15', 1, ?, ?)
        ON CONFLICT(name, institution_id, admin_level_id, territory_id, legislature) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO topics (topic_id, canonical_key, label, created_at, updated_at)
        VALUES (101, 't:101', 'Vivienda y alquiler', ?, ?)
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO topic_set_topics (topic_set_id, topic_id, stakes_rank, is_high_stakes, created_at, updated_at)
        VALUES (1, 101, 1, 1, ?, ?)
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO topic_positions (
          topic_id, topic_set_id, person_id, mandate_id, institution_id,
          as_of_date, stance, score, confidence, evidence_count, last_evidence_date,
          computed_method, computed_version, computed_at, created_at, updated_at
        ) VALUES (101, 1, 1, 1, 1, '2026-02-16', 'support', 0.8, 0.9, 3, '2026-02-16', 'votes', 'v1', ?, ?, ?)
        """,
        (ts, ts, ts),
    )
    conn.commit()


def _seed_no_concern_match_citizen_db(conn: sqlite3.Connection) -> None:
    _seed_scope_fallback_citizen_db(conn)
    conn.execute(
        """
        UPDATE topics
        SET label = 'Administracion publica interna'
        WHERE topic_id = 101
        """
    )
    conn.commit()


def _seed_empty_citizen_export_db(conn: sqlite3.Connection) -> None:
    ts = "2026-02-17T00:00:00Z"

    conn.execute(
        """
        INSERT INTO sources (source_id, name, scope, default_url, data_format, is_active, created_at, updated_at)
        VALUES ('test_source', 'Test Source', 'test', 'https://example.com', 'test', 1, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
        VALUES (7, 'Congreso de los Diputados', 'nacional', '', ?, ?)
        ON CONFLICT(name, level, territory_code) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
        VALUES (1, 'Partido A', 'PA', ?, ?)
        ON CONFLICT(party_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO persons (person_id, full_name, canonical_key, created_at, updated_at)
        VALUES (1, 'Alice Example', 'person:alice', ?, ?)
        ON CONFLICT(person_id) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO mandates (
          mandate_id, person_id, institution_id, party_id,
          role_title, level, territory_code,
          is_active,
          source_id, source_record_id,
          first_seen_at, last_seen_at,
          raw_payload
        ) VALUES (1, 1, 7, 1, 'Diputada', 'nacional', '', 1, 'test_source', 'm1', ?, ?, '{}')
        """,
        (ts, ts),
    )
    conn.execute(
        """
        INSERT INTO topic_sets (topic_set_id, name, institution_id, legislature, is_active, created_at, updated_at)
        VALUES (1, 'Congreso / votos', 7, '15', 1, ?, ?)
        ON CONFLICT(name, institution_id, admin_level_id, territory_id, legislature) DO UPDATE SET updated_at=excluded.updated_at
        """,
        (ts, ts),
    )
    conn.commit()


class TestExportCitizenSnapshot(unittest.TestCase):
    def test_build_snapshot_freshness_flags_future_as_of_dates(self) -> None:
        freshness = build_snapshot_freshness(
            generated_at="2026-03-06T12:00:00+00:00",
            as_of_date="2026-03-10",
        )

        self.assertEqual(freshness["freshness_tier"], "future")
        self.assertEqual(freshness["freshness_label"], "futura")
        self.assertEqual(freshness["warning_reason"], "future_as_of_date")
        self.assertEqual(freshness["date_consistency_ok"], False)
        self.assertEqual(freshness["timeline_delta_days"], -4)
        self.assertEqual(freshness["data_age_days"], -4)
        self.assertEqual(freshness["should_warn"], True)

    def test_export_includes_v2_optional_fields_and_filters_by_max_items_per_concern(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "citizen.db"
            out_path = td_path / "citizen.json"

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                apply_schema(conn, Path(DEFAULT_SCHEMA))
                _seed_min_citizen_db(conn)
            finally:
                conn.close()

            # Export with max-items-per-concern=1 should keep at most 1 topic per concern.
            cmd = [
                "python3",
                "scripts/export_citizen_snapshot.py",
                "--db",
                str(db_path),
                "--out",
                str(out_path),
                "--topic-set-id",
                "1",
                "--institution-id",
                "7",
                "--as-of-date",
                "2026-02-16",
                "--computed-method",
                "auto",
                "--max-items-per-concern",
                "1",
                "--max-topics",
                "200",
                "--max-bytes",
                "5000000",
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            data = json.loads(out_path.read_text(encoding="utf-8"))
            meta = data["meta"]

            self.assertEqual(meta["computed_method"], "combined")
            self.assertNotIn("db_path", meta)
            self.assertIn("methods_available", meta)
            self.assertEqual(meta["methods_available"], ["combined", "votes"])
            self.assertIn("quality", meta)
            self.assertIn("freshness", meta)
            self.assertIn("honesty", meta)
            quality = meta["quality"]
            freshness = meta["freshness"]
            honesty = meta["honesty"]
            self.assertEqual(int(quality["cells_total"]), 4)
            self.assertEqual(int(quality["clear_total"]), 4)
            self.assertEqual(int(quality["any_signal_total"]), 4)
            self.assertEqual(int(quality["unknown_total"]), 0)
            self.assertAlmostEqual(float(quality["clear_pct"]), 1.0, places=6)
            self.assertAlmostEqual(float(quality["any_signal_pct"]), 1.0, places=6)
            self.assertAlmostEqual(float(quality["unknown_pct"]), 0.0, places=6)
            self.assertAlmostEqual(float(quality["confidence_avg_signal"]), 0.775, places=6)
            self.assertEqual(quality["confidence_tiers"], {"high": 4, "medium": 0, "low": 0, "none": 0})
            self.assertEqual(
                quality["stance_counts"],
                {"support": 3, "oppose": 1, "mixed": 0, "unclear": 0, "no_signal": 0},
            )
            self.assertEqual(
                quality["confidence_thresholds"],
                {"high_min": 0.66, "medium_min": 0.33},
            )
            self.assertEqual(freshness["freshness_version"], "citizen_snapshot_freshness_v1")
            self.assertEqual(freshness["as_of_date"], "2026-02-16")
            self.assertEqual(freshness["generated_at"], meta["generated_at"])
            self.assertIsInstance(freshness["data_age_days"], int)
            self.assertGreaterEqual(int(freshness["data_age_days"]), 0)
            self.assertEqual(freshness["timeline_delta_days"], freshness["data_age_days"])
            self.assertEqual(freshness["date_consistency_ok"], True)
            if int(freshness["data_age_days"]) <= 7:
                self.assertEqual(freshness["freshness_tier"], "fresh")
                self.assertEqual(freshness["freshness_label"], "reciente")
                self.assertEqual(freshness["warning_reason"], "none")
            elif int(freshness["data_age_days"]) <= 30:
                self.assertEqual(freshness["freshness_tier"], "aging")
                self.assertEqual(freshness["freshness_label"], "vigente")
                self.assertEqual(freshness["warning_reason"], "aging_snapshot")
            else:
                self.assertEqual(freshness["freshness_tier"], "stale")
                self.assertEqual(freshness["freshness_label"], "antigua")
                self.assertEqual(freshness["warning_reason"], "stale_snapshot")

            self.assertEqual(honesty["honesty_version"], "citizen_honesty_contract_v1")
            self.assertEqual(honesty["unknown_definition"], "unknown = incierto + sin_senal")
            self.assertEqual(honesty["match_definition"], "match/mismatch solo cuentan cuando hay senal clara comparable")
            self.assertEqual(honesty["no_imputation"], True)
            self.assertIn("audit_links", honesty)
            self.assertEqual(honesty["audit_links"]["explorer_temas"], "../explorer-temas/")
            self.assertEqual(honesty["audit_links"]["explorer_sql"], "../explorer/")

            topics = data["topics"]
            # vivienda + empleo => 2 topics selected, vivienda has 2 candidates but max=1 should pick the first.
            self.assertEqual(len(topics), 2)
            labels = {t["label"] for t in topics}
            self.assertIn("Vivienda y alquiler", labels)
            self.assertIn("Empleo y salarios", labels)

            for t in topics:
                self.assertIn("concern_ids", t)
                self.assertIsInstance(t["concern_ids"], list)
                # Determinism: sorted unique.
                self.assertEqual(t["concern_ids"], sorted(set(t["concern_ids"])))

            parties = data["parties"]
            self.assertEqual(len(parties), 2)
            pos = data["party_topic_positions"]
            self.assertEqual(len(pos), len(topics) * len(parties))

            # Validator should accept optional v2 keys.
            vcmd = [
                "python3",
                "scripts/validate_citizen_snapshot.py",
                "--path",
                str(out_path),
                "--max-bytes",
                "5000000",
                "--strict-grid",
            ]
            subprocess.run(vcmd, check=True, capture_output=True, text=True)

    def test_validator_rejects_inconsistent_future_freshness_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "citizen.db"
            out_path = td_path / "citizen.json"

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                apply_schema(conn, Path(DEFAULT_SCHEMA))
                _seed_min_citizen_db(conn)
            finally:
                conn.close()

            cmd = [
                "python3",
                "scripts/export_citizen_snapshot.py",
                "--db",
                str(db_path),
                "--out",
                str(out_path),
                "--topic-set-id",
                "1",
                "--institution-id",
                "7",
                "--as-of-date",
                "2026-02-16",
                "--computed-method",
                "auto",
                "--max-items-per-concern",
                "1",
                "--max-topics",
                "200",
                "--max-bytes",
                "5000000",
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            data = json.loads(out_path.read_text(encoding="utf-8"))
            data["meta"]["freshness"]["freshness_tier"] = "future"
            data["meta"]["freshness"]["freshness_label"] = "futura"
            data["meta"]["freshness"]["data_age_days"] = 0
            data["meta"]["freshness"]["timeline_delta_days"] = 0
            data["meta"]["freshness"]["date_consistency_ok"] = True
            data["meta"]["freshness"]["warning_reason"] = "none"
            out_path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")

            vcmd = [
                "python3",
                "scripts/validate_citizen_snapshot.py",
                "--path",
                str(out_path),
                "--max-bytes",
                "5000000",
                "--strict-grid",
            ]
            result = subprocess.run(vcmd, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("future state must expose negative data_age_days", result.stderr)

    def test_resolve_scope_falls_back_to_topic_set_institution_and_votes(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            apply_schema(conn, Path(DEFAULT_SCHEMA))
            _seed_scope_fallback_citizen_db(conn)
            scope = citizen_snapshot.resolve_scope(
                conn,
                args=Namespace(
                    topic_set_id=1,
                    institution_id=7,
                    as_of_date="",
                    computed_method="auto",
                ),
            )
        finally:
            conn.close()

        self.assertEqual(scope.topic_set_id, 1)
        self.assertEqual(scope.institution_id, 1)
        self.assertEqual(scope.as_of_date, "2026-02-16")
        self.assertEqual(scope.computed_method, "votes")
        self.assertEqual(scope.computed_version, "v1")

    def test_export_declared_snapshot_degrades_to_no_data_grid_when_positions_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "citizen-fallback.db"
            out_path = td_path / "citizen_declared.json"

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                apply_schema(conn, Path(DEFAULT_SCHEMA))
                _seed_scope_fallback_citizen_db(conn)
            finally:
                conn.close()

            cmd = [
                "python3",
                "scripts/export_citizen_snapshot.py",
                "--db",
                str(db_path),
                "--out",
                str(out_path),
                "--topic-set-id",
                "1",
                "--institution-id",
                "7",
                "--computed-method",
                "declared",
                "--max-bytes",
                "5000000",
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(data["meta"]["computed_method"], "declared")
            self.assertEqual(data["meta"]["computed_version"], "no_data")
            self.assertNotIn("methods_available", data["meta"])
            self.assertEqual(len(data["topics"]), 1)
            self.assertEqual(len(data["parties"]), 1)
            self.assertEqual(len(data["party_topic_positions"]), 1)
            self.assertEqual(data["party_topic_positions"][0]["stance"], "no_signal")

            vcmd = [
                "python3",
                "scripts/validate_citizen_snapshot.py",
                "--path",
                str(out_path),
                "--max-bytes",
                "5000000",
                "--strict-grid",
            ]
            subprocess.run(vcmd, check=True, capture_output=True, text=True)

    def test_export_keeps_topics_when_concern_filter_matches_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "citizen-no-concern.db"
            out_path = td_path / "citizen.json"

            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                apply_schema(conn, Path(DEFAULT_SCHEMA))
                _seed_no_concern_match_citizen_db(conn)
            finally:
                conn.close()

            cmd = [
                "python3",
                "scripts/export_citizen_snapshot.py",
                "--db",
                str(db_path),
                "--out",
                str(out_path),
                "--topic-set-id",
                "1",
                "--institution-id",
                "7",
                "--computed-method",
                "auto",
                "--max-bytes",
                "5000000",
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["topics"]), 1)
            self.assertEqual(data["topics"][0]["label"], "Administracion publica interna")
            self.assertEqual(len(data["party_topic_positions"]), 1)

    def test_export_reuses_fallback_snapshot_on_severe_regression(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            fallback_db_path = td_path / "citizen-good.db"
            fallback_snapshot_path = td_path / "citizen-good.json"
            regressed_db_path = td_path / "citizen-bad.db"
            out_path = td_path / "citizen-regressed.json"

            conn = sqlite3.connect(str(fallback_db_path))
            conn.row_factory = sqlite3.Row
            try:
                apply_schema(conn, Path(DEFAULT_SCHEMA))
                _seed_min_citizen_db(conn)
            finally:
                conn.close()

            subprocess.run(
                [
                    "python3",
                    "scripts/export_citizen_snapshot.py",
                    "--db",
                    str(fallback_db_path),
                    "--out",
                    str(fallback_snapshot_path),
                    "--topic-set-id",
                    "1",
                    "--institution-id",
                    "7",
                    "--computed-method",
                    "auto",
                    "--max-items-per-concern",
                    "1",
                    "--max-topics",
                    "200",
                    "--max-bytes",
                    "5000000",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            conn = sqlite3.connect(str(regressed_db_path))
            conn.row_factory = sqlite3.Row
            try:
                apply_schema(conn, Path(DEFAULT_SCHEMA))
                _seed_empty_citizen_export_db(conn)
            finally:
                conn.close()

            result = subprocess.run(
                [
                    "python3",
                    "scripts/export_citizen_snapshot.py",
                    "--db",
                    str(regressed_db_path),
                    "--out",
                    str(out_path),
                    "--topic-set-id",
                    "1",
                    "--institution-id",
                    "7",
                    "--computed-method",
                    "auto",
                    "--fallback-snapshot",
                    str(fallback_snapshot_path),
                    "--max-bytes",
                    "5000000",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            fallback_data = json.loads(fallback_snapshot_path.read_text(encoding="utf-8"))
            data = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(data["meta"]["as_of_date"], fallback_data["meta"]["as_of_date"])
            self.assertEqual(data["meta"]["computed_method"], fallback_data["meta"]["computed_method"])
            self.assertEqual(len(data["topics"]), len(fallback_data["topics"]))
            self.assertEqual(len(data["party_topic_positions"]), len(fallback_data["party_topic_positions"]))
            self.assertIn("reusing fallback", result.stderr)
