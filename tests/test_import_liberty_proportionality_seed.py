from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_proportionality_seed import import_seed as import_prop_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed


class TestImportLibertyProportionalitySeed(unittest.TestCase):
    def test_import_seed_upserts_proportionality_tables(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "prop.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                prop_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_proportionality_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")

                got1 = import_prop_seed(conn, seed_doc=prop_seed_doc, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got1["counts"]["methodology_inserted"]), 1)
                self.assertEqual(int(got1["counts"]["reviews_inserted"]), 8)
                self.assertEqual(int(got1["counts"]["unresolved_fragment_refs"]), 0)

                got2 = import_prop_seed(conn, seed_doc=prop_seed_doc, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got2["counts"]["methodology_inserted"]), 0)
                self.assertGreaterEqual(int(got2["counts"]["methodology_updated"]), 1)
                self.assertGreaterEqual(int(got2["counts"]["reviews_updated"]), 8)

                row = conn.execute("SELECT COUNT(*) AS n FROM liberty_proportionality_methodologies").fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute("SELECT COUNT(*) AS n FROM liberty_proportionality_reviews").fetchone()
                self.assertEqual(int(row["n"]), 8)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
