import json
import sqlite3
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, seed_sources
from publicdata_sqlite.provenance import seed_sources_from_config
from scripts import export_public_viz_health as export
from scripts import extract_health_pdfs_es as extract
from scripts import ingest_health_es as ingest

DEFINITION = {
    "source_id": "oecd_health_statistics",
    "dataset_code": "DSD_SHA@DF_SHA",
    "indicator_code": "EXP_HEALTH.HF1._Z",
    "frequency_code": "A",
    "unit_code": "PT_B1GQ",
    "label": "Gasto sanitario público",
    "source_url": "https://db.nomics.world/OECD/DSD_SHA@DF_SHA",
}
SISLE = ingest.MANUAL_DIR / "sisle_sns.json"


def series(values: dict[str, float], geo: str = "ESP") -> list[dict]:
    obs = [{"period": p, "value": v, "pointer": f"/x/{p}"} for p, v in values.items()]
    return [ingest.area_series(f"k|{geo}", geo, {}, obs)]


class IngestHealthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_schema(self.conn, Path(DEFAULT_SCHEMA))
        seed_sources(self.conn)
        seed_sources_from_config(self.conn, ingest.LOCAL_SOURCES)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def load(self, sha: str, values: dict[str, float]) -> dict:
        return ingest.load_indicator(
            self.conn, dict(DEFINITION), sha, 10, "etl/data/raw/x.json", "https://example.org", "2026-10-19", {}, series(values)
        )

    def test_new_release_compares_every_observation_and_is_idempotent(self) -> None:
        self.assertEqual(self.load("a" * 64, {"2022": 6.9, "2023": 6.6, "2024": 6.7})["releases"], 1)
        self.assertEqual(self.load("a" * 64, {"2022": 6.9})["releases"], 0)
        self.load("b" * 64, {"2022": 6.9, "2023": 6.5, "2025": 6.8})
        states = dict(tuple(row) for row in self.conn.execute(
            """
            SELECT o.period_label, o.revision_state FROM indicator_observation_versions o
            JOIN indicator_releases r USING (indicator_release_id) WHERE r.comparison_state = 'compared'
            """
        ).fetchall())
        self.assertEqual(states, {"2022": "unchanged", "2023": "changed", "2024": "deleted", "2025": "baseline"})
        self.assertEqual([tuple(r) for r in self.conn.execute("SELECT DISTINCT domain_key FROM indicator_definitions")], [("sanidad",)])

    def test_observation_evidence_can_point_at_a_cited_pdf(self) -> None:
        obs = {
            "period": "2025-12-31", "start": "2025-12-31", "end": "2025-12-31", "interval_kind": "point_in_time",
            "value": 122, "pointer": "pdf:page=4;row=TOTAL 853.740", "evidence_url": "https://www.sanidad.gob.es/x.pdf",
            "evidence_sha256": "c" * 64, "evidence_raw_path": "etl/data/raw/health/sisle/x.pdf", "status": "rectified",
            "extra_evidence": [("https://www.sanidad.gob.es/nota.pdf", "d" * 64, "etl/data/raw/health/sisle/nota.pdf", "pdf:page=1", None)],
        }
        ingest.load_indicator(
            self.conn, {**DEFINITION, "source_id": "minsan_sisle_sns", "frequency_code": "S", "unit_code": "DAYS"},
            "e" * 64, 10, "etl/data/manual/health/sisle_sns.json", "https://www.sanidad.gob.es/", "2026-10-19", {},
            [ingest.area_series("sisle|ES", "ES", {}, [obs])],
        )
        rows = [tuple(r) for r in self.conn.execute(
            "SELECT source_content_sha256, value_json_pointer FROM indicator_observation_evidence ORDER BY 1"
        )]
        self.assertEqual(rows, [("c" * 64, "pdf:page=4;row=TOTAL 853.740"), ("d" * 64, "pdf:page=1")])
        self.assertEqual(tuple(self.conn.execute("SELECT interval_kind, source_status_code FROM indicator_observation_versions").fetchone()),
                         ("point_in_time", "rectified"))

    def test_jsonstat_cells_decode_flat_indexes(self) -> None:
        data = {
            "id": ["geo", "time"], "size": [2, 2], "value": {"0": 1.0, "3": 4.0}, "status": {"3": "b"},
            "dimension": {"geo": {"category": {"index": {"ES": 0, "DE": 1}}}, "time": {"category": {"index": {"2023": 0, "2024": 1}}}},
        }
        cells = list(ingest.jsonstat_cells(data))
        self.assertEqual(cells, [({"geo": "ES", "time": "2023"}, 1.0, 0, None), ({"geo": "DE", "time": "2024"}, 4.0, 3, "b")])

    def test_sisle_row_parsers(self) -> None:
        self.assertEqual(extract.tokens("TOTAL 853.740 7.157 21.012 17,70 21,6 122 -4"),
                         ["853.740", "7.157", "21.012", "17,70", "21,6", "122", "-4"])
        page = "SITUACIÓN DE LA LISTA DE ESPERA QUIRÚRGICA\nDATOS A 31 DE DICIEMBRE DE 2014\nESPECIALIDADES\n" \
               "  TOTAL     511.923    -47.412    11,40    9,3    87   -11\n(*) Cataluña estimada\n"
        row = extract.surgery([page])
        self.assertEqual((row["cut_date"], row["patients"], row["rate_per_1000"], row["pct_over_6_months"], row["mean_days"]),
                         ("2014-12-31", 511923, 11.4, 9.3, 87.0))
        self.assertEqual(row["footnotes"], ["(*) Cataluña estimada"])

    def test_curated_sisle_file_is_complete_and_cited(self) -> None:
        data = json.loads(SISLE.read_text(encoding="utf-8"))
        files = {r["file"]: r for r in data["reports"]}
        for row in data["surgery"] + data["consultations"]:
            self.assertIn(row["report"], files)
            self.assertTrue(row["quote"].startswith("TOTAL"), row)
            self.assertRegex(files[row["report"]]["sha256"], r"^[0-9a-f]{64}$")
        dates = [row["cut_date"] for row in data["surgery"]]
        self.assertEqual(dates, sorted(set(dates)))
        # Every December from 2003 to 2025 is present (the chart uses December cuts).
        self.assertEqual({d[:4] for d in dates if d.endswith("-12-31")}, {str(y) for y in range(2003, 2026)})
        self.assertEqual({b["cut_date"] for b in data["breaks"]}, {"2012-06-30", "2016-12-31", "2018-12-31", "2025-06-30"})
        for b in data["breaks"]:
            self.assertIn(b["report"], files)

    def test_export_cut_points_keep_breaks_and_rectifications(self) -> None:
        rows = [
            {"period": "2018-12-31", "value": 129.0, "status": "break", "labels": [{"code": "break", "label": "Andalucía"}]},
            {"period": "2025-12-31", "value": 122.0, "status": "rectified", "labels": [{"code": "rectified", "label": "CLM", "initial_value": 121}]},
        ]
        points = export.cut_points(rows, 0)
        self.assertEqual(points[0]["breaks"], ["Andalucía"])
        self.assertEqual(points[1]["rectified"], {"initial": 121, "label": "CLM"})

    def test_barometro_gp_block_is_found_by_label(self) -> None:
        rows = [
            (185, {"A": "Pregunta 5c"}),
            (186, {"A": "Desde que Ud. pidió la cita para esta consulta, hasta que le/la atendió el/la médico/a de familia, ¿cuánto tiempo pasó?"}),
            (187, {"A": "Le/la atendió ese mismo día que la pidió", "B": "10.8"}),
            (188, {"A": "Le/la atendió al día siguiente", "B": "11.0"}),
            (189, {"A": "Pasó más de un día porque no había cita antes", "B": "69.8"}),
            (213, {"A": "Media", "B": "9.15"}),
            (383, {"A": "Media  (días)", "B": "128.91"}),
        ]
        found = {item["metric"]: (item["row"], item["value"]) for item in ingest.gp_access(2025, {"Resultados": rows})}
        self.assertEqual(found, {"same_day": (187, 10.8), "next_day": (188, 11.0), "no_slot": (189, 69.8), "mean_days": (213, 9.15)})

    def test_xlsx_reader_reads_shared_strings_and_numbers(self) -> None:
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
            z.writestr("xl/workbook.xml", f'<workbook {ns}><sheets><sheet name="P 16" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/sharedStrings.xml", f'<sst {ns}><si><t>TOTAL</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData><row r="25"><c r="A25" t="s"><v>0</v></c>'
                       '<c r="AB25"><v>8.63</v></c></row></sheetData></worksheet>')
        self.assertEqual(ingest.read_xlsx(buf.getvalue()), {"P 16": [(25, {"A": "TOTAL", "AB": "8.63"})]})

    def test_spearman_handles_ties_and_order(self) -> None:
        self.assertAlmostEqual(export.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(export.spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)
        self.assertAlmostEqual(export.spearman([1, 1, 2, 3], [5, 5, 6, 7]), 1.0)

    def test_curated_siap_values_are_cited(self) -> None:
        data = json.loads((ingest.MANUAL_DIR / "siap_2023.json").read_text(encoding="utf-8"))
        self.assertRegex(data["source"]["sha256"], r"^[0-9a-f]{64}$")
        for row in data["values"]:
            self.assertTrue(row["quote"] and row["page"] >= 1, row)
            digits = f"{int(row['value']):,}".replace(",", ".")
            self.assertIn(digits, row["quote"], row)

    def test_published_data_vs_story_figure_is_complete(self) -> None:
        data = json.loads((Path(__file__).resolve().parents[1] / "ui/site/public/visualizaciones/data/sanidad.json").read_text(encoding="utf-8"))
        story = data["data_vs_story"]
        self.assertGreaterEqual(len(story["countries"]["rows"]), 25)
        self.assertIn("ES", {c["code"] for c in story["countries"]["rows"]})
        self.assertEqual(story["countries"]["eu"]["x"], 100.0)
        regions = story["regions"]
        self.assertEqual(regions["n"], len(regions["rows"]))
        for row in regions["rows"]:
            self.assertGreater(row["x"], 0)
            self.assertGreater(row["x0"], 0)
        self.assertEqual(regions["days_up"], sum(1 for x in regions["rows"] if x["y"] > x["y0"]))

    def test_published_patient_and_money_sections(self) -> None:
        data = json.loads((Path(__file__).resolve().parents[1] / "ui/site/public/visualizaciones/data/sanidad.json").read_text(encoding="utf-8"))
        dental = data["patient"]["dental_cost"]
        self.assertGreaterEqual(dental["of"], 25)
        es = next(row for row in dental["rows"] if row["code"] == "ES")
        self.assertGreater(es["poor"], es["rich"])
        shares = data["money"]["functional_shares"]
        last = data["money"]["last"]
        total = sum(next(p["value"] for p in pts if p["year"] == last) for pts in shares.values())
        self.assertAlmostEqual(total, 100.0, delta=0.6)  # shares of the consolidated total, rounded to one decimal
        self.assertIn("doctors_in_spain", data["pay"]["doctors_abroad"])

    def test_curated_egsp_structure_adds_up(self) -> None:
        data = json.loads((ingest.MANUAL_DIR / "egsp_estructura.json").read_text(encoding="utf-8"))
        for section, total_label in (("economica", "GASTO TOTAL SECTORES"), ("funcional", "TOTAL CONSOLIDADO")):
            total = next(r for r in data[section] if r["label"] == total_label)["values"]
            parts = [r for r in data[section] if r["label"] not in ("TOTAL CONSOLIDADO", "GASTO TOTAL SECTORES")]
            for year, value in total.items():
                self.assertLessEqual(abs(sum(r["values"][year] for r in parts) - value), 5, (section, year))


if __name__ == "__main__":
    unittest.main()
