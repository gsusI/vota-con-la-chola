from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.declared_positions import backfill_topic_positions_from_declared_evidence
from etl.parlamentario_es.declared_stance import backfill_declared_stance_from_topic_evidence
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors
from etl.politicos_es.db import seed_dimensions
from etl.politicos_es.util import now_utc_iso, sha256_bytes


def _seed_min_programas_prereqs(conn) -> None:  # type: ignore[no-untyped-def]
    now = now_utc_iso()
    seed_dimensions(conn)

    # Minimal territory anchor used by programas topic_set.
    conn.execute(
        """
        INSERT INTO territories (code, name, level, parent_territory_id, created_at, updated_at)
        VALUES ('ES', 'España', 'nacional', NULL, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
          name=excluded.name,
          level=excluded.level,
          updated_at=excluded.updated_at
        """,
        (now, now),
    )

    # Minimal parties referenced by the sample manifest.
    for pid, name in ((1, "PSOE"), (2, "PP"), (29, "SUMAR")):
        conn.execute(
            """
            INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(party_id) DO UPDATE SET
              name=excluded.name,
              acronym=excluded.acronym,
              updated_at=excluded.updated_at
            """,
            (int(pid), str(name), str(name), now, now),
        )
    conn.commit()


class TestParlProgramasPartidos(unittest.TestCase):
    def test_programas_partidos_sample_ingest_is_idempotent_and_traceable(self) -> None:
        connectors = get_connectors()
        connector = connectors["programas_partidos"]
        snapshot_date = "2026-02-17"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "parl-programas.db"
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                _seed_min_programas_prereqs(conn)

                manifest_path = Path(PARL_SOURCE_CONFIG["programas_partidos"]["fallback_file"])
                self.assertTrue(manifest_path.exists(), f"Missing sample manifest: {manifest_path}")

                seen1, loaded1, _msg1 = ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )
                self.assertEqual(int(seen1), 3)
                self.assertEqual(int(loaded1), 3)

                # Basic storage counts.
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM source_records WHERE source_id = 'programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    3,
                )
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM text_documents WHERE source_id = 'programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    3,
                )
                evidence_total_1 = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(evidence_total_1, 11)

                # topic_set created exactly once for the election_cycle.
                ts = conn.execute(
                    """
                    SELECT topic_set_id
                    FROM topic_sets
                    WHERE name = 'Programas de partidos'
                      AND legislature = 'es_generales_2023'
                    ORDER BY topic_set_id DESC
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(ts)
                topic_set_id = int(ts["topic_set_id"])
                ts_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_sets
                        WHERE name = 'Programas de partidos'
                          AND legislature = 'es_generales_2023'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(ts_count, 1)

                # Full topic_set_topics list derived from concerns config (stable size).
                concerns = json.loads(Path("ui/citizen/concerns_v1.json").read_text(encoding="utf-8"))["concerns"]
                expected_topics = len(concerns)
                self.assertGreaterEqual(expected_topics, 10)
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM topic_set_topics WHERE topic_set_id = ?",
                            (topic_set_id,),
                        ).fetchone()["c"]
                    ),
                    expected_topics,
                )

                # source_record_id and content_sha256 match the referenced doc bytes.
                rows = conn.execute(
                    """
                    SELECT source_record_id, content_sha256, source_record_pk
                    FROM source_records
                    WHERE source_id = 'programas_partidos'
                    ORDER BY source_record_id ASC
                    """
                ).fetchall()
                self.assertEqual(len(rows), 3)
                pk_by_id = {str(r["source_record_id"]): int(r["source_record_pk"]) for r in rows}

                for party_id, local_path in (
                    (1, "etl/data/raw/samples/programas_partidos/psoe_programa_sample.html"),
                    (2, "etl/data/raw/samples/programas_partidos/pp_programa_sample.html"),
                    (29, "etl/data/raw/samples/programas_partidos/sumar_programa_sample.html"),
                ):
                    srid = f"programas_partidos:es_generales_2023:{int(party_id)}:programa"
                    expected_sha = sha256_bytes(Path(local_path).read_bytes())
                    row = conn.execute(
                        """
                        SELECT content_sha256
                        FROM source_records
                        WHERE source_id = 'programas_partidos' AND source_record_id = ?
                        """,
                        (srid,),
                    ).fetchone()
                    self.assertIsNotNone(row)
                    self.assertEqual(str(row["content_sha256"]), expected_sha)

                # text_documents raw bytes were persisted under the passed raw_dir.
                td = conn.execute(
                    """
                    SELECT raw_path
                    FROM text_documents
                    WHERE source_id = 'programas_partidos'
                    ORDER BY source_record_pk ASC
                    """
                ).fetchall()
                self.assertEqual(len(td), 3)
                for r in td:
                    p = Path(str(r["raw_path"] or ""))
                    self.assertTrue(p.exists(), f"Missing raw bytes file: {p}")
                    self.assertTrue(str(p).startswith(str(raw_dir)), f"raw_path not under raw_dir: {p}")

                # Capture key set for evidence rows (ignore evidence_id autoincrement).
                ev_keys_1 = {
                    (
                        int(r["topic_id"]),
                        int(r["person_id"]),
                        str(r["title"] or ""),
                        int(r["source_record_pk"]),
                    )
                    for r in conn.execute(
                        """
                        SELECT topic_id, person_id, title, source_record_pk
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchall()
                }
                self.assertEqual(len(ev_keys_1), evidence_total_1)

                # Re-run ingest: counts and key sets remain stable; no duplicated topic_sets/institutions.
                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )

                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM source_records WHERE source_id = 'programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    3,
                )
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM text_documents WHERE source_id = 'programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    3,
                )
                evidence_total_2 = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(evidence_total_2, evidence_total_1)

                ev_keys_2 = {
                    (
                        int(r["topic_id"]),
                        int(r["person_id"]),
                        str(r["title"] or ""),
                        int(r["source_record_pk"]),
                    )
                    for r in conn.execute(
                        """
                        SELECT topic_id, person_id, title, source_record_pk
                        FROM topic_evidence
                        WHERE source_id = 'programas_partidos'
                          AND evidence_type = 'declared:programa'
                        """
                    ).fetchall()
                }
                self.assertEqual(ev_keys_1, ev_keys_2)

                rows2 = conn.execute(
                    """
                    SELECT source_record_id, source_record_pk
                    FROM source_records
                    WHERE source_id = 'programas_partidos'
                    ORDER BY source_record_id ASC
                    """
                ).fetchall()
                pk_by_id_2 = {str(r["source_record_id"]): int(r["source_record_pk"]) for r in rows2}
                self.assertEqual(pk_by_id, pk_by_id_2)

                inst_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM institutions
                        WHERE name = 'Programas de partidos'
                          AND level = 'editorial'
                          AND territory_code = ''
                        """
                    ).fetchone()["c"]
                )
                self.assertEqual(inst_count, 1)

                # Declared stance signal should exist for the sample (support + oppose).
                stance_res = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="programas_partidos",
                    limit=0,
                    min_auto_confidence=0.62,
                    enable_review_queue=True,
                    dry_run=False,
                )
                self.assertGreaterEqual(int(stance_res.get("support", 0)), 1)
                self.assertGreaterEqual(int(stance_res.get("oppose", 0)), 1)

                # Declared positions should be computable from the signaled rows.
                pos_res = backfill_topic_positions_from_declared_evidence(
                    conn,
                    source_id="programas_partidos",
                    as_of_date=snapshot_date,
                    computed_method="declared",
                    computed_version="v1",
                    dry_run=False,
                )
                self.assertGreaterEqual(int(pos_res.get("positions_total", 0)), 1)

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

