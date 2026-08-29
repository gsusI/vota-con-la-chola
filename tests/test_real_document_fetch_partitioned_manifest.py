from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from scripts.validate_real_document_fetch_scale_cohort import (
    canonical_projection_line,
    iter_manifest_rows,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / (
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-fetch-scale-cohort-10k-v1-20260829.json"
)


class TestRealDocumentFetchPartitionedManifest(unittest.TestCase):
    def test_real_10k_manifest_streams_and_reconciles_semantic_identity(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        digest = hashlib.sha256()
        rows = 0
        hosts: dict[str, int] = {}
        validation_modes: dict[str, int] = {}
        for row in iter_manifest_rows(manifest=manifest, manifest_path=MANIFEST):
            digest.update(canonical_projection_line(row))
            rows += 1
            host = str(row["source_host"])
            mode = str(row["validation_mode"])
            hosts[host] = hosts.get(host, 0) + 1
            validation_modes[mode] = validation_modes.get(mode, 0) + 1
            payload = row["payload"]
            self.assertIs(payload["synthetic_or_mock_records_counted"], False)
            self.assertIs(
                payload["official_public_domain_personal_information_retained"],
                True,
            )

        selection = manifest["selection"]
        self.assertEqual(rows, 10_000)
        self.assertEqual(hosts, selection["hosts"])
        self.assertEqual(validation_modes, selection["validation_modes"])
        self.assertEqual(digest.hexdigest(), manifest["cohort_semantic_sha256"])

    def test_real_partition_descriptor_scope_drift_fails_closed(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        drifted = copy.deepcopy(manifest)
        descriptor = drifted["row_manifest"]["partitions"][0]
        descriptor["size_decile"] = int(descriptor["size_decile"]) + 1
        with self.assertRaisesRegex(ValueError, "size-decile mismatch"):
            list(iter_manifest_rows(manifest=drifted, manifest_path=MANIFEST))


if __name__ == "__main__":
    unittest.main()
