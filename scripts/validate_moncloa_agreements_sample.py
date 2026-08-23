#!/usr/bin/env python3
"""Validate the real-only Moncloa agreements materialization and publication."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = REPO_ROOT / "etl/data/staging/moncloa-aiops04-matrix-20260216.db"
DEFAULT_DB = REPO_ROOT / "etl/data/staging/agreements-moncloa-mvp.db"
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/agreements-moncloa-sample.json"
DEFAULT_PUBLIC = REPO_ROOT / "ui/gh-pages-next/public/agreements/data/moncloa-sample.json"
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/AGREEMENTS-20260819/evidence/moncloa-agreements-validation.json"
)

SOURCE_ID = "moncloa_referencias"
REQUIRED_RECORDS = 11
FORBIDDEN_DATA_MARKERS = (
    "synthetic",
    "mock data",
    "dummy data",
    "fake data",
    "placeholder data",
    "example.invalid",
    "john doe",
    "jane doe",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--published", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_bytes(data)
    temp.replace(path)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def validate_artifact(
    snapshot: dict[str, Any],
    source: sqlite3.Connection,
    materialized: sqlite3.Connection,
    errors: list[str],
) -> dict[str, Any]:
    if snapshot.get("real_data_only") is not True:
        fail(errors, "real_data_only must be true")
    if snapshot.get("synthetic_or_mock") is not False:
        fail(errors, "synthetic_or_mock must be false")
    if snapshot.get("public_domain_information_policy") != "retained_exactly":
        fail(errors, "public-domain information retention policy mismatch")
    records = snapshot.get("records")
    if not isinstance(records, list):
        fail(errors, "records must be a list")
        return {}
    if len(records) != REQUIRED_RECORDS:
        fail(errors, f"expected {REQUIRED_RECORDS} records, got {len(records)}")

    counts = snapshot.get("counts") or {}
    for key in ("meetings", "agreements", "meeting_evidence", "agreement_evidence"):
        if counts.get(key) != REQUIRED_RECORDS:
            fail(errors, f"count mismatch for {key}: {counts.get(key)}")
    if counts.get("attendance_claims") != 0:
        fail(errors, "sample must not invent attendance claims")
    if counts.get("influence_assertions") != 0:
        fail(errors, "fact sample must contain zero influence assertions")
    if snapshot.get("influence_assertions") != []:
        fail(errors, "influence_assertions payload must be empty")

    source_capture = (snapshot.get("source") or {}).get("capture") or {}
    capture_path = REPO_ROOT / str(source_capture.get("path") or "")
    if not capture_path.is_file():
        fail(errors, "captured source file missing")
    else:
        if capture_path.stat().st_size != source_capture.get("bytes"):
            fail(errors, "captured source byte count mismatch")
        if sha256_file(capture_path) != source_capture.get("content_sha256"):
            fail(errors, "captured source SHA-256 mismatch")
    if not str(source_capture.get("source_url") or "").startswith(
        "https://www.lamoncloa.gob.es/"
    ):
        fail(errors, "capture source URL is not the official public origin")

    record_ids: set[str] = set()
    meeting_ids: set[str] = set()
    agreement_ids: set[str] = set()
    topic_total = 0
    party_total = 0
    for record in records:
        meeting = record.get("meeting") or {}
        agreement = record.get("agreement") or {}
        provenance = record.get("provenance") or {}
        record_id = str(provenance.get("source_record_id") or "")
        if not record_id or record_id in record_ids:
            fail(errors, f"missing or duplicate source record ID: {record_id}")
        record_ids.add(record_id)
        if provenance.get("source_id") != SOURCE_ID:
            fail(errors, f"unexpected source ID: {record_id}")
        if not str(provenance.get("source_url") or "").startswith(
            "https://www.lamoncloa.gob.es/"
        ):
            fail(errors, f"non-official source URL: {record_id}")
        if provenance.get("capture_sha256") != source_capture.get("content_sha256"):
            fail(errors, f"capture lineage mismatch: {record_id}")

        source_row = source.execute(
            """
            SELECT
              source_record_pk,
              content_sha256,
              json_extract(raw_payload, '$.event_date_iso') AS event_date,
              json_extract(raw_payload, '$.published_at_iso') AS published_at,
              json_extract(raw_payload, '$.title') AS title,
              json_extract(raw_payload, '$.summary_text') AS summary_text,
              json_extract(raw_payload, '$.source_url') AS source_url
            FROM source_records
            WHERE source_id = ? AND source_record_id = ?
            """,
            (SOURCE_ID, record_id),
        ).fetchone()
        if source_row is None:
            fail(errors, f"source record missing: {record_id}")
            continue
        summary = str(source_row["summary_text"] or "")
        if "acuerdo" not in summary.casefold():
            fail(errors, f"record does not explicitly say acuerdo: {record_id}")
        if meeting.get("summary") != summary or agreement.get("summary") != summary:
            fail(errors, f"summary differs from captured source: {record_id}")
        if meeting.get("event_date") != source_row["event_date"]:
            fail(errors, f"meeting date differs from source: {record_id}")
        if agreement.get("adopted_on") != source_row["event_date"]:
            fail(errors, f"adoption date differs from source: {record_id}")
        if agreement.get("agreement_status") != "adopted":
            fail(errors, f"agreement status is not adopted: {record_id}")
        if agreement.get("influence_state") != "not_asserted":
            fail(errors, f"influence state must remain not_asserted: {record_id}")
        if meeting.get("attendance_disclosure_state") != "not_disclosed":
            fail(errors, f"attendance disclosure must remain not_disclosed: {record_id}")
        participants = meeting.get("participants") or []
        if len(participants) != 2:
            fail(errors, f"expected only convener/discloser actors: {record_id}")
        if any(item.get("attendance_claim_state") != "not_claimed" for item in participants):
            fail(errors, f"invented attendee claim: {record_id}")

        meeting_id = str(meeting.get("meeting_id") or "")
        agreement_id = str(agreement.get("agreement_id") or "")
        if not meeting_id or meeting_id in meeting_ids:
            fail(errors, f"missing or duplicate meeting ID: {record_id}")
        if not agreement_id or agreement_id in agreement_ids:
            fail(errors, f"missing or duplicate agreement ID: {record_id}")
        meeting_ids.add(meeting_id)
        agreement_ids.add(agreement_id)
        if agreement.get("meeting_id") != meeting_id:
            fail(errors, f"agreement does not link its meeting: {record_id}")

        agreement_evidence = agreement.get("evidence") or []
        meeting_evidence = meeting.get("evidence") or []
        for evidence in (*agreement_evidence, *meeting_evidence):
            if evidence.get("exact_quote") != summary:
                fail(errors, f"evidence quote differs from source: {record_id}")
            if evidence.get("quote_sha256") != sha256_bytes(summary.encode("utf-8")):
                fail(errors, f"evidence quote hash mismatch: {record_id}")
            if evidence.get("content_sha256") != source_row["content_sha256"]:
                fail(errors, f"evidence record hash mismatch: {record_id}")
            if evidence.get("evidence_state") != "captured_bytes":
                fail(errors, f"primary evidence is not captured bytes: {record_id}")

        parties = agreement.get("parties") or []
        if [party.get("party_role") for party in parties[:2]] != [
            "adopter",
            "publishing_body",
        ]:
            fail(errors, f"mandatory official actor roles missing: {record_id}")
        for party in parties[2:]:
            if str(party.get("source_label") or "").casefold() not in summary.casefold():
                fail(errors, f"actor not found exactly in source excerpt: {record_id}")
        party_total += len(parties)

        topics = agreement.get("topics") or []
        if not topics:
            fail(errors, f"agreement lacks topic assignment: {record_id}")
        for topic in topics:
            if topic.get("assignment_kind") != "derived_rule":
                fail(errors, f"topic is not visibly derived: {record_id}")
            if topic.get("review_status") != "unreviewed":
                fail(errors, f"topic review state was invented: {record_id}")
            if str(topic.get("match_text") or "").casefold() not in summary.casefold():
                fail(errors, f"topic match text absent from source: {record_id}")
        topic_total += len(topics)

        db_row = materialized.execute(
            """
            SELECT a.agreement_id, a.meeting_id, a.summary, a.content_sha256,
                   m.attendance_disclosure_state
            FROM agreements AS a
            JOIN accountability_meetings AS m ON m.meeting_id = a.meeting_id
            WHERE a.agreement_id = ?
            """,
            (agreement_id,),
        ).fetchone()
        if db_row is None:
            fail(errors, f"materialized agreement missing: {agreement_id}")
        elif tuple(db_row) != (
            agreement_id,
            meeting_id,
            summary,
            source_row["content_sha256"],
            "not_disclosed",
        ):
            fail(errors, f"materialized agreement differs: {agreement_id}")

    if party_total != counts.get("agreement_parties"):
        fail(errors, "agreement party total mismatch")
    if topic_total != counts.get("agreement_topics"):
        fail(errors, "agreement topic total mismatch")

    db_tables = (
        "accountability_meetings",
        "meeting_participants",
        "meeting_agenda_items",
        "meeting_evidence",
        "agreements",
        "agreement_parties",
        "agreement_evidence",
        "agreement_topics",
        "influence_assertions",
    )
    database_counts = {
        table: int(materialized.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in db_tables
    }
    if database_counts["influence_assertions"] != 0:
        fail(errors, "materialized DB contains influence assertions")
    db_attendance_claims = int(
        materialized.execute(
            "SELECT COUNT(*) FROM meeting_participants WHERE attendance_claim_state <> 'not_claimed'"
        ).fetchone()[0]
    )
    if db_attendance_claims != 0:
        fail(errors, "materialized DB contains unsupported attendance claims")
    fk_errors = [tuple(row) for row in materialized.execute("PRAGMA foreign_key_check")]
    if fk_errors:
        fail(errors, f"foreign key violations: {len(fk_errors)}")
    integrity = str(materialized.execute("PRAGMA integrity_check").fetchone()[0])
    if integrity != "ok":
        fail(errors, f"SQLite integrity check failed: {integrity}")

    serialized = canonical_json(snapshot).casefold()
    serialized_records = canonical_json(records).casefold()
    for marker in FORBIDDEN_DATA_MARKERS:
        if marker in serialized_records:
            fail(errors, f"forbidden fake-data marker found: {marker}")
    for marker in ("/users/", "file:///", "googledrive", "@gmail.com"):
        if marker in serialized:
            fail(errors, f"private workstation marker found: {marker}")

    return {
        "records": len(records),
        "meeting_ids": len(meeting_ids),
        "agreement_ids": len(agreement_ids),
        "agreement_parties": party_total,
        "agreement_topics": topic_total,
        "attendance_claims": db_attendance_claims,
        "influence_assertions": database_counts["influence_assertions"],
        "foreign_key_violations": len(fk_errors),
        "integrity_check": integrity,
        "database_counts": database_counts,
    }


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    required = (args.source_db, args.db, args.published, args.public)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"missing required artifacts: {', '.join(missing)}")

    published_bytes = args.published.read_bytes()
    public_bytes = args.public.read_bytes()
    if published_bytes != public_bytes:
        errors.append("published and public artifacts differ")
    snapshot = json.loads(published_bytes)

    source = sqlite3.connect(f"file:{args.source_db}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    materialized = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    materialized.row_factory = sqlite3.Row
    try:
        metrics = validate_artifact(snapshot, source, materialized, errors)
    finally:
        source.close()
        materialized.close()

    report = {
        "status": "ok" if not errors else "error",
        "release_id": snapshot.get("release_id"),
        "artifact_sha256": sha256_bytes(published_bytes),
        "artifact_bytes": len(published_bytes),
        "metrics": metrics,
        "errors": errors,
    }
    atomic_json(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
