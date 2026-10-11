from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from publicdata_connectors_es.representatives.parsers import parse_xlsx_source
from publicdata_docs.extraction import (
    DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
    DOCUMENT_LOCATOR_ALGORITHM_VERSION,
    build_document_text_locators,
    extract_document_path,
)
from publicdata_docs.xlsx import (
    DEFAULT_MAX_TEXT_CHARS,
    XLSX_CONTENT_TYPE,
    XlsxExtractionError,
    extract_xlsx_path,
)
from scripts.inventory_document_corpus import inspect_xlsx
from scripts.locate_real_document_text import EMPTY_TEXT_SHA256, locate_one
from scripts.validate_real_document_text_locators import replay_one

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "etl/data/raw"
MUNICIPAL_XLSX = (
    RAW_ROOT
    / "municipal_concejales/2026/02/12/municipal_concejales_20260212T120801Z.xlsx"
)
ANDALUCIA_BUDGET_XLSX = (
    RAW_ROOT
    / "elections/andalucia_2026/execution_evidence/partidas-de-gastos.xlsx"
)
ANDALUCIA_OUTCOMES_XLSX = (
    RAW_ROOT
    / "elections/andalucia_2026/execution_evidence/objetivos-actuaciones-e-indicadores.xlsx"
)


def _rewrite_real_xlsx(
    source: Path,
    output: Path,
    *,
    replacements: dict[str, bytes],
    additions: dict[str, bytes] | None = None,
) -> None:
    """Make a contract-test derivative while retaining official source rows."""

    with ZipFile(source) as source_archive, ZipFile(
        output, "w", compression=ZIP_DEFLATED
    ) as output_archive:
        for info in source_archive.infolist():
            payload = replacements.get(info.filename, source_archive.read(info))
            output_archive.writestr(info, payload)
        for name, payload in (additions or {}).items():
            output_archive.writestr(name, payload)


class RealXlsxDocumentProcessingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        required = [MUNICIPAL_XLSX, ANDALUCIA_BUDGET_XLSX, ANDALUCIA_OUTCOMES_XLSX]
        if any(not path.is_file() for path in required):
            raise unittest.SkipTest("real official XLSX cohort is unavailable")

    def test_every_real_municipal_cell_is_retained_with_public_identity(self) -> None:
        workbook = extract_xlsx_path(MUNICIPAL_XLSX, max_text_chars=33_554_432)
        records = parse_xlsx_source(MUNICIPAL_XLSX.read_bytes())
        first = records[0]
        self.assertEqual(workbook.worksheet_count, 1)
        self.assertEqual(workbook.worksheet_rows, 66_899)
        self.assertEqual(workbook.nonempty_worksheet_rows, 66_898)
        self.assertEqual(workbook.nonempty_cells, 668_781)
        self.assertEqual(len(records), 66_895)
        for key in ("Nombre", "1er Apellido", "2º Apellido"):
            self.assertIn(
                json.dumps(str(first[key]), ensure_ascii=False),
                workbook.text,
            )
        self.assertNotIn("[REDACTED", workbook.text)
        self.assertEqual(workbook.text_chars, len(workbook.text))

    def test_real_xlsx_row_groups_are_exact_and_scale_bounded(self) -> None:
        extraction = extract_document_path(
            MUNICIPAL_XLSX,
            content_type=XLSX_CONTENT_TYPE,
            max_input_bytes=134_217_728,
            max_text_chars=33_554_432,
        )
        locators = build_document_text_locators(
            extraction.text,
            raw_path=MUNICIPAL_XLSX,
            content_type=XLSX_CONTENT_TYPE,
            extraction_method=extraction.method,
            expected_page_count=None,
            max_span_chars=8_192,
            max_locators_per_content=2_000,
        )
        self.assertEqual(extraction.method, "xlsx_openxml_path")
        self.assertFalse(extraction.truncated)
        self.assertLessEqual(len(locators), 10)
        self.assertLessEqual(max(item.text_chars for item in locators), 4 * 1024 * 1024)
        self.assertTrue(all(item.locator_type == "xlsx_row_group" for item in locators))
        self.assertTrue(all(item.locator_value.startswith("sheet:0001#rows:") for item in locators))
        self.assertEqual(
            "".join(
                extraction.text[item.text_start_char : item.text_end_char]
                for item in locators
            ),
            extraction.text,
        )
        for item in locators:
            segment = extraction.text[item.text_start_char : item.text_end_char]
            self.assertEqual(
                hashlib.sha256(segment.encode("utf-8")).hexdigest(),
                item.text_sha256,
            )
        self.assertEqual(
            DOCUMENT_EXTRACTION_ALGORITHM_VERSION,
            "document_extraction_v4_pdf_markup_xlsx_phonetic_bounded",
        )
        self.assertEqual(
            DOCUMENT_LOCATOR_ALGORITHM_VERSION,
            "document_text_locator_v6_markup_sections_xlsx_cross_sheet_row_groups",
        )

    def test_real_budget_workbooks_inventory_every_observed_value(self) -> None:
        expected = {
            ANDALUCIA_BUDGET_XLSX: (12_773, 336_354, 12_721_438),
            ANDALUCIA_OUTCOMES_XLSX: (4_780, 187_429, 20_130_984),
        }
        for path, (rows, cells, text_chars) in expected.items():
            with self.subTest(path=path.name):
                item = inspect_xlsx(path, RAW_ROOT)
                self.assertEqual(item["status"], "ok")
                self.assertEqual(item["quality_class"], "xlsx_public_cells_with_text")
                self.assertEqual(item["nonempty_worksheet_rows"], rows)
                self.assertEqual(item["nonempty_cells"], cells)
                self.assertEqual(item["text_chars"], text_chars)

    def test_real_xlsx_parser_rejects_unbounded_or_inconsistent_xml(self) -> None:
        with ZipFile(ANDALUCIA_BUDGET_XLSX) as archive:
            worksheet = archive.read("xl/worksheets/sheet1.xml")
        declaration_end = worksheet.index(b"?>") + 2
        dtd_worksheet = (
            worksheet[:declaration_end]
            + b'<!DOCTYPE worksheet [<!ENTITY public "forbidden">]>'
            + worksheet[declaration_end:]
        )
        mismatched_worksheet, replacements = re.subn(
            rb'(<c\s+[^>]*r=")[A-Z]+1(")',
            rb"\1A2\2",
            worksheet,
            count=1,
        )
        self.assertEqual(replacements, 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dtd_path = root / "real-derived-dtd.xlsx"
            mismatch_path = root / "real-derived-coordinate-mismatch.xlsx"
            _rewrite_real_xlsx(
                ANDALUCIA_BUDGET_XLSX,
                dtd_path,
                replacements={"xl/worksheets/sheet1.xml": dtd_worksheet},
            )
            _rewrite_real_xlsx(
                ANDALUCIA_BUDGET_XLSX,
                mismatch_path,
                replacements={"xl/worksheets/sheet1.xml": mismatched_worksheet},
            )
            with self.assertRaisesRegex(XlsxExtractionError, "doctype"):
                extract_xlsx_path(dtd_path)
            with self.assertRaisesRegex(XlsxExtractionError, "containing row"):
                extract_xlsx_path(mismatch_path)
            with self.assertRaisesRegex(XlsxExtractionError, "depth"):
                extract_xlsx_path(ANDALUCIA_BUDGET_XLSX, max_xml_depth=1)
            with self.assertRaisesRegex(XlsxExtractionError, "element count"):
                extract_xlsx_path(ANDALUCIA_BUDGET_XLSX, max_xml_elements=1)

    def test_real_derived_phonetic_annotation_is_retained_as_typed_text(self) -> None:
        with ZipFile(ANDALUCIA_BUDGET_XLSX) as archive:
            shared = archive.read("xl/sharedStrings.xml")
        public_annotation = "lectura pública oficial"
        injected, replacements = re.subn(
            rb"</si>",
            (
                '<rPh sb="0" eb="4"><t>'
                + public_annotation
                + "</t></rPh></si>"
            ).encode("utf-8"),
            shared,
            count=1,
        )
        self.assertEqual(replacements, 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            derived = Path(temp_dir) / "real-derived-phonetic.xlsx"
            _rewrite_real_xlsx(
                ANDALUCIA_BUDGET_XLSX,
                derived,
                replacements={"xl/sharedStrings.xml": injected},
            )
            workbook = extract_xlsx_path(derived)
        self.assertIn(public_annotation, workbook.text)
        phonetic_cells = [
            cell
            for line in workbook.text.splitlines()
            for cell in json.loads(line)["cells"]
            if len(cell) == 5
        ]
        self.assertTrue(phonetic_cells)
        annotation = json.loads(phonetic_cells[0][4])
        self.assertEqual(annotation[0]["text"], public_annotation)
        self.assertEqual(annotation[0]["attributes"], [["eb", "4"], ["sb", "0"]])

    def test_real_derived_blank_workbook_flows_to_no_text_locator(self) -> None:
        blank = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main"><sheetData/></worksheet>'
        ).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            derived = root / "real-derived-blank.xlsx"
            _rewrite_real_xlsx(
                ANDALUCIA_BUDGET_XLSX,
                derived,
                replacements={"xl/worksheets/sheet1.xml": blank},
            )
            workbook = extract_xlsx_path(derived)
            extraction = extract_document_path(
                derived,
                content_type=XLSX_CONTENT_TYPE,
                max_input_bytes=134_217_728,
                max_text_chars=DEFAULT_MAX_TEXT_CHARS,
            )
            locators = build_document_text_locators(
                extraction.text,
                raw_path=derived,
                content_type=XLSX_CONTENT_TYPE,
                extraction_method=extraction.method,
                expected_page_count=None,
            )
            raw_sha256 = hashlib.sha256(derived.read_bytes()).hexdigest()
            no_text_row = {
                "content_sha256": raw_sha256,
                "representative_path": derived.name,
                "bytes": derived.stat().st_size,
                "mime_type": XLSX_CONTENT_TYPE,
                "page_count": None,
                "native_extraction_status": "native_no_text",
                "native_text_sha256": EMPTY_TEXT_SHA256,
                "native_text_cas_path": "",
                "native_text_chars": 0,
                "native_extraction_method": "xlsx_openxml_path",
            }
            outcome = locate_one(
                no_text_row,
                raw_root=root,
                native_root=root,
                max_span_chars=8_192,
                max_xlsx_span_chars=4 * 1024 * 1024,
                max_xlsx_locators_per_content=10,
                pdf_timeout_seconds=120,
                markup_section_max_depth=1,
                max_semantic_markup_bytes=64 * 1024 * 1024,
                max_locators_per_content=2_000,
            )
            replayed = replay_one(
                no_text_row,
                raw_root=root,
                native_root=root,
                max_span_chars=8_192,
                max_xlsx_span_chars=4 * 1024 * 1024,
                max_xlsx_locators_per_content=10,
                pdf_timeout_seconds=120,
                markup_section_max_depth=1,
                max_semantic_markup_bytes=64 * 1024 * 1024,
                max_locators_per_content=2_000,
            )
        self.assertEqual(workbook.worksheet_count, 1)
        self.assertEqual(workbook.text, "")
        self.assertEqual(extraction.text, "")
        self.assertEqual(len(locators), 1)
        self.assertEqual(locators[0].locator_type, "document_no_text")
        self.assertFalse(locators[0].has_text)
        self.assertEqual(outcome.status, "succeeded")
        self.assertEqual(outcome.locators[0].locator_type, "document_no_text")
        self.assertEqual(replayed[1][0][2], "document_no_text")

    def test_real_rows_across_eleven_sheets_stay_below_locator_fanout(self) -> None:
        with ZipFile(ANDALUCIA_BUDGET_XLSX) as archive:
            workbook_xml = archive.read("xl/workbook.xml")
            relationships = archive.read("xl/_rels/workbook.xml.rels")
            worksheet = archive.read("xl/worksheets/sheet1.xml")
        row_match = re.search(rb"<row\b[^>]*>.*?</row>", worksheet, re.DOTALL)
        worksheet_root = re.search(rb"<worksheet\b[^>]*>", worksheet)
        self.assertIsNotNone(row_match)
        self.assertIsNotNone(worksheet_root)
        minimal_sheet = (
            worksheet_root.group(0)
            + b"<sheetData>"
            + row_match.group(0)
            + b"</sheetData></worksheet>"
        )
        sheet_entries: list[bytes] = []
        relation_entries: list[bytes] = []
        additions: dict[str, bytes] = {}
        for sheet_number in range(2, 12):
            relation_id = f"rIdDerived{sheet_number}"
            sheet_entries.append(
                (
                    f'<sheet name="Official row {sheet_number}" '
                    f'sheetId="{sheet_number}" r:id="{relation_id}"/>'
                ).encode("utf-8")
            )
            relation_entries.append(
                (
                    f'<Relationship Id="{relation_id}" '
                    'Type="http://schemas.openxmlformats.org/'
                    'officeDocument/2006/relationships/worksheet" '
                    f'Target="worksheets/sheet{sheet_number}.xml"/>'
                ).encode("utf-8")
            )
            additions[f"xl/worksheets/sheet{sheet_number}.xml"] = minimal_sheet
        workbook_xml = workbook_xml.replace(
            b"</sheets>", b"".join(sheet_entries) + b"</sheets>"
        )
        relationships = relationships.replace(
            b"</Relationships>",
            b"".join(relation_entries) + b"</Relationships>",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            derived = Path(temp_dir) / "real-derived-eleven-sheets.xlsx"
            _rewrite_real_xlsx(
                ANDALUCIA_BUDGET_XLSX,
                derived,
                replacements={
                    "xl/workbook.xml": workbook_xml,
                    "xl/_rels/workbook.xml.rels": relationships,
                    "xl/worksheets/sheet1.xml": minimal_sheet,
                },
                additions=additions,
            )
            extraction = extract_document_path(
                derived,
                content_type=XLSX_CONTENT_TYPE,
                max_input_bytes=134_217_728,
                max_text_chars=DEFAULT_MAX_TEXT_CHARS,
            )
            locators = build_document_text_locators(
                extraction.text,
                raw_path=derived,
                content_type=XLSX_CONTENT_TYPE,
                extraction_method=extraction.method,
                expected_page_count=None,
            )
        self.assertLessEqual(len(locators), 10)
        self.assertTrue(any(item.locator_value.startswith("from:sheet:") for item in locators))
        self.assertEqual(
            "".join(
                extraction.text[item.text_start_char : item.text_end_char]
                for item in locators
            ),
            extraction.text,
        )


if __name__ == "__main__":
    unittest.main()
