from __future__ import annotations

import json
import unittest

from scripts import export_parliamentary_accountability_snapshot as accountability


class TestExportParliamentaryAccountabilitySnapshot(unittest.TestCase):
    def test_sanitize_accountability_payload_redacts_local_urls_and_db_path(self) -> None:
        payload = {
            "meta": {
                "generated_at": "2026-03-06T00:00:00+00:00",
                "db_path": "etl/data/staging/politicos-es.db",
            },
            "events_preview": [
                {
                    "vote_event_id": "vote:1",
                    "source_url": "file:///Users/alice/private/vote.json",
                    "quality": {
                        "has_source_url": True,
                    },
                }
            ],
            "outcomes": {
                "samples": [
                    {
                        "vote_event_id": "vote:1",
                        "source_url": "file:///Users/alice/private/vote.json",
                        "initiative_source_url": "file:///Users/alice/private/init.json",
                        "initiative_doc_url": "file:///Users/alice/private/doc.pdf",
                    }
                ]
            },
        }

        sanitized = accountability.sanitize_accountability_payload(payload)
        serialized = json.dumps(sanitized, ensure_ascii=False)

        self.assertNotIn("db_path", serialized)
        self.assertNotIn("/Users/alice", serialized)
        self.assertEqual(sanitized["events_preview"][0]["source_url"], "")
        self.assertEqual(sanitized["outcomes"]["samples"][0]["source_url"], "")
        self.assertEqual(sanitized["outcomes"]["samples"][0]["initiative_source_url"], "")
        self.assertEqual(sanitized["outcomes"]["samples"][0]["initiative_doc_url"], "")


if __name__ == "__main__":
    unittest.main()
