from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from publicdata_evidence import (
    add_signal_evidence,
    approve_signal_publication,
    create_review_signal,
    ensure_integrity_signal_schema,
    public_integrity_signals,
    record_right_of_reply,
    record_signal_correction,
    record_signal_review,
    transition_signal,
)
from publicdata_sqlite import open_db


def evidence(source_id: str, record_pk: int, role: str = "observed") -> dict[str, object]:
    url = f"https://official.example/{source_id}/{record_pk}"
    return {
        "evidence_role": role,
        "independent_source_key": source_id,
        "source_id": source_id,
        "source_record_pk": record_pk,
        "source_url": url,
        "content_sha256": hashlib.sha256(url.encode()).hexdigest(),
        "excerpt": "Observed primary-source fact; no allegation.",
    }


class TestIntegritySignalWorkflow(unittest.TestCase):
    def test_schema_repair_withdraws_legacy_superseded_signal(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        ensure_integrity_signal_schema(conn)
        conn.execute(
            """
            INSERT INTO integrity_signals (
              signal_id, detector_id, detector_version, signal_type,
              subject_type, subject_id, state, summary, publication_status,
              created_at, updated_at
            ) VALUES (
              'legacy-superseded', 'detector', 'v1', 'pattern',
              'contract', 'contract-1', 'superseded', 'legacy row', 'internal',
              '2026-08-11T00:00:00+00:00', '2026-08-11T00:00:00+00:00'
            )
            """
        )
        conn.commit()

        ensure_integrity_signal_schema(conn)

        row = conn.execute(
            "SELECT publication_status FROM integrity_signals WHERE signal_id = ?",
            ("legacy-superseded",),
        ).fetchone()
        self.assertEqual(row["publication_status"], "withdrawn")
        conn.close()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.conn = open_db(Path(self.temp_dir.name) / "integrity.db")
        self.conn.execute(
            "CREATE TABLE source_records (source_record_pk INTEGER PRIMARY KEY)"
        )
        self.conn.executemany(
            "INSERT INTO source_records VALUES (?)", [(1,), (2,), (3,), (4,)]
        )
        ensure_integrity_signal_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp_dir.cleanup()

    def test_machine_cannot_publish_and_false_positive_is_rejected(self) -> None:
        signal_id = create_review_signal(
            self.conn,
            signal_id="signal-false-positive",
            detector_id="procurement-threshold-review",
            detector_version="v1",
            signal_type="threshold_bunching_candidate",
            subject_type="contracting_authority",
            subject_id="authority-a",
            summary="Review signal only; not a finding of misconduct.",
            evidence=[evidence("source-a", 1)],
            limitations=["Configured analytical threshold is not a legal conclusion."],
        )
        with self.assertRaisesRegex(ValueError, "human reviewer"):
            transition_signal(
                self.conn,
                signal_id=signal_id,
                to_state="corroborated_risk",
                actor_kind="detector",
                actor_id="automation",
                rationale="model score",
            )

        add_signal_evidence(
            self.conn,
            signal_id=signal_id,
            evidence=[evidence("source-b", 2, "counterevidence")],
        )
        transition_signal(
            self.conn,
            signal_id=signal_id,
            to_state="rejected",
            actor_kind="human_reviewer",
            actor_id="reviewer-fixture",
            rationale="Counterevidence explains the apparent pattern.",
        )
        self.assertEqual(public_integrity_signals(self.conn), [])

    def test_corroboration_reply_publication_and_correction_are_gated(self) -> None:
        signal_id = create_review_signal(
            self.conn,
            signal_id="signal-corroborated",
            detector_id="procurement-threshold-review",
            detector_version="v1",
            signal_type="threshold_bunching_candidate",
            subject_type="contracting_authority",
            subject_id="authority-b",
            summary="Two independent primary records warrant human review.",
            evidence=[evidence("source-a", 1), evidence("source-b", 2, "corroborating")],
        )
        record_signal_review(
            self.conn,
            signal_id=signal_id,
            reviewer_id="reviewer-one",
            reviewer_independence_class="maintainer",
            decision="corroborate",
            rationale="First evidence review.",
        )
        with self.assertRaisesRegex(ValueError, "two human"):
            transition_signal(
                self.conn,
                signal_id=signal_id,
                to_state="corroborated_risk",
                actor_kind="human_reviewer",
                actor_id="reviewer-one",
                rationale="Only one review exists.",
            )
        record_signal_review(
            self.conn,
            signal_id=signal_id,
            reviewer_id="reviewer-two",
            reviewer_independence_class="independent",
            decision="corroborate",
            rationale="Independent second evidence review.",
        )
        transition_signal(
            self.conn,
            signal_id=signal_id,
            to_state="corroborated_risk",
            actor_kind="human_reviewer",
            actor_id="reviewer-fixture",
            rationale="Two independent traceable sources corroborate the narrow pattern.",
        )
        with self.assertRaisesRegex(ValueError, "right-of-reply"):
            approve_signal_publication(
                self.conn,
                signal_id=signal_id,
                reviewer_id="maintainer-fixture",
                rationale="premature",
            )
        record_right_of_reply(
            self.conn,
            signal_id=signal_id,
            response_status="no_response_after_deadline",
            recorded_by="maintainer-fixture",
            response_summary="Documented contact window closed.",
        )
        approve_signal_publication(
            self.conn,
            signal_id=signal_id,
            reviewer_id="maintainer-fixture",
            rationale="Narrow risk language approved; no corruption finding claimed.",
        )
        self.assertEqual(len(public_integrity_signals(self.conn)), 1)

        record_signal_correction(
            self.conn,
            signal_id=signal_id,
            correction_type="counterevidence",
            rationale="New official record changes the interpretation.",
            corrected_by="maintainer-fixture",
            evidence_url="https://official.example/correction",
        )
        self.assertEqual(public_integrity_signals(self.conn), [])
        row = self.conn.execute(
            "SELECT state, publication_status FROM integrity_signals WHERE signal_id = ?",
            (signal_id,),
        ).fetchone()
        self.assertEqual((row["state"], row["publication_status"]), ("superseded", "withdrawn"))

    def test_official_finding_requires_traceable_official_evidence(self) -> None:
        signal_id = create_review_signal(
            self.conn,
            signal_id="signal-official",
            detector_id="audit-linker",
            detector_version="v1",
            signal_type="official_audit_finding",
            subject_type="institution",
            subject_id="institution-a",
            summary="Review official control-body finding.",
            evidence=[evidence("source-a", 1), evidence("source-b", 2, "corroborating")],
        )
        record_signal_review(
            self.conn,
            signal_id=signal_id,
            reviewer_id="reviewer-one",
            reviewer_independence_class="maintainer",
            decision="corroborate",
            rationale="First review.",
        )
        record_signal_review(
            self.conn,
            signal_id=signal_id,
            reviewer_id="reviewer-two",
            reviewer_independence_class="independent",
            decision="corroborate",
            rationale="Independent second review.",
        )
        transition_signal(
            self.conn,
            signal_id=signal_id,
            to_state="corroborated_risk",
            actor_kind="human_reviewer",
            actor_id="reviewer-fixture",
            rationale="Corroborated for official-document review.",
        )
        with self.assertRaisesRegex(ValueError, "official evidence"):
            transition_signal(
                self.conn,
                signal_id=signal_id,
                to_state="official_finding",
                actor_kind="maintainer",
                actor_id="maintainer-fixture",
                rationale="missing official finding",
            )
        add_signal_evidence(
            self.conn,
            signal_id=signal_id,
            evidence=[evidence("control-body", 3, "official_finding")],
        )
        transition_signal(
            self.conn,
            signal_id=signal_id,
            to_state="official_finding",
            actor_kind="maintainer",
            actor_id="maintainer-fixture",
            rationale="Official control-body record attached verbatim by reference.",
        )


if __name__ == "__main__":
    unittest.main()
