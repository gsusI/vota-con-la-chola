from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_delegated_enforcement_seed import import_seed as import_delegated_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_delegated_person_window_queue import (
    _is_accepted_non_nominative_actor,
    build_queue_report,
    main,
)


class TestReportLibertyDelegatedPersonWindowQueue(unittest.TestCase):
    def test_non_nominative_marker_is_accepted(self) -> None:
        self.assertTrue(
            _is_accepted_non_nominative_actor(
                designated_actor_label="Unidad procedimental sancionadora (AEAT)",
                evidence_quote="review:auto_assist:approved_non_nominative_unit_from_BOE-A-2010-5072",
            )
        )
        self.assertFalse(
            _is_accepted_non_nominative_actor(
                designated_actor_label="Delegaciones AEAT",
                evidence_quote="review:auto_assist:approved_from_BOE-A-2007-12769",
            )
        )

    def test_report_failed_when_empty(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "delegated_queue_empty.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_queue_report(
                    conn,
                    limit=0,
                    institution_hint_terms=["ministerio"],
                    max_actionable_rows=-1,
                    dedupe_fragment_latest=True,
                )
            finally:
                conn.close()
        self.assertEqual(str(got["status"]), "failed")
        self.assertIn("no_delegated_links", list(got["strict_fail_reasons"]))

    def test_report_materializes_actionable_queue_for_seed(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "delegated_queue_seeded.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                delegated_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_delegated_enforcement_seed_v1.json").read_text(encoding="utf-8"))
                # Force one actionable row to keep contract coverage stable even if canonical seed improves.
                if isinstance(delegated_seed_doc.get("links"), list) and delegated_seed_doc["links"]:
                    delegated_seed_doc["links"][0]["designated_actor_label"] = ""
                    delegated_seed_doc["links"][0]["enforcement_evidence_date"] = ""

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_delegated_seed(conn, seed_doc=delegated_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_queue_report(
                    conn,
                    limit=0,
                    institution_hint_terms=["ministerio", "direccion", "agencia", "delegaciones", "inspeccion", "dgt", "aeat"],
                    max_actionable_rows=-1,
                    dedupe_fragment_latest=True,
                )
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["links_total"]), 8)
        self.assertGreater(int(got["totals"]["actionable_queue_rows"]), 0)
        self.assertTrue("institutional_designated_actor" in got["by_reason"] or "missing_designated_actor" in got["by_reason"])

    def test_main_strict_fails_when_actionable_threshold_exceeded(self) -> None:
        with TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "delegated_queue_strict.db"
            out_json = td_path / "delegated_queue.json"
            out_csv = td_path / "delegated_queue.csv"

            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                delegated_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_delegated_enforcement_seed_v1.json").read_text(encoding="utf-8"))
                if isinstance(delegated_seed_doc.get("links"), list) and delegated_seed_doc["links"]:
                    delegated_seed_doc["links"][0]["designated_actor_label"] = ""
                    delegated_seed_doc["links"][0]["enforcement_evidence_date"] = ""
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_delegated_seed(conn, seed_doc=delegated_seed_doc, source_id="", snapshot_date="2026-02-23")
            finally:
                conn.close()

            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--max-actionable-rows",
                    "0",
                    "--queue-csv-out",
                    str(out_csv),
                    "--out",
                    str(out_json),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(payload["status"]), "degraded")
            self.assertGreater(int(payload["totals"]["actionable_queue_rows"]), 0)
            self.assertTrue(out_csv.exists())


if __name__ == "__main__":
    unittest.main()
