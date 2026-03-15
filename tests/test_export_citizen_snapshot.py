from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema
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
        # previous combined snapshot for diff companion
        (101, p1, m1, "support", 0.7, 0.8, 2, "combined", "v0", "2026-02-10"),
        (101, p2, m2, "support", 0.55, 0.6, 1, "combined", "v0", "2026-02-10"),
        (102, p1, m1, "support", 0.5, 0.6, 1, "combined", "v0", "2026-02-10"),
        (102, p2, m2, "support", 0.5, 0.6, 1, "combined", "v0", "2026-02-10"),
        # previous votes snapshot for diff companion
        (101, p1, m1, "support", 0.7, 0.8, 2, "votes", "v0", "2026-02-10"),
        (101, p2, m2, "support", 0.55, 0.6, 1, "votes", "v0", "2026-02-10"),
        (102, p1, m1, "support", 0.5, 0.6, 1, "votes", "v0", "2026-02-10"),
        (102, p2, m2, "support", 0.5, 0.6, 1, "votes", "v0", "2026-02-10"),
        # combined
        (101, p1, m1, "support", 0.8, 0.9, 3, "combined", "v1", "2026-02-16"),
        (101, p2, m2, "oppose", -0.7, 0.8, 2, "combined", "v1", "2026-02-16"),
        (102, p1, m1, "support", 0.6, 0.7, 2, "combined", "v1", "2026-02-16"),
        (102, p2, m2, "support", 0.6, 0.7, 2, "combined", "v1", "2026-02-16"),
        # votes
        (101, p1, m1, "support", 0.8, 0.9, 3, "votes", "v1", "2026-02-16"),
        (101, p2, m2, "oppose", -0.7, 0.8, 2, "votes", "v1", "2026-02-16"),
        (102, p1, m1, "support", 0.6, 0.7, 2, "votes", "v1", "2026-02-16"),
        (102, p2, m2, "support", 0.6, 0.7, 2, "votes", "v1", "2026-02-16"),
    ]
    for topic_id, person_id, mandate_id, stance, score, conf, evc, method, version, row_as_of_date in rows:
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
                str(row_as_of_date),
                str(stance),
                float(score),
                float(conf),
                int(evc),
                str(row_as_of_date),
                str(method),
                str(version),
                str(computed_at),
                ts,
                ts,
            ),
        )

    # Evidence rows for lineage samples.
    evidence_rows = [
        (10101, 101, p1, m1, "revealed:vote", "support", 1, 0.91, "2026-02-16", "https://example.com/vote-101-a"),
        (10102, 101, p2, m2, "revealed:vote", "oppose", -1, 0.82, "2026-02-16", "https://example.com/vote-101-b"),
        (10201, 102, p1, m1, "revealed:vote", "support", 1, 0.73, "2026-02-16", "https://example.com/vote-102-a"),
        (10202, 102, p2, m2, "revealed:vote", "support", 1, 0.71, "2026-02-16", "https://example.com/vote-102-b"),
    ]
    for evidence_id, topic_id, person_id, mandate_id, evidence_type, stance, polarity, confidence, evidence_date, source_url in evidence_rows:
        conn.execute(
            """
            INSERT INTO topic_evidence (
              evidence_id, topic_id, topic_set_id, person_id, mandate_id, institution_id,
              evidence_type, evidence_date, title, excerpt, stance, polarity,
              weight, confidence, topic_method, stance_method,
              source_id, source_url, source_snapshot_date, raw_payload, created_at, updated_at
            ) VALUES (?, ?, 1, ?, ?, 7, ?, ?, ?, ?, ?, ?, 1.0, ?, 'test', 'test', 'test_source', ?, ?, '{}', ?, ?)
            """,
            (
                int(evidence_id),
                int(topic_id),
                int(person_id),
                int(mandate_id),
                str(evidence_type),
                str(evidence_date),
                f"Evidence {evidence_id}",
                f"Excerpt {evidence_id}",
                str(stance),
                int(polarity),
                float(confidence),
                str(source_url),
                str(evidence_date),
                ts,
                ts,
            ),
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
            comparability = json.loads((td_path / "citizen_comparability.json").read_text(encoding="utf-8"))
            lineage = json.loads((td_path / "citizen_lineage.json").read_text(encoding="utf-8"))
            diff = json.loads((td_path / "citizen_snapshot_diff.json").read_text(encoding="utf-8"))
            robustness = json.loads((td_path / "citizen_ranking_robustness.json").read_text(encoding="utf-8"))
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
            self.assertEqual(comparability["meta"]["artifact_version"], "citizen_comparability_v1")
            self.assertEqual(len(comparability["rows"]), len(pos))
            comparable_key = {
                (int(row["topic_id"]), int(row["party_id"])): row for row in comparability["rows"]
            }
            self.assertTrue(bool(comparable_key[(101, 1)]["comparable_ok"]))
            self.assertEqual(comparable_key[(101, 1)]["reason_code"], "clear_support")
            self.assertEqual(int(comparable_key[(101, 1)]["support_members"]), 1)
            self.assertEqual(int(comparable_key[(101, 1)]["unknown_total"]), 0)

            self.assertEqual(lineage["meta"]["artifact_version"], "citizen_lineage_v1")
            self.assertEqual(len(lineage["rows"]), len(pos))
            lineage_key = {
                (int(row["topic_id"]), int(row["party_id"])): row for row in lineage["rows"]
            }
            lineage_row = lineage_key[(101, 1)]
            self.assertEqual(lineage_row["aggregate"]["computed_method"], "combined")
            self.assertEqual(int(lineage_row["positions"]["total_positions"]), 1)
            self.assertGreaterEqual(int(lineage_row["evidence"]["evidence_rows_total"]), 1)
            self.assertEqual(int(lineage_row["evidence"]["sample_evidence"][0]["evidence_id"]), 10101)

            self.assertEqual(diff["meta"]["artifact_version"], "citizen_snapshot_diff_v1")
            self.assertEqual(diff["meta"]["previous_as_of_date"], "2026-02-10")
            self.assertGreaterEqual(int(diff["meta"]["changed_rows_total"]), 1)
            diff_key = {(int(row["topic_id"]), int(row["party_id"])): row for row in diff["rows"]}
            self.assertIn((101, 2), diff_key)
            self.assertTrue(bool(diff_key[(101, 2)]["stance_changed"]))
            self.assertEqual(diff_key[(101, 2)]["primary_change"], "stance_changed")

            self.assertEqual(robustness["meta"]["artifact_version"], "citizen_ranking_robustness_v1")
            self.assertEqual(robustness["meta"]["computed_method"], "combined")
            self.assertEqual(int(robustness["meta"]["rows_total"]), 2)
            robustness_by_party = {int(row["party_id"]): row for row in robustness["rows"]}
            leader_row = robustness_by_party[1]
            runner_row = robustness_by_party[2]
            self.assertEqual(int(leader_row["rank"]), 1)
            self.assertEqual(int(leader_row["closest_neighbor_party_id"]), 2)
            self.assertEqual(leader_row["focus_pair"]["relation"], "holding_above")
            self.assertEqual(int(leader_row["focus_pair"]["driver_topics_needed"]), 1)
            self.assertEqual(int(leader_row["focus_pair"]["driver_topics"][0]["topic_id"]), 101)
            self.assertEqual(leader_row["rank_band"]["id"], "fragile")
            self.assertEqual(int(runner_row["rank"]), 2)
            self.assertEqual(runner_row["focus_pair"]["relation"], "chasing")

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
