import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, seed_sources
from publicdata_sqlite.provenance import seed_sources_from_config
from scripts import export_public_viz_housing as export
from scripts import ingest_housing_es as ingest

DEFINITION = {
    "source_id": "bde_indicadores_vivienda",
    "dataset_code": "si_1_5",
    "indicator_code": "epa_hogares",
    "frequency_code": "Q",
    "unit_code": "THOUSANDS_HOUSEHOLDS",
    "label": "Hogares",
    "source_url": "https://www.bde.es/",
}

BDE_CSV = "\n".join([
    '"CÓDIGO DE LA SERIE",DEPA202100.T,D_1KB02000',
    '"NÚMERO SECUENCIAL",1,2',
    '"ALIAS DE LA SERIE","SI_1_5.36","SI_1_5.17"',
    '"DESCRIPCIÓN DE LA SERIE","EPA. Hogares","Viviendas iniciadas"',
    '"DESCRIPCIÓN DE LAS UNIDADES","Miles de personas","Viviendas"',
    '"FRECUENCIA","TRIMESTRAL","MENSUAL"',
    '"ENE 2024","_",100',
    '"FEB 2024","_",110',
    '"MAR 2024",19000.5,120',
    '"JUN 2024",19100.0,"_"',
    '"FUENTE","Instituto Nacional de Estadística","Ministerio"',
    '"NOTAS","",""',
]).encode("latin-1")


def series(values: dict[str, float]) -> list[dict]:
    obs = [{"period": p, "value": v, "pointer": f"/rows/{p}"} for p, v in values.items()]
    return [ingest.geo_series("k|ES", "ES", {}, obs)]


class IngestHousingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        apply_schema(self.conn, Path(DEFAULT_SCHEMA))
        seed_sources(self.conn)
        seed_sources_from_config(self.conn, ingest.LOCAL_SOURCES)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def load(self, sha: str, values: dict[str, float]) -> dict:
        return ingest.load_indicator(
            self.conn, dict(DEFINITION), sha, 10, "etl/data/raw/x.csv", "https://example.org", "2026-10-19", {}, series(values)
        )

    def test_new_release_compares_every_observation_with_quarter_bounds(self) -> None:
        self.load("a" * 64, {"2024-Q1": 19000.5, "2024-Q2": 19100.0, "2024-Q3": 19200.0})
        self.assertEqual(self.load("a" * 64, {"2024-Q1": 1.0})["releases"], 0)  # same payload: idempotent
        self.load("b" * 64, {"2024-Q1": 19000.5, "2024-Q2": 19150.0, "2024-Q4": 19300.0})
        rows = self.conn.execute(
            """
            SELECT o.period_label, o.revision_state, o.revision_ordinal, o.period_start, o.period_end, o.interval_kind
            FROM indicator_observation_versions o JOIN indicator_releases r USING (indicator_release_id)
            WHERE r.comparison_state = 'compared'
            """
        ).fetchall()
        got = {row[0]: row[1:] for row in rows}
        self.assertEqual(got["2024-Q1"][:2], ("unchanged", 1))
        self.assertEqual(got["2024-Q2"][:2], ("changed", 2))
        self.assertEqual(got["2024-Q3"], ("deleted", 2, "2024-07-01", "2024-09-30", "calendar_quarter"))
        self.assertEqual(got["2024-Q4"][:2], ("baseline", 1))
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_bde_csv_parses_alias_frequency_and_cells(self) -> None:
        raw = ingest.Raw("bde_si_1_5.csv", "https://www.bde.es/x.csv", BDE_CSV, "2026-10-19T00:00:00+00:00")
        batches = {d["indicator_code"]: (d, s) for d, s in ingest.parse_bde(raw)}
        hh_def, hh = batches["epa_hogares"]
        self.assertEqual(hh_def["frequency_code"], "Q")
        self.assertEqual([(o["period"], o["value"], o["pointer"]) for o in hh[0]["observations"]],
                         [("2024-Q1", "19000.5", "/rows/8/cols/1"), ("2024-Q2", "19100.0", "/rows/9/cols/1")])
        starts = batches["viviendas_iniciadas_total"][1][0]["observations"]
        self.assertEqual([o["period"] for o in starts], ["2024-01", "2024-02", "2024-03"])

    def test_jsonstat_flat_index_decomposition(self) -> None:
        data = {
            "id": ["geo", "time"], "size": [2, 3],
            "dimension": {"geo": {"category": {"index": {"ES": 0, "DE": 1}}}, "time": {"category": {"index": {"2023": 0, "2024": 1, "2025": 2}}}},
            "value": {"2": 30.2, "4": 24.0},
        }
        cells = sorted((c["geo"], c["time"], v) for c, _flat, v in ingest.jsonstat_cells(data))
        self.assertEqual(cells, [("DE", "2024", 24.0), ("ES", "2025", 30.2)])

    def test_curated_document_must_match_its_sha256(self) -> None:
        with tempfile.NamedTemporaryFile(dir=ingest.REPO_ROOT / "tests", suffix=".txt") as handle:
            handle.write(b"censo")
            handle.flush()
            rel = Path(handle.name).relative_to(ingest.REPO_ROOT).as_posix()
            ok = ingest.document_ref({"raw_file": rel, "raw_sha256": ingest.sha256_bytes(b"censo"), "locator": "p. 3"})
            self.assertEqual(ok["locator"], "p. 3")
            with self.assertRaises(ValueError):
                ingest.document_ref({"raw_file": rel, "raw_sha256": "0" * 64})

    def test_annual_aggregation_drops_partial_years(self) -> None:
        quarters = {"2025-Q1": 1.0, "2025-Q2": 2.0, "2025-Q3": 3.0, "2025-Q4": 4.0, "2026-Q1": 9.0}
        self.assertEqual(export.annual(quarters), {2025: 2.5})
        months = {f"2025-{m:02d}": 1.0 for m in range(1, 13)} | {"2026-01": 5.0}
        self.assertEqual(export.annual(months, "sum"), {2025: 12.0})


class RegionalParsingTest(unittest.TestCase):
    def test_region_labels_from_mivau_and_ine_map_to_nuts2(self) -> None:
        cases = {
            "Madrid (Comunidad de)": "ES30", "Madrid, Comunidad de": "ES30", "Balears (Illes)": "ES53", "Balears, Illes": "ES53",
            "Castilla - La Mancha": "ES42", "Castilla-La Mancha": "ES42", "Comunitat Valenciana": "ES52", "Rioja (La)": "ES23",
            "Navarra (Comunidad Foral de) ": "ES22", "País Vasco": "ES21", "Andalucía ": "ES61", "Asturias, Principado de": "ES12",
        }
        for label, code in cases.items():
            self.assertEqual(ingest.ccaa_code(label), code, label)
        for province in ("Almería", "Valencia/València", "Alicante/Alacant", "Bizkaia", "Total Nacional", None):
            self.assertIsNone(ingest.ccaa_code(province), province)

    def test_ine_periods(self) -> None:
        self.assertEqual(ingest.ine_period({"Anyo": 2024, "FK_Periodo": 28}), "2024")
        self.assertEqual(ingest.ine_period({"Anyo": 2025, "FK_Periodo": 21}), "2025-Q3")
        self.assertEqual(ingest.ine_period({"Anyo": 2026, "FK_Periodo": 5}), "2026-05")

    def test_ine_table_selector_keeps_national_and_regional_totals_only(self) -> None:
        pick = ingest.INE_TABLES["59056"][-1]
        self.assertEqual(pick("Total Nacional. Total. Índice. "), "ES")
        self.assertEqual(pick("Andalucía. Total. Índice. "), "ES61")
        self.assertIsNone(pick("Andalucía. Total. Variación anual. "))
        self.assertIsNone(pick("Andalucía. Vivienda colectiva. Índice. "))

    def test_connected_story_uses_epa_windows_census_fallback_and_flags_2021(self) -> None:
        completed = {2001: 500.0, 2019: 80.0, 2020: 90.0, 2021: 100.0, 2022: 90.0}
        net = {2019: 100.0, 2020: 100.0, 2021: -50.0, 2022: 300.0}
        census = [{"from": 1991, "to": 2001, "per_year": 250.0}]
        income = {y: 7.0 for y in completed}
        story = {p["year"]: p for p in export.connected_story(completed, net, census, income, {}, {}, first_year=2001)}
        self.assertEqual((story[2001]["x"], story[2001]["basis"]), (2.0, "censos 1991–2001"))
        self.assertEqual((story[2020]["x"], story[2020]["basis"]), (0.85, "epa"))
        self.assertEqual(story[2021]["basis"], "epa_2021")
        self.assertEqual(story[2022]["window"], [2020, 2021, 2022])

    def test_oecd_property_revenue_keeps_totals_and_maps_oecd_average(self) -> None:
        payload = {"series": {"docs": [
            {"series_code": "ESP.TAX_REV.S13.T_4100._T.PT_B1GQ.A", "period": ["2023", "2024"], "value": [0.9, 0.89]},
            {"series_code": "OECD_REP.TAX_REV.S13.T_4400._T.PT_B1GQ.A", "period": ["2023"], "value": [0.37]},
            {"series_code": "ESP.TAX_REV.S13.T_4100._T.XDC.A", "period": ["2024"], "value": [14.0]},
        ]}}
        raw = ingest.Raw("x.json", "https://db.nomics.world", json.dumps(payload).encode(), "2026-10-19T00:00:00+00:00")
        batches = {d["indicator_code"]: s for d, s in ingest.parse_oecd_rev(raw)}
        self.assertEqual(sorted(batches), ["TAX_REV.S13.T_4100", "TAX_REV.S13.T_4400"])
        self.assertEqual([s["geo_code"] for s in batches["TAX_REV.S13.T_4400"]], ["OECD"])
        self.assertEqual(len(batches["TAX_REV.S13.T_4100"][0]["observations"]), 2)

    def test_wage_survey_selectors(self) -> None:
        median = ingest.EES_TABLES["28191"][0][2]
        self.assertTrue(median("Ambos sexos. Total Nacional. Dato base. Mediana. "))
        self.assertFalse(median("Mujeres. Total Nacional. Dato base. Mediana. "))
        self.assertFalse(median("Ambos sexos. Total Nacional. Dato base. Percentil 10. "))
        by_age = ingest.EES_TABLES["28201"][0][2]
        self.assertTrue(by_age("Ambos sexos. De 25 a 34 años. Dato base. Total Nacional. Salario medio bruto. "))

    def test_regional_rent_sources_cover_every_region(self) -> None:
        self.assertEqual(sorted(ingest.INE_CCAA_TO_NUTS.values()), sorted(ingest.CCAA))
        renters = ingest.INE_TABLES["9997"][-1]
        income = ingest.INE_TABLES["9949"][-1]
        self.assertEqual(renters("Andalucía. Alquiler a precio de mercado. Hogar. "), "ES61")
        self.assertIsNone(renters("Andalucía. Alquiler inferior al precio de mercado. Hogar. "))
        self.assertEqual(income("Total Nacional. Renta neta media por hogar. Base 2013. "), "ES")
        self.assertIsNone(income("Total Nacional. Renta media por hogar (con alquiler imputado). Base 2013. "))

    def test_ecv_split_tables_keep_both_sexes_national_and_single_tenures(self) -> None:
        by_age = ingest.INE_SPLIT_TABLES["9994"][-1]
        self.assertEqual(by_age("Ambos sexos. De 16 a 29 años. Total Nacional. Propiedad sin hipoteca. Hogar. "),
                         {"edad": "De 16 a 29 años", "tenencia": "Propiedad sin hipoteca"})
        self.assertIsNone(by_age("Hombres. De 16 a 29 años. Total Nacional. Propiedad sin hipoteca. Hogar. "))
        income = ingest.INE_SPLIT_TABLES["59956"][-1]
        self.assertEqual(income("Total Nacional. Alquiler a precio de mercado. Renta neta media por hogar. Base 2013. "),
                         {"tenencia": "Alquiler a precio de mercado"})
        self.assertIsNone(income("Total Nacional. Propiedad. Renta media por hogar (con alquiler imputado). Base 2013. "))

    def test_serpavi_municipalities_keep_only_city_provinces(self) -> None:
        rows = [
            ("CPRO", "NPRO", "CUMUN", "NMUN", "ALQTBID12_M_VC_23", "ALQTBID12_M_VC_24", "BI_ALVHEPCO_TVC_24"),
            (28, "Madrid", 28079, "Madrid", 820.0, 868.75, 300447),
            (28, "Madrid", 28065, "Getafe", None, 700.0, 12120),
            (49, "Zamora", 49275, "Zamora", 400.0, 409.7, 3865),
        ]
        batches = {d["indicator_code"]: s for d, s in ingest.serpavi_municipalities(iter(rows))}
        rent = {s["geo_code"]: [(o["period"], o["value"]) for o in s["observations"]] for s in batches["serpavi_alquiler_mensual_mediano_vc_municipio"]}
        self.assertEqual(rent, {"28065": [("2024", 700.0)], "28079": [("2023", 820.0), ("2024", 868.75)]})
        self.assertEqual(batches["serpavi_viviendas_alquiladas_vc_municipio"][1]["geo_level"], "municipality")

    def test_mortgage_payment_is_a_french_annuity(self) -> None:
        self.assertAlmostEqual(export.mortgage_payment(100000, 0), 100000 / 300)
        self.assertAlmostEqual(export.mortgage_payment(265392, 2.78), 1228.36, places=2)

    def test_tax_decomposition_splits_net_years_exactly(self) -> None:
        # The coordinator's reference: 6.71 gross years in 2025 at a 23.5 % rate, 4.94 in 2000 at 19.8 %.
        out = export.tax_decomposition({2000: 4.94, 2013: 5.95, 2019: 6.3, 2025: 6.71}, {2000: 19.8, 2013: 22.9, 2019: 21.8, 2025: 23.5}, (2000, 2013, 2019))
        first = out["from_base"][0]
        self.assertEqual((first["from"], first["to"]), (2000, 2025))
        self.assertAlmostEqual(first["years_to"], 8.77, places=2)
        self.assertAlmostEqual(first["tax_part"], 0.4, places=2)
        for row in out["from_base"] + out["steps"]:
            self.assertAlmostEqual(row["price_part"] + row["tax_part"], row["change"], places=1)
        step = next(row for row in out["steps"] if row["from"] == 2013)
        self.assertEqual(step["to"], 2019)
        self.assertLess(step["tax_part"], 0)  # the rate fell between 2013 and 2019

    def test_index_rebase(self) -> None:
        self.assertEqual(export.index_to({2015: 80.0, 2025: 100.0}, 2015), {2015: 100.0, 2025: 125.0})
        self.assertEqual(export.index_to({2016: 1.0}, 2015), {})


if __name__ == "__main__":
    unittest.main()
