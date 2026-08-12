from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from publicdata_connectors_es.infoelectoral.candidates import (
    CandidateArchiveMetrics,
    CandidateArchiveSpec,
    iter_candidate_archive,
)
from etl.infoelectoral_es.candidates import (
    candidate_report,
    ingest_candidate_archive,
    upsert_candidate_archive_catalog,
)
from etl.infoelectoral_es.db import seed_sources
from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema
from publicdata_sqlite import open_db
from scripts.ingest_infoelectoral_candidates import (
    _catalog_specs,
    build_report,
    enqueue_catalog,
    run_worker,
)


def _put(chars: list[str], start: int, end: int, value: str) -> None:
    encoded = value.ljust(end - start)[: end - start]
    chars[start:end] = list(encoded)


def _party_line() -> bytes:
    chars = [" "] * 232
    _put(chars, 0, 2, "04")
    _put(chars, 2, 6, "2023")
    _put(chars, 6, 8, "05")
    _put(chars, 8, 14, "000123")
    _put(chars, 14, 64, "PE")
    _put(chars, 64, 214, "PARTIDO EJEMPLO")
    _put(chars, 214, 220, "000123")
    _put(chars, 220, 226, "000123")
    _put(chars, 226, 232, "000123")
    return "".join(chars).encode("iso-8859-1")


def _candidate_line(*, full_name: tuple[str, str, str] = ("MARÍA", "PÉREZ", "LÓPEZ")) -> bytes:
    chars = [" "] * 120
    _put(chars, 0, 2, "04")
    _put(chars, 2, 6, "2023")
    _put(chars, 6, 8, "05")
    _put(chars, 8, 9, "1")
    _put(chars, 9, 11, "28")
    _put(chars, 11, 12, "9")
    _put(chars, 12, 15, "079")
    _put(chars, 15, 21, "000123")
    _put(chars, 21, 24, "001")
    _put(chars, 24, 25, "T")
    _put(chars, 25, 50, full_name[0])
    _put(chars, 50, 75, full_name[1])
    _put(chars, 75, 100, full_name[2])
    _put(chars, 100, 101, "M")
    _put(chars, 101, 109, "01011980")
    _put(chars, 109, 119, "12345678Z")
    _put(chars, 119, 120, "N")
    return "".join(chars).encode("iso-8859-1")


def _write_archive(path: Path, *, duplicate: bool = False) -> None:
    candidate_lines = [_candidate_line()]
    if duplicate:
        candidate_lines.append(
            _candidate_line(full_name=("OTRA", "PERSONA", "DUPLICADA"))
        )
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("03042305.DAT", _party_line() + b"\r\n")
        archive.writestr("04042305.DAT", b"\r\n".join(candidate_lines) + b"\r\n")


def _spec() -> CandidateArchiveSpec:
    return CandidateArchiveSpec(
        archive_id="tipo:4|conv:202305|doc:04202305_MUNI.zip",
        source_url=(
            "https://infoelectoral.interior.gob.es/estaticos/docxl/"
            "apliextr/04202305_MUNI.zip"
        ),
        election_date="2023-05-28",
        election_type_code="04",
        election_id="202305",
    )


def _insert_catalog_archive(conn) -> None:
    now_iso = "2026-08-11T00:00:00Z"
    conn.execute(
        """
        INSERT INTO infoelectoral_convocatoria_tipos (
          tipo_convocatoria, descripcion, source_id, raw_payload,
          created_at, updated_at
        ) VALUES ('04', 'Municipales', 'infoelectoral_descargas', '{}', ?, ?)
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO infoelectoral_convocatorias (
          convocatoria_id, tipo_convocatoria, cod, fecha, descripcion,
          ambito_territorio, source_id, raw_payload, created_at, updated_at
        ) VALUES (
          'conv-202305', '04', '202305', '2023-05-28',
          'Elecciones municipales', 'España', 'infoelectoral_descargas',
          '{}', ?, ?
        )
        """,
        (now_iso, now_iso),
    )
    conn.execute(
        """
        INSERT INTO infoelectoral_archivos_extraccion (
          archivo_id, convocatoria_id, tipo_convocatoria, id_convocatoria,
          descripcion, nombre_doc, ambito, download_url, source_id,
          raw_payload, created_at, updated_at
        ) VALUES (
          ?, 'conv-202305', '04', '202305',
          'Elecciones municipales de 28 de mayo de 2023',
          '04202305_MUNI.zip', 'Municipal', ?, 'infoelectoral_descargas',
          '{}', ?, ?
        )
        """,
        (_spec().archive_id, _spec().source_url, now_iso, now_iso),
    )
    conn.commit()


def _run_fixture_worker(conn, *, local_dir: Path, store_root: Path):
    return run_worker(
        conn,
        pipeline_id="candidate-fixture-v1",
        worker_id="candidate-fixture-worker",
        store_root=store_root,
        local_archive_dir=local_dir,
        timeout=5,
        max_items=1,
        batch_rows=1,
        max_archive_bytes=1024 * 1024,
        max_uncompressed_bytes=1024 * 1024,
        max_candidate_rows=10,
        max_members=10,
        max_party_rows=10,
        max_compression_ratio=250.0,
        min_free_bytes=0,
        max_row_drift_ratio=0.15,
        allow_large_drift=False,
        insecure_ssl=False,
        ca_bundle=None,
    )


class TestInfoelectoralCandidates(unittest.TestCase):
    def test_parser_retains_public_domain_dni_and_birth_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "candidates.zip"
            _write_archive(path)
            records = list(
                iter_candidate_archive(
                    path,
                    spec=_spec(),
                    source_content_sha256="a" * 64,
                )
            )
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.full_name, "MARÍA PÉREZ LÓPEZ")
        self.assertEqual(record.candidacy_name, "PARTIDO EJEMPLO")
        self.assertEqual(record.province_code, "28")
        self.assertEqual(record.gender_code, "M")
        self.assertEqual(record.birth_date, "1980-01-01")
        self.assertEqual(record.birth_date_source, "01011980")
        self.assertEqual(record.dni, "12345678Z")
        payload = record.public_source_payload()
        self.assertIn("12345678Z", payload)
        self.assertIn("01011980", payload)

    def test_parser_reports_candidate_and_party_source_row_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "candidates.zip"
            _write_archive(path)
            metrics = CandidateArchiveMetrics()
            records = list(
                iter_candidate_archive(
                    path,
                    spec=_spec(),
                    source_content_sha256="a" * 64,
                    metrics=metrics,
                )
            )
        self.assertEqual(len(records), 1)
        self.assertEqual(metrics.candidate_rows, 1)
        self.assertEqual(metrics.party_rows, 1)

    def test_parser_rejects_duplicate_natural_occurrence_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "candidates.zip"
            _write_archive(path, duplicate=True)
            with self.assertRaisesRegex(RuntimeError, "duplicate candidate"):
                list(
                    iter_candidate_archive(
                        path,
                        spec=_spec(),
                        source_content_sha256="b" * 64,
                    )
                )

    def test_parser_rejects_unsafe_zip_member(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "candidates.zip"
            with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
                archive.writestr("../03042305.DAT", _party_line())
                archive.writestr("04042305.DAT", _candidate_line())
            with self.assertRaisesRegex(RuntimeError, "unsafe member"):
                list(
                    iter_candidate_archive(
                        path,
                        spec=_spec(),
                        source_content_sha256="c" * 64,
                    )
                )

    def test_ingest_is_idempotent_and_preserves_removed_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "candidates.zip"
            _write_archive(path)
            base = list(
                iter_candidate_archive(
                    path,
                    spec=_spec(),
                    source_content_sha256="d" * 64,
                )
            )[0]
            removed = replace(
                base,
                candidate_occurrence_id="infoelectoral-candidate:removed",
                source_record_id="infoelectoral-candidate:removed",
                candidate_order=2,
                full_name="OTRA PERSONA CANDIDATA",
                given_name="OTRA",
                surname_1="PERSONA",
                surname_2="CANDIDATA",
                source_line_number=2,
            )
            conn = open_db(root / "candidates.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                upsert_candidate_archive_catalog(
                    conn,
                    spec=_spec(),
                    snapshot_date="2026-08-11",
                )
                first = ingest_candidate_archive(
                    conn,
                    [base, removed],
                    spec=_spec(),
                    snapshot_date="2026-08-11",
                    source_content_sha256="d" * 64,
                    archive_bytes=path.stat().st_size,
                    raw_path="etl/data/object-origin/restricted/test.zip",
                    party_rows=1,
                    batch_rows=1,
                )
                second = ingest_candidate_archive(
                    conn,
                    [base],
                    spec=_spec(),
                    snapshot_date="2026-08-12",
                    source_content_sha256="d" * 64,
                    archive_bytes=path.stat().st_size,
                    raw_path="etl/data/object-origin/restricted/test.zip",
                    party_rows=1,
                )
                report = candidate_report(conn)
                self.assertEqual(first["processed"], 2)
                self.assertEqual(second["processed"], 1)
                self.assertEqual(report["status"], "ok")
                self.assertEqual(report["totals"]["candidate_occurrences"], 2)
                self.assertEqual(
                    report["totals"]["present_candidate_occurrences"], 1
                )
                self.assertEqual(
                    report["totals"]["absent_candidate_occurrences"], 1
                )
                self.assertEqual(report["totals"]["observations"], 3)
                self.assertEqual(report["totals"]["source_party_rows"], 1)
                self.assertTrue(report["checks"]["archive_candidate_rows_reconcile"])
                self.assertTrue(report["checks"]["loaded_archives_have_party_rows"])
                payloads = "\n".join(
                    str(row[0])
                    for row in conn.execute(
                        "SELECT raw_payload FROM source_records "
                        "WHERE source_id='infoelectoral_candidates'"
                    )
                )
                self.assertIn("12345678Z", payloads)
                self.assertIn("01011980", payloads)
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()

    def test_catalog_enqueue_creates_one_stable_pending_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = open_db(Path(temp_dir) / "catalog.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                _insert_catalog_archive(conn)
                specs = _catalog_specs(conn)
                first = enqueue_catalog(
                    conn,
                    pipeline_id="candidate-fixture-v1",
                    snapshot_date="2026-08-11",
                    max_archive_bytes=1024 * 1024,
                    max_attempts=3,
                )
                second = enqueue_catalog(
                    conn,
                    pipeline_id="candidate-fixture-v1",
                    snapshot_date="2026-08-11",
                    max_archive_bytes=1024 * 1024,
                    max_attempts=3,
                )
                self.assertEqual(specs, [_spec()])
                self.assertEqual(first["enqueue"]["inserted_total"], 1)
                self.assertEqual(second["enqueue"]["inserted_total"], 0)
                self.assertEqual(second["queue"]["items_total"], 1)
                self.assertEqual(second["queue"]["state_counts"]["pending"], 1)
            finally:
                conn.close()

    def test_local_replay_worker_loads_provenance_and_completes_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_dir = root / "incoming"
            local_dir.mkdir()
            _write_archive(local_dir / "04202305_MUNI.zip")
            conn = open_db(root / "worker.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                _insert_catalog_archive(conn)
                enqueue_catalog(
                    conn,
                    pipeline_id="candidate-fixture-v1",
                    snapshot_date="2026-08-11",
                    max_archive_bytes=1024 * 1024,
                    max_attempts=1,
                )
                payload = json.loads(
                    conn.execute(
                        "SELECT payload_json FROM pipeline_work_items"
                    ).fetchone()[0]
                )
                payload["minimum_candidate_rows"] = 1
                conn.execute(
                    "UPDATE pipeline_work_items SET payload_json=?",
                    (json.dumps(payload, sort_keys=True),),
                )
                conn.commit()
                worker = _run_fixture_worker(
                    conn,
                    local_dir=local_dir,
                    store_root=root / "restricted-store",
                )
                report = build_report(
                    conn,
                    pipeline_id="candidate-fixture-v1",
                    db_path=root / "worker.db",
                )
                self.assertEqual(worker["status"], "ok")
                self.assertEqual(worker["succeeded"], 1)
                self.assertEqual(worker["archives"][0]["acquisition_mode"], "local_replay")
                self.assertEqual(worker["archives"][0]["party_rows"], 1)
                self.assertEqual(report["queue"]["state_counts"]["succeeded"], 1)
                self.assertEqual(report["facts"]["totals"]["candidate_occurrences"], 1)
                self.assertEqual(report["facts"]["totals"]["source_party_rows"], 1)
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM raw_fetches "
                        "WHERE source_id='infoelectoral_candidates'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM run_fetches "
                        "WHERE source_id='infoelectoral_candidates'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()

    def test_worker_blocks_large_archive_row_drift_before_fact_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            local_dir = root / "incoming"
            local_dir.mkdir()
            _write_archive(local_dir / "04202305_MUNI.zip")
            conn = open_db(root / "drift.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                _insert_catalog_archive(conn)
                enqueue_catalog(
                    conn,
                    pipeline_id="candidate-fixture-v1",
                    snapshot_date="2026-08-11",
                    max_archive_bytes=1024 * 1024,
                    max_attempts=1,
                )
                payload = json.loads(
                    conn.execute(
                        "SELECT payload_json FROM pipeline_work_items"
                    ).fetchone()[0]
                )
                payload["minimum_candidate_rows"] = 1
                conn.execute(
                    "UPDATE pipeline_work_items SET payload_json=?",
                    (json.dumps(payload, sort_keys=True),),
                )
                conn.execute(
                    "UPDATE infoelectoral_candidate_archives "
                    "SET candidate_rows=100, status='loaded'"
                )
                conn.commit()
                worker = _run_fixture_worker(
                    conn,
                    local_dir=local_dir,
                    store_root=root / "restricted-store",
                )
                self.assertEqual(worker["status"], "partial")
                self.assertEqual(worker["failed"], 1)
                self.assertIn("source drift blocked", worker["archives"][0]["error"])
                self.assertEqual(
                    conn.execute(
                        "SELECT state FROM pipeline_work_items"
                    ).fetchone()[0],
                    "dead",
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM infoelectoral_candidate_occurrences"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM raw_fetches "
                        "WHERE source_id='infoelectoral_candidates'"
                    ).fetchone()[0],
                    0,
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
