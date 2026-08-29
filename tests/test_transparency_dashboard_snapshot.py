from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_transparency_dashboard_snapshot import (
    DEFAULT_DOCUMENT_FETCH_OPERATIONS_JSON,
    DEFAULT_OBSTRUCTION_JSON,
    DEFAULT_ORIGIN_VERIFICATION_JSON,
    DEFAULT_READINESS_JSON,
    DEFAULT_RELEASE_REGISTRY_JSON,
    DEFAULT_REPO_BLOB_BASE,
    DEFAULT_STATUS_JSON,
    build_payload,
    build_releases,
    read_json,
)
from scripts.validate_transparency_dashboard_snapshot import validate


class TransparencyDashboardSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.status = read_json(DEFAULT_STATUS_JSON)
        cls.obstruction = read_json(DEFAULT_OBSTRUCTION_JSON)
        cls.readiness = read_json(DEFAULT_READINESS_JSON)
        cls.origin = read_json(DEFAULT_ORIGIN_VERIFICATION_JSON)
        cls.document_fetch = read_json(DEFAULT_DOCUMENT_FETCH_OPERATIONS_JSON)
        cls.registry = read_json(DEFAULT_RELEASE_REGISTRY_JSON)
        cls.releases = build_releases(cls.registry, DEFAULT_REPO_BLOB_BASE)
        cls.payload = build_payload(
            status=cls.status,
            obstruction=cls.obstruction,
            readiness=cls.readiness,
            origin=cls.origin,
            document_fetch=cls.document_fetch,
            releases=cls.releases,
            generated_at="2026-08-19T17:30:00+00:00",
            status_path=DEFAULT_STATUS_JSON.as_posix(),
            obstruction_path=DEFAULT_OBSTRUCTION_JSON.as_posix(),
            readiness_path=DEFAULT_READINESS_JSON.as_posix(),
            origin_path=DEFAULT_ORIGIN_VERIFICATION_JSON.as_posix(),
            document_fetch_path=DEFAULT_DOCUMENT_FETCH_OPERATIONS_JSON.as_posix(),
            release_registry_path=DEFAULT_RELEASE_REGISTRY_JSON.as_posix(),
            repo_blob_base=DEFAULT_REPO_BLOB_BASE,
        )

    def test_real_source_health_and_obstruction_counts_reconcile(self) -> None:
        status_summary = self.status["summary"]
        obstruction_summary = self.obstruction["summary"]["obstruction"]

        self.assertEqual(self.payload["source_health"]["summary"]["present"], status_summary["present"])
        self.assertEqual(
            self.payload["obstruction"]["open_incidents_total"],
            obstruction_summary["open_incidents_total"],
        )
        self.assertEqual(
            self.payload["obstruction"]["blocked_sources_total"],
            obstruction_summary["blocked_sources_total"],
        )

    def test_verified_public_snapshot_totals_are_derived_from_real_corpora(self) -> None:
        remote_corpora = self.origin["checks"]["remote_corpora"]
        snapshot = self.payload["published_snapshot"]

        self.assertTrue(snapshot["verification_passed"])
        self.assertEqual(snapshot["rows_total"], sum(item["rows"] for item in remote_corpora))
        self.assertEqual(snapshot["data_files_total"], sum(item["files"] for item in remote_corpora))
        self.assertEqual(snapshot["release_id"], self.origin["checks"]["latest_manifest_sha256"])
        self.assertTrue(snapshot["metadata_freshness"])
        self.assertEqual(snapshot["warnings"], [])

    def test_every_metric_and_release_has_traceable_real_evidence(self) -> None:
        self.assertGreater(len(self.payload["metrics"]), 0)
        for metric in self.payload["metrics"]:
            self.assertTrue(metric["source_path"])
            self.assertTrue(metric["source_url"].startswith(("/", "https://")))
            self.assertIsInstance(metric["value"], int)

        self.assertEqual(len(self.payload["recent_changes"]), len(self.registry["releases"]))
        for release in self.payload["recent_changes"]:
            self.assertTrue(Path(release["note"]["path"]).is_file())
            self.assertEqual(len(release["note"]["sha256"]), 64)
            for evidence in release["evidence"]:
                self.assertTrue(Path(evidence["path"]).is_file())
                self.assertEqual(len(evidence["sha256"]), 64)

    def test_generated_feed_passes_independent_validator_and_real_only_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "transparency.json"
            path.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
            report = validate(path, 1_000_000)

        self.assertEqual(report["status"], "ok", report["errors"])
        self.assertEqual(self.payload["policy"]["synthetic_or_mock_records"], "forbidden")
        self.assertEqual(self.payload["policy"]["placeholder_releases"], "forbidden")
        self.assertEqual(self.payload["policy"]["public_domain_personal_information"], "retained")


if __name__ == "__main__":
    unittest.main()
