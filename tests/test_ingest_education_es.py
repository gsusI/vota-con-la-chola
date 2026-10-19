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
                quote = row["quote"].replace("\u2010", "-")  # some INEE PDFs use a Unicode hyphen for the minus sign
                self.assertTrue(value in quote or value.replace(".", ",") in quote, (key, row["area"], row["year"]))

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

    def test_mother_table_yields_rate_and_weight_from_one_file(self) -> None:
        px = """STUB="Tipo de indicador","Sexo","Nivel de formación de la madre";
HEADING="periodo";
VALUES("Tipo de indicador")="Tasa de abandono (2)","Peso del nivel de la madre (3)";
VALUES("Sexo")="AMBOS SEXOS";
VALUES("Nivel de formación de la madre")="TOTAL","E. Superior";
VALUES("periodo")="2025";
UNITS="Porcentajes";
DATA=12.8
2.4
100
6.6;
""".encode("iso-8859-15")
        name, _url, parse = next(s for s in ingest.MEFP_SOURCES if s[0] == "mefp_aban_1_08.px")
        batches = list(parse(ingest.Raw(name, "https://example.org", px, "2026-10-19T00:00:00+00:00")))
        codes = {definition["indicator_code"]: {s["dimensions"]["Nivel de formación de la madre"]: s["observations"][0]["value"] for s in series}
                 for definition, series in batches}
        self.assertEqual(codes, {"abandono_por_formacion_madre": {"TOTAL": 12.8, "E. Superior": 2.4},
                                 "abandono_peso_formacion_madre": {"TOTAL": 100.0, "E. Superior": 6.6}})

    def test_mother_decomposition_recovers_population_shares_and_splits_the_change(self) -> None:
        from scripts.export_public_viz_education import MOTHER_LEVELS, mother_decomposition
        # Population shares 50/50 -> 20/80 across two groups (others empty but non-zero to keep the identity defined).
        pop = {2002: [0.50, 0.0, 0.0, 0.50, 0.0], 2025: [0.20, 0.0, 0.0, 0.80, 0.0]}
        rate = {2002: [40.0, 1.0, 1.0, 10.0, 1.0], 2025: [30.0, 1.0, 1.0, 5.0, 1.0]}
        rates: dict = {g: {} for g in MOTHER_LEVELS} | {"TOTAL": {}}
        weights: dict = {g: {} for g in MOTHER_LEVELS}
        for year in pop:
            eps = 1e-6
            shares = [s or eps for s in pop[year]]
            total = sum(s * r for s, r in zip(shares, rate[year])) / sum(shares)
            rates["TOTAL"][year] = total
            for g, s, r in zip(MOTHER_LEVELS, shares, rate[year]):
                rates[g][year] = r
                weights[g][year] = s * r / sum(shares) / total * 100
        out = mother_decomposition(rates, weights)
        self.assertEqual(out["share_check"], 100.0)
        self.assertEqual(out["rows"][0]["share_first"], 50.0)
        self.assertEqual(out["rows"][3]["share_last"], 80.0)
        split = out["decomposition"][0]
        self.assertEqual((split["from"], split["to"]), (2002, 2025))
        self.assertAlmostEqual(split["within"] + split["composition"], split["total_change"], delta=0.11)
        # within: 0.35 × (−10) + 0.65 × (−5) = −6.75; composition: −0.30 × 35 + 0.30 × 7.5 = −8.25
        self.assertAlmostEqual(split["within"], -6.75, delta=0.06)
        self.assertAlmostEqual(split["composition"], -8.25, delta=0.06)


if __name__ == "__main__":
    unittest.main()
