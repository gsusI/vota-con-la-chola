import sqlite3
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, seed_sources
from publicdata_sqlite.provenance import seed_sources_from_config
from scripts import ingest_public_finance_es as ingest

DEFINITION = {
    "source_id": "oecd_revenue_statistics",
    "dataset_code": "DSD_REV_COMP_OECD@DF_RSOECD",
    "indicator_code": "TAX_REV.S13._T",
    "frequency_code": "A",
    "unit_code": "PT_B1GQ",
    "label": "Total",
    "source_url": "https://db.nomics.world/OECD/DSD_REV_COMP_OECD@DF_RSOECD",
}


def series(values: dict[str, float]) -> list[dict]:
    obs = [{"period": p, "value": v, "pointer": f"/x/{p}"} for p, v in values.items()]
    return [ingest.area_series("k|ESP", "ESP", {}, obs)]


class IngestPublicFinanceTest(unittest.TestCase):
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

    def states(self) -> dict[str, tuple[str, int]]:
        rows = self.conn.execute(
            """
            SELECT o.period_label, o.revision_state, o.revision_ordinal FROM indicator_observation_versions o
            JOIN indicator_releases r USING (indicator_release_id)
            WHERE r.comparison_state = 'compared'
            """
        ).fetchall()
        return {period: (state, ordinal) for period, state, ordinal in rows}

    def test_new_release_compares_every_observation(self) -> None:
        self.assertEqual(self.load("a" * 64, {"1965": 14.27, "1966": 13.5, "1967": 15.0})["releases"], 1)
        self.assertEqual(self.load("a" * 64, {"1965": 14.27})["releases"], 0)  # same payload: idempotent
        self.load("b" * 64, {"1965": 14.27, "1966": 13.6, "2024": 36.7})
        self.assertEqual(
            self.states(),
            {"1965": ("unchanged", 1), "1966": ("changed", 2), "1967": ("deleted", 2), "2024": ("baseline", 1)},
        )
        evidence = self.conn.execute("SELECT COUNT(*) FROM indicator_observation_evidence").fetchone()[0]
        self.assertEqual(evidence, 6)  # every stored value (not deletions) points at its raw cell
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_eurostat_list_filter_yields_one_indicator_per_code(self) -> None:
        # JSON-stat cube: freq(1) x unit(1) x cofog99(2) x geo(2) x time(2), flattened row-major.
        cube = {
            "id": ["freq", "unit", "cofog99", "geo", "time"], "size": [1, 1, 2, 2, 2],
            "dimension": {
                "freq": {"category": {"index": {"A": 0}}},
                "unit": {"category": {"index": {"PC_GDP": 0}}},
                "cofog99": {"category": {"index": {"GF07": 0, "GF09": 1}, "label": {"GF07": "Health", "GF09": "Education"}}},
                "geo": {"category": {"index": {"ES": 0, "DE": 1}}},
                "time": {"category": {"index": {"2023": 0, "2024": 1}}},
            },
            "value": {"0": 6.4, "1": 6.5, "2": 7.5, "3": 7.6, "4": 4.0, "5": 4.1, "7": 4.5},
        }
        raw = ingest.Raw.__new__(ingest.Raw)
        raw.data = cube
        spec = {
            "name": "t", "dataset": "gov_10a_exp", "filters": {"unit": "PC_GDP", "cofog99": ["GF07", "GF09", "GF99"]},
            "unit_code": "PC_GDP", "unit_label": "%", "label": "Gasto: {label}", "definition": "x",
        }
        batches = {d["indicator_code"]: (d, series) for d, series in ingest.parse_eurostat_dataset(spec)(raw)}
        self.assertEqual(sorted(batches), ["GF07", "GF09"])  # codes absent from the cube are skipped
        self.assertEqual(batches["GF09"][0]["label"], "Gasto: Education")
        values = {s["geo_code"]: [(o["period"], o["value"]) for o in s["observations"]] for s in batches["GF09"][1]}
        self.assertEqual(values, {"ES": [("2023", 4.0), ("2024", 4.1)], "DE": [("2024", 4.5)]})
        self.assertIn("cofog99=GF09", batches["GF09"][1][0]["key"])

    def test_eu_silc_series_are_declared(self) -> None:
        # The tax page's «bolsillo» figures need EU-SILC median income and housing cost next to the national accounts.
        names = {spec["name"]: spec for spec in ingest.EUROSTAT_DATASETS}
        self.assertEqual(names["ilc_di03_pps"]["filters"]["statinfo"], ["MED_EI", "MEAN_EI"])
        self.assertIn("RENT_MKT", names["ilc_lvho07c"]["filters"]["tenure"])
        self.assertIn("B_60", names["ilc_mded01"]["filters"]["rskpovth"])
        self.assertEqual(len(names), len(ingest.EUROSTAT_DATASETS))  # raw file stems must be unique

    def test_oecd_dbnomics_parsers_group_by_measure(self) -> None:
        raw = ingest.Raw.__new__(ingest.Raw)
        raw.data = {"series": {"docs": [
            {"series_code": "ESP.A.INC_DISP_GINI", "period": ["2022", "2023"], "value": [0.32, "NA"],
             "dimensions": {"REF_AREA": "ESP", "MEASURE": "INC_DISP_GINI", "AGE": "_T"}},
            {"series_code": "DEU.A.INC_DISP_GINI", "period": ["2022"], "value": [0.31],
             "dimensions": {"REF_AREA": "DEU", "MEASURE": "INC_DISP_GINI", "AGE": "_T"}},
            {"series_code": "ESP.A.POP", "period": ["2022"], "value": [1.0],
             "dimensions": {"REF_AREA": "ESP", "MEASURE": "POP", "AGE": "_T"}},
        ]}}
        batches = list(ingest.parse_oecd_idd(raw))
        self.assertEqual([d["indicator_code"] for d, _ in batches], ["INC_DISP_GINI._T"])  # unknown measures dropped
        series = {s["geo_code"]: [(o["period"], o["value"]) for o in s["observations"]] for s in batches[0][1]}
        self.assertEqual(series, {"ESP": [("2022", 0.32)], "DEU": [("2022", 0.31)]})  # "NA" cells skipped

    def test_segment_series_are_declared(self) -> None:
        # «Cinco hogares» and the age split need these EU-SILC/ICW cuts; TOTAL age stays in ilc_di03_nac (one indicator).
        names = {spec["name"]: spec for spec in ingest.EUROSTAT_DATASETS}
        self.assertNotIn("TOTAL", names["ilc_di03_age_nac"]["filters"]["age"])
        self.assertIn("Y_GE65", names["ilc_di03_age_nac"]["filters"]["age"])
        self.assertIn("A1_LT65", names["ilc_mded02"]["filters"]["hhcomp"])
        self.assertEqual(names["ilc_mded03_rent"]["filters"]["tenure"], "RENT")
        self.assertIn("A1_GE65", names["ilc_mded03_own"]["filters"]["hhcomp"])
        self.assertEqual(names["icw_tax_03"]["filters"]["quant_inc"][-1], "QU5")

    def test_taxing_wages_households_parser(self) -> None:
        raw = ingest.Raw.__new__(ingest.Raw)
        doc = lambda m, hh, inc, sp, unit, v: {  # noqa: E731
            "series_code": f"ESP.{m}.{hh}.{inc}.{sp}.{unit}", "period": ["2024"], "value": [v],
            "dimensions": {"REF_AREA": "ESP", "MEASURE": m, "HOUSEHOLD_TYPE": hh, "INCOME_PRINCIPAL": inc,
                           "INCOME_SPOUSE": sp, "UNIT_MEASURE": unit}}
        raw.data = {"series": {"docs": [
            doc("NPATR", "S_C2", "AW67", "_Z", "PT_WG_EARN_G", 5.8),
            doc("NPATR", "S_C2", "AW67", "_Z", "XDC", 1.0),  # wrong unit for the measure: dropped
            doc("AV_TW", "S_C0", "AW100", "_Z", "PT_COS_LB", 41.1),  # single earner's wedge stays in parse_oecd_tw
            doc("AV_TW", "C_C2", "AW100", "NOEARN_UNEMP", "PT_COS_LB", 36.3),
            doc("GEBT", "C_C2", "AW100", "AW67", "XDC", 52558.0),
        ]}}
        batches = {d["indicator_code"]: (d, s) for d, s in ingest.parse_oecd_tw_households(raw)}
        self.assertEqual(sorted(batches), ["AV_TW.C_C2.AW100.NOEARN_UNEMP", "GEBT.C_C2.AW100.AW67", "NPATR.S_C2.AW67._Z"])
        self.assertEqual(batches["NPATR.S_C2.AW67._Z"][0]["unit_code"], "PT_WG_EARN_G")
        self.assertIn("pareja no trabaja", batches["AV_TW.C_C2.AW100.NOEARN_UNEMP"][0]["label"])
        self.assertEqual(batches["GEBT.C_C2.AW100.AW67"][1][0]["observations"][0]["value"], 52558.0)

    def test_case_interpolation(self) -> None:
        from scripts import export_public_viz_fiscal as export

        schedule = [(0.67, 18.5), (1.0, 23.1), (1.67, 29.3)]
        self.assertAlmostEqual(export.interp(schedule, 1.0), 23.1)
        self.assertAlmostEqual(export.interp(schedule, 0.835), (18.5 + 23.1) / 2)
        self.assertAlmostEqual(export.interp(schedule, 0.5), 18.5 - 0.17 / 0.33 * 4.6)  # extrapolates the first segment

    def test_lineage_relation_mapping(self) -> None:
        self.assertEqual(ingest.relation_type("SE DEROGA"), "deroga")
        self.assertEqual(ingest.relation_type("SE AÑADE"), "modifica")
        self.assertEqual(ingest.norm_id("BOE-A-2006-20764"), "es:boe-a-2006-20764")


if __name__ == "__main__":
    unittest.main()
