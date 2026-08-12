from __future__ import annotations

import argparse
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from etl.infoelectoral_es.db import seed_sources
from etl.infoelectoral_es.elected_officials import (
    elected_officials_report,
    ingest_elected_officials,
)
from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema
from publicdata_connectors_es.infoelectoral.elected_officials import (
    WORKBOOKS,
    iter_elected_officials,
)
from publicdata_sqlite import open_db
from scripts.ingest_infoelectoral_elected_officials import (
    _source_drift_report,
    _storage_preflight,
    run,
)


def _column_name(index: int) -> str:
    value = index + 1
    output = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        output = chr(65 + remainder) + output
    return output


def _write_xlsx(path: Path, rows: list[list[str]]) -> None:
    xml_rows: list[str] = []
    for row_number, values in enumerate(rows, start=1):
        cells = []
        for index, value in enumerate(values):
            reference = f"{_column_name(index)}{row_number}"
            cells.append(
                f'<c r="{reference}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def _workbook_fixture(path: Path, chamber: str, *, duplicate: bool = False) -> None:
    if chamber == "congreso":
        header = [
            "Fecha",
            "Código elección",
            "Tipo elección",
            "Código Provincia",
            "Provincia",
            "Cargos Electos",
            "Candidatura",
            "Siglas Candidatura",
        ]
        row = [
            "45130",
            "ELEC-1",
            "Congreso",
            "28",
            "Madrid",
            "Persona Congreso",
            "Partido Ejemplo",
            "PE",
        ]
    else:
        header = [
            "Fecha",
            "Código elección",
            "Tipo elección",
            "Código Provincia",
            "Provincia",
            "Distrito Electoral",
            "Circunscripción",
            "Cargos Electos",
            "Candidatura",
            "Siglas Candidatura",
            "Votos",
        ]
        row = [
            "45130",
            "ELEC-1",
            "Senado",
            "28",
            "Madrid",
            "1",
            "Madrid",
            "Persona Senado",
            "Partido Ejemplo",
            "PE",
            "12345",
        ]
    rows = [["Datos oficiales"], header, row]
    if duplicate:
        rows.append(row)
    _write_xlsx(path, rows)


def _fixture_records(root: Path):
    records = []
    for spec in WORKBOOKS:
        path = root / f"{spec.chamber}.xlsx"
        _workbook_fixture(path, spec.chamber)
        records.extend(
            iter_elected_officials(
                path,
                spec=spec,
                source_content_sha256=(spec.chamber * 64)[:64],
            )
        )
    return records


class TestInfoelectoralElectedOfficials(unittest.TestCase):
    def test_parser_maps_both_official_workbook_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for spec in WORKBOOKS:
                path = root / f"{spec.chamber}.xlsx"
                _workbook_fixture(path, spec.chamber)
                records = list(
                    iter_elected_officials(
                        path,
                        spec=spec,
                        source_content_sha256=spec.chamber * 8,
                    )
                )
                self.assertEqual(len(records), 1)
                record = records[0]
                self.assertEqual(record.chamber, spec.chamber)
                self.assertEqual(record.territory_code, "ES-PROV-28")
                self.assertEqual(record.institution_name, spec.institution_name)
                if spec.chamber == "senado":
                    self.assertEqual(record.votes, 12345)
                    self.assertEqual(record.constituency, "Madrid")
                else:
                    self.assertIsNone(record.votes)

    def test_parser_rejects_duplicate_outcome_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "congreso.xlsx"
            _workbook_fixture(path, "congreso", duplicate=True)
            with self.assertRaisesRegex(RuntimeError, "duplicate elected-official"):
                list(
                    iter_elected_officials(
                        path,
                        spec=WORKBOOKS[0],
                        source_content_sha256="a" * 64,
                    )
                )

    def test_sample_ingest_is_idempotent_and_reconciled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = open_db(Path(temp_dir) / "elected.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                records = _fixture_records(Path(temp_dir))
                first = ingest_elected_officials(
                    conn,
                    records,
                    snapshot_date="2026-08-11",
                    batch_rows=1,
                )
                second = ingest_elected_officials(
                    conn,
                    records,
                    snapshot_date="2026-08-11",
                    batch_rows=2,
                )
                self.assertEqual(first["processed"], 2)
                self.assertEqual(second["processed"], 2)
                report = elected_officials_report(conn)
                self.assertEqual(report["status"], "ok")
                self.assertEqual(report["totals"]["elected_officials"], 2)
                self.assertEqual(report["totals"]["mandates"], 2)
                self.assertEqual(report["totals"]["observations"], 2)
                self.assertTrue(report["checks"]["direct_person_links_complete"])
                self.assertTrue(report["checks"]["direct_mandate_links_complete"])
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()

    def test_presence_and_observations_preserve_removed_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = open_db(Path(temp_dir) / "elected.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                records = _fixture_records(Path(temp_dir))
                removed = replace(
                    records[0],
                    elected_official_id="fixture-removed-outcome",
                    source_record_id="fixture-removed-source-record",
                    full_name="Persona Retirada",
                    source_row_number=999,
                )
                ingest_elected_officials(
                    conn,
                    [*records, removed],
                    snapshot_date="2026-08-11",
                    batch_rows=2,
                )
                ingest_elected_officials(
                    conn,
                    records,
                    snapshot_date="2026-08-12",
                    batch_rows=2,
                )
                report = elected_officials_report(conn)
                self.assertEqual(report["status"], "ok")
                self.assertEqual(report["totals"]["elected_officials"], 3)
                self.assertEqual(report["totals"]["present_elected_officials"], 2)
                self.assertEqual(report["totals"]["absent_elected_officials"], 1)
                self.assertEqual(report["totals"]["observations"], 5)
                state = conn.execute(
                    """
                    SELECT first_seen_snapshot_date, last_seen_snapshot_date,
                           is_present
                    FROM infoelectoral_elected_officials
                    WHERE elected_official_id = ?
                    """,
                    (removed.elected_official_id,),
                ).fetchone()
                self.assertEqual(
                    tuple(state),
                    ("2026-08-11", "2026-08-11", 0),
                )
                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()

    def test_end_to_end_local_replay_tracks_provenance_and_reruns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            congreso = root / "congreso.xlsx"
            senado = root / "senado.xlsx"
            _workbook_fixture(congreso, "congreso")
            _workbook_fixture(senado, "senado")
            args = argparse.Namespace(
                db=str(root / "elected.db"),
                schema=str(DEFAULT_SCHEMA),
                snapshot_date="2026-08-11",
                store_root=str(root / "store"),
                manifest_root=str(root / "manifests"),
                report_out=str(root / "report.json"),
                timeout=5,
                batch_rows=1,
                max_workbook_bytes=1024 * 1024,
                max_uncompressed_bytes=4 * 1024 * 1024,
                max_rows=10,
                minimum_congreso_rows=1,
                minimum_senado_rows=1,
                min_free_bytes=0,
                ca_bundle=None,
                insecure_ssl=False,
                from_file=[f"congreso={congreso}", f"senado={senado}"],
            )
            first = run(args)
            second = run(args)
            self.assertEqual(first["status"], "ok")
            self.assertTrue(first["source_drift"]["bootstrap"])
            self.assertEqual(first["actor_lane"]["net_new_mandates"], 2)
            self.assertEqual(second["status"], "ok")
            self.assertEqual(second["source_drift"]["status"], "ok")
            self.assertEqual(second["actor_lane"]["net_new_mandates"], 0)
            conn = open_db(Path(args.db))
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM mandates").fetchone()[0], 2)
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0],
                    2,
                )
                paths = [
                    str(row[0])
                    for row in conn.execute(
                        "SELECT raw_path FROM raw_fetches UNION ALL SELECT raw_path FROM run_fetches"
                    )
                ]
                self.assertTrue(paths)
                self.assertTrue(all(not Path(path).is_absolute() for path in paths))
            finally:
                conn.close()

    def test_source_drift_blocks_large_unreviewed_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = open_db(Path(temp_dir) / "elected.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                ingest_elected_officials(
                    conn,
                    _fixture_records(Path(temp_dir)),
                    snapshot_date="2026-08-11",
                )
                blocked = _source_drift_report(
                    conn,
                    incoming_counts={"congreso": 10, "senado": 1},
                    max_row_drift_ratio=0.15,
                    allow_large_drift=False,
                )
                reviewed = _source_drift_report(
                    conn,
                    incoming_counts={"congreso": 10, "senado": 1},
                    max_row_drift_ratio=0.15,
                    allow_large_drift=True,
                )
                self.assertEqual(blocked["status"], "blocked")
                self.assertFalse(blocked["ready"])
                self.assertEqual(reviewed["status"], "override")
                self.assertTrue(reviewed["ready"])
            finally:
                conn.close()

    def test_storage_preflight_blocks_before_acquisition(self) -> None:
        usage = type("Usage", (), {"free": 100, "total": 1_000, "used": 900})()
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "scripts.ingest_infoelectoral_elected_officials.shutil.disk_usage",
                return_value=usage,
            ):
                report = _storage_preflight(
                    Path(temp_dir), min_free_bytes=80, reserve_bytes=30
                )
        self.assertFalse(report["ready"])
        self.assertEqual(report["headroom_bytes"], -10)


if __name__ == "__main__":
    unittest.main()
