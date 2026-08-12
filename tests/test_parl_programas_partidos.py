from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.declared_positions import (
    backfill_topic_positions_from_declared_evidence,
)
from etl.parlamentario_es.declared_stance import (
    backfill_declared_stance_from_topic_evidence,
)
from etl.parlamentario_es.pipeline import (
    _extract_program_pdf_text,
    _is_programmatic_program_doc,
    _programa_keyword_excerpt_window,
    ingest_one_source as ingest_parl_source,
)
from etl.parlamentario_es.registry import get_connectors
from etl.politicos_es.db import seed_dimensions
from etl.politicos_es.util import normalize_key_part, now_utc_iso, sha256_bytes


SNAPSHOT_DATE = "2026-08-12"
ELECTION_CYCLE = "es_andalucia_2026"
BOE_OFFICIAL_CAPTURE = Path("etl/data/raw/official-captures/boe/boe-rss-20260812.xml")

REAL_PROGRAMS = (
    {
        "party_id": 1,
        "party_name": "Por Un Mundo Más Justo",
        "party_acronym": "MUNDO+JUSTO",
        "source_url": "https://andalucia.porunmundomasjusto.es/assets/descargas/programa-mj-andalucia-2026.pdf",
        "pdf_path": Path(
            "etl/data/raw/elections/andalucia_2026/programas/andalucia_2026_programa_mj.pdf"
        ),
        "text_path": Path(
            "etl/data/raw/elections/andalucia_2026/programas/text/andalucia_2026_programa_mj.txt"
        ),
    },
)
BOE_CONTROL_PARTY = {
    "party_id": 2,
    "party_name": "Partido Socialista Obrero Español de Andalucía",
    "party_acronym": "PSOE-A",
}


def _seed_min_programas_prereqs(conn) -> None:  # type: ignore[no-untyped-def]
    now = now_utc_iso()
    seed_dimensions(conn)
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
    for program in (*REAL_PROGRAMS, BOE_CONTROL_PARTY):
        conn.execute(
            """
            INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(party_id) DO UPDATE SET
              name=excluded.name,
              acronym=excluded.acronym,
              updated_at=excluded.updated_at
            """,
            (
                int(program["party_id"]),
                str(program["party_name"]),
                str(program["party_acronym"]),
                now,
                now,
            ),
        )
    conn.commit()


def _write_real_program_manifest(path: Path) -> Path:
    fields = (
        "party_id",
        "party_name",
        "election_cycle",
        "kind",
        "source_url",
        "format_hint",
        "language",
        "scope",
        "snapshot_date",
        "local_path",
        "notes",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for program in REAL_PROGRAMS:
            writer.writerow(
                {
                    "party_id": program["party_id"],
                    "party_name": program["party_name"],
                    "election_cycle": ELECTION_CYCLE,
                    "kind": "programa",
                    "source_url": program["source_url"],
                    "format_hint": "txt",
                    "language": "es",
                    "scope": "andalucia",
                    "snapshot_date": SNAPSHOT_DATE,
                    "local_path": program["text_path"],
                    "notes": "Texto extraído de PDF electoral público capturado",
                }
            )
    return path


class TestParlProgramasPartidos(unittest.TestCase):
    def test_program_classifier_uses_real_program_and_official_non_program_capture(self) -> None:
        program = REAL_PROGRAMS[0]
        program_text = Path(program["text_path"]).read_text(
            encoding="utf-8",
            errors="replace",
        )[:120000]
        boe_text = BOE_OFFICIAL_CAPTURE.read_text(
            encoding="utf-8",
            errors="replace",
        )[:120000]
        keywords = ["vivienda", "empleo", "sanidad", "educacion", "energia"]

        is_program, program_reason = _is_programmatic_program_doc(
            source_url=str(program["source_url"]),
            text_for_matching=program_text,
            concern_keywords_norm=keywords,
        )
        is_boe_program, boe_reason = _is_programmatic_program_doc(
            source_url="https://www.boe.es/rss/boe.php",
            text_for_matching=boe_text,
            concern_keywords_norm=keywords,
        )

        self.assertTrue(is_program)
        self.assertIn(program_reason, {"policy_pair_hit", "url_program_hint", "text_program_phrase"})
        self.assertFalse(is_boe_program)
        self.assertEqual(boe_reason, "no_programmatic_signal")

    def test_extract_program_pdf_text_from_real_capture(self) -> None:
        pdf_path = Path(REAL_PROGRAMS[0]["pdf_path"])
        self.assertTrue(pdf_path.exists(), f"Missing captured program PDF: {pdf_path}")
        extracted = _extract_program_pdf_text(pdf_path.read_bytes(), pdf_path)
        normalized = normalize_key_part(extracted)
        self.assertGreater(len(normalized), 10_000)
        self.assertIn("andalucia", normalized)
        self.assertIn("vivienda", normalized)

    def test_keyword_excerpt_comes_from_real_program_text(self) -> None:
        program_text = normalize_key_part(
            Path(REAL_PROGRAMS[0]["text_path"]).read_text(
                encoding="utf-8",
                errors="replace",
            )[:120000]
        )
        excerpt = _programa_keyword_excerpt_window(
            program_text,
            ["vivienda", "empleo", "sanidad"],
        )
        self.assertTrue(excerpt)
        self.assertTrue(any(token in excerpt for token in ("vivienda", "empleo", "sanidad")))
        self.assertIn(excerpt, program_text)

    def test_real_program_ingest_is_idempotent_traceable_and_position_ready(self) -> None:
        connector = get_connectors()["programas_partidos"]

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_dir = td_path / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = _write_real_program_manifest(td_path / "programas.csv")
            conn = open_db(td_path / "parl-programas.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                _seed_min_programas_prereqs(conn)

                seen_1, loaded_1, _ = ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=SNAPSHOT_DATE,
                    strict_network=True,
                    options={},
                )
                self.assertEqual(int(seen_1), len(REAL_PROGRAMS))
                self.assertEqual(int(loaded_1), len(REAL_PROGRAMS))

                rows_1 = conn.execute(
                    """
                    SELECT source_record_id, source_record_pk, content_sha256
                    FROM source_records
                    WHERE source_id='programas_partidos'
                    ORDER BY source_record_id
                    """
                ).fetchall()
                self.assertEqual(len(rows_1), len(REAL_PROGRAMS))
                pk_by_id_1 = {
                    str(row["source_record_id"]): int(row["source_record_pk"])
                    for row in rows_1
                }
                for program in REAL_PROGRAMS:
                    source_record_id = (
                        f"programas_partidos:{ELECTION_CYCLE}:"
                        f"{int(program['party_id'])}:programa"
                    )
                    row = next(
                        item
                        for item in rows_1
                        if str(item["source_record_id"]) == source_record_id
                    )
                    self.assertEqual(
                        str(row["content_sha256"]),
                        sha256_bytes(Path(program["text_path"]).read_bytes()),
                    )

                evidence_rows_1 = conn.execute(
                    """
                    SELECT evidence_id, topic_id, person_id, source_record_pk
                    FROM topic_evidence
                    WHERE source_id='programas_partidos'
                      AND evidence_type='declared:programa'
                    ORDER BY evidence_id
                    """
                ).fetchall()
                self.assertGreater(len(evidence_rows_1), 0)
                evidence_keys_1 = {
                    (
                        int(row["topic_id"]),
                        int(row["person_id"]),
                        int(row["source_record_pk"]),
                    ): int(row["evidence_id"])
                    for row in evidence_rows_1
                }

                seen_2, loaded_2, _ = ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=SNAPSHOT_DATE,
                    strict_network=True,
                    options={},
                )
                self.assertEqual(int(seen_2), len(REAL_PROGRAMS))
                self.assertEqual(int(loaded_2), len(REAL_PROGRAMS))

                rows_2 = conn.execute(
                    """
                    SELECT source_record_id, source_record_pk
                    FROM source_records
                    WHERE source_id='programas_partidos'
                    ORDER BY source_record_id
                    """
                ).fetchall()
                self.assertEqual(
                    pk_by_id_1,
                    {
                        str(row["source_record_id"]): int(row["source_record_pk"])
                        for row in rows_2
                    },
                )
                evidence_rows_2 = conn.execute(
                    """
                    SELECT evidence_id, topic_id, person_id, source_record_pk
                    FROM topic_evidence
                    WHERE source_id='programas_partidos'
                      AND evidence_type='declared:programa'
                    ORDER BY evidence_id
                    """
                ).fetchall()
                self.assertEqual(
                    evidence_keys_1,
                    {
                        (
                            int(row["topic_id"]),
                            int(row["person_id"]),
                            int(row["source_record_pk"]),
                        ): int(row["evidence_id"])
                        for row in evidence_rows_2
                    },
                )

                stance_result = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="programas_partidos",
                    limit=0,
                    min_auto_confidence=0.62,
                    enable_review_queue=True,
                    dry_run=False,
                )
                self.assertGreater(
                    sum(
                        int(stance_result.get(key, 0))
                        for key in ("support", "oppose", "review_pending")
                    ),
                    0,
                )
                position_result = backfill_topic_positions_from_declared_evidence(
                    conn,
                    source_id="programas_partidos",
                    as_of_date=SNAPSHOT_DATE,
                    computed_method="declared",
                    computed_version="v1",
                    dry_run=False,
                )
                self.assertGreaterEqual(int(position_result.get("positions_total", 0)), 1)
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()

    def test_real_non_program_capture_is_traceable_but_creates_no_program_evidence(self) -> None:
        connector = get_connectors()["programas_partidos"]
        self.assertTrue(BOE_OFFICIAL_CAPTURE.exists())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            manifest_path = td_path / "programas-filter.csv"
            fields = (
                "party_id",
                "party_name",
                "election_cycle",
                "kind",
                "source_url",
                "format_hint",
                "language",
                "scope",
                "snapshot_date",
                "local_path",
                "notes",
            )
            with manifest_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "party_id": REAL_PROGRAMS[0]["party_id"],
                        "party_name": REAL_PROGRAMS[0]["party_name"],
                        "election_cycle": ELECTION_CYCLE,
                        "kind": "programa",
                        "source_url": REAL_PROGRAMS[0]["source_url"],
                        "format_hint": "txt",
                        "language": "es",
                        "scope": "andalucia",
                        "snapshot_date": SNAPSHOT_DATE,
                        "local_path": REAL_PROGRAMS[0]["text_path"],
                        "notes": "Texto extraído de PDF electoral público capturado",
                    }
                )
                writer.writerow(
                    {
                        "party_id": BOE_CONTROL_PARTY["party_id"],
                        "party_name": BOE_CONTROL_PARTY["party_name"],
                        "election_cycle": ELECTION_CYCLE,
                        "kind": "programa",
                        "source_url": "https://www.boe.es/rss/boe.php",
                        "format_hint": "xml",
                        "language": "es",
                        "scope": "nacional",
                        "snapshot_date": SNAPSHOT_DATE,
                        "local_path": BOE_OFFICIAL_CAPTURE,
                        "notes": "Control negativo oficial: RSS del BOE capturado",
                    }
                )

            conn = open_db(td_path / "parl-programas-filter.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                _seed_min_programas_prereqs(conn)
                seen, loaded, message = ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=td_path / "raw",
                    timeout=5,
                    from_file=manifest_path,
                    url_override=None,
                    snapshot_date=SNAPSHOT_DATE,
                    strict_network=True,
                    options={},
                )
                self.assertEqual(int(seen), 2)
                self.assertEqual(int(loaded), 2)
                message_obj = json.loads(str(message or "{}"))
                skipped = (((message_obj.get("out") or {}).get("info") or {}).get("skipped") or {})
                self.assertEqual(int(skipped.get("non_program_doc", 0)), 1)

                boe_source_record_id = (
                    f"programas_partidos:{ELECTION_CYCLE}:"
                    f"{int(BOE_CONTROL_PARTY['party_id'])}:programa"
                )
                boe_evidence = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM topic_evidence AS e
                    JOIN source_records AS sr ON sr.source_record_pk=e.source_record_pk
                    WHERE e.source_id='programas_partidos'
                      AND sr.source_record_id=?
                    """,
                    (boe_source_record_id,),
                ).fetchone()
                self.assertEqual(int(boe_evidence["c"]), 0)
                self.assertEqual(
                    int(
                        conn.execute(
                            "SELECT COUNT(*) AS c FROM source_records WHERE source_id='programas_partidos'"
                        ).fetchone()["c"]
                    ),
                    2,
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
