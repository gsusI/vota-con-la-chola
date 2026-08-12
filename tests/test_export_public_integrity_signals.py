from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from publicdata_evidence import (
    approve_signal_publication,
    create_review_signal,
    record_right_of_reply,
    record_signal_review,
    record_signal_correction,
    transition_signal,
)
from publicdata_sqlite import open_db
from scripts.export_public_integrity_signals import build_public_integrity_snapshot


class TestExportPublicIntegritySignals(unittest.TestCase):
    def test_export_includes_only_approved_and_withdraws_correction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            conn = open_db(Path(temp_dir) / "signals.db")
            try:
                conn.execute(
                    "CREATE TABLE source_records (source_record_pk INTEGER PRIMARY KEY)"
                )
                conn.executemany("INSERT INTO source_records VALUES (?)", [(1,), (2,)])
                evidence = []
                for index, source in ((1, "source-a"), (2, "source-b")):
                    url = f"https://official.example/{source}"
                    evidence.append(
                        {
                            "evidence_role": "observed",
                            "independent_source_key": source,
                            "source_id": source,
                            "source_record_pk": index,
                            "source_url": url,
                            "content_sha256": hashlib.sha256(url.encode()).hexdigest(),
                        }
                    )
                signal_id = create_review_signal(
                    conn,
                    signal_id="signal-approved",
                    detector_id="fixture",
                    detector_version="v1",
                    signal_type="review_pattern",
                    subject_type="institution",
                    subject_id="institution-a",
                    summary="Narrow reviewed pattern; not a corruption finding.",
                    evidence=evidence,
                )
                internal = build_public_integrity_snapshot(
                    conn, snapshot_date="2026-08-10"
                )
                self.assertEqual(internal["signals_total"], 0)

                record_signal_review(
                    conn,
                    signal_id=signal_id,
                    reviewer_id="reviewer-one",
                    reviewer_independence_class="maintainer",
                    decision="corroborate",
                    rationale="First review.",
                )
                record_signal_review(
                    conn,
                    signal_id=signal_id,
                    reviewer_id="reviewer-two",
                    reviewer_independence_class="independent",
                    decision="corroborate",
                    rationale="Independent second review.",
                )
                transition_signal(
                    conn,
                    signal_id=signal_id,
                    to_state="corroborated_risk",
                    actor_kind="human_reviewer",
                    actor_id="reviewer",
                    rationale="Two independent official records.",
                )
                record_right_of_reply(
                    conn,
                    signal_id=signal_id,
                    response_status="not_required",
                    recorded_by="maintainer",
                )
                approve_signal_publication(
                    conn,
                    signal_id=signal_id,
                    reviewer_id="maintainer",
                    rationale="Approved with narrow non-allegation language.",
                )
                approved = build_public_integrity_snapshot(
                    conn, snapshot_date="2026-08-10"
                )
                self.assertEqual(approved["signals_total"], 1)
                self.assertEqual(approved["signals"][0]["independent_source_count"], 2)
                self.assertTrue(
                    approved["safety_contract"]["anomaly_is_not_corruption_finding"]
                )

                record_signal_correction(
                    conn,
                    signal_id=signal_id,
                    correction_type="counterevidence",
                    rationale="Corrected by later official evidence.",
                    corrected_by="maintainer",
                )
                corrected = build_public_integrity_snapshot(
                    conn, snapshot_date="2026-08-10"
                )
                self.assertEqual(corrected["signals_total"], 0)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
