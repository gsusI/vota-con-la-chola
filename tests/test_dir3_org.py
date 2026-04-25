from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG
from etl.politicos_es.connectors.dir3_org import (
    Dir3UnidadesAgeConnector,
    find_dir3_age_distribution_url,
    normalize_dir3_record,
    parse_dir3_xlsx,
)
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.government_org import backfill_government_org_units
from etl.politicos_es.pipeline import ingest_one_source


def _minimal_xlsx(rows: list[list[str]]) -> bytes:
    shared: list[str] = []
    shared_idx: dict[str, int] = {}

    def shared_ref(value: str) -> int:
        if value not in shared_idx:
            shared_idx[value] = len(shared)
            shared.append(value)
        return shared_idx[value]

    sheet_rows: list[str] = []
    for ridx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for cidx, value in enumerate(row):
            col = chr(ord("A") + cidx)
            cells.append(f'<c r="{col}{ridx}" t="s"><v>{shared_ref(value)}</v></c>')
        sheet_rows.append(f'<row r="{ridx}">{"".join(cells)}</row>')

    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">'
        + "".join(f"<si><t>{value}</t></si>" for value in shared)
        + "</sst>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Unidades" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )

    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/sharedStrings.xml", shared_xml)
    return buf.getvalue()


class TestDir3Org(unittest.TestCase):
    def test_find_dir3_age_distribution_url_from_catalog_payload(self) -> None:
        catalog_payload = {
            "result": {
                "items": [
                    {
                        "distribution": [
                            {
                                "title": [{"_value": "Catalogo de provincias"}],
                                "accessURL": "https://example.test/provincias.xlsx",
                            },
                            {
                                "title": [{"_value": "Listado de información básica de unidades orgánicas de la AGE"}],
                                "accessURL": "https://example.test/Listado%20Unidades%20AGE.xlsx",
                            },
                        ]
                    }
                ]
            }
        }

        self.assertEqual(
            find_dir3_age_distribution_url(catalog_payload),
            "https://example.test/Listado%20Unidades%20AGE.xlsx",
        )

    def test_parse_dir3_xlsx_normalizes_parent_code(self) -> None:
        payload = _minimal_xlsx(
            [
                [
                    "Codigo unidad organica",
                    "Denominacion unidad organica",
                    "Codigo unidad organica superior",
                    "Denominacion unidad organica superior",
                    "Nivel jerarquico",
                ],
                ["EA0040879 - v4", "Departamento de Asuntos Institucionales", "E00000001", "Presidencia del Gobierno", "2"],
            ]
        )
        rows = parse_dir3_xlsx(payload)
        self.assertEqual(len(rows), 1)

        record = normalize_dir3_record(rows[0], feed_url="file://dir3.xlsx")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["org_unit_code"], "EA0040879")
        self.assertEqual(record["org_unit_version"], "4")
        self.assertEqual(record["parent_org_unit_code"], "E00000001")
        self.assertEqual(record["organic_level"], 2)

    def test_sample_ingest_backfills_org_graph(self) -> None:
        connector = Dir3UnidadesAgeConnector()
        sample_path = Path(SOURCE_CONFIG["dir3_unidades_age"]["fallback_file"])
        self.assertTrue(sample_path.exists())

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "politicos-test.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                seen, loaded, note = ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date="2026-02-12",
                    strict_network=True,
                )
                self.assertEqual((seen, loaded, note), (3, 3, "from-file"))

                result = backfill_government_org_units(conn, source_ids=("dir3_unidades_age",))
                self.assertEqual(result["org_units_upserted"], 3)
                self.assertEqual(result["relationships_upserted"], 2)
                self.assertEqual(result["relationships_missing_parent"], 0)

                unit_count = conn.execute("SELECT COUNT(*) AS c FROM government_org_units").fetchone()["c"]
                rel_count = conn.execute("SELECT COUNT(*) AS c FROM government_org_relationships").fetchone()["c"]
                self.assertEqual(unit_count, 3)
                self.assertEqual(rel_count, 2)

                row = conn.execute(
                    """
                    SELECT child.org_unit_code AS child_code, parent.org_unit_code AS parent_code
                    FROM government_org_relationships rel
                    JOIN government_org_units child ON child.org_unit_id = rel.subject_org_unit_id
                    JOIN government_org_units parent ON parent.org_unit_id = rel.object_org_unit_id
                    WHERE child.org_unit_code = 'EA0040880'
                    """
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["parent_code"], "EA0040879")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
