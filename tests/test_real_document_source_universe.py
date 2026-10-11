from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = REPO_ROOT / "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence"
PROVENANCE_AUDIT = EVIDENCE_ROOT / "real-document-provenance-audit.json"


class RealDocumentSourceUniverseTests(unittest.TestCase):
    def test_real_official_universe_replays_numeric_target_without_inferring_representativeness(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report_path = Path(temporary) / "source-universe.json"
            validation_path = Path(temporary) / "source-universe-validation.json"
            provenance = json.loads(PROVENANCE_AUDIT.read_text(encoding="utf-8"))
            common = [
                "--provenance-audit",
                str(PROVENANCE_AUDIT),
                "--host-health",
                str(EVIDENCE_ROOT / "real-document-host-health-20260829.json"),
                "--acquisition-validation",
                str(
                    EVIDENCE_ROOT
                    / "real-document-fetch-scale-cohort-10k-v1-validation-physical-20260829.json"
                ),
                "--obstruction-snapshot",
                str(
                    REPO_ROOT
                    / "ui/gh-pages-next/public/obstruction-tracker/data/obstructions.json"
                ),
            ]
            subprocess.run(
                [
                    sys.executable,
                    "scripts/report_real_document_source_universe.py",
                    *common,
                    "--target-urls",
                    "100000",
                    "--out",
                    str(report_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "scripts/validate_real_document_source_universe.py",
                    "--report",
                    str(report_path),
                    *common,
                    "--out",
                    str(validation_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            validation = json.loads(validation_path.read_text(encoding="utf-8"))

        edge_descriptor = provenance["edge_manifest"]
        self.assertEqual(
            report["edge_counts"]["edge_rows"], edge_descriptor["rows"]
        )
        self.assertEqual(
            report["edge_counts"]["edge_rows"],
            provenance["totals"]["provenance_edges"],
        )
        self.assertEqual(
            report["edge_counts"]["edge_rows"],
            report["edge_counts"]["public_https_edges"]
            + report["edge_counts"]["public_http_edges"],
        )
        self.assertEqual(
            report["inputs"]["edge_manifest"],
            {
                "path": edge_descriptor["path"],
                "bytes": edge_descriptor["bytes"],
                "sha256": edge_descriptor["sha256"],
            },
        )
        self.assertEqual(report["summary"]["unique_public_urls"], 115_246)
        self.assertEqual(report["summary"]["unique_https_urls"], 111_600)
        self.assertEqual(
            report["summary"]["contract_eligible_physically_healthy_https_urls"],
            101_303,
        )
        self.assertEqual(report["summary"]["healthy_host_uncontracted_https_urls"], 1)
        self.assertEqual(report["summary"]["numeric_target_gap_urls"], 0)
        self.assertTrue(report["summary"]["numeric_target_available"])
        self.assertEqual(
            report["summary"]["representative_cohort_status"],
            "decision_required_dec_01",
        )
        self.assertEqual(report["status"], "ready_for_numeric_cohort_preparation")
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["policy"]["network_requests_performed"], 0)
        self.assertFalse(report["policy"]["synthetic_or_mock_records_counted"])
        self.assertTrue(
            report["policy"]["official_public_domain_personal_information_retained"]
        )
        self.assertEqual(
            report["inputs"]["obstruction_snapshot"]["descriptor_kind"],
            "canonical_json_projection",
        )
        self.assertEqual(
            report["inputs"]["obstruction_snapshot"]["projection_schema"],
            "obstruction_classification_projection_v1",
        )
        hosts = {row["host"]: row for row in report["hosts"]}
        self.assertEqual(
            hosts["www.boe.es"]["contract_eligible_https_urls"], 101_217
        )
        self.assertEqual(
            hosts["www.boe.es"]["classification"],
            "partially_contract_implemented_and_physically_healthy",
        )
        self.assertEqual(
            hosts["www.parlamentodeandalucia.es"]["contract_eligible_https_urls"],
            86,
        )
        self.assertEqual(
            hosts["www.senado.es"]["classification"],
            "known_blocked_no_new_lever",
        )
        self.assertEqual(validation["status"], "ok")
        self.assertEqual(validation["errors"], [])
        self.assertEqual(
            validation["inputs"]["edge_manifest"],
            report["inputs"]["edge_manifest"],
        )
        self.assertEqual(
            validation["checks"]["edge_rows_replayed"],
            report["edge_counts"]["edge_rows"],
        )
        self.assertEqual(
            validation["checks"]["unique_https_urls_replayed"],
            report["summary"]["unique_https_urls"],
        )


if __name__ == "__main__":
    unittest.main()
