from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_liberty_restrictions_snapshot import (
    ACCOUNTABILITY_PARQUET_FIELDS,
    IRLC_PARQUET_FIELDS,
    append_jsonl_entry,
    build_accountability_parquet_rows,
    build_irlc_parquet_rows,
    build_snapshot,
    build_snapshot_changelog_entry,
    build_snapshot_diff,
    history_has_entry,
    read_jsonl_entries,
    write_parquet_table,
)
from scripts.import_liberty_delegated_enforcement_seed import import_seed as import_delegated_seed
from scripts.import_liberty_enforcement_seed import import_seed as import_enforcement_seed
from scripts.import_liberty_indirect_accountability_seed import import_seed as import_indirect_seed
from scripts.import_liberty_proportionality_seed import import_seed as import_prop_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed


class TestExportLibertyRestrictionsSnapshot(unittest.TestCase):
    def test_export_snapshot_contains_restrictions_and_edges(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "export_ok.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                prop_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_proportionality_seed_v1.json").read_text(encoding="utf-8"))
                enforcement_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_enforcement_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
                delegated_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_delegated_enforcement_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_prop_seed(conn, seed_doc=prop_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_enforcement_seed(conn, seed_doc=enforcement_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_delegated_seed(conn, seed_doc=delegated_seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_snapshot(conn, snapshot_date="2026-02-23")
            finally:
                conn.close()

        self.assertEqual(str(got["schema_version"]), "liberty_restrictions_snapshot_v1")
        self.assertEqual(int(got["totals"]["restrictions_total"]), 11)
        self.assertGreaterEqual(int(got["totals"]["accountability_edges_total"]), 1)
        self.assertEqual(int(got["totals"]["proportionality_reviews_total"]), 8)
        self.assertGreaterEqual(int(got["totals"]["actors_scored_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["persons_scored_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["enforcement_observations_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["indirect_edges_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["indirect_attributable_edges_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["delegated_links_total"]), 1)
        self.assertGreaterEqual(int(got["totals"]["fragments_with_delegated_chain_total"]), 1)
        self.assertEqual(len(got["restrictions"]), 11)
        self.assertGreaterEqual(len(got["accountability_edges"]), 1)
        self.assertEqual(len(got["proportionality_reviews"]), 8)
        self.assertGreaterEqual(len(got["accountability_scores"]), 1)
        self.assertGreaterEqual(len(got["personal_accountability_scores"]), 1)
        self.assertIn("enforcement_variation", got)
        self.assertIn("indirect_accountability_summary", got)
        self.assertGreaterEqual(len(got["indirect_accountability_edges"]), 1)
        self.assertIn("actor_person_name", got["indirect_accountability_edges"][0])
        self.assertIn("actor_role_title", got["indirect_accountability_edges"][0])
        self.assertIn("appointment_start_date", got["indirect_accountability_edges"][0])
        self.assertIn("personal_accountability_summary", got)
        self.assertIn("indirect_identity_resolution_pct", got["personal_accountability_summary"]["coverage"])
        self.assertIn("indirect_person_edges_identity_resolved_total", got["personal_accountability_summary"]["totals"])
        self.assertIn("delegated_enforcement_summary", got)
        self.assertGreaterEqual(len(got["delegated_enforcement_links"]), 1)

        irlc_rows = build_irlc_parquet_rows(got)
        accountability_rows = build_accountability_parquet_rows(got)
        self.assertEqual(len(irlc_rows), 11)
        self.assertEqual(len(accountability_rows), int(got["totals"]["accountability_edges_total"]))
        self.assertIn("irlc_score", irlc_rows[0])
        self.assertIn("actor_label", accountability_rows[0])

    def test_snapshot_diff_and_changelog_contract(self) -> None:
        previous = {
            "snapshot_date": "2026-02-22",
            "schema_version": "liberty_restrictions_snapshot_v1",
            "totals": {"restrictions_total": 1, "accountability_edges_total": 1},
            "restrictions": [{"assessment_key": "a-1"}],
            "accountability_edges": [
                {
                    "fragment_id": "f-1",
                    "role": "approve",
                    "actor_label": "Actor A",
                    "evidence_date": "2026-01-01",
                    "source_url": "https://example.org/a",
                }
            ],
            "proportionality_reviews": [{"review_key": "r-1"}],
            "accountability_scores": [{"actor_label": "Actor A", "score": 1.0}],
            "indirect_accountability_edges": [{"edge_key": "e-1"}],
            "delegated_enforcement_links": [{"link_key": "d-1"}],
        }
        current = {
            "snapshot_date": "2026-02-23",
            "schema_version": "liberty_restrictions_snapshot_v1",
            "totals": {"restrictions_total": 2, "accountability_edges_total": 1},
            "restrictions": [{"assessment_key": "a-1"}, {"assessment_key": "a-2"}],
            "accountability_edges": [
                {
                    "fragment_id": "f-1",
                    "role": "approve",
                    "actor_label": "Actor A",
                    "evidence_date": "2026-01-01",
                    "source_url": "https://example.org/a",
                }
            ],
            "proportionality_reviews": [{"review_key": "r-1"}],
            "accountability_scores": [{"actor_label": "Actor A", "score": 1.0}],
            "indirect_accountability_edges": [{"edge_key": "e-1"}],
            "delegated_enforcement_links": [{"link_key": "d-1"}],
        }
        diff = build_snapshot_diff(current, previous, previous_snapshot_path="prev.json")
        self.assertEqual(_as_text(diff["status"]), "changed")
        self.assertEqual(int(diff["changed_sections_total"]), 1)
        self.assertEqual(int(diff["sections"]["restrictions"]["added_total"]), 1)
        self.assertEqual(int(diff["items_added_total"]), 1)
        self.assertEqual(int(diff["items_removed_total"]), 0)

        entry = build_snapshot_changelog_entry(
            current,
            diff,
            snapshot_path="current.json",
            previous_snapshot_path="prev.json",
            diff_path="diff.json",
        )
        self.assertTrue(_as_text(entry["entry_id"]))
        self.assertEqual(_as_text(entry["change_summary"]["status"]), "changed")
        self.assertEqual(int(entry["change_summary"]["items_added_total"]), 1)

    def test_parquet_write_and_changelog_dedupe(self) -> None:
        try:
            import pyarrow.parquet as pq  # type: ignore
        except Exception:  # noqa: BLE001
            self.skipTest("pyarrow no instalado en entorno de test")

        with TemporaryDirectory() as td:
            base = Path(td)
            irlc_out = base / "irlc.parquet"
            acc_out = base / "accountability.parquet"
            history_path = base / "changelog.jsonl"

            irlc_meta = write_parquet_table(
                [
                    {
                        "assessment_key": "a-1",
                        "fragment_id": "f-1",
                        "norm_id": "n-1",
                        "boe_id": "BOE-A-0001",
                        "norm_title": "Norma X",
                        "fragment_type": "article",
                        "fragment_label": "Art. 1",
                        "competent_body": "Org",
                        "appeal_path": "Recurso",
                        "right_category_id": "right_1",
                        "right_label": "Seguridad",
                        "method_version": "irlc_v1",
                        "reach_score": 80.0,
                        "intensity_score": 70.0,
                        "due_process_risk_score": 50.0,
                        "reversibility_risk_score": 60.0,
                        "discretionality_score": 55.0,
                        "compliance_cost_score": 40.0,
                        "irlc_score": 61.0,
                        "confidence": 0.8,
                        "source_url": "https://example.org/x",
                    }
                ],
                out_path=irlc_out,
                fields=IRLC_PARQUET_FIELDS,
            )
            acc_meta = write_parquet_table(
                [
                    {
                        "fragment_id": "f-1",
                        "norm_id": "n-1",
                        "boe_id": "BOE-A-0001",
                        "norm_title": "Norma X",
                        "role": "approve",
                        "actor_label": "Actor A",
                        "evidence_date": "2026-01-01",
                        "source_url": "https://example.org/x",
                    }
                ],
                out_path=acc_out,
                fields=ACCOUNTABILITY_PARQUET_FIELDS,
            )

            self.assertEqual(int(irlc_meta["rows"]), 1)
            self.assertEqual(int(acc_meta["rows"]), 1)

            self.assertEqual(pq.read_table(irlc_out).num_rows, 1)
            self.assertEqual(pq.read_table(acc_out).num_rows, 1)

            entry = {"entry_id": "snap-1", "snapshot_date": "2026-02-23"}
            append_jsonl_entry(history_path, entry)
            rows = read_jsonl_entries(history_path)
            self.assertTrue(history_has_entry(rows, "snap-1"))
            self.assertFalse(history_has_entry(rows, "snap-2"))


def _as_text(value: object) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    unittest.main()
