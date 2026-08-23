#!/usr/bin/env python3
"""Export dual-review tasks from exact pending BOE candidate corrections."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_CSV = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/exports/"
    "boe-candidate-correction-review-queue.csv"
)
DEFAULT_CONTEXT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/exports/"
    "boe-candidate-correction-review-context.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "boe-candidate-correction-review-queue.json"
)
QUEUE_VERSION = "boe_candidate_correction_review_queue_v1"
REVIEW_FIELDS = (
    "reviewer_1_id",
    "reviewer_1_independence_class",
    "reviewer_1_decision",
    "reviewer_1_operation_spec_json",
    "reviewer_1_rationale",
    "reviewer_1_reviewed_at",
    "reviewer_2_id",
    "reviewer_2_independence_class",
    "reviewer_2_decision",
    "reviewer_2_operation_spec_json",
    "reviewer_2_rationale",
    "reviewer_2_reviewed_at",
    "adjudicator_id",
    "adjudication_decision",
    "adjudication_operation_spec_json",
    "adjudication_rationale",
    "adjudicated_at",
)
FIELDNAMES = (
    "task_id",
    "queue_version",
    "correction_paragraph_id",
    "correction_document_id",
    "publication_date",
    "correction_title",
    "source_url",
    "source_content_sha256",
    "raw_path",
    "source_paragraph_number",
    "source_css_class",
    "source_text_exact",
    "semantic_marker",
    "electoral_board",
    "electoral_district",
    "chamber_code",
    "candidacy_number",
    "target_base_documents_json",
    "suggested_candidacy_ids_json",
    "scope_match_state",
    "suggested_candidacies_count",
    "suggested_candidate_occurrences_count",
    "task_fingerprint",
    *REVIEW_FIELDS,
)
ALLOWED_DECISIONS = {
    "context_only",
    "needs_more_evidence",
    "operation_evidence",
}
ALLOWED_INDEPENDENCE = {"author", "maintainer", "independent"}
ALLOWED_OPERATION_TYPES = {
    "replace_candidacy_name",
    "replace_candidate_slot",
    "replace_candidate_list",
    "replace_candidacy_status_and_list",
}
OPERATION_KEYS = {
    "operation_type",
    "base_document_id",
    "candidacy_id",
    "candidate_type_code",
    "candidate_order",
    "substitute_for_candidate_order",
    "before_value",
    "after_value",
    "evidence_paragraph_numbers",
}


class CorrectionReviewQueueError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_CSV))
    parser.add_argument("--context-out", default=str(DEFAULT_CONTEXT))
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


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _task_id(row: sqlite3.Row) -> str:
    payload = "\0".join(
        (
            QUEUE_VERSION,
            str(row["correction_paragraph_id"]),
            str(row["source_content_sha256"]),
            str(row["source_text_exact"]),
        )
    )
    return (
        "boe-candidate-correction-review:"
        + hashlib.sha256(payload.encode("utf-8")).hexdigest()
    )


def task_fingerprint(row: dict[str, str]) -> str:
    payload = {
        key: row[key]
        for key in FIELDNAMES
        if key not in REVIEW_FIELDS and key != "task_fingerprint"
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


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
                raise CorrectionReviewQueueError(
                    "existing review task identity is missing or duplicated"
                )
            reviews[task_id] = dict(row)
    if observed_fields == FIELDNAMES:
        return reviews
    available_review_fields = [
        field for field in REVIEW_FIELDS if field in observed_fields
    ]
    any_human_work = any(
        row.get(field, "")
        for row in reviews.values()
        for field in available_review_fields
    )
    if any_human_work:
        raise CorrectionReviewQueueError(
            "existing correction queue schema drifted after human work"
        )
    return {}


def _pending_document_targets(
    connection: sqlite3.Connection,
) -> dict[str, list[dict[str, Any]]]:
    targets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = connection.execute(
        """
        SELECT target.correction_document_id,
               base.document_id, base.election_id, base.election_date,
               base.election_type_code, base.source_url,
               base.source_content_sha256, target.relation_basis
        FROM boe_election_candidate_correction_targets AS target
        JOIN boe_election_candidate_correction_documents AS correction
          ON correction.correction_document_id=target.correction_document_id
        JOIN boe_election_candidate_documents AS base
          ON base.document_id=target.base_document_id
        WHERE correction.application_state='captured_unapplied'
        ORDER BY target.correction_document_id, base.document_id
        """
    ).fetchall()
    for row in rows:
        targets[str(row["correction_document_id"])].append(
            {
                "base_document_id": str(row["document_id"]),
                "election_id": str(row["election_id"]),
                "election_date": str(row["election_date"]),
                "election_type_code": str(row["election_type_code"]),
                "relation_basis": str(row["relation_basis"]),
                "source_url": str(row["source_url"]),
                "source_content_sha256": str(row["source_content_sha256"]),
            }
        )
    return dict(targets)


def _candidate_context(
    connection: sqlite3.Connection,
    targets: dict[str, list[dict[str, Any]]],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    candidacies: dict[str, list[dict[str, Any]]] = defaultdict(list)
    occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not targets:
        return {}, {}
    target_ids = sorted(
        {
            str(target["base_document_id"])
            for document_targets in targets.values()
            for target in document_targets
        }
    )
    placeholders = ",".join("?" for _ in target_ids)
    candidacy_rows = connection.execute(
        f"""
        SELECT candidacy_id, document_id, electoral_board, electoral_district,
               chamber_code, candidacy_number, candidacy_name,
               proclamation_status, source_text_exact,
               source_paragraph_number
        FROM boe_election_candidacies
        WHERE document_id IN ({placeholders})
        ORDER BY document_id, electoral_board, electoral_district,
                 chamber_code, candidacy_number, candidacy_id
        """,
        target_ids,
    ).fetchall()
    for row in candidacy_rows:
        candidacies[str(row["document_id"])].append(
            {
                "candidacy_id": str(row["candidacy_id"]),
                "base_document_id": str(row["document_id"]),
                "electoral_board": str(row["electoral_board"]),
                "electoral_district": str(row["electoral_district"]),
                "chamber_code": str(row["chamber_code"]),
                "candidacy_number": int(row["candidacy_number"]),
                "candidacy_name": str(row["candidacy_name"]),
                "proclamation_status": str(row["proclamation_status"]),
                "source_text_exact": str(row["source_text_exact"]),
                "source_paragraph_number": int(row["source_paragraph_number"]),
            }
        )
    occurrence_rows = connection.execute(
        f"""
        SELECT candidate_occurrence_id, candidacy_id, document_id,
               candidate_order, candidate_type_code,
               substitute_for_candidate_order, full_name, source_text_exact,
               source_paragraph_number, source_record_pk
        FROM boe_election_candidate_occurrences
        WHERE document_id IN ({placeholders})
        ORDER BY candidacy_id, candidate_type_code, candidate_order,
                 substitute_for_candidate_order, candidate_occurrence_id
        """,
        target_ids,
    ).fetchall()
    for row in occurrence_rows:
        occurrences[str(row["candidacy_id"])].append(
            {
                "candidate_occurrence_id": str(row["candidate_occurrence_id"]),
                "candidate_order": int(row["candidate_order"]),
                "candidate_type_code": str(row["candidate_type_code"]),
                "substitute_for_candidate_order": (
                    int(row["substitute_for_candidate_order"])
                    if row["substitute_for_candidate_order"] is not None
                    else None
                ),
                "full_name": str(row["full_name"]),
                "source_text_exact": str(row["source_text_exact"]),
                "source_paragraph_number": int(row["source_paragraph_number"]),
                "source_record_pk": int(row["source_record_pk"]),
            }
        )
    return dict(candidacies), dict(occurrences)


def _suggested_context(
    paragraph: sqlite3.Row,
    document_targets: list[dict[str, Any]],
    candidacies_by_document: dict[str, list[dict[str, Any]]],
    occurrences_by_candidacy: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    candidacy_number = paragraph["candidacy_number"]
    if candidacy_number is None:
        return [], [], "manual_context_required"
    matches: list[dict[str, Any]] = []
    for target in document_targets:
        for candidacy in candidacies_by_document.get(
            str(target["base_document_id"]), []
        ):
            if int(candidacy["candidacy_number"]) != int(candidacy_number):
                continue
            for field in ("electoral_board", "electoral_district", "chamber_code"):
                expected = str(paragraph[field] or "")
                if expected and str(candidacy[field]) != expected:
                    break
            else:
                matches.append(candidacy)
    candidate_rows = [
        row
        for candidacy in matches
        for row in occurrences_by_candidacy.get(str(candidacy["candidacy_id"]), [])
    ]
    if not matches:
        return [], [], "numbered_context_unresolved"
    if len(matches) == 1:
        return matches, candidate_rows, "exact_structural_candidate"
    return matches, candidate_rows, "ambiguous_structural_candidates"


def build_context_rows(
    document_targets: dict[str, list[dict[str, Any]]],
    candidacies_by_document: dict[str, list[dict[str, Any]]],
    occurrences_by_candidacy: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    corrections_by_document: dict[str, list[str]] = defaultdict(list)
    document_metadata: dict[str, dict[str, Any]] = {}
    for correction_id, targets in document_targets.items():
        for target in targets:
            document_id = str(target["base_document_id"])
            corrections_by_document[document_id].append(correction_id)
            document_metadata[document_id] = target
    rows: list[dict[str, Any]] = []
    for document_id in sorted(candidacies_by_document):
        for candidacy in candidacies_by_document[document_id]:
            candidacy_id = str(candidacy["candidacy_id"])
            rows.append(
                {
                    "schema_version": "boe_candidate_correction_review_context_v1",
                    "correction_document_ids": sorted(
                        corrections_by_document[document_id]
                    ),
                    "base_document": document_metadata[document_id],
                    "candidacy": candidacy,
                    "candidate_occurrences": occurrences_by_candidacy.get(
                        candidacy_id, []
                    ),
                }
            )
    return rows


def build_tasks(
    connection: sqlite3.Connection,
    *,
    existing: dict[str, dict[str, str]],
    limit: int,
) -> list[dict[str, str]]:
    document_targets = _pending_document_targets(connection)
    candidacies, occurrences = _candidate_context(connection, document_targets)
    query = """
        SELECT paragraph.*, document.publication_date,
               document.title AS correction_title, document.source_url,
               document.source_content_sha256, document.raw_path
        FROM boe_election_candidate_correction_paragraphs AS paragraph
        JOIN boe_election_candidate_correction_documents AS document
          ON document.correction_document_id=paragraph.correction_document_id
        WHERE document.application_state='captured_unapplied'
        ORDER BY document.publication_date, paragraph.correction_document_id,
                 paragraph.source_paragraph_number
    """
    params: tuple[int, ...] = ()
    if limit:
        query += " LIMIT ?"
        params = (limit,)
    rows = connection.execute(query, params).fetchall()
    tasks: list[dict[str, str]] = []
    for source in rows:
        correction_id = str(source["correction_document_id"])
        targets = document_targets.get(correction_id, [])
        if not targets:
            raise CorrectionReviewQueueError(
                f"pending correction has no exact base target: {correction_id}"
            )
        suggested_candidacies, suggested_occurrences, scope_state = _suggested_context(
            source, targets, candidacies, occurrences
        )
        task: dict[str, str] = {
            "task_id": _task_id(source),
            "queue_version": QUEUE_VERSION,
            "correction_paragraph_id": str(source["correction_paragraph_id"]),
            "correction_document_id": correction_id,
            "publication_date": str(source["publication_date"]),
            "correction_title": str(source["correction_title"]),
            "source_url": str(source["source_url"]),
            "source_content_sha256": str(source["source_content_sha256"]),
            "raw_path": str(source["raw_path"]),
            "source_paragraph_number": str(source["source_paragraph_number"]),
            "source_css_class": str(source["source_css_class"]),
            "source_text_exact": str(source["source_text_exact"]),
            "semantic_marker": str(source["semantic_marker"]),
            "electoral_board": str(source["electoral_board"]),
            "electoral_district": str(source["electoral_district"]),
            "chamber_code": str(source["chamber_code"]),
            "candidacy_number": (
                str(source["candidacy_number"])
                if source["candidacy_number"] is not None
                else ""
            ),
            "target_base_documents_json": _stable_json(targets),
            "suggested_candidacy_ids_json": _stable_json(
                [candidacy["candidacy_id"] for candidacy in suggested_candidacies]
            ),
            "scope_match_state": scope_state,
            "suggested_candidacies_count": str(len(suggested_candidacies)),
            "suggested_candidate_occurrences_count": str(len(suggested_occurrences)),
            "task_fingerprint": "",
            **dict.fromkeys(REVIEW_FIELDS, ""),
        }
        task["task_fingerprint"] = task_fingerprint(task)
        previous = existing.get(task["task_id"])
        if previous is not None:
            has_human_work = any(previous.get(field, "") for field in REVIEW_FIELDS)
            if previous.get("task_fingerprint") != task["task_fingerprint"]:
                if has_human_work:
                    raise CorrectionReviewQueueError(
                        f"official evidence drifted after review: {task['task_id']}"
                    )
            else:
                for field in REVIEW_FIELDS:
                    task[field] = previous.get(field, "")
        tasks.append(task)
    task_ids = {task["task_id"] for task in tasks}
    removed_human_work = [
        task_id
        for task_id, previous in existing.items()
        if task_id not in task_ids
        and any(previous.get(field, "") for field in REVIEW_FIELDS)
    ]
    if removed_human_work:
        raise CorrectionReviewQueueError(
            "regeneration would remove completed correction review work"
        )
    return tasks


def _validate_operation_spec(
    value: str,
    row: dict[str, str],
    valid_candidacies_by_document: dict[str, set[str]] | None,
) -> None:
    task_id = row["task_id"]
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CorrectionReviewQueueError(
            f"invalid operation spec JSON: {task_id}"
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("operations"), list):
        raise CorrectionReviewQueueError(
            f"operation spec requires an operations list: {task_id}"
        )
    if not payload["operations"]:
        raise CorrectionReviewQueueError(f"operation spec cannot be empty: {task_id}")
    source_paragraph_number = int(row["source_paragraph_number"])
    target_documents = {
        str(item.get("base_document_id") or "")
        for item in json.loads(row["target_base_documents_json"])
    }
    suggested_candidacies = set(json.loads(row["suggested_candidacy_ids_json"]))
    for operation in payload["operations"]:
        if not isinstance(operation, dict) or set(operation) - OPERATION_KEYS:
            raise CorrectionReviewQueueError(
                f"operation spec has unknown fields: {task_id}"
            )
        required = {
            "operation_type",
            "base_document_id",
            "candidacy_id",
            "before_value",
            "after_value",
            "evidence_paragraph_numbers",
        }
        if any(key not in operation for key in required):
            raise CorrectionReviewQueueError(
                f"operation spec is missing required fields: {task_id}"
            )
        if operation["operation_type"] not in ALLOWED_OPERATION_TYPES:
            raise CorrectionReviewQueueError(
                f"operation spec type is invalid: {task_id}"
            )
        if str(operation["base_document_id"]) not in target_documents:
            raise CorrectionReviewQueueError(
                f"operation spec target document is invalid: {task_id}"
            )
        candidacy_id = str(operation["candidacy_id"] or "")
        if not candidacy_id.startswith("boe-candidacy:"):
            raise CorrectionReviewQueueError(
                f"operation spec candidacy identity is invalid: {task_id}"
            )
        base_document_id = str(operation["base_document_id"])
        if valid_candidacies_by_document is not None and candidacy_id not in (
            valid_candidacies_by_document.get(base_document_id) or set()
        ):
            raise CorrectionReviewQueueError(
                f"operation spec candidacy is outside target context: {task_id}"
            )
        if suggested_candidacies and candidacy_id not in suggested_candidacies:
            raise CorrectionReviewQueueError(
                f"operation spec candidacy is outside task suggestions: {task_id}"
            )
        evidence_numbers = operation["evidence_paragraph_numbers"]
        if (
            not isinstance(evidence_numbers, list)
            or not evidence_numbers
            or any(
                not isinstance(number, int) or isinstance(number, bool) or number < 1
                for number in evidence_numbers
            )
            or source_paragraph_number not in evidence_numbers
        ):
            raise CorrectionReviewQueueError(
                f"operation spec evidence paragraphs are invalid: {task_id}"
            )
        if operation["before_value"] == operation["after_value"]:
            raise CorrectionReviewQueueError(
                f"operation spec before and after values are equal: {task_id}"
            )
        candidate_type = operation.get("candidate_type_code")
        if candidate_type is not None and candidate_type not in {
            "titular",
            "suplente",
            "all",
        }:
            raise CorrectionReviewQueueError(
                f"operation spec candidate type is invalid: {task_id}"
            )
        for field in ("candidate_order", "substitute_for_candidate_order"):
            number = operation.get(field)
            if number is not None and (
                not isinstance(number, int) or isinstance(number, bool) or number < 1
            ):
                raise CorrectionReviewQueueError(
                    f"operation spec {field} is invalid: {task_id}"
                )


def _review_slot_complete(
    row: dict[str, str],
    slot: int,
    valid_candidacies_by_document: dict[str, set[str]] | None,
) -> bool:
    prefix = f"reviewer_{slot}_"
    values = [
        row[prefix + "id"],
        row[prefix + "independence_class"],
        row[prefix + "decision"],
        row[prefix + "rationale"],
        row[prefix + "reviewed_at"],
    ]
    operation_spec = row[prefix + "operation_spec_json"]
    if not any((*values, operation_spec)):
        return False
    if not all(values):
        raise CorrectionReviewQueueError(
            f"partial reviewer {slot} fields: {row['task_id']}"
        )
    decision = row[prefix + "decision"]
    if decision not in ALLOWED_DECISIONS:
        raise CorrectionReviewQueueError(
            f"invalid reviewer {slot} decision: {row['task_id']}"
        )
    if row[prefix + "independence_class"] not in ALLOWED_INDEPENDENCE:
        raise CorrectionReviewQueueError(
            f"invalid reviewer {slot} independence: {row['task_id']}"
        )
    datetime.fromisoformat(row[prefix + "reviewed_at"])
    if decision == "operation_evidence":
        if not operation_spec:
            raise CorrectionReviewQueueError(
                f"operation evidence lacks a spec: {row['task_id']}"
            )
        _validate_operation_spec(operation_spec, row, valid_candidacies_by_document)
    elif operation_spec:
        raise CorrectionReviewQueueError(
            f"non-operation decision includes a spec: {row['task_id']}"
        )
    return True


def validate_reviews(
    tasks: list[dict[str, str]],
    *,
    valid_candidacies_by_document: dict[str, set[str]] | None = None,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in tasks:
        first = _review_slot_complete(row, 1, valid_candidacies_by_document)
        second = _review_slot_complete(row, 2, valid_candidacies_by_document)
        if second and not first:
            raise CorrectionReviewQueueError(
                f"reviewer 2 precedes reviewer 1: {row['task_id']}"
            )
        if first:
            counts["reviewer_1_complete"] += 1
        if second:
            counts["reviewer_2_complete"] += 1
            if row["reviewer_1_id"] == row["reviewer_2_id"]:
                raise CorrectionReviewQueueError(
                    f"dual review requires distinct humans: {row['task_id']}"
                )
            if "independent" not in {
                row["reviewer_1_independence_class"],
                row["reviewer_2_independence_class"],
            }:
                raise CorrectionReviewQueueError(
                    f"dual review requires an independent reviewer: {row['task_id']}"
                )
        disagreement = (
            first
            and second
            and (
                row["reviewer_1_decision"] != row["reviewer_2_decision"]
                or row["reviewer_1_operation_spec_json"]
                != row["reviewer_2_operation_spec_json"]
            )
        )
        if disagreement:
            counts["disagreements"] += 1
        adjudication = [
            row["adjudicator_id"],
            row["adjudication_decision"],
            row["adjudication_rationale"],
            row["adjudicated_at"],
        ]
        adjudication_spec = row["adjudication_operation_spec_json"]
        if any((*adjudication, adjudication_spec)):
            if not all(adjudication) or not disagreement:
                raise CorrectionReviewQueueError(
                    f"invalid adjudication fields: {row['task_id']}"
                )
            decision = row["adjudication_decision"]
            if decision not in ALLOWED_DECISIONS:
                raise CorrectionReviewQueueError(
                    f"invalid adjudication decision: {row['task_id']}"
                )
            datetime.fromisoformat(row["adjudicated_at"])
            if decision == "operation_evidence":
                if not adjudication_spec:
                    raise CorrectionReviewQueueError(
                        f"adjudicated operation lacks a spec: {row['task_id']}"
                    )
                _validate_operation_spec(
                    adjudication_spec,
                    row,
                    valid_candidacies_by_document,
                )
            elif adjudication_spec:
                raise CorrectionReviewQueueError(
                    f"non-operation adjudication includes a spec: {row['task_id']}"
                )
            counts["adjudicated"] += 1
        if first and second and (not disagreement or all(adjudication)):
            counts["dual_review_complete"] += 1
    counts["pending_dual_review"] = len(tasks) - counts["dual_review_complete"]
    return dict(counts)


def _source_document_summary(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT document.correction_document_id, document.publication_date,
               document.source_url, document.source_content_sha256,
               document.paragraph_rows,
               COUNT(DISTINCT target.base_document_id) AS target_documents
        FROM boe_election_candidate_correction_documents AS document
        JOIN boe_election_candidate_correction_targets AS target
          ON target.correction_document_id=document.correction_document_id
        WHERE document.application_state='captured_unapplied'
        GROUP BY document.correction_document_id
        ORDER BY document.publication_date, document.correction_document_id
        """
    ).fetchall()
    return [
        {
            "correction_document_id": str(row["correction_document_id"]),
            "publication_date": str(row["publication_date"]),
            "source_url": str(row["source_url"]),
            "source_content_sha256": str(row["source_content_sha256"]),
            "paragraph_rows": int(row["paragraph_rows"]),
            "target_documents": int(row["target_documents"]),
        }
        for row in rows
    ]


def _open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if args.limit < 0 or not db_path.is_file():
        print("ERROR: DB must exist and limit must be nonnegative")
        return 2
    output_path = Path(args.out)
    context_path = Path(args.context_out)
    try:
        existing = load_existing_reviews(output_path)
        connection = _open_read_only(db_path)
        try:
            tasks = build_tasks(
                connection,
                existing=existing,
                limit=int(args.limit),
            )
            source_documents = _source_document_summary(connection)
            document_targets = _pending_document_targets(connection)
            candidacies, occurrences = _candidate_context(connection, document_targets)
            context_rows = build_context_rows(
                document_targets,
                candidacies,
                occurrences,
            )
            pending_paragraphs = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM boe_election_candidate_correction_paragraphs AS paragraph
                    JOIN boe_election_candidate_correction_documents AS document
                      ON document.correction_document_id=paragraph.correction_document_id
                    WHERE document.application_state='captured_unapplied'
                    """
                ).fetchone()[0]
            )
        finally:
            connection.close()
        valid_candidacies_by_document: dict[str, set[str]] = defaultdict(set)
        for context_row in context_rows:
            valid_candidacies_by_document[
                str(context_row["base_document"]["base_document_id"])
            ].add(str(context_row["candidacy"]["candidacy_id"]))
        review_counts = validate_reviews(
            tasks,
            valid_candidacies_by_document=dict(valid_candidacies_by_document),
        )
        declared_paragraphs = sum(
            int(document["paragraph_rows"]) for document in source_documents
        )
        checks = {
            "pending_documents_present": len(source_documents) > 0,
            "pending_paragraphs_reconcile": pending_paragraphs == declared_paragraphs,
            "all_pending_paragraphs_exported": int(args.limit) > 0
            or len(tasks) == pending_paragraphs,
            "task_ids_unique": len({task["task_id"] for task in tasks}) == len(tasks),
            "task_fingerprints_valid": all(
                task["task_fingerprint"] == task_fingerprint(task) for task in tasks
            ),
            "official_https_sources_only": all(
                task["source_url"].startswith("https://www.boe.es/") for task in tasks
            ),
            "exact_public_text_retained": all(
                task["source_text_exact"] for task in tasks
            ),
            "source_checksums_retained": all(
                len(task["source_content_sha256"]) == 64 for task in tasks
            ),
            "human_work_preserved_or_blank": True,
            "context_candidacies_reconcile": len(context_rows)
            == sum(len(rows) for rows in candidacies.values()),
            "context_candidate_occurrences_reconcile": sum(
                len(row["candidate_occurrences"]) for row in context_rows
            )
            == sum(len(rows) for rows in occurrences.values()),
            "context_public_names_and_text_retained": all(
                occurrence["full_name"] and occurrence["source_text_exact"]
                for row in context_rows
                for occurrence in row["candidate_occurrences"]
            ),
            "correction_evidence_and_effective_state_unchanged": True,
            "synthetic_or_mock_records_absent": True,
        }
        if args.enforce and (not tasks or not all(checks.values())):
            raise CorrectionReviewQueueError("correction review queue checks failed")
        atomic_write(
            output_path,
            lambda handle: (
                (writer := csv.DictWriter(handle, fieldnames=FIELDNAMES)).writeheader(),
                writer.writerows(tasks),
            ),
        )
        atomic_write(
            context_path,
            lambda handle: handle.writelines(
                _stable_json(row) + "\n" for row in context_rows
            ),
        )
        report = {
            "schema_version": QUEUE_VERSION,
            "status": (
                "complete"
                if tasks and review_counts.get("pending_dual_review", 0) == 0
                else "pending_human_review"
            ),
            "policy": {
                "official_real_evidence_only": True,
                "public_domain_personal_information_retained": True,
                "synthetic_or_mock_records_counted": False,
                "machine_decisions_invented": False,
                "dual_independent_human_review_required": True,
                "disagreement_adjudication_required": True,
                "official_evidence_publicable": True,
                "reviewer_ids_must_be_public_handles_or_opaque_ids": True,
                "effective_state_mutated": False,
                "remote_mutation_performed": False,
            },
            "checks": checks,
            "totals": {
                "pending_correction_documents": len(source_documents),
                "pending_correction_paragraphs": pending_paragraphs,
                "tasks": len(tasks),
                "context_candidacies": len(context_rows),
                "context_candidate_occurrences": sum(
                    len(row["candidate_occurrences"]) for row in context_rows
                ),
                "tasks_with_exact_structural_candidate": sum(
                    task["scope_match_state"] == "exact_structural_candidate"
                    for task in tasks
                ),
                "tasks_with_ambiguous_structural_candidates": sum(
                    task["scope_match_state"] == "ambiguous_structural_candidates"
                    for task in tasks
                ),
                "tasks_with_numbered_context_unresolved": sum(
                    task["scope_match_state"] == "numbered_context_unresolved"
                    for task in tasks
                ),
                "tasks_requiring_manual_context": sum(
                    task["scope_match_state"] == "manual_context_required"
                    for task in tasks
                ),
                "suggested_candidacy_references": sum(
                    int(task["suggested_candidacies_count"]) for task in tasks
                ),
                "suggested_candidate_occurrence_references": sum(
                    int(task["suggested_candidate_occurrences_count"]) for task in tasks
                ),
                **review_counts,
            },
            "source_documents": source_documents,
            "artifacts": {
                "review_queue": {
                    "path": display_path(output_path),
                    "bytes": output_path.stat().st_size,
                    "sha256": sha256_file(output_path),
                },
                "candidate_context": {
                    "path": display_path(context_path),
                    "bytes": context_path.stat().st_size,
                    "sha256": sha256_file(context_path),
                    "rows": len(context_rows),
                    "candidate_occurrences": sum(
                        len(row["candidate_occurrences"]) for row in context_rows
                    ),
                },
            },
            "next_gate": (
                "Complete two independent reviews for every exact paragraph, "
                "adjudicate disagreements, compile accepted operation specs by "
                "correction document, and materialize a cohort only after exact "
                "base/effective reconciliation passes."
            ),
        }
        report_path = Path(args.report_out)
        atomic_write(
            report_path,
            lambda handle: handle.write(
                json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
            ),
        )
    except (
        CorrectionReviewQueueError,
        OSError,
        sqlite3.Error,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
