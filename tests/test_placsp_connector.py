from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.connectors.placsp_contracts import (
    PlacspSindicacionConnector,
    parse_placsp_atom_entries,
)
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source


PLACSP_OFFICIAL_ARCHIVE = Path(
    "etl/data/object-origin/placsp-contracts/bd/a7/"
    "bda70aa0a7437d031e5d3f6114e5a637920ea1a460e1aba67d200209ae5eab7f.zip"
)
PLACSP_OFFICIAL_MEMBER = "licitacionesPerfilesContratanteCompleto3.atom"
PLACSP_OFFICIAL_URL = (
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/"
    "licitacionesPerfilesContratanteCompleto3_2025.zip"
)


def _official_placsp_payload() -> bytes:
    with zipfile.ZipFile(PLACSP_OFFICIAL_ARCHIVE) as archive:
        return archive.read(PLACSP_OFFICIAL_MEMBER)


def _write_official_placsp_capture(directory: Path) -> Path:
    capture_path = directory / PLACSP_OFFICIAL_MEMBER
    capture_path.write_bytes(_official_placsp_payload())
    return capture_path


class TestPlacspConnector(unittest.TestCase):
    def test_extract_from_official_capture_includes_contracting_fields(self) -> None:
        connector = PlacspSindicacionConnector()
        self.assertTrue(
            PLACSP_OFFICIAL_ARCHIVE.exists(),
            f"Missing official archive: {PLACSP_OFFICIAL_ARCHIVE}",
        )

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_dir = td_path / "raw"
            capture_path = _write_official_placsp_capture(td_path)
            extracted = connector.extract(
                raw_dir=raw_dir,
                timeout=5,
                from_file=capture_path,
                url_override=PLACSP_OFFICIAL_URL,
                strict_network=True,
            )

            self.assertGreaterEqual(len(extracted.records), 3)
            with_expediente = [r for r in extracted.records if str(r.get("expediente") or "").strip()]
            with_organo = [r for r in extracted.records if str(r.get("organo_contratacion") or "").strip()]
            with_cpv = [r for r in extracted.records if str(r.get("cpv") or "").strip()]
            with_amount = [r for r in extracted.records if r.get("amount_eur") is not None]
            with_pubdate = [r for r in extracted.records if str(r.get("published_at_iso") or "").strip()]
            self.assertGreater(len(with_expediente), 0)
            self.assertGreater(len(with_organo), 0)
            self.assertGreater(len(with_cpv), 0)
            self.assertGreater(len(with_amount), 0)
            self.assertGreater(len(with_pubdate), 0)

            ids = [str(r.get("source_record_id") or "") for r in extracted.records]
            self.assertTrue(all(id_value for id_value in ids))

    def test_parser_source_record_id_is_stable(self) -> None:
        payload = _official_placsp_payload()

        records_1 = parse_placsp_atom_entries(
            payload,
            feed_url=PLACSP_OFFICIAL_URL,
            content_type="application/atom+xml",
        )
        records_2 = parse_placsp_atom_entries(
            payload,
            feed_url=PLACSP_OFFICIAL_URL,
            content_type="application/atom+xml",
        )

        ids_1 = sorted(str(row.get("source_record_id") or "") for row in records_1)
        ids_2 = sorted(str(row.get("source_record_id") or "") for row in records_2)
        self.assertEqual(ids_1, ids_2)

    def test_source_records_ingest_is_idempotent_for_official_national_capture(self) -> None:
        snapshot_date = "2026-08-12"
        connector = PlacspSindicacionConnector()

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "politicos-test.db"
            raw_dir = td_path / "raw"
            capture_path = _write_official_placsp_capture(td_path)
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=capture_path,
                    url_override=PLACSP_OFFICIAL_URL,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )

                counts_1 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        """
                        SELECT source_id, COUNT(*) AS c
                        FROM source_records
                        WHERE source_id = 'placsp_sindicacion'
                        GROUP BY source_id
                        ORDER BY source_id
                        """
                    ).fetchall()
                }
                self.assertGreater(counts_1.get("placsp_sindicacion", 0), 0)

                ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=capture_path,
                    url_override=PLACSP_OFFICIAL_URL,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )

                counts_2 = {
                    row["source_id"]: int(row["c"])
                    for row in conn.execute(
                        """
                        SELECT source_id, COUNT(*) AS c
                        FROM source_records
                        WHERE source_id = 'placsp_sindicacion'
                        GROUP BY source_id
                        ORDER BY source_id
                        """
                    ).fetchall()
                }
                self.assertEqual(counts_1, counts_2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
