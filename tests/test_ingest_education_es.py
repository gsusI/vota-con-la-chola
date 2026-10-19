import json
import sqlite3
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, seed_sources
from publicdata_sqlite.provenance import seed_sources_from_config
from scripts import ingest_education_es as ingest

PX = """TITLE="5. Tasas de idoneidad en la edad de 15 años por sexo, comunidad  autónoma y periodo.";
STUB="Sexo","Comunidad autónoma";
HEADING="periodo";
VALUES("Sexo")="AMBOS SEXOS","HOMBRES";
VALUES("Comunidad autónoma")="TOTAL","Andalucía";
VALUES("periodo")="2024-25","2023-24 (*)";
UNITS="Porcentaje de alumnos";
DATA=76.3 75.7
70.1 ".."
72.6 70.9
66.0 65.1;
""".encode("iso-8859-15")

DEFINITION = {
    "source_id": "mefp_educabase",
    "dataset_code": "idoneidad_05",
    "indicator_code": "tasa_idoneidad_15",
    "frequency_code": "SY",
    "unit_code": "PC",
    "label": "Idoneidad",
    "source_url": "https://estadisticas.educacion.gob.es/",
}


class IngestEducationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_schema(self.conn, Path(DEFAULT_SCHEMA))
        seed_sources(self.conn)
        seed_sources_from_config(self.conn, ingest.LOCAL_SOURCES)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def test_pcaxis_cells_follow_stub_heading_order(self) -> None:
        px = ingest.parse_px(PX)
        cells = list(ingest.px_cells(px))
        self.assertEqual(len(cells), 8)
        index, coords, cell = cells[2]
        self.assertEqual(coords, {"Sexo": "AMBOS SEXOS", "Comunidad autónoma": "Andalucía", "periodo": "2024-25"})
        self.assertEqual(cell, "70.1")
        self.assertIsNone(ingest.px_number(cells[3][2]))  # ".." is a missing value, not zero

    def test_mefp_parser_keeps_selected_cells_with_school_year_periods(self) -> None:
        parse = ingest.parse_mefp(
            "idoneidad_05", "/x", "idoneidad_05.px", indicator_code="tasa_idoneidad_15", label="Idoneidad",
            unit_code="PC", definition_text="", keep=lambda c: c["Sexo"] == "AMBOS SEXOS", period_var="periodo",
            region_var="Comunidad autónoma", school=True,
        )
        raw = ingest.Raw("idoneidad_05.px", "https://example.org", PX, "2026-10-19T00:00:00+00:00")
        (definition, series), = list(parse(raw))
        by_geo = {s["geo_code"]: s for s in series}
        self.assertEqual(set(by_geo), {"ES", "ES-CCAA:Andalucía"})
        total = by_geo["ES"]["observations"]
        self.assertEqual([(o["period"], o["value"], o["pointer"]) for o in total], [("2024-25", 76.3, "/DATA/0"), ("2023-24", 75.7, "/DATA/1")])
        self.assertEqual((total[0]["start"], total[0]["end"]), ("2024-09-01", "2025-08-31"))
        self.assertEqual(total[1]["status"], "provisional")
        self.assertEqual(len(by_geo["ES-CCAA:Andalucía"]["observations"]), 1)

    def test_release_comparison_and_evidence(self) -> None:
        def load(sha: str, values: dict[str, float]) -> dict:
            obs = [{"period": p, "value": v, "pointer": f"/DATA/{i}", **ingest.school_year(p)} for i, (p, v) in enumerate(values.items())]
            series = [ingest.area_series("idoneidad|ES", "ES", {}, obs)]
            return ingest.load_indicator(self.conn, dict(DEFINITION), sha, 10, "etl/data/raw/education/x.px",
                                         "https://example.org", "2026-10-19", {}, series)

        self.assertEqual(load("a" * 64, {"2023-24": 75.7, "2024-25": 76.0})["releases"], 1)
        self.assertEqual(load("a" * 64, {"2023-24": 75.7})["releases"], 0)  # same payload: idempotent
        load("b" * 64, {"2023-24": 75.7, "2024-25": 76.3})
        states = dict(tuple(row) for row in self.conn.execute(
            """
            SELECT o.period_label, o.revision_state FROM indicator_observation_versions o
            JOIN indicator_releases r USING (indicator_release_id) WHERE r.comparison_state = 'compared'
            """
        ).fetchall())
        self.assertEqual(states, {"2023-24": "unchanged", "2024-25": "changed"})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM indicator_observation_evidence").fetchone()[0], 4)
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_curated_pisa_rows_cite_a_known_document(self) -> None:
        data = json.loads((ingest.MANUAL_DIR / "pisa_curated_es.json").read_text(encoding="utf-8"))
        for key, rows in data["series"].items():
            self.assertIn(key, ingest.CURATED_LABELS)
            for row in rows:
                self.assertIn(row["document"], data["documents"])
                self.assertTrue(row["quote"] and row["pdf_page"] > 0)
                if key.endswith("_flag"):
                    continue  # membership flags quote the sentence that lists the group, not a number
                value = format(row["value"], "g")
                self.assertTrue(value in row["quote"] or value.replace(".", ",") in row["quote"], (key, row["area"], row["year"]))

    def test_teacher_salary_series_keep_every_dimension(self) -> None:
        payload = json.dumps({"series": {"docs": [{
            "series_code": "ESP.SAL_STA.IX.INST_EDU_PUB.ISCED11_24._T._T.TE.TYP_EXP.EXP15._Z",
            "period": ["2009", "2015", "2024"], "value": [113.9, 100.0, "NA"],
        }]}}).encode()
        raw = ingest.Raw("oecd_eag_teacher_salaries_dbnomics.json", "https://example.org", payload, "2026-10-19T00:00:00+00:00")
        (definition, series), = list(ingest.parse_oecd_salaries(raw))
        self.assertEqual(definition["unit_code"], "IX2015")
        self.assertEqual(series[0]["dimensions"]["EDUCATION_LEV"], "ISCED11_24")
        self.assertEqual(series[0]["dimensions"]["PERS_EXP_LEV"], "EXP15")
        self.assertEqual([o["period"] for o in series[0]["observations"]], ["2009", "2015"])  # "NA" is not a value

    def test_regional_pisa_rows_map_to_ministry_region_names(self) -> None:
        data = json.loads((ingest.MANUAL_DIR / "pisa_curated_es.json").read_text(encoding="utf-8"))
        regions = {row["area"] for row in data["series"]["pisa_math_mean"] if row["area"].startswith("ES-CCAA:")}
        self.assertEqual(len(regions), 19)  # 17 comunidades + Ceuta y Melilla
        self.assertIn("ES-CCAA:Asturias, Principado de", regions)

    def test_ine_epf_keeps_only_education_series(self) -> None:
        payload = json.dumps([
            {"COD": "A", "Nombre": "Gasto medio por hogar. Quintil 1. Servicios de educación. Dato base. ", "Data": [{"Anyo": 2025, "Valor": 190.4}]},
            {"COD": "B", "Nombre": "Gasto medio por hogar. Quintil 1. Vivienda. Dato base. ", "Data": [{"Anyo": 2025, "Valor": 5000.0}]},
        ]).encode()
        raw = ingest.Raw("ine_epf_t73828.json", "https://example.org", payload, "2026-10-19T00:00:00+00:00")
        (definition, series), = list(ingest.parse_ine_epf(73828)(raw))
        self.assertEqual(definition["source_id"], "ine_epf")
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["observations"][0]["pointer"], "/0/Data/0/Valor")

    def test_oecd_earnings_keep_full_time_25_64_both_sexes(self) -> None:
        def doc(code: str) -> dict:
            return {"series_code": code, "period": ["2023"], "value": [149.0]}
        payload = json.dumps({"series": {"docs": [
            doc("ESP._T.Y25T64.ISCED11A_5T8._T.EARN_RELATIVE._Z._T._Z.ED_NED.EMP._Z.PT_EARN_WR_ISCED11A_3.OBS.FT.EARNINGS.A"),
            doc("ESP.F.Y25T64.ISCED11A_5T8._T.EARN_RELATIVE._Z._T._Z.ED_NED.EMP._Z.PT_EARN_WR_ISCED11A_3.OBS.FT.EARNINGS.A"),
            doc("ESP._T.Y25T64.ISCED11A_5T8._T.EARN_RELATIVE._Z._T._Z.ED_NED.EMP._Z.PT_EARN_WR_ISCED11A_3.OBS._T.EARNINGS.A"),
        ]}}).encode()
        raw = ingest.Raw("oecd_eag_earnings_dbnomics.json", "https://example.org", payload, "2026-10-19T00:00:00+00:00")
        (_definition, series), = list(ingest.parse_oecd_earnings(raw))
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["dimensions"]["ATTAINMENT_LEV"], "ISCED11A_5T8")


if __name__ == "__main__":
    unittest.main()
