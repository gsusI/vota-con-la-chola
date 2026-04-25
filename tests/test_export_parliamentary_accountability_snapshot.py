from __future__ import annotations

import json
import sqlite3
import unittest

from scripts import export_parliamentary_accountability_snapshot as accountability


class TestExportParliamentaryAccountabilitySnapshot(unittest.TestCase):
    def test_build_initiative_measure_index_returns_empty_when_table_missing(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            by_initiative, by_vote_ref = accountability.build_initiative_measure_index(conn)
        finally:
            conn.close()

        self.assertEqual(by_initiative, {})
        self.assertEqual(by_vote_ref, {})

    def test_select_initiative_measure_previews_prefers_vote_event_specific_matches(self) -> None:
        measure_generic = {
            "measure_point_id": "m-1",
            "rank": 1,
            "title": "Medida general",
            "summary": "Resumen general",
            "policy_area": "movilidad",
            "status": "approved",
            "support_side": "yes",
        }
        measure_specific = {
            "measure_point_id": "m-2",
            "rank": 2,
            "title": "Medida ligada a una votacion concreta",
            "summary": "Resumen de la votacion concreta",
            "policy_area": "movilidad",
            "status": "approved",
            "support_side": "yes",
        }
        by_initiative = {"initiative:1": [measure_generic, measure_specific]}
        by_vote_ref = {
            ("initiative:1", "url:https://example.test/vote/1"): [measure_specific],
            ("initiative:1", "https://example.test/vote/1"): [measure_specific],
        }

        selected = accountability.select_initiative_measure_previews(
            {
                "initiative_id": "initiative:1",
                "vote_event_id": "url:https://example.test/vote/1",
                "source_url": "https://example.test/vote/1",
            },
            by_initiative,
            by_vote_ref,
        )

        self.assertEqual(selected["initiative_measure_points_total"], 2)
        self.assertEqual(selected["initiative_measures_count"], 1)
        self.assertEqual(selected["initiative_measure_match_scope"], "vote_event")
        self.assertEqual(
            selected["initiative_measures"],
            [
                {
                    "rank": 2,
                    "title": "Medida ligada a una votacion concreta",
                    "summary": "Resumen de la votacion concreta",
                    "policy_area": "movilidad",
                    "status": "approved",
                    "support_side": "yes",
                }
            ],
        )

    def test_select_initiative_measure_previews_falls_back_to_initiative_rows(self) -> None:
        by_initiative = {
            "initiative:2": [
                {
                    "measure_point_id": "m-11",
                    "rank": 1,
                    "title": "Medida uno",
                    "summary": "Resumen uno",
                    "policy_area": "consumo",
                    "status": "approved",
                    "support_side": "yes",
                },
                {
                    "measure_point_id": "m-12",
                    "rank": 2,
                    "title": "Medida dos",
                    "summary": "Resumen dos",
                    "policy_area": "consumo",
                    "status": "pending",
                    "support_side": "mixed",
                },
            ]
        }

        selected = accountability.select_initiative_measure_previews(
            {
                "initiative_id": "initiative:2",
                "vote_event_id": "url:https://example.test/vote/2",
                "source_url": "https://example.test/vote/2",
            },
            by_initiative,
            {},
            preview_limit=1,
        )

        self.assertEqual(selected["initiative_measure_points_total"], 2)
        self.assertEqual(selected["initiative_measures_count"], 2)
        self.assertEqual(selected["initiative_measure_match_scope"], "initiative")
        self.assertEqual(
            selected["initiative_measures"],
            [
                {
                    "rank": 1,
                    "title": "Medida uno",
                    "summary": "Resumen uno",
                    "policy_area": "consumo",
                    "status": "approved",
                    "support_side": "yes",
                }
            ],
        )

    def test_select_featured_outcome_rows_prioritizes_rows_with_measures(self) -> None:
        featured = accountability.select_featured_outcome_rows(
            [
                {
                    "vote_event_id": "vote:high-margin",
                    "outcome": "passed",
                    "initiative_measures_count": 0,
                },
                {
                    "vote_event_id": "vote:with-measure",
                    "outcome": "passed",
                    "initiative_measures_count": 1,
                    "vote_date": "2026-02-12",
                },
                {
                    "vote_event_id": "vote:second",
                    "outcome": "failed",
                    "initiative_measures_count": 0,
                },
            ],
            limit=2,
        )

        self.assertEqual(
            [row["vote_event_id"] for row in featured],
            ["vote:with-measure", "vote:high-margin"],
        )

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
