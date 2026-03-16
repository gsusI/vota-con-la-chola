from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.export_liberty_delegated_alternative_capture_targets import STRICT_FAIL_EXIT, build_capture_targets, main


class TestExportLibertyDelegatedAlternativeCaptureTargets(unittest.TestCase):
    def test_build_capture_targets_emits_pending_only_with_direct_boe_docs(self) -> None:
        pending_rows = [
            {
                "link_key": "k-aeat",
                "decision": "pending",
                "pending_reason": "auto_assist:role_alignment_failed:procedural_unit_not_found",
                "delegated_institution_label": "AEAT",
                "designated_role_title": "Unidad procedimental sancionadora",
                "capture_query_primary": "nombramiento Unidad procedimental sancionadora AEAT",
                "capture_query_secondary": "nombramiento AEAT",
                "top_candidates_json": json.dumps(
                    [
                        {
                            "candidate_rank_for_link": 1,
                            "candidate_boe_id": "BOE-A-2024-12397",
                            "candidate_score": 29,
                            "candidate_doc_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2024-12397",
                            "candidate_title": "Resolución candidata",
                        },
                        {
                            "candidate_rank_for_link": 2,
                            "candidate_boe_id": "BOE-A-2010-5072",
                            "candidate_score": 28,
                            "candidate_doc_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2010-5072",
                            "candidate_title": "Resolución candidata 2",
                        },
                    ]
                ),
            },
            {
                "link_key": "k-approved",
                "decision": "approved",
                "pending_reason": "",
                "delegated_institution_label": "DGT",
                "designated_role_title": "Subdireccion",
                "capture_query_primary": "nombramiento DGT",
                "capture_query_secondary": "",
                "top_candidates_json": "[]",
            },
        ]

        rows, summary = build_capture_targets(pending_rows=pending_rows, max_candidate_doc_targets_per_link=2)

        self.assertEqual(int(summary["pending_links_total"]), 1)
        self.assertEqual(int(summary["boe_doc_candidates_emitted_total"]), 2)
        self.assertEqual(int(summary["max_candidate_doc_targets_per_link"]), 2)
        self.assertEqual(int(summary["pending_reason_counts"]["auto_assist:role_alignment_failed:procedural_unit_not_found"]), 1)

        labels = {str(r["target_label"]) for r in rows if str(r["target_group"]) == "boe_direct_doc"}
        self.assertIn("boe_direct_doc_BOE-A-2024-12397", labels)
        self.assertIn("boe_direct_doc_BOE-A-2010-5072", labels)
        self.assertTrue(all(str(r["link_key"]) == "k-aeat" for r in rows))

    def test_main_strict_min_targets_per_link_can_fail(self) -> None:
        with TemporaryDirectory() as td:
            td_path = Path(td)
            in_csv = td_path / "pending.csv"
            out_csv = td_path / "targets.csv"
            out_json = td_path / "summary.json"
            fieldnames = [
                "link_key",
                "decision",
                "pending_reason",
                "delegated_institution_label",
                "designated_role_title",
                "capture_query_primary",
                "capture_query_secondary",
                "top_candidates_json",
            ]
            with in_csv.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "link_key": "k-dgt",
                        "decision": "pending",
                        "pending_reason": "auto_assist:role_alignment_failed:role_topic_overlap_zero",
                        "delegated_institution_label": "DGT",
                        "designated_role_title": "Subdireccion de Gestion de Sanciones",
                        "capture_query_primary": "nombramiento Subdireccion de Gestion de Sanciones DGT",
                        "capture_query_secondary": "nombramiento DGT",
                        "top_candidates_json": "[]",
                    }
                )

            rc = main(
                [
                    "--pending-resolution-csv",
                    str(in_csv),
                    "--max-candidate-doc-targets-per-link",
                    "0",
                    "--strict-min-targets-per-link",
                    "10",
                    "--out",
                    str(out_csv),
                    "--summary-out",
                    str(out_json),
                ]
            )

            self.assertEqual(rc, STRICT_FAIL_EXIT)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(int(payload["summary"]["pending_links_total"]), 1)
            self.assertGreater(int(payload["summary"]["target_rows_total"]), 0)


if __name__ == "__main__":
    unittest.main()
