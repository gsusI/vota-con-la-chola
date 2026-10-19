import json
import sqlite3
import unittest
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


if __name__ == "__main__":
    unittest.main()
