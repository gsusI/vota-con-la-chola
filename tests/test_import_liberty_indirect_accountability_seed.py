from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_indirect_accountability_seed import import_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed


class TestImportLibertyIndirectAccountabilitySeed(unittest.TestCase):
    def test_import_is_idempotent(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "indirect_import.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")

                got1 = import_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                got2 = import_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")

                self.assertEqual(str(got1["status"]), "ok")
                self.assertEqual(int(got1["counts"]["edges_inserted"]), 12)
                self.assertEqual(int(got1["counts"]["unresolved_fragment_refs"]), 0)

                self.assertEqual(str(got2["status"]), "ok")
                self.assertEqual(int(got2["counts"]["edges_updated"]), 12)

                row = conn.execute("SELECT COUNT(*) AS n FROM liberty_indirect_methodologies").fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute("SELECT COUNT(*) AS n FROM liberty_indirect_responsibility_edges").fetchone()
                self.assertEqual(int(row["n"]), 12)
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM liberty_indirect_responsibility_edges
                    WHERE TRIM(COALESCE(actor_person_name, '')) <> ''
                      AND TRIM(COALESCE(actor_role_title, '')) <> ''
                      AND TRIM(COALESCE(appointment_start_date, '')) <> ''
                    """
                ).fetchone()
                self.assertEqual(int(row["n"]), 12)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
