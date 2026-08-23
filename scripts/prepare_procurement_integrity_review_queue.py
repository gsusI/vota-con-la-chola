#!/usr/bin/env python3
"""Export immutable dual-review tasks for real procurement integrity signals."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_sqlite import open_db
from scripts.detect_procurement_integrity_signals import (
    _signal_id,
    iter_threshold_pattern_rows,
)

DEFAULT_DB = Path("etl/data/staging/placsp-contracts-real-s1-20260811.db")
DEFAULT_CSV = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/exports/"
    "procurement-integrity-human-review.csv"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "procurement-integrity-human-review-queue.json"
)
DETECTOR_ID = "procurement-threshold-pattern-review"
DETECTOR_VERSION = "v4"
REVIEW_FIELDS = (
    "reviewer_1_id",
    "reviewer_1_independence_class",
    "reviewer_1_decision",
    "reviewer_1_rationale",
    "reviewer_1_reviewed_at",
    "reviewer_2_id",
    "reviewer_2_independence_class",
    "reviewer_2_decision",
    "reviewer_2_rationale",
    "reviewer_2_reviewed_at",
    "adjudicator_id",
    "adjudication_decision",
    "adjudication_rationale",
    "adjudicated_at",
)
FIELDNAMES = (
    "task_id",
    "signal_id",
    "detector_id",
    "detector_version",
    "subject_type",
    "subject_id",
    "contracting_authority",
    "cpv_code",
    "period_start",
    "period_end",
    "record_count",
    "amount_eur",
    "review_priority",
    "summary",
    "limitations_json",
    "evidence_count",
    "evidence_basis_json",
    "evidence_row_ids_json",
    "source_record_pks_json",
    "source_urls_json",
    "content_sha256s_json",
    "amounts_eur_decimal_json",
    "stable_contract_ids_json",
    "lot_ids_json",
    "supplier_identifiers_json",
    "evidence_excerpts_json",
    "task_fingerprint",
    *REVIEW_FIELDS,
)
ALLOWED_DECISIONS = {"needs_more_evidence", "corroborate", "reject"}
ALLOWED_INDEPENDENCE = {"author", "maintainer", "independent"}


class ReviewQueueError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_CSV))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args()


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def atomic_write(path: Path, writer: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_existing_reviews(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    reviews: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        observed_fields = tuple(reader.fieldnames or ())
        for row in reader:
            task_id = str(row.get("task_id") or "")
            if not task_id or task_id in reviews:
                raise ReviewQueueError("existing review task identity is invalid")
            reviews[task_id] = dict(row)
    if observed_fields != FIELDNAMES:
        review_fields_available = all(
            field in observed_fields for field in REVIEW_FIELDS
        )
        any_human_work = review_fields_available and any(
            row.get(field, "")
            for row in reviews.values()
            for field in REVIEW_FIELDS
        )
        if any_human_work:
            raise ReviewQueueError("existing review queue with human work drifted")
        return {}
    return reviews


def task_fingerprint(row: dict[str, str]) -> str:
    payload = {
        key: row[key]
        for key in FIELDNAMES
        if key not in REVIEW_FIELDS and key != "task_fingerprint"
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def build_tasks(
    connection: sqlite3.Connection,
    *,
    existing: dict[str, dict[str, str]],
    limit: int,
) -> list[dict[str, str]]:
    rows = connection.execute(
        """
        SELECT signal_id, detector_id, detector_version, subject_type, subject_id,
               period_start, period_end, review_priority, summary, metrics_json,
               limitations_json
        FROM integrity_signals
        WHERE detector_id=? AND detector_version=?
          AND state='review_signal' AND publication_status='internal'
        ORDER BY review_priority DESC, signal_id
        """,
        (DETECTOR_ID, DETECTOR_VERSION),
    ).fetchall()
    if limit > 0:
        rows = rows[:limit]
    selected_signal_ids = {str(row["signal_id"]) for row in rows}
    evidence_by_signal: dict[str, list[sqlite3.Row]] = defaultdict(list)
    detection_digests: dict[tuple[str, str, str], Any] = {}
    group_rows: dict[tuple[str, str, str], list[sqlite3.Row]] = defaultdict(list)
    for item in iter_threshold_pattern_rows(
        connection,
        threshold_eur=15_000.0,
        min_records=3,
        source_ids=("placsp_sindicacion",),
    ):
        key = (
            str(item["contracting_authority"]),
            str(item["cpv_code"]),
            str(item["period_month"]),
        )
        group_rows[key].append(item)
    for (authority, cpv_code, period_month), evidence_rows in group_rows.items():
        digest = hashlib.sha256()
        for item in evidence_rows:
            digest.update(
                json.dumps(
                    [
                        str(item["evidence_basis"]),
                        int(item["evidence_row_id"]),
                        int(item["source_record_pk"]),
                        str(item["amount_eur_decimal"]),
                    ],
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        fingerprint = digest.hexdigest()
        signal_id = _signal_id(
            authority,
            cpv_code,
            period_month,
            fingerprint,
        )
        detection_digests[(authority, cpv_code, period_month)] = fingerprint
        if signal_id in selected_signal_ids:
            evidence_by_signal[signal_id] = evidence_rows
    tasks: list[dict[str, str]] = []
    for signal in rows:
        signal_id = str(signal["signal_id"])
        evidence = evidence_by_signal.get(signal_id, [])
        if not evidence:
            raise ReviewQueueError(f"signal has no official evidence: {signal_id}")
        for item in evidence:
            parsed = urlparse(str(item["source_url"] or ""))
            if (
                parsed.scheme != "https"
                or (parsed.hostname or "").lower() != "contrataciondelestado.es"
                or not item["source_record_pk"]
                or len(str(item["content_sha256"] or "")) != 64
            ):
                raise ReviewQueueError(f"signal evidence contract failed: {signal_id}")
        metrics = json.loads(str(signal["metrics_json"] or "{}"))
        if len(evidence) != int(metrics.get("records") or 0):
            raise ReviewQueueError(f"signal evidence count drifted: {signal_id}")
        key = (
            str(metrics.get("contracting_authority") or ""),
            str(metrics.get("cpv_code") or ""),
            str(signal["period_start"] or "")[:7],
        )
        if detection_digests.get(key) != str(
            metrics.get("detection_fingerprint") or ""
        ):
            raise ReviewQueueError(f"signal evidence fingerprint drifted: {signal_id}")
        task_id = f"procurement-review:{signal_id}"
        task: dict[str, str] = {
            "task_id": task_id,
            "signal_id": signal_id,
            "detector_id": str(signal["detector_id"]),
            "detector_version": str(signal["detector_version"]),
            "subject_type": str(signal["subject_type"]),
            "subject_id": str(signal["subject_id"]),
            "contracting_authority": str(metrics.get("contracting_authority") or ""),
            "cpv_code": str(metrics.get("cpv_code") or ""),
            "period_start": str(signal["period_start"] or ""),
            "period_end": str(signal["period_end"] or ""),
            "record_count": str(int(metrics.get("records") or 0)),
            "amount_eur": str(metrics.get("amount_eur") or ""),
            "review_priority": str(int(signal["review_priority"] or 0)),
            "summary": str(signal["summary"]),
            "limitations_json": str(signal["limitations_json"]),
            "evidence_count": str(len(evidence)),
            "evidence_basis_json": json.dumps(
                [str(item["evidence_basis"]) for item in evidence],
                separators=(",", ":"),
            ),
            "evidence_row_ids_json": json.dumps(
                [int(item["evidence_row_id"]) for item in evidence],
                separators=(",", ":"),
            ),
            "source_record_pks_json": json.dumps(
                [int(item["source_record_pk"]) for item in evidence],
                separators=(",", ":"),
            ),
            "source_urls_json": json.dumps(
                [str(item["source_url"]) for item in evidence],
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            "content_sha256s_json": json.dumps(
                [str(item["content_sha256"]) for item in evidence],
                separators=(",", ":"),
            ),
            "amounts_eur_decimal_json": json.dumps(
                [str(item["amount_eur_decimal"]) for item in evidence],
                separators=(",", ":"),
            ),
            "stable_contract_ids_json": json.dumps(
                [str(item["stable_contract_id"] or "") for item in evidence],
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            "lot_ids_json": json.dumps(
                [str(item["lot_id"] or "") for item in evidence],
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            "supplier_identifiers_json": json.dumps(
                [str(item["supplier_identifier"] or "") for item in evidence],
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            "evidence_excerpts_json": json.dumps(
                [
                    (
                        f"Official {item['evidence_basis']} "
                        f"{item['source_record_id']} amount_eur="
                        f"{item['amount_eur_decimal']} supplier_identifier="
                        f"{item['supplier_identifier'] or ''} lot_id="
                        f"{item['lot_id'] or ''}. Pattern review only."
                    )
                    for item in evidence
                ],
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            "task_fingerprint": "",
            **{field: "" for field in REVIEW_FIELDS},
        }
        task["task_fingerprint"] = task_fingerprint(task)
        previous = existing.get(task_id)
        if previous:
            if previous["task_fingerprint"] != task["task_fingerprint"]:
                raise ReviewQueueError(f"immutable review task drifted: {task_id}")
            for field in REVIEW_FIELDS:
                task[field] = previous[field]
        tasks.append(task)
    completed_task_ids = {
        task_id
        for task_id, row in existing.items()
        if any(row[field] for field in REVIEW_FIELDS)
    }
    missing_completed = completed_task_ids - {task["task_id"] for task in tasks}
    if missing_completed:
        raise ReviewQueueError("regeneration would remove completed human work")
    return tasks


def review_slot_complete(row: dict[str, str], slot: int) -> bool:
    values = [
        row[f"reviewer_{slot}_id"],
        row[f"reviewer_{slot}_independence_class"],
        row[f"reviewer_{slot}_decision"],
        row[f"reviewer_{slot}_rationale"],
        row[f"reviewer_{slot}_reviewed_at"],
    ]
    if not any(values):
        return False
    if not all(values):
        raise ReviewQueueError(f"partial reviewer {slot} fields: {row['task_id']}")
    if row[f"reviewer_{slot}_decision"] not in ALLOWED_DECISIONS:
        raise ReviewQueueError(f"invalid reviewer {slot} decision: {row['task_id']}")
    if row[f"reviewer_{slot}_independence_class"] not in ALLOWED_INDEPENDENCE:
        raise ReviewQueueError(f"invalid reviewer {slot} independence: {row['task_id']}")
    datetime.fromisoformat(row[f"reviewer_{slot}_reviewed_at"].replace("Z", "+00:00"))
    return True


def validate_reviews(tasks: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter()
    for row in tasks:
        first = review_slot_complete(row, 1)
        second = review_slot_complete(row, 2)
        if second and not first:
            raise ReviewQueueError(f"reviewer 2 precedes reviewer 1: {row['task_id']}")
        if second:
            if row["reviewer_1_id"] == row["reviewer_2_id"]:
                raise ReviewQueueError(
                    f"dual review requires distinct humans: {row['task_id']}"
                )
            if "independent" not in {
                row["reviewer_1_independence_class"],
                row["reviewer_2_independence_class"],
            }:
                raise ReviewQueueError(
                    f"dual review requires an independent reviewer: {row['task_id']}"
                )
        if first:
            counts["reviewer_1_complete"] += 1
        if second:
            counts["reviewer_2_complete"] += 1
        disagreement = (
            first
            and second
            and row["reviewer_1_decision"] != row["reviewer_2_decision"]
        )
        if disagreement:
            counts["disagreements"] += 1
        adjudication = [row[field] for field in REVIEW_FIELDS[-4:]]
        if any(adjudication):
            if not all(adjudication) or not disagreement:
                raise ReviewQueueError(f"invalid adjudication fields: {row['task_id']}")
            if row["adjudication_decision"] not in ALLOWED_DECISIONS:
                raise ReviewQueueError(f"invalid adjudication decision: {row['task_id']}")
            counts["adjudicated"] += 1
        if first and second and (not disagreement or all(adjudication)):
            counts["dual_review_complete"] += 1
    counts["pending_dual_review"] = len(tasks) - counts["dual_review_complete"]
    return dict(counts)


def main() -> int:
    args = parse_args()
    if args.limit < 0 or not Path(args.db).is_file():
        print("ERROR: DB must exist and limit must be nonnegative")
        return 2
    output_path = Path(args.out)
    try:
        existing = load_existing_reviews(output_path)
        connection = open_db(Path(args.db))
        try:
            tasks = build_tasks(connection, existing=existing, limit=int(args.limit))
        finally:
            connection.close()
        review_counts = validate_reviews(tasks)
        atomic_write(
            output_path,
            lambda handle: (
                (writer := csv.DictWriter(handle, fieldnames=FIELDNAMES)).writeheader(),
                writer.writerows(tasks),
            ),
        )
        report = {
            "schema_version": "procurement_integrity_human_review_queue_v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "complete" if review_counts.get("pending_dual_review", 0) == 0 and tasks else "pending_human_review",
            "detector": {"id": DETECTOR_ID, "version": DETECTOR_VERSION},
            "policy": {
                "official_real_evidence_only": True,
                "public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
                "machine_decisions_invented": False,
                "dual_independent_human_review_required": True,
                "disagreement_adjudication_required": True,
                "review_signal_is_not_corruption_finding": True,
                "public_by_default": False,
                "remote_mutation_performed": False,
            },
            "totals": {
                "tasks": len(tasks),
                "official_evidence_rows": sum(
                    int(task["evidence_count"]) for task in tasks
                ),
                **review_counts,
            },
            "artifact": {
                "path": display_path(output_path),
                "bytes": output_path.stat().st_size,
                "sha256": sha256_file(output_path),
            },
        }
        report_path = Path(args.report_out)
        atomic_write(
            report_path,
            lambda handle: handle.write(
                json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True)
                + "\n"
            ),
        )
    except (ReviewQueueError, OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    if args.enforce and (not tasks or report["status"] not in {"pending_human_review", "complete"}):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
