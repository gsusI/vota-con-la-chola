from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources as seed_politicos_sources
from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso

from etl.parlamentario_es.config import SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import seed_sources as seed_parl_sources
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors as get_parl_connectors


def _orador_full_name(raw: str) -> str:
    text = normalize_ws(raw)
    if not text:
        return ""
    base = text.split("(", 1)[0].strip()
    if "," in base:
        family, given = [normalize_ws(part) for part in base.split(",", 1)]
        return normalize_ws(f"{given} {family}")
    return base


class TestCongresoIntervencionesSamplesE2E(unittest.TestCase):
    def test_congreso_intervenciones_sample_is_idempotent_and_inserts_evidence(self) -> None:
        connectors = get_parl_connectors()
        connector = connectors["congreso_intervenciones"]
        snapshot_date = "2026-02-12"

        sample_path = Path(PARL_SOURCE_CONFIG["congreso_intervenciones"]["fallback_file"])
        self.assertTrue(sample_path.exists(), f"Missing sample: {sample_path}")

        items = json.loads(sample_path.read_text(encoding="utf-8"))
        self.assertIsInstance(items, list)
        target = None
        for item in items:
            if not isinstance(item, dict):
                continue
            orador = normalize_ws(str(item.get("ORADOR") or ""))
            if "Requena Ruiz" in orador:
                target = item
                break
        self.assertIsNotNone(target, "Sample must include a recognizable ORADOR (Requena Ruiz...)")

        leg_raw = normalize_ws(str(target.get("LEGISLATURA") or ""))
        m = re.search(r"(\d+)", leg_raw)
        self.assertIsNotNone(m, f"Expected legislature in sample LEG: {leg_raw!r}")
        legislature = str(int(m.group(1)))

        expediente = normalize_ws(str(target.get("NUMEXPEDIENTE") or ""))
        self.assertTrue(expediente, "Expected NUMEXPEDIENTE in sample")
        initiative_id = f"congreso:leg{legislature}:exp:{expediente}"

        title = normalize_ws(str(target.get("OBJETOINICIATIVA") or "")) or initiative_id
        person_full_name = _orador_full_name(normalize_ws(str(target.get("ORADOR") or "")))
        self.assertTrue(person_full_name, "Expected ORADOR full name")

        now_iso = now_utc_iso()

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_politicos_sources(conn)
                seed_dimensions(conn)
                seed_parl_sources(conn)

                # Minimal anchors required by _ingest_congreso_intervenciones:
                # - person+mandate in mandates[source_id='congreso_diputados'] so ORADOR can resolve to person_id
                # - institution + topic_set for Congreso + legislature
                # - parl_initiatives row so topic_evidence.initiative_id FK can be satisfied
                with conn:
                    conn.execute(
                        """
                        INSERT INTO territories (code, name, level, parent_territory_id, created_at, updated_at)
                        VALUES ('ES', 'España', 'country', NULL, ?, ?)
                        ON CONFLICT(code) DO UPDATE SET
                          name=excluded.name,
                          level=excluded.level,
                          updated_at=excluded.updated_at
                        """,
                        (now_iso, now_iso),
                    )

                    row = conn.execute("SELECT territory_id FROM territories WHERE code = 'ES'").fetchone()
                    self.assertIsNotNone(row)
                    es_territory_id = int(row["territory_id"])

                    row = conn.execute("SELECT admin_level_id FROM admin_levels WHERE code = 'nacional'").fetchone()
                    self.assertIsNotNone(row)
                    admin_level_id = int(row["admin_level_id"])

                    conn.execute(
                        """
                        INSERT INTO institutions (
                          name, level, admin_level_id, territory_code, territory_id, created_at, updated_at
                        ) VALUES (?, ?, ?, '', ?, ?, ?)
                        ON CONFLICT(name, level, territory_code) DO UPDATE SET
                          admin_level_id=excluded.admin_level_id,
                          territory_id=excluded.territory_id,
                          updated_at=excluded.updated_at
                        """,
                        ("Congreso de los Diputados", "nacional", admin_level_id, es_territory_id, now_iso, now_iso),
                    )
                    row = conn.execute(
                        """
                        SELECT institution_id
                        FROM institutions
                        WHERE name = 'Congreso de los Diputados' AND level = 'nacional' AND territory_code = ''
                        """
                    ).fetchone()
                    self.assertIsNotNone(row)
                    institution_id = int(row["institution_id"])

                    person_ckey = normalize_key_part(person_full_name)
                    conn.execute(
                        """
                        INSERT INTO persons (
                          full_name, given_name, family_name,
                          gender, gender_id,
                          birth_date, territory_code, territory_id,
                          canonical_key, created_at, updated_at
                        ) VALUES (?, NULL, NULL, NULL, NULL, NULL, '', NULL, ?, ?, ?)
                        ON CONFLICT(canonical_key) DO UPDATE SET
                          full_name=excluded.full_name,
                          updated_at=excluded.updated_at
                        """,
                        (person_full_name, person_ckey, now_iso, now_iso),
                    )
                    row = conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (person_ckey,),
                    ).fetchone()
                    self.assertIsNotNone(row)
                    person_id = int(row["person_id"])

                    conn.execute(
                        """
                        INSERT INTO mandates (
                          person_id, institution_id, party_id,
                          role_title, role_id,
                          level, admin_level_id,
                          territory_code, territory_id,
                          start_date, end_date, is_active,
                          source_id, source_record_id, source_record_pk, source_snapshot_date,
                          first_seen_at, last_seen_at, raw_payload
                        ) VALUES (?, ?, NULL, 'Diputado', NULL, 'nacional', ?, '', ?, NULL, NULL, 1, 'congreso_diputados', 'test:jdrr', NULL, ?, ?, ?, '{}')
                        ON CONFLICT(source_id, source_record_id) DO UPDATE SET
                          person_id=excluded.person_id,
                          institution_id=excluded.institution_id,
                          admin_level_id=excluded.admin_level_id,
                          territory_id=excluded.territory_id,
                          is_active=excluded.is_active,
                          last_seen_at=excluded.last_seen_at,
                          raw_payload=excluded.raw_payload
                        """,
                        (person_id, institution_id, admin_level_id, es_territory_id, snapshot_date, now_iso, now_iso),
                    )

                    conn.execute(
                        """
                        INSERT INTO parl_initiatives (
                          initiative_id, legislature, expediente, title,
                          source_id, source_url, source_record_pk, source_snapshot_date,
                          raw_payload, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'congreso_iniciativas', NULL, NULL, ?, '{}', ?, ?)
                        ON CONFLICT(initiative_id) DO UPDATE SET
                          title=excluded.title,
                          updated_at=excluded.updated_at
                        """,
                        (initiative_id, legislature, expediente, title, snapshot_date, now_iso, now_iso),
                    )

                    conn.execute(
                        """
                        INSERT INTO topic_sets (
                          name, description,
                          institution_id, admin_level_id, territory_id,
                          legislature, valid_from, valid_to,
                          is_active, created_at, updated_at
                        ) VALUES (?, 'test topic_set', ?, ?, ?, ?, NULL, NULL, 1, ?, ?)
                        ON CONFLICT(name, institution_id, admin_level_id, territory_id, legislature) DO UPDATE SET
                          updated_at=excluded.updated_at
                        """,
                        (
                            "Congreso de los Diputados / leg 15 / votaciones (auto)",
                            institution_id,
                            admin_level_id,
                            es_territory_id,
                            legislature,
                            now_iso,
                            now_iso,
                        ),
                    )
                    row = conn.execute(
                        """
                        SELECT topic_set_id
                        FROM topic_sets
                        WHERE name = ?
                          AND institution_id = ?
                          AND admin_level_id = ?
                          AND territory_id = ?
                          AND legislature = ?
                        """,
                        (
                            "Congreso de los Diputados / leg 15 / votaciones (auto)",
                            institution_id,
                            admin_level_id,
                            es_territory_id,
                            legislature,
                        ),
                    ).fetchone()
                    self.assertIsNotNone(row)
                    topic_set_id = int(row["topic_set_id"])

                    conn.execute(
                        """
                        INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
                        VALUES (?, ?, NULL, NULL, ?, ?)
                        ON CONFLICT(canonical_key) DO UPDATE SET
                          label=excluded.label,
                          updated_at=excluded.updated_at
                        """,
                        (initiative_id, title, now_iso, now_iso),
                    )
                    row = conn.execute(
                        "SELECT topic_id FROM topics WHERE canonical_key = ?",
                        (initiative_id,),
                    ).fetchone()
                    self.assertIsNotNone(row)
                    topic_id = int(row["topic_id"])

                    conn.execute(
                        """
                        INSERT INTO topic_set_topics (
                          topic_set_id, topic_id,
                          stakes_score, stakes_rank, is_high_stakes, notes,
                          created_at, updated_at
                        ) VALUES (?, ?, 1.0, 1, 1, 'test', ?, ?)
                        ON CONFLICT(topic_set_id, topic_id) DO UPDATE SET
                          updated_at=excluded.updated_at
                        """,
                        (topic_set_id, topic_id, now_iso, now_iso),
                    )

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

                ev1 = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM topic_evidence WHERE source_id = 'congreso_intervenciones' AND evidence_type = 'declared:intervention'"
                    ).fetchone()["c"]
                )
                self.assertGreaterEqual(ev1, 1)

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

                ev2 = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM topic_evidence WHERE source_id = 'congreso_intervenciones' AND evidence_type = 'declared:intervention'"
                    ).fetchone()["c"]
                )
                self.assertEqual(ev1, ev2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

