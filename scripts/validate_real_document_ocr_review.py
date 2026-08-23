#!/usr/bin/env python3
"""Validate real OCR human-review work without inventing review decisions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import uuid
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-page-ocr-human-review-queue.json"
)
DEFAULT_REVIEW_CSV = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/exports/"
    "real-document-page-ocr-human-review.csv"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-page-ocr-human-review-validation.json"
)
REVIEW_FIELDS = ("review_decision", "review_notes", "reviewer_id", "reviewed_at")
REQUIRED_ASSIGNMENT_FIELDS = {
    "review_id",
    "source_group",
    "document_sha256",
    "document_path",
    "page_number",
    "routing_reason",
    "native_page_text",
    "ocr_status",
    "ocr_page_text",
}


class OcrReviewValidationError(RuntimeError):
    """Raised when real OCR review work violates its evidence contract."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.name


def sha256_path(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise OcrReviewValidationError(f"missing queue report: {display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OcrReviewValidationError(f"invalid queue report: {exc}") from exc
    if not isinstance(payload, dict):
        raise OcrReviewValidationError("queue report must be a JSON object")
    return payload


def read_review_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise OcrReviewValidationError(f"missing review CSV: {display_path(path)}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    required = REQUIRED_ASSIGNMENT_FIELDS | set(REVIEW_FIELDS)
    if not required.issubset(fields):
        missing = sorted(required - set(fields))
        raise OcrReviewValidationError(
            "review CSV fields are incomplete: " + ", ".join(missing)
        )
    if not rows:
        raise OcrReviewValidationError("review CSV has no real tasks")
    return fields, rows


def assignment_sha256(fields: list[str], rows: list[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    assignment_fields = [field for field in fields if field not in REVIEW_FIELDS]
    for row in rows:
        payload = {field: row[field] for field in assignment_fields}
        digest.update(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def valid_reviewed_at(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate(*, queue_report_path: Path, review_csv_path: Path) -> dict[str, Any]:
    queue_report = load_json(queue_report_path)
    if (
        queue_report.get("schema_version")
        != "real_document_page_ocr_human_review_queue_v1"
        or queue_report.get("status") != "ready_for_human_review"
        or not all(
            value is True for value in (queue_report.get("checks") or {}).values()
        )
    ):
        raise OcrReviewValidationError("queue report is not a valid real review batch")
    policy = queue_report.get("policy") or {}
    if (
        policy.get("synthetic_or_mock_records_counted") is not False
        or policy.get("official_public_domain_personal_information_retained")
        is not True
        or policy.get("review_labels_invented") is not False
    ):
        raise OcrReviewValidationError("queue report violates real-data review policy")

    fields, rows = read_review_csv(review_csv_path)
    queue = queue_report.get("queue") or {}
    assignment_digest = assignment_sha256(fields, rows)
    allowed_decisions = set(
        (queue_report.get("review") or {}).get("allowed_decisions") or []
    )
    if not allowed_decisions:
        raise OcrReviewValidationError("queue report has no allowed review decisions")

    errors: list[str] = []
    ids: set[str] = set()
    completed = 0
    decision_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    routing_counts: Counter[str] = Counter()
    source_decisions: Counter[tuple[str, str]] = Counter()
    for index, row in enumerate(rows, start=2):
        review_id = row["review_id"].strip()
        decision = row["review_decision"].strip()
        notes = row["review_notes"].strip()
        reviewer = row["reviewer_id"].strip()
        reviewed_at = row["reviewed_at"].strip()
        if not review_id or review_id in ids:
            errors.append(f"row {index}: missing or duplicate review_id")
        ids.add(review_id)
        if (
            len(row["document_sha256"].strip()) != 64
            or not row["document_path"].strip()
            or not row["page_number"].strip().isdigit()
            or not row["source_group"].strip()
            or not row["routing_reason"].strip()
        ):
            errors.append(f"row {index}: invalid real-page assignment")
        if decision:
            completed += 1
            if decision not in allowed_decisions:
                errors.append(f"row {index}: invalid review_decision")
            if not notes or not reviewer or not valid_reviewed_at(reviewed_at):
                errors.append(
                    f"row {index}: completed decision requires notes, reviewer, "
                    "and timezone-aware reviewed_at"
                )
            decision_counts[decision] += 1
            source_decisions[(row["source_group"], decision)] += 1
        elif notes or reviewer or reviewed_at:
            errors.append(f"row {index}: pending decision has stray human fields")
        source_counts[row["source_group"]] += 1
        routing_counts[row["routing_reason"]] += 1

    pending = len(rows) - completed
    checks = {
        "queue_report_integrity_passed": True,
        "assignment_rows_match_queue": len(rows) == int(queue.get("rows", -1)),
        "immutable_assignment_hash_matches": (
            assignment_digest == queue.get("assignment_sha256")
        ),
        "review_ids_are_unique": len(ids) == len(rows),
        "review_rows_are_well_formed": not errors,
        "no_machine_generated_review_decisions": True,
        "no_synthetic_or_mock_records": True,
        "official_public_domain_personal_information_retained": True,
    }
    batch_complete = pending == 0 and not errors
    return {
        "schema_version": "real_document_page_ocr_human_review_validation_v1",
        "generated_at": utc_now(),
        "status": "complete"
        if batch_complete and all(checks.values())
        else "pending_human_review"
        if all(checks.values())
        else "failed",
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "machine_generated_review_decisions": False,
            "reviewer_identity_is_required_for_completed_rows": True,
            "review_notes_are_required_for_completed_rows": True,
        },
        "inputs": {
            "queue_report": {
                "path": display_path(queue_report_path),
                "bytes": queue_report_path.stat().st_size,
                "sha256": sha256_path(queue_report_path),
            },
            "review_csv": {
                "path": display_path(review_csv_path),
                "bytes": review_csv_path.stat().st_size,
                "sha256": sha256_path(review_csv_path),
                "assignment_sha256": assignment_digest,
            },
        },
        "totals": {
            "review_rows": len(rows),
            "human_reviews_completed": completed,
            "human_reviews_pending": pending,
        },
        "breakdown": {
            "decisions": dict(sorted(decision_counts.items())),
            "source_groups": dict(sorted(source_counts.items())),
            "routing_reasons": dict(sorted(routing_counts.items())),
            "source_decisions": {
                "|".join(key): value for key, value in sorted(source_decisions.items())
            },
        },
        "gates": {
            "batch_complete": batch_complete,
            "double_review_complete": False,
            "adjudication_complete": False,
            "promotion_ready": False,
        },
        "diagnostics": {"errors": errors[:50]},
        "checks": checks,
        "next_action": (
            "Have human reviewers complete every decision, note, reviewer ID, and "
            "timezone-aware timestamp; rerun with --require-complete, then perform "
            "independent second review and adjudication before promotion."
        ),
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-report", default=str(DEFAULT_QUEUE_REPORT))
    parser.add_argument("--review-csv", default=str(DEFAULT_REVIEW_CSV))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce-integrity", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = validate(
            queue_report_path=Path(args.queue_report),
            review_csv_path=Path(args.review_csv),
        )
        write_json_atomic(Path(args.report_out), report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        if args.enforce_integrity and report["status"] == "failed":
            return 1
        if args.require_complete and report["status"] != "complete":
            return 1
        return 0
    except (OcrReviewValidationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
