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

    def test_lineage_relation_mapping(self) -> None:
        self.assertEqual(ingest.relation_type("SE DEROGA"), "deroga")
        self.assertEqual(ingest.relation_type("SE AÑADE"), "modifica")
        self.assertEqual(ingest.norm_id("BOE-A-2006-20764"), "es:boe-a-2006-20764")


if __name__ == "__main__":
    unittest.main()
