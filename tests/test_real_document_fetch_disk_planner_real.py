from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_real_document_fetch_scale_cohort import (
    begin_output_transaction,
    publish_transaction_artifact,
    rollback_output_transaction,
    write_partitioned_rows,
)
from scripts.validate_real_document_fetch_scale_cohort import (
    canonical_projection_line,
    iter_manifest_rows,
    validate_preflight,
)


ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "etl/data/staging"
SOURCE_DB = STAGING / "politicos-es.db"
SCHEMA = ROOT / "etl/load/sqlite_schema.sql"
EDGES = ROOT / "etl/data/manifests/real-document-provenance-edges.jsonl"
RAW_ROOT = ROOT / "etl/data/raw"
HOST_HEALTH = ROOT / (
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-host-health-20260829.json"
)
REFERENCE_MANIFEST = ROOT / (
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-fetch-scale-cohort-v2-20260829.json"
)
PREPARE = ROOT / "scripts/prepare_real_document_fetch_scale_cohort.py"
EXPECTED_LEGACY_SEMANTIC_SHA256 = (
    "555b33e18fde9911647552470f925fa835d2e75fd8e440d71601c53618083170"
)
PREPARED_AT = "2026-08-29T18:38:04.541170Z"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def planner_inputs_available() -> bool:
    return all(
        path.exists()
        for path in (SOURCE_DB, SCHEMA, EDGES, RAW_ROOT, HOST_HEALTH, REFERENCE_MANIFEST)
    )


@unittest.skipUnless(planner_inputs_available(), "real local planner inputs unavailable")
class TestRealDocumentFetchDiskPlanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="real-document-disk-planner-test-",
            dir=STAGING,
        )
        cls.work = Path(cls.temporary.name)
        cls.db_path = cls.work / "cohort.db"
        cls.manifest_path = cls.work / "cohort.json"
        cls.partition_dir = cls.work / "cohort-rows"
        command = [
            sys.executable,
            str(PREPARE),
            "--source-db",
            str(SOURCE_DB.relative_to(ROOT)),
            "--schema",
            str(SCHEMA.relative_to(ROOT)),
            "--provenance-edges",
            str(EDGES.relative_to(ROOT)),
            "--raw-root",
            str(RAW_ROOT.relative_to(ROOT)),
            "--host-health",
            str(HOST_HEALTH.relative_to(ROOT)),
            "--out-db",
            str(cls.db_path.relative_to(ROOT)),
            "--manifest-out",
            str(cls.manifest_path.relative_to(ROOT)),
            "--manifest-layout",
            "partitioned_v4",
            "--manifest-partition-dir",
            str(cls.partition_dir.relative_to(ROOT)),
            "--boe-document-rows",
            "800",
            "--boe-summary-rows",
            "114",
            "--prepared-at",
            PREPARED_AT,
        ]
        cls.completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if cls.completed.returncode != 0:
            raise AssertionError(
                f"real planner failed: {cls.completed.stdout}\n{cls.completed.stderr}"
            )
        cls.command = command
        cls.manifest = json.loads(cls.manifest_path.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_real_selection_matches_committed_legacy_cohort(self) -> None:
        reference = json.loads(REFERENCE_MANIFEST.read_text(encoding="utf-8"))
        reference_rows = reference["rows"]
        candidate_rows = list(
            iter_manifest_rows(
                manifest=self.manifest,
                manifest_path=self.manifest_path,
            )
        )
        fields = (
            "source_pipeline_id",
            "source_id",
            "source_url",
            "source_host",
            "document_kind",
            "validation_mode",
            "size_decile",
            "expected_bytes",
            "expected_content_sha256",
        )
        project = lambda row: tuple(row.get(field) for field in fields)
        self.assertEqual([project(row) for row in candidate_rows], [project(row) for row in reference_rows])
        self.assertEqual(reference["cohort_semantic_sha256"], EXPECTED_LEGACY_SEMANTIC_SHA256)
        digest = hashlib.sha256()
        for row in candidate_rows:
            digest.update(canonical_projection_line(row))
        self.assertEqual(digest.hexdigest(), self.manifest["cohort_selection_sha256"])
        self.assertEqual(len(candidate_rows), 1_000)

    def test_v4_queue_payload_priority_and_preflight_are_exact(self) -> None:
        report = validate_preflight(
            manifest_path=self.manifest_path,
            db_path=self.db_path,
            max_planner_peak_rss_bytes=256 * 1024 * 1024,
        )
        self.assertEqual(report["status"], "ok", report["errors"])
        self.assertTrue(report["checks"]["disk_planning_contract_validated"])
        self.assertTrue(report["checks"]["selection_identity_validated"])
        self.assertTrue(report["checks"]["execution_contract_validated"])
        self.assertEqual(report["checks"]["real_policy_rows"], 1_000)
        self.assertEqual(report["checks"]["official_public_information_rows"], 1_000)
        self.assertEqual(report["checks"]["known_blocked_host_rows"], 0)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT item_key, priority, payload_json
                FROM pipeline_work_items
                WHERE pipeline_id = 'real_document_fetch_scale_cohort_v2'
                ORDER BY item_key
                """
            ).fetchall()
        self.assertEqual(len(rows), 1_000)
        self.assertEqual(len({row[0] for row in rows}), 1_000)
        for _url, _priority, payload_json in rows:
            payload = json.loads(payload_json)
            self.assertIs(payload["synthetic_or_mock_records_counted"], False)
            self.assertIs(
                payload["official_public_domain_personal_information_retained"],
                True,
            )

    def test_real_rows_roll_over_into_deterministic_bounded_shards(self) -> None:
        real_rows = []
        for row in iter_manifest_rows(
            manifest=self.manifest,
            manifest_path=self.manifest_path,
        ):
            if row["source_pipeline_id"] == "boe_document_fetch" and row["size_decile"] == 1:
                real_rows.append(row)
            if len(real_rows) == 6:
                break
        shard_dir = self.work / "bounded-real-row-shards"
        row_manifest = write_partitioned_rows(
            partition_dir=shard_dir,
            rows=iter(real_rows),
            bounded_shards=True,
            max_partition_rows=2,
        )
        self.assertEqual(row_manifest["layout"], "partitioned_jsonl_gzip_v2")
        self.assertEqual([row["rows"] for row in row_manifest["partitions"]], [2, 2, 2])
        self.assertEqual(
            [row["shard_ordinal"] for row in row_manifest["partitions"]],
            [1, 2, 3],
        )
        derived_manifest = {
            "schema_version": "real_document_fetch_scale_cohort_v4",
            "row_manifest": row_manifest,
        }
        validated_rows = list(
            iter_manifest_rows(
                manifest=derived_manifest,
                manifest_path=self.manifest_path,
            )
        )
        self.assertEqual(
            [row["source_url"] for row in validated_rows],
            [row["source_url"] for row in real_rows],
        )

    def test_embedded_25001_attempt_fails_without_outputs(self) -> None:
        blocked_db = self.work / "embedded-overflow.db"
        blocked_manifest = self.work / "embedded-overflow.json"
        command = [
            sys.executable,
            str(PREPARE),
            "--source-db",
            str(SOURCE_DB.relative_to(ROOT)),
            "--host-health",
            str(HOST_HEALTH.relative_to(ROOT)),
            "--out-db",
            str(blocked_db.relative_to(ROOT)),
            "--manifest-out",
            str(blocked_manifest.relative_to(ROOT)),
            "--manifest-layout",
            "embedded_v2",
            "--boe-document-rows",
            "25001",
            "--boe-summary-rows",
            "0",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("embedded manifest exceeds bounded compatibility limit", completed.stdout)
        self.assertFalse(blocked_db.exists())
        self.assertFalse(blocked_manifest.exists())

    def test_occupied_real_outputs_are_byte_identical_after_refusal(self) -> None:
        before = {
            "db": sha256_path(self.db_path),
            "manifest": sha256_path(self.manifest_path),
            "partitions": {
                path.name: sha256_path(path)
                for path in sorted(self.partition_dir.iterdir())
                if path.is_file()
            },
        }
        completed = subprocess.run(
            self.command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("output already exists", completed.stdout)
        after = {
            "db": sha256_path(self.db_path),
            "manifest": sha256_path(self.manifest_path),
            "partitions": {
                path.name: sha256_path(path)
                for path in sorted(self.partition_dir.iterdir())
                if path.is_file()
            },
        }
        self.assertEqual(after, before)

    def test_incomplete_real_bundle_rolls_back_only_owned_artifacts(self) -> None:
        recovery_root = self.work / "recovery"
        recovery_root.mkdir()
        targets = {
            "database": recovery_root / "queue.db",
            "manifest": recovery_root / "manifest.json",
            "partitions": recovery_root / "rows",
        }
        transaction = begin_output_transaction(targets)
        staged_db = transaction["run_dir"] / "queue-copy.db"
        staged_rows = transaction["run_dir"] / "rows-copy"
        shutil.copy2(self.db_path, staged_db)
        shutil.copytree(self.partition_dir, staged_rows)
        publish_transaction_artifact(transaction, role="database", staged_path=staged_db)
        publish_transaction_artifact(transaction, role="partitions", staged_path=staged_rows)
        self.assertTrue(targets["database"].exists())
        self.assertTrue(targets["partitions"].exists())
        self.assertFalse(targets["manifest"].exists())
        rollback_output_transaction(transaction)
        self.assertFalse(targets["database"].exists())
        self.assertFalse(targets["partitions"].exists())
        self.assertFalse(transaction["journal_path"].exists())
        self.assertFalse(transaction["run_dir"].exists())


if __name__ == "__main__":
    unittest.main()
