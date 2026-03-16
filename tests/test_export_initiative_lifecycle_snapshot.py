from __future__ import annotations

import unittest
from unittest import mock

from scripts import export_initiative_lifecycle_snapshot as lifecycle


class TestExportInitiativeLifecycleSnapshot(unittest.TestCase):
    def test_build_payload_does_not_expose_db_path_metadata(self) -> None:
        fake_initiatives = [
            {
                "initiative_id": "init:1",
                "source_id": "congreso_iniciativas",
                "competent_committee": "Comision X",
                "legislature": "15",
                "current_status": "En tramitacion",
                "vote_count": 1,
                "link_summary": {"link_confidence_bucket": "alta"},
            }
        ]

        with mock.patch.object(
            lifecycle,
            "build_initiatives_payload",
            return_value=(fake_initiatives, {"Comision X": fake_initiatives}, {"by_title": 1}, {"alta": 1}),
        ), mock.patch.object(
            lifecycle,
            "build_bottleneck_payload",
            return_value={"committees": []},
        ):
            payload = lifecycle.build_payload(
                conn=mock.MagicMock(),
                max_votes_per_initiative=240,
                max_initiatives=0,
                min_committee_sample=4,
            )

        self.assertNotIn("db_path", payload["meta"])
        self.assertEqual(payload["meta"]["total_initiatives"], 1)
        self.assertEqual(payload["meta"]["linked_initiatives"], 1)


if __name__ == "__main__":
    unittest.main()
