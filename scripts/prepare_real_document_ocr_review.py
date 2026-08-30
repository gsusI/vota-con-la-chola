#!/usr/bin/env python3
"""Prepare a stratified human review packet from real OCR page outputs."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    iter_generation_rows,
)

DEFAULT_RAW_ROOT = Path("etl/data/raw")
DEFAULT_OCR_ROOT = Path("etl/data/derived/real-document-page-ocr-v2")
DEFAULT_OCR_MANIFEST = Path(
    "etl/data/published/real-document-page-ocr-manifest-latest.jsonl"
)
DEFAULT_QUEUE = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/exports/"
    "real-document-page-ocr-human-review.csv"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-page-ocr-human-review-queue.json"
)
REVIEW_FIELDS = ("review_decision", "review_notes", "reviewer_id", "reviewed_at")


class OcrReviewQueueError(RuntimeError):
    """Raised when a real OCR review queue cannot be built exactly."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.name


def safe_child(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise OcrReviewQueueError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise OcrReviewQueueError(f"path escapes root: {relative}") from exc
    return candidate


def sha256_path(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assignment_sha256(path: Path) -> str:
    """Hash immutable task fields while permitting audited human review fields."""
    digest = hashlib.sha256()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(REVIEW_FIELDS).issubset(reader.fieldnames):
            raise OcrReviewQueueError("review queue fields are incomplete")
        assignment_fields = [
            field for field in reader.fieldnames if field not in REVIEW_FIELDS
        ]
        for row in reader:
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


def refuse_review_overwrite(path: Path) -> None:
    if not path.is_file():
        return
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(REVIEW_FIELDS).issubset(reader.fieldnames):
            raise OcrReviewQueueError("existing review queue fields are incomplete")
        for row in reader:
            if any((row.get(field) or "").strip() for field in REVIEW_FIELDS):
                raise OcrReviewQueueError(
                    "refusing to overwrite completed human review fields; preserve "
                    "the reviewed CSV and validate it instead"
                )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--ocr-root", default=str(DEFAULT_OCR_ROOT))
    parser.add_argument("--ocr-manifest", default=str(DEFAULT_OCR_MANIFEST))
    parser.add_argument("--queue-out", default=str(DEFAULT_QUEUE))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--sample-pages", type=int, default=40)
    parser.add_argument("--pdftotext-timeout", type=float, default=120.0)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    try:
        yield from iter_generation_rows(
            path,
            dataset="page_ocr",
            row_schema_version="real_document_page_ocr_manifest_row_v1",
        )
    except GenerationManifestError as exc:
        raise OcrReviewQueueError(
            f"invalid OCR manifest {display_path(path)}: {exc}"
        ) from exc


def candidate_key(row: Mapping[str, Any]) -> tuple[str, int]:
    return str(row["document_sha256"]), int(row["page_number"])


def stratum_key(row: Mapping[str, Any]) -> tuple[str, str, str, bool]:
    return (
        str(row["source_group"]),
        str(row["routing_reason"]),
        str(row["ocr_status"]),
        bool(row["improved_over_native"]),
    )


def select_review_rows(
    rows: list[dict[str, Any]], sample_pages: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if sample_pages < 1 or sample_pages > len(rows):
        raise OcrReviewQueueError("sample-pages is outside the real candidate range")
    ordered = sorted(rows, key=candidate_key)
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    reasons: Counter[str] = Counter()

    def add(row: dict[str, Any], reason: str) -> None:
        identity = candidate_key(row)
        if identity in seen or len(selected) >= sample_pages:
            return
        selected.append(row)
        seen.add(identity)
        reasons[reason] += 1

    for row in ordered:
        if row["ocr_status"] == "ocr_no_text":
            add(row, "all_ocr_no_text")
    for row in ordered:
        if row["improved_over_native"] is True:
            add(row, "all_material_gain")

    source_reason_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(
        list
    )
    for row in ordered:
        source_reason_groups[
            (str(row["source_group"]), str(row["routing_reason"]))
        ].append(row)
    for group in sorted(source_reason_groups):
        group_selected = sum(
            (
                str(row["source_group"]),
                str(row["routing_reason"]),
            )
            == group
            for row in selected
        )
        for row in source_reason_groups[group]:
            if group_selected >= 5 or len(selected) >= sample_pages:
                break
            before = len(selected)
            add(row, "source_reason_minimum")
            if len(selected) > before:
                group_selected += 1

    strata: dict[tuple[str, str, str, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        if candidate_key(row) not in seen:
            strata[stratum_key(row)].append(row)
    while len(selected) < sample_pages:
        progressed = False
        for stratum in sorted(strata, key=lambda value: tuple(map(str, value))):
            bucket = strata[stratum]
            while bucket and candidate_key(bucket[0]) in seen:
                bucket.pop(0)
            if not bucket:
                continue
            add(bucket.pop(0), "stratified_round_robin_fill")
            progressed = True
            if len(selected) >= sample_pages:
                break
        if not progressed:
            break
    if len(selected) != sample_pages:
        raise OcrReviewQueueError(
            f"could not fill review sample: {len(selected)} != {sample_pages}"
        )
    return selected, dict(sorted(reasons.items()))


def read_ocr_text(row: Mapping[str, Any], ocr_root: Path) -> str:
    if row["ocr_status"] == "ocr_no_text":
        return ""
    relative = str(row.get("ocr_text_cas_path") or "")
    path = safe_child(ocr_root, relative)
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        text = handle.read()
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != row.get("ocr_text_sha256"):
        raise OcrReviewQueueError(f"OCR CAS checksum drift: {relative}")
    return text


def extract_native_page_text(
    row: Mapping[str, Any],
    *,
    raw_root: Path,
    pdftotext: str,
    timeout: float,
) -> str:
    page_number = int(row["page_number"])
    pdf_path = safe_child(raw_root, str(row["representative_path"]))
    completed = subprocess.run(
        [
            pdftotext,
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-enc",
            "UTF-8",
            str(pdf_path),
            "-",
        ],
        check=False,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise OcrReviewQueueError(
            f"pdftotext failed for {row['representative_path']}:{page_number}"
        )
    return " ".join(completed.stdout.decode("utf-8", errors="replace").split())


def write_queue(
    selected: list[dict[str, Any]],
    *,
    raw_root: Path,
    ocr_root: Path,
    queue_out: Path,
    pdftotext: str,
    timeout: float,
) -> dict[str, Any]:
    queue_out.parent.mkdir(parents=True, exist_ok=True)
    temp_path = queue_out.with_name(f".{queue_out.name}.{uuid.uuid4().hex}.tmp")
    fieldnames = [
        "review_id",
        "source_group",
        "document_sha256",
        "document_path",
        "page_number",
        "routing_reason",
        "native_inventory_non_whitespace_chars",
        "native_page_text",
        "ocr_status",
        "ocr_text_chars",
        "ocr_page_text",
        "improved_over_native_by_50_chars",
        "review_decision",
        "review_notes",
        "reviewer_id",
        "reviewed_at",
    ]
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for index, row in enumerate(selected, start=1):
                writer.writerow(
                    {
                        "review_id": f"ocr-review-{index:04d}",
                        "source_group": row["source_group"],
                        "document_sha256": row["document_sha256"],
                        "document_path": row["representative_path"],
                        "page_number": row["page_number"],
                        "routing_reason": row["routing_reason"],
                        "native_inventory_non_whitespace_chars": row[
                            "native_text_chars"
                        ],
                        "native_page_text": extract_native_page_text(
                            row,
                            raw_root=raw_root,
                            pdftotext=pdftotext,
                            timeout=timeout,
                        ),
                        "ocr_status": row["ocr_status"],
                        "ocr_text_chars": row["ocr_text_chars"],
                        "ocr_page_text": read_ocr_text(row, ocr_root),
                        "improved_over_native_by_50_chars": (
                            "1" if row["improved_over_native"] else "0"
                        ),
                        "review_decision": "",
                        "review_notes": "",
                        "reviewer_id": "",
                        "reviewed_at": "",
                    }
                )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, queue_out)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return {
        "path": display_path(queue_out),
        "rows": len(selected),
        "bytes": queue_out.stat().st_size,
        "sha256": sha256_path(queue_out),
        "assignment_sha256": assignment_sha256(queue_out),
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if int(args.sample_pages) < 1 or float(args.pdftotext_timeout) <= 0:
        print("ERROR: sample-pages and timeout must be positive")
        return 2
    raw_root = Path(args.raw_root)
    ocr_root = Path(args.ocr_root)
    ocr_manifest = Path(args.ocr_manifest)
    queue_out = Path(args.queue_out)
    report_out = Path(args.report_out)
    pdftotext = shutil.which("pdftotext")
    if not raw_root.is_dir() or not ocr_root.is_dir() or not pdftotext:
        print("ERROR: raw root, OCR root, and pdftotext are required")
        return 2
    try:
        refuse_review_overwrite(queue_out)
        rows = list(iter_jsonl(ocr_manifest))
        for row in rows:
            if (
                row.get("schema_version") != "real_document_page_ocr_manifest_row_v1"
                or row.get("synthetic_or_mock") is not False
                or row.get("official_public_domain_personal_information_retained")
                is not True
                or row.get("additive_to_native_text") is not True
                or row.get("work_state") != "succeeded"
            ):
                raise OcrReviewQueueError("unsafe OCR manifest row")
        selected, selection_reasons = select_review_rows(rows, int(args.sample_pages))
        queue = write_queue(
            selected,
            raw_root=raw_root,
            ocr_root=ocr_root,
            queue_out=queue_out,
            pdftotext=pdftotext,
            timeout=float(args.pdftotext_timeout),
        )
        strata_all = Counter(stratum_key(row) for row in rows)
        strata_selected = Counter(stratum_key(row) for row in selected)
        checks = {
            "queue_has_requested_real_rows": queue["rows"] == int(args.sample_pages),
            "all_ocr_no_text_pages_selected": sum(
                row["ocr_status"] == "ocr_no_text" for row in selected
            )
            == sum(row["ocr_status"] == "ocr_no_text" for row in rows),
            "all_material_gain_pages_selected": sum(
                row["improved_over_native"] is True for row in selected
            )
            == sum(row["improved_over_native"] is True for row in rows),
            "both_source_groups_selected": len(
                {row["source_group"] for row in selected}
            )
            == len({row["source_group"] for row in rows}),
            "both_routing_reasons_selected": len(
                {row["routing_reason"] for row in selected}
            )
            == len({row["routing_reason"] for row in rows}),
            "human_review_fields_are_blank": True,
            "no_synthetic_or_mock_records": True,
            "official_public_domain_personal_information_retained": True,
        }
        report = {
            "schema_version": "real_document_page_ocr_human_review_queue_v1",
            "generated_at": utc_now(),
            "status": "ready_for_human_review" if all(checks.values()) else "failed",
            "policy": {
                "official_real_documents_only": True,
                "synthetic_or_mock_records_counted": False,
                "official_public_domain_personal_information_retained": True,
                "review_labels_invented": False,
                "machine_generated_review_decisions": False,
            },
            "input": {
                "path": display_path(ocr_manifest),
                "rows": len(rows),
                "bytes": ocr_manifest.stat().st_size,
                "sha256": sha256_path(ocr_manifest),
            },
            "queue": queue,
            "selection": {
                "requested_pages": int(args.sample_pages),
                "selected_pages": len(selected),
                "algorithm": (
                    "all OCR-no-text pages, all >=50-character-gain pages, at least "
                    "five per source/reason where available, then deterministic "
                    "round-robin across remaining strata"
                ),
                "selection_reason_counts": selection_reasons,
                "all_strata": {
                    "|".join(map(str, key)): value
                    for key, value in sorted(
                        strata_all.items(), key=lambda item: tuple(map(str, item[0]))
                    )
                },
                "selected_strata": {
                    "|".join(map(str, key)): value
                    for key, value in sorted(
                        strata_selected.items(),
                        key=lambda item: tuple(map(str, item[0])),
                    )
                },
            },
            "review": {
                "human_reviews_completed": 0,
                "human_reviews_pending": len(selected),
                "allowed_decisions": [
                    "ocr_better",
                    "native_better",
                    "equivalent",
                    "both_unusable",
                ],
                "promotion_ready": False,
            },
            "checks": checks,
            "next_action": (
                "Have identified reviewers complete all 40 decisions and notes, "
                "then compute accuracy and usability by source and routing reason."
            ),
        }
        write_json_atomic(report_out, report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        if args.enforce and report["status"] != "ready_for_human_review":
            return 1
        return 0
    except (
        OcrReviewQueueError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
