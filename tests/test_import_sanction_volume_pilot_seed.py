from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed as import_data_catalog_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.import_sanction_volume_pilot_seed import import_seed as import_volume_pilot_seed


class TestImportSanctionVolumePilotSeed(unittest.TestCase):
    def test_import_seed_upserts_pilot_tables(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "pilot.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                data_seed = json.loads((root / "etl" / "data" / "seeds" / "sanction_data_catalog_seed_v1.json").read_text(encoding="utf-8"))
                volume_seed = json.loads((root / "etl" / "data" / "seeds" / "sanction_volume_pilot_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed, source_id="", snapshot_date="2026-02-23")
                import_data_catalog_seed(conn, seed_doc=data_seed, source_id="", snapshot_date="2026-02-23")

                got1 = import_volume_pilot_seed(conn, seed_doc=volume_seed, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got1["counts"]["volume_observations_inserted"]), 9)
                self.assertEqual(int(got1["counts"]["procedural_metrics_inserted"]), 6)
                self.assertEqual(int(got1["counts"]["municipal_ordinances_inserted"]), 20)
                self.assertEqual(int(got1["counts"]["municipal_fragments_inserted"]), 3)
                self.assertEqual(int(got1["counts"]["unresolved_sanction_source_refs"]), 0)
                self.assertEqual(int(got1["counts"]["unresolved_infraction_type_refs"]), 0)
                self.assertEqual(int(got1["counts"]["unresolved_kpi_refs"]), 0)
                self.assertEqual(int(got1["counts"]["unresolved_norm_refs"]), 0)
                self.assertEqual(int(got1["counts"]["unresolved_fragment_refs"]), 0)
                self.assertEqual(int(got1["counts"]["unresolved_ordinance_refs"]), 0)

                got2 = import_volume_pilot_seed(conn, seed_doc=volume_seed, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got2["counts"]["volume_observations_inserted"]), 0)
                self.assertEqual(int(got2["counts"]["procedural_metrics_inserted"]), 0)
                self.assertEqual(int(got2["counts"]["municipal_ordinances_inserted"]), 0)
                self.assertEqual(int(got2["counts"]["municipal_fragments_inserted"]), 0)
                self.assertGreaterEqual(int(got2["counts"]["volume_observations_updated"]), 9)
                self.assertGreaterEqual(int(got2["counts"]["procedural_metrics_updated"]), 6)
                self.assertGreaterEqual(int(got2["counts"]["municipal_ordinances_updated"]), 20)
                self.assertGreaterEqual(int(got2["counts"]["municipal_fragments_updated"]), 3)

                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_volume_observations").fetchone()
                self.assertEqual(int(row["n"]), 9)
                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_metrics").fetchone()
                self.assertEqual(int(row["n"]), 6)
                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_municipal_ordinances").fetchone()
                self.assertEqual(int(row["n"]), 20)
                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_municipal_ordinance_fragments").fetchone()
                self.assertEqual(int(row["n"]), 3)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
