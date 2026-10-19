import io
import json
import sqlite3
import unittest
import zipfile
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, seed_sources
from publicdata_sqlite.provenance import seed_sources_from_config
from scripts import export_public_viz_employment as export
from scripts import ingest_employment_es as ingest

DEFINITION = {
    "source_id": "ameco_dbnomics",
    "dataset_code": "ZUTN",
    "indicator_code": "ZUTN",
    "frequency_code": "A",
    "unit_code": "PC_ACT",
    "label": "Paro",
    "source_url": "https://db.nomics.world/AMECO/ZUTN",
}


def series(values: dict[str, float], geo: str = "ESP") -> list[dict]:
    obs = [{"period": p, "value": v, "pointer": f"/x/{p}"} for p, v in values.items()]
    return [ingest.area_series(f"k|{geo}", geo, {}, obs)]


class FakeRaw:
    def __init__(self, data: dict, retrieved_at: str = "2026-10-19T00:00:00+00:00"):
        self.data, self.retrieved_at = data, retrieved_at


class IngestEmploymentTest(unittest.TestCase):
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
        self.assertEqual(self.load("a" * 64, {"1980": 11.7, "1981": 14.0, "1982": 16.0})["releases"], 1)
        self.assertEqual(self.load("a" * 64, {"1980": 11.7})["releases"], 0)
        self.load("b" * 64, {"1980": 11.7, "1981": 14.1, "2025": 10.5})
        states = dict(
            tuple(row) for row in self.conn.execute(
                """
                SELECT o.period_label, o.revision_state FROM indicator_observation_versions o
                JOIN indicator_releases r USING (indicator_release_id) WHERE r.comparison_state = 'compared'
                """
            ).fetchall()
        )
        self.assertEqual(states, {"1980": "unchanged", "1981": "changed", "1982": "deleted", "2025": "baseline"})
        domain = [tuple(row) for row in self.conn.execute("SELECT DISTINCT domain_key FROM indicator_definitions")]
        self.assertEqual(domain, [("empleo",)])
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_quarterly_periods_get_quarter_bounds(self) -> None:
        self.assertEqual(ingest.period_bounds("2024T3"), ("2024-07-01", "2024-09-30"))
        self.assertEqual(ingest.period_bounds("1995"), ("1995-01-01", "1995-12-31"))

    def test_ameco_marks_vintage_year_and_later_as_forecast(self) -> None:
        raw = FakeRaw({"series": {"docs": [{
            "series_code": "ESP.1.0.0.0.ZUTN", "indexed_at": "2026-06-04T01:29:11Z",
            "period": ["2024", "2025", "2026", "2027"], "value": [11.4, 10.5, 9.9, "NA"],
        }]}})
        (_, rows), = list(ingest.parse_ameco("ZUTN")(raw))
        statuses = {o["period"]: o["status"] for o in rows[0]["observations"]}
        self.assertEqual(statuses, {"2024": None, "2025": None, "2026": "forecast"})

    def test_eurostat_jsonstat_flat_index(self) -> None:
        # dims: freq(1) x age(2) x geo(2) x time(2); value index = age*4 + geo*2 + time
        raw = FakeRaw({
            "id": ["freq", "age", "unit", "geo", "time"], "size": [1, 2, 1, 2, 2],
            "dimension": {
                "freq": {"category": {"index": {"A": 0}}},
                "age": {"category": {"index": {"Y15-74": 0, "Y15-24": 1}, "label": {"Y15-74": "15-74", "Y15-24": "15-24"}}},
                "unit": {"category": {"index": {"PC_ACT": 0}}},
                "geo": {"category": {"index": {"ES": 0, "EU27_2020": 1}}},
                "time": {"category": {"index": {"2024": 0, "2025": 1}}},
            },
            "value": {"0": 11.4, "1": 10.5, "3": 6.0, "5": 24.9},
            "status": {"5": "p"},
        })
        batches = {d["indicator_code"]: s for d, s in ingest.parse_eurostat("une_rt_a")(raw)}
        total = {s["geo_code"]: {o["period"]: o["value"] for o in s["observations"]} for s in batches["Y15-74.PC_ACT"]}
        youth = {s["geo_code"]: {o["period"]: (o["value"], o["status"]) for o in s["observations"]} for s in batches["Y15-24.PC_ACT"]}
        self.assertEqual(total, {"ES": {"2024": 11.4, "2025": 10.5}, "EU27_2020": {"2025": 6.0}})
        self.assertEqual(youth, {"ES": {"2025": (24.9, "p")}})

    def test_ine_quarters_and_annual_mean_of_complete_years(self) -> None:
        raw = FakeRaw({"Nombre": "Tasa de paro", "Data": [
            {"Anyo": 2025, "FK_Periodo": p, "Valor": v} for p, v in zip((19, 20, 21, 22), (11.0, 10.0, 10.0, 9.0))
        ] + [{"Anyo": 2026, "FK_Periodo": 19, "Valor": 10.8}]})
        (_, rows), = list(ingest.parse_ine("EPA452434")(raw))
        periods = {o["period"]: o["value"] for o in rows[0]["observations"]}
        self.assertEqual(periods["2025T4"], 9.0)
        self.assertEqual(export.quarterly_to_annual(periods), {2025: 10.0})

    def test_ratio_is_computed_only_on_shared_years(self) -> None:
        self.assertEqual(export.ratio({1990: 16.0, 1991: 16.0}, {1991: 8.0}), {1991: 200.0})

    def test_events_require_a_citation(self) -> None:
        data = json.loads((ingest.MANUAL_DIR / "events_es.json").read_text(encoding="utf-8"))
        self.assertTrue(all(event["source_url"].startswith("https://") for event in data["events"]))
        counts = ingest.load_events(self.conn, "2026-10-19")
        self.assertEqual(counts["observations"], len(data["events"]))


    def test_monthly_periods(self) -> None:
        self.assertEqual(ingest.period_bounds("2024-02"), ("2024-02-01", "2024-02-29"))
        self.assertEqual(ingest.period_bounds("2025-12"), ("2025-12-01", "2025-12-31"))

    def test_pcaxis_cell_order_last_variable_fastest(self) -> None:
        px = (
            'STUB="Periodo","tipo contrato";\nHEADING="Sexo";\n'
            'VALUES("Periodo")="202501","202502";\nVALUES("tipo contrato")="TOTAL","FD";\nVALUES("Sexo")="Total Sexo","Mujer";\n'
            'DATA=\n100 60 10 4\n110 65 12 ".";\n'
        ).encode("cp1252")
        dims, tokens = ingest.parse_px(px)
        self.assertEqual([d for d, _ in dims], ["Periodo", "tipo contrato", "Sexo"])
        self.assertEqual(ingest.px_cell(dims, tokens, {"Periodo": "202502", "tipo contrato": "FD", "Sexo": "Total Sexo"}), (6, 12.0))
        self.assertEqual(ingest.px_cell(dims, tokens, {"Periodo": "202502", "tipo contrato": "FD", "Sexo": "Mujer"}), (7, None))

    def test_xlsx_reader_resolves_shared_strings(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                        '<sheet name="MLR-18" sheetId="1" r:id="rId1"/></sheets></workbook>')
            zf.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            zf.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                        '<si><t>Trabajadores fijos discontinuos</t></si></sst>')
            zf.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                        '<row r="18"><c r="A18" t="s"><v>0</v></c><c r="C18"><v>687884.25</v></c></row></sheetData></worksheet>')
        cells = ingest.xlsx_sheet(buf.getvalue(), "MLR-18")
        self.assertEqual(ingest.xlsx_rows(cells)[18], {"A": "Trabajadores fijos discontinuos", "C": "687884.25"})

    def test_pct_change_and_rebase(self) -> None:
        self.assertAlmostEqual(export.pct_change({2007: 200.0, 2013: 168.2}, 2007, 2013), -15.9)
        self.assertIsNone(export.pct_change({2007: 1.0}, 2007, 2013))
        self.assertEqual(export.rebase({1994: 50.0, 1995: 80.0, 2025: 100.0}, 1995), {1995: 100.0, 2025: 125.0})


    def test_published_narratives_add_up(self) -> None:
        data = json.loads((export.OUT_JSON).read_text(encoding="utf-8"))
        nar = data["narratives"]
        for row in nar["structural_gap"]["rows"]:
            self.assertAlmostEqual(row["gap"], row["structural"] + row["cyclical"], delta=0.02)
            self.assertAlmostEqual(row["gap"], row["es"] - row["eu"], delta=0.02)
        for q in nar["reform"]["quarters"]:
            self.assertAlmostEqual(q["total"], q["ordinary"] + q["fd"] + q["temporal"], delta=0.5)


    def test_series_split_at_eurostat_breaks(self) -> None:
        segs = export.segments({2022: 1.0, 2023: 2.0, 2024: 9.0, 2025: 10.0}, {2024: "b"})
        self.assertEqual(segs, [{2022: 1.0, 2023: 2.0}, {2024: 9.0, 2025: 10.0}])

    def test_dg_empl_upper_case_jsonstat_is_normalised(self) -> None:
        data = {"id": ["FREQ", "GEO", "TIME_PERIOD"], "dimension": {"FREQ": {}, "GEO": {}, "TIME_PERIOD": {}}}
        out = ingest.lower_jsonstat(data)
        self.assertEqual(out["id"], ["freq", "geo", "time"])
        self.assertEqual(sorted(out["dimension"]), ["freq", "geo", "time"])
        self.assertEqual(ingest.period_bounds("2025-S2"), ("2025-07-01", "2025-12-31"))


    def test_shift_share_parts_add_up(self) -> None:
        secs = export.SS_SECTORS
        Y = {x: {"ES": {2000: 100.0, 2024: 100.0}} for x in secs}
        H = {x: {"ES": {2000: 10.0, 2024: 10.0}} for x in secs}
        Y["A"]["ES"][2024] = 130.0  # agriculture becomes 30 % more productive, same hours
        H["G-I"]["ES"][2024] = 20.0  # hours move into commerce at the same productivity
        Y["G-I"]["ES"][2024] = 200.0
        res = export.shift_share(Y, H, "ES", 2000, 2024)
        self.assertAlmostEqual(res["within"] + res["shift"] + res["interaction"], res["total"], delta=0.15)
        self.assertGreater(res["within"], 0)
        self.assertEqual(res["shift"], 0.0)  # every sector had the same starting productivity

    def test_published_composition_blocks(self) -> None:
        comp = json.loads(export.OUT_JSON.read_text(encoding="utf-8"))["composition"]
        bases = [row["base"] for row in comp["base_year"]["productivity"]["rows"]]
        self.assertEqual(bases, export.BASES)
        for row in comp["education_counterfactual"]:
            self.assertLessEqual(abs(row["es_eu_mix"] - row["es"]), row["es"])  # a reweighting, not a different scale

    def test_second_cut_of_a_eurostat_table_keeps_its_own_code(self) -> None:
        url = ingest.eurostat_url("lfst_r_lfu3rt_es")
        self.assertIn("/lfst_r_lfu3rt?", url)
        self.assertIn("geo=ES30", url)
        self.assertIn("isced11=ED5-8", url)
        raw = FakeRaw({
            "id": ["freq", "isced11", "geo", "time"], "size": [1, 1, 2, 1],
            "dimension": {
                "freq": {"category": {"index": {"A": 0}}},
                "isced11": {"category": {"index": {"ED5-8": 0}}},
                "geo": {"category": {"index": {"ES21": 0, "ES30": 1}, "label": {"ES21": "País Vasco", "ES30": "Comunidad de Madrid"}}},
                "time": {"category": {"index": {"2025": 0}}},
            },
            "value": {"0": 2.9, "1": 3.3},
            "status": {"0": "du"},
        })
        (definition, rows), = list(ingest.parse_eurostat("lfst_r_lfu3rt_es")(raw))
        self.assertEqual(definition["dataset_code"], "lfst_r_lfu3rt_es")
        self.assertIn("/lfst_r_lfu3rt/", definition["source_url"])
        self.assertEqual({r["geo_code"]: r["observations"][0]["status"] for r in rows}, {"ES21": "du", "ES30": None})

    def test_published_segments_never_impute_unreliable_cells(self) -> None:
        seg = json.loads(export.OUT_JSON.read_text(encoding="utf-8"))["segments"]
        spec = json.loads(export.SEGMENTS_FILE.read_text(encoding="utf-8"))
        grouped = {code for g in spec["markets"]["groups"] for code in g["regions"]}
        self.assertEqual(grouped, {r["code"] for r in seg["regions"]})  # every community in exactly one market
        observed = []
        for row in seg["rows"]:
            for geo, flag in row["flags"].items():
                if flag in export.UNRELIABLE:
                    self.assertIsNone(row["values"][geo])
            observed += [v for v in row["values"].values() if v is not None]
        self.assertEqual(seg["extremes"]["min"]["value"], min(observed))
        self.assertEqual(seg["extremes"]["max"]["value"], max(observed))
        self.assertEqual(len(seg["cases"]), len(spec["cases"]))
        for case in seg["cases"]:
            self.assertTrue(all(f["value"] is not None for f in [*case["figures"], *case["national"]]))
        ts = seg["temporary_by_sector"]
        for sec in ("all", "private", "public"):
            self.assertTrue(all(0 < p["value"] < 100 for p in ts["series"][sec]))
        last = {sec: ts["series"][sec][-1]["value"] for sec in ("all", "private", "public")}
        self.assertTrue(min(last["private"], last["public"]) <= last["all"] <= max(last["private"], last["public"]))

    def test_published_copy_claims_hold(self) -> None:
        data = json.loads(export.OUT_JSON.read_text(encoding="utf-8"))
        h = data["headline"]
        # «el primer año de la serie y el de mayor ventaja de España»
        lv = data["productivity"]["level_vs_eu27"]["ESP"]
        self.assertEqual(lv[0]["year"], h["productivity_base"])
        self.assertEqual(max(p["value"] for p in lv), lv[0]["value"])
        # «parecido al europeo hasta before_years[1]; la brecha se abre en gap_from_year»
        self.assertEqual(h["before_years"][1] + 1, h["gap_from_year"])
        self.assertLess(abs(h["ratio_mean_before_gap"] - 1), 0.1)


if __name__ == "__main__":
    unittest.main()
