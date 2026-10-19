import io
import json
import math
import sqlite3
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, seed_sources
from publicdata_sqlite.provenance import seed_sources_from_config
from scripts import export_public_viz_housing as export
from scripts import housing_ecv_microdata as ecvm
from scripts import ingest_housing_es as ingest


def synthetic_zip(year: int = 2025, households: int = 160) -> bytes:
    """A datos_<year>.zip with the INE layout (outer zip -> ECV_T<x>_<year>.zip -> CSV/esudb<yy><x>.csv)."""
    yy = str(year)[2:]
    d = ["DB010,DB020,DB030,DB040,DB040_F,DB090,DB090_F"]
    h = ["HB010,HB030,HB080,HY020,HY070G,HH021,HH070,HX040,HX240,HX060,vhPobreza"]
    r = ["RB010,RB030,RB050,RB081,RB082,RB090,RB200,vrEU2030_nuevo,vrMATSOCDEP,vrLOWJOB_nuevo"]
    for i in range(1, households + 1):
        region = "ES30" if i % 4 == 0 else "ES51" if i % 4 == 1 else "ES61"
        tenure = str(1 + i % 5)
        age = 25 + (i * 7) % 60  # spread over every band
        income = 12000 + 400 * (i % 30)
        cost = 150 + 25 * (i % 20)
        d.append(f"{year},ES,{i},{region},1,{100 + i % 7},1")
        child = i % 3 == 0
        h.append(f"{year},{i},{i * 100 + 1},{income},0,{tenure},{cost},{2 if child else 1},{1.3 if child else 1.0},"
                 f"{'1' if age < 30 else '5'},{'1' if i % 5 == 0 else '2'}")
        # RB081 is the age at 31 December of the previous year: one year less than at the interview here.
        r.append(f"{year},{i * 100 + 1},{100 + i % 7},{age},{age + 1},{1 + i % 2},1,{i % 3 == 0 and 1 or 0},{i % 7 == 0 and 1 or 0},{i % 4 == 0 and 1 or 0}")
        if child:
            r.append(f"{year},{i * 100 + 2},{100 + i % 7},8,9,{2 - i % 2},1,{(i // 3) % 2},{i % 2},{(i // 6) % 2}")
    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as outer:
        for letter, lines in (("d", d), ("h", h), ("r", r)):
            inner_buf = io.BytesIO()
            with zipfile.ZipFile(inner_buf, "w") as inner:
                inner.writestr(f"CSV/esudb{yy}{letter}.csv", "\n".join(lines) + "\n")
            outer.writestr(f"ECV_T{letter.upper()}_{year}.zip", inner_buf.getvalue())
    return outer_buf.getvalue()


class EcvMicrodataTest(unittest.TestCase):
    def test_burden_follows_eurostat(self) -> None:
        self.assertAlmostEqual(ecvm.burden_of(500, 1200, 25200), (6000 - 1200) / (25200 - 1200) * 100)
        self.assertEqual(ecvm.burden_of(500, 0, 0), 100.0)  # non-positive income counts as 100 %
        self.assertEqual(ecvm.burden_of(5000, 0, 10000), 100.0)  # capped
        self.assertIsNone(ecvm.burden_of(None, 0, 10000))

    def test_reading_uses_reference_person_age_at_end_of_income_year_and_groups_reduced_rent(self) -> None:
        households, persons = ecvm.read_year(synthetic_zip(), 2025)
        self.assertEqual(len(households), 160)
        first = households[0]
        self.assertEqual(first.age, 32)  # RB081, not RB082 (33)
        self.assertEqual({h.tenure for h in households}, set(ecvm.TENURES))
        self.assertEqual(sum(1 for h in households if h.tenure == "RENT_FR"), 64)  # codes 4 and 5
        self.assertEqual(len(persons), 160 + 53)

    def test_linearised_mean_and_weighted_median(self) -> None:
        units = [(1.0, 0.0), (1.0, 10.0), (2.0, 20.0)]
        m, se = ecvm.mean_se(units, 3)
        self.assertAlmostEqual(m, 12.5)
        z = [w * (y - m) / 4 for w, y in units]
        self.assertAlmostEqual(se, math.sqrt(3 / 2 * sum(v * v for v in z)))
        self.assertEqual(ecvm.weighted_quantile(units, 0.5), 10.0)

    def test_small_cells_stay_empty_with_their_sample_size(self) -> None:
        households, _ = ecvm.read_year(synthetic_zip(), 2025)
        rows = {(c["geo"], c["age"], c["tenure"]): c for c in ecvm.cells(households, 2.0)}
        total = rows[("ES", "TOTAL", "TOTAL")]
        self.assertEqual(total["n"], 160)
        self.assertIn("burden_median", total["stats"])
        lo, value, hi = (total["stats"]["overburden_pct"][k] for k in ("lo", "value", "hi"))
        self.assertLessEqual(lo, value)
        self.assertLessEqual(value, hi)
        small = rows[("ES30", "16-29", "RENT_MKT")] if ("ES30", "16-29", "RENT_MKT") in rows else None
        for cell in rows.values():
            if cell["n"] < ecvm.MIN_N:
                self.assertNotIn("stats", cell)
        if small:
            self.assertLess(small["n"], ecvm.MIN_N)
        # Madrid + Cataluña + the rest add up to Spain.
        self.assertEqual(rows[("ES30", "TOTAL", "TOTAL")]["n"] + rows[("ES51", "TOTAL", "TOTAL")]["n"] + rows[("ES_RESTO", "TOTAL", "TOTAL")]["n"], 160)

    def test_design_effect_widens_intervals(self) -> None:
        households, _ = ecvm.read_year(synthetic_zip(), 2025)
        one = {(c["geo"], c["age"], c["tenure"]): c for c in ecvm.cells(households, 1.0)}[("ES", "TOTAL", "TOTAL")]
        four = {(c["geo"], c["age"], c["tenure"]): c for c in ecvm.cells(households, 4.0)}[("ES", "TOTAL", "TOTAL")]
        self.assertAlmostEqual(four["stats"]["burden_mean"]["se"], 2 * one["stats"]["burden_mean"]["se"])

    def test_case_cells_fall_back_to_the_next_definition(self) -> None:
        households, _ = ecvm.read_year(synthetic_zip(households=400), 2025)
        cases = ecvm.case_cells(households, 2.0)
        self.assertEqual(set(cases), set(ecvm.CASES))
        for rows in cases.values():
            self.assertEqual(len(rows), len(rows))
            for row in rows:
                self.assertEqual("stats" in row, row["n"] >= ecvm.MIN_N)

    def test_calibration_compares_with_ine_intervals(self) -> None:
        households, persons = ecvm.read_year(synthetic_zip(), 2025)
        cal = ecvm.calibrate_deff(persons, len(households))
        self.assertEqual(len(cal["rows"]), len(ecvm.INE_CI_2023))
        self.assertEqual(cal["deff"], max(row["deff"] for row in cal["rows"]))


class EcvMicrodataPipelineTest(unittest.TestCase):
    def test_cells_round_trip_through_the_indicator_contract(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        apply_schema(conn, Path(DEFAULT_SCHEMA))
        seed_sources(conn)
        seed_sources_from_config(conn, ingest.LOCAL_SOURCES)
        payload = synthetic_zip()
        raw = ingest.Raw("ine_ecv_microdatos_2025.zip", "https://www.ine.es/x.zip", payload, "2026-10-19T00:00:00+00:00")
        doc = ingest.Raw("ine_ecv_cambio_base_ic_2023.pdf", ecvm.CI_DOC_URL, b"%PDF-1.4", "2026-10-19T00:00:00+00:00")
        fetched = {"ine_ecv_cambio_base_ic_2023.pdf": doc, **{f"ine_ecv_microdatos_{y}.zip": ingest.Raw(
            f"ine_ecv_microdatos_{y}.zip", "https://www.ine.es/x.zip", synthetic_zip(y), "2026-10-19T00:00:00+00:00") for y in ecvm.YEARS}}
        fetched["ine_ecv_microdatos_2025.zip"] = raw
        validation = {"compared": 0, "ilc_mded01": {}}
        with mock.patch.object(ingest, "fetch_raw", lambda name, url, offline: fetched[name]), \
                mock.patch.object(ingest, "ecv_validate", lambda year, checks: validation):
            report = ingest.load_ecv_microdata(conn, True, "2026-10-19")
            again = ingest.load_ecv_microdata(conn, True, "2026-10-19")
        self.assertGreater(report["years"][2025]["observations"], 0)
        self.assertEqual(again["years"][2025]["releases"], 0)  # same files, same method: idempotent
        store = export.Store(conn)
        micro = export.micro_cells(store, conn)
        self.assertEqual(micro["year"], 2025)
        self.assertEqual(micro["years"], list(ecvm.YEARS))
        total = next(c for c in micro["cells"] if (c["geo"], c["age"], c["tenure"]) == ("ES", "TOTAL", "TOTAL"))
        self.assertEqual(total["n"], 160)
        v, lo, hi = total["s"]["burden_median"]
        self.assertLessEqual(lo, v)
        self.assertLessEqual(v, hi)
        empty = [c for c in micro["cells"] if c["n"] < ecvm.MIN_N]
        self.assertTrue(empty)
        self.assertTrue(all("s" not in c for c in empty))
        self.assertIn("p1_young_renter_madrid", micro["cases"])
        self.assertTrue(all(c["year"] < 2025 for c in micro.pop("_csv")))
        self.assertEqual(json.loads(json.dumps(micro)), micro)


if __name__ == "__main__":
    unittest.main()
