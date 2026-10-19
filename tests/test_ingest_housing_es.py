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


if __name__ == "__main__":
    unittest.main()
