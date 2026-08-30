from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.export_obstruction_tracker_snapshot import (
    DEFAULT_BLOCKERS_LOG,
    DEFAULT_READINESS_JSON,
    DEFAULT_REPO_BLOB_BASE,
    DEFAULT_STATUS_JSON,
    DEFAULT_PUBLIC_EVIDENCE_BASE,
    build_payload,
    canonicalize_public_evidence_text,
    load_status_payload,
    parse_name_and_shame_log,
)
from scripts.validate_obstruction_tracker_snapshot import validate_payload


class ObstructionTrackerSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.status = load_status_payload(DEFAULT_STATUS_JSON)
        cls.readiness = load_status_payload(DEFAULT_READINESS_JSON)
        cls.incidents = parse_name_and_shame_log(
            DEFAULT_BLOCKERS_LOG,
            DEFAULT_REPO_BLOB_BASE,
            DEFAULT_PUBLIC_EVIDENCE_BASE,
        )
        cls.payload = build_payload(
            cls.status,
            cls.incidents,
            readiness_payload=cls.readiness,
            generated_at="2026-08-19T12:00:00+00:00",
            public_status_path="/explorer-sources/data/status.json",
            status_json_evidence_path=DEFAULT_STATUS_JSON.as_posix(),
            blockers_log_path=DEFAULT_BLOCKERS_LOG.as_posix(),
            readiness_json_path=DEFAULT_READINESS_JSON.as_posix(),
            repo_blob_base=DEFAULT_REPO_BLOB_BASE,
            public_evidence_base=DEFAULT_PUBLIC_EVIDENCE_BASE,
        )

    def test_real_public_sources_reconcile_end_to_end(self) -> None:
        open_incidents = [item for item in self.incidents if item["status"] == "OPEN"]
        summary = self.payload["summary"]["obstruction"]

        self.assertGreater(len(open_incidents), 0)
        self.assertEqual(summary["open_incidents_total"], len(open_incidents))
        self.assertEqual(summary["historical_incidents_total"], len(self.incidents))
        self.assertEqual(
            sum(source["incident_count"] for source in self.payload["blocked_sources"]),
            len(open_incidents),
        )
        readiness = self.payload["scale_readiness"]
        self.assertEqual(readiness["status"], "not_ready")
        self.assertIs(readiness["foundation"]["ready"], False)
        self.assertEqual(
            readiness["failure"]["reason"],
            "BOE document corpus checks failed",
        )
        self.assertEqual(readiness["summary"], {})
        self.assertEqual(readiness["corpora"], [])
        self.assertEqual(readiness["gaps"], [])

    def test_evidence_references_resolve_to_real_repository_files(self) -> None:
        references = {
            link["path"]
            for incident in self.incidents
            for key in ("evidence", "tracker_rows_impacted", "resolution_evidence")
            for link in incident[key]
            if not link["path"].startswith(("http://", "https://"))
        }

        self.assertGreater(len(references), 0)
        for reference in references:
            path = reference.rsplit(":", 1)[0] if reference.rsplit(":", 1)[-1].isdigit() else reference
            self.assertNotIn("`", reference)
            self.assertTrue(Path(path).exists(), reference)

    def test_public_contract_passes_validator_without_invented_rows(self) -> None:
        serialized = json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
        report = validate_payload(self.payload, file_size_bytes=len(serialized), max_bytes=5_000_000)

        self.assertEqual(report["status"], "ok", report["errors"])
        self.assertNotIn(b"`", serialized)
        self.assertEqual(self.payload["policy"]["data_origin"], "official_real_records_only")
        self.assertEqual(self.payload["policy"]["synthetic_or_mock_records"], "forbidden")
        self.assertEqual(self.payload["policy"]["public_domain_personal_information"], "retained")

    def test_public_evidence_text_is_byte_stable_without_trailing_whitespace(self) -> None:
        source = "HTTP/2 403 \r\nHeader: retained\t\r\n\r\n"

        self.assertEqual(
            canonicalize_public_evidence_text(source),
            "HTTP/2 403\nHeader: retained\n",
        )


if __name__ == "__main__":
    unittest.main()
