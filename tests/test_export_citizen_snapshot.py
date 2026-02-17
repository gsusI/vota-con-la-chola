from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema


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


class TestExportCitizenSnapshot(unittest.TestCase):
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
            self.assertIn("methods_available", meta)
            self.assertEqual(meta["methods_available"], ["combined", "votes"])

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
