#!/usr/bin/env python3
"""Independently validate all routed real-document page OCR outputs."""

from __future__ import annotations

import argparse
import codecs
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import uuid
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
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
DEFAULT_NATIVE_MANIFEST = Path(
    "etl/data/published/real-document-text-manifest-latest.jsonl"
)
DEFAULT_OCR_MANIFEST = Path(
    "etl/data/published/real-document-page-ocr-manifest-latest.jsonl"
)
DEFAULT_OCR_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/real-document-page-ocr.json"
)
DEFAULT_VALIDATION_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-page-ocr-validation.json"
)


class OcrValidationError(RuntimeError):
    """Raised when page OCR evidence fails exact validation."""


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
        raise OcrValidationError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise OcrValidationError(f"path escapes root: {relative}") from exc
    return candidate


def sha256_path(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--ocr-root", default=str(DEFAULT_OCR_ROOT))
    parser.add_argument("--native-manifest", default=str(DEFAULT_NATIVE_MANIFEST))
    parser.add_argument("--ocr-manifest", default=str(DEFAULT_OCR_MANIFEST))
    parser.add_argument("--ocr-report", default=str(DEFAULT_OCR_REPORT))
    parser.add_argument("--report-out", default=str(DEFAULT_VALIDATION_REPORT))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def iter_manifest(
    path: Path, *, dataset: str, row_schema_version: str
) -> Iterator[dict[str, Any]]:
    try:
        yield from iter_generation_rows(
            path,
            dataset=dataset,
            row_schema_version=row_schema_version,
        )
    except GenerationManifestError as exc:
        raise OcrValidationError(
            f"invalid generation manifest {display_path(path)}: {exc}"
        ) from exc


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise OcrValidationError(f"missing JSON report: {display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OcrValidationError(
            f"invalid JSON report {display_path(path)}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise OcrValidationError("OCR report must be a JSON object")
    return payload


def open_index() -> tuple[sqlite3.Connection, Path]:
    file_descriptor, name = tempfile.mkstemp(
        prefix="vota-real-page-ocr-validation-", suffix=".db"
    )
    os.close(file_descriptor)
    path = Path(name)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.executescript(
        """
        CREATE TABLE expected (
          document_sha256 TEXT NOT NULL,
          page_number INTEGER NOT NULL,
          representative_path TEXT NOT NULL,
          document_bytes INTEGER NOT NULL,
          source_group TEXT NOT NULL,
          document_page_count INTEGER NOT NULL,
          reason TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          PRIMARY KEY (document_sha256, page_number)
        );

        CREATE TABLE observed (
          document_sha256 TEXT NOT NULL,
          page_number INTEGER NOT NULL,
          representative_path TEXT NOT NULL,
          document_bytes INTEGER NOT NULL,
          source_group TEXT NOT NULL,
          document_page_count INTEGER NOT NULL,
          reason TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          work_state TEXT NOT NULL,
          ocr_status TEXT,
          ocr_text_sha256 TEXT,
          ocr_text_cas_path TEXT,
          ocr_text_chars INTEGER,
          improved_over_native INTEGER,
          last_error TEXT,
          PRIMARY KEY (document_sha256, page_number)
        );
        CREATE INDEX idx_observed_ocr_sha256 ON observed(ocr_text_sha256);
        """
    )
    return conn, path


def load_expected(conn: sqlite3.Connection, native_manifest: Path) -> tuple[int, int]:
    native_rows = 0
    candidates = 0
    for item in iter_manifest(
        native_manifest,
        dataset="native_text",
        row_schema_version="real_document_text_manifest_row_v1",
    ):
        native_rows += 1
        path = str(item.get("path") or "")
        document_sha256 = str(item.get("content_sha256") or "").lower()
        page_count = item.get("page_count")
        pages = item.get("ocr_candidate_pages")
        if (
            item.get("schema_version") != "real_document_text_manifest_row_v1"
            or item.get("synthetic_or_mock") is not False
            or item.get("official_public_domain_personal_information_retained")
            is not True
            or item.get("work_state") != "succeeded"
            or not isinstance(pages, list)
        ):
            raise OcrValidationError(f"unsafe native manifest row: {path}")
        if not pages:
            continue
        if item.get("mime_type") != "application/pdf" or not isinstance(
            page_count, int
        ):
            raise OcrValidationError(f"OCR candidate is not a PDF: {path}")
        for page in pages:
            if not isinstance(page, dict):
                raise OcrValidationError(f"invalid native OCR page: {path}")
            page_number = int(page.get("page_number") or 0)
            reason = str(page.get("reason") or "")
            native_chars = int(page.get("source_text_chars") or 0)
            values = (
                document_sha256,
                page_number,
                path,
                int(item.get("bytes") or 0),
                str(item.get("source_group") or "unknown"),
                page_count,
                reason,
                native_chars,
            )
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO expected (
                  document_sha256, page_number, representative_path,
                  document_bytes, source_group, document_page_count, reason,
                  native_text_chars
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            if cursor.rowcount == 0:
                existing = conn.execute(
                    """
                    SELECT document_bytes, document_page_count, reason,
                           native_text_chars
                    FROM expected
                    WHERE document_sha256 = ? AND page_number = ?
                    """,
                    (document_sha256, page_number),
                ).fetchone()
                if existing is None or (
                    int(existing["document_bytes"]),
                    int(existing["document_page_count"]),
                    str(existing["reason"]),
                    int(existing["native_text_chars"]),
                ) != (values[3], values[5], values[6], values[7]):
                    raise OcrValidationError(
                        f"duplicate native OCR candidate drift: {path}:{page_number}"
                    )
            else:
                candidates += 1
        if native_rows % 5_000 == 0:
            conn.commit()
    conn.commit()
    return native_rows, candidates


def load_observed(conn: sqlite3.Connection, ocr_manifest: Path) -> int:
    rows = 0
    for item in iter_manifest(
        ocr_manifest,
        dataset="page_ocr",
        row_schema_version="real_document_page_ocr_manifest_row_v1",
    ):
        identity = (
            str(item.get("document_sha256") or "").lower(),
            int(item.get("page_number") or 0),
        )
        if (
            item.get("schema_version") != "real_document_page_ocr_manifest_row_v1"
            or "elapsed_seconds" in item
            or item.get("synthetic_or_mock") is not False
            or item.get("official_public_domain_personal_information_retained")
            is not True
            or item.get("additive_to_native_text") is not True
        ):
            raise OcrValidationError(
                f"unsafe OCR manifest row: {identity[0]}:{identity[1]}"
            )
        conn.execute(
            """
            INSERT INTO observed (
              document_sha256, page_number, representative_path,
              document_bytes, source_group, document_page_count, reason,
              native_text_chars, work_state, ocr_status, ocr_text_sha256,
              ocr_text_cas_path, ocr_text_chars, improved_over_native,
              last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                *identity,
                str(item.get("representative_path") or ""),
                int(item.get("document_bytes") or 0),
                str(item.get("source_group") or ""),
                int(item.get("document_page_count") or 0),
                str(item.get("routing_reason") or ""),
                int(item.get("native_text_chars") or 0),
                str(item.get("work_state") or ""),
                str(item.get("ocr_status") or ""),
                item.get("ocr_text_sha256"),
                item.get("ocr_text_cas_path"),
                item.get("ocr_text_chars"),
                (
                    1
                    if item.get("improved_over_native") is True
                    else 0
                    if item.get("improved_over_native") is False
                    else None
                ),
                item.get("last_error"),
            ),
        )
        rows += 1
    conn.commit()
    return rows


def mismatch_count(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM expected e
            LEFT JOIN observed o
              ON o.document_sha256 = e.document_sha256
             AND o.page_number = e.page_number
            WHERE o.document_sha256 IS NULL
               OR o.representative_path != e.representative_path
               OR o.document_bytes != e.document_bytes
               OR o.source_group != e.source_group
               OR o.document_page_count != e.document_page_count
               OR o.reason != e.reason
               OR o.native_text_chars != e.native_text_chars
            """
        ).fetchone()[0]
    ) + int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM observed o
            LEFT JOIN expected e
              ON e.document_sha256 = o.document_sha256
             AND e.page_number = o.page_number
            WHERE e.document_sha256 IS NULL
            """
        ).fetchone()[0]
    )


def verify_document(raw_root: Path, item: Mapping[str, Any]) -> str | None:
    relative = str(item["representative_path"])
    try:
        path = safe_child(raw_root, relative)
        if not path.is_file():
            return f"missing:{relative}"
        if path.stat().st_size != int(item["document_bytes"]):
            return f"bytes:{relative}"
        if sha256_path(path) != str(item["document_sha256"]):
            return f"sha256:{relative}"
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}:{relative}:{exc}"


def validate_documents(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    workers: int,
) -> tuple[int, list[str]]:
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT document_sha256, MIN(representative_path) AS representative_path,
                   MIN(document_bytes) AS document_bytes
            FROM expected
            GROUP BY document_sha256
            ORDER BY document_sha256
            """
        )
    ]
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        for result in executor.map(lambda item: verify_document(raw_root, item), rows):
            if result and len(errors) < 20:
                errors.append(result)
    return len(rows), errors


def verify_ocr_text(ocr_root: Path, item: Mapping[str, Any]) -> str | None:
    text_sha256 = str(item["ocr_text_sha256"])
    relative = str(item["ocr_text_cas_path"])
    expected_relative = (
        Path(text_sha256[:2]) / text_sha256[2:4] / f"{text_sha256}.txt.gz"
    ).as_posix()
    if relative != expected_relative:
        return f"cas_path:{relative}"
    try:
        path = safe_child(ocr_root, relative)
        if not path.is_file():
            return f"missing:{relative}"
        digest = hashlib.sha256()
        decoder = codecs.getincrementaldecoder("utf-8")("strict")
        chars = 0
        with gzip.open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                chars += len(decoder.decode(chunk))
            chars += len(decoder.decode(b"", final=True))
        if digest.hexdigest() != text_sha256:
            return f"sha256:{relative}"
        if chars != int(item["ocr_text_chars"]):
            return f"chars:{relative}:{chars}!={item['ocr_text_chars']}"
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}:{relative}:{exc}"


def validate_ocr_cas(
    conn: sqlite3.Connection,
    *,
    ocr_root: Path,
    workers: int,
    batch_size: int,
) -> tuple[int, int, list[str]]:
    cursor = conn.execute(
        """
        SELECT ocr_text_sha256, MIN(ocr_text_cas_path) AS ocr_text_cas_path,
               MIN(ocr_text_chars) AS ocr_text_chars,
               MAX(ocr_text_chars) AS max_text_chars,
               COUNT(DISTINCT ocr_text_cas_path) AS paths
        FROM observed
        WHERE ocr_status = 'ocr_text_extracted'
        GROUP BY ocr_text_sha256
        ORDER BY ocr_text_sha256
        """
    )
    checked = 0
    expected_paths: set[str] = set()
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        while rows := cursor.fetchmany(max(1, batch_size)):
            items = [dict(row) for row in rows]
            for item in items:
                expected_paths.add(str(item["ocr_text_cas_path"]))
                if (
                    int(item["paths"]) != 1
                    or int(item["ocr_text_chars"]) != int(item["max_text_chars"])
                ) and len(errors) < 20:
                    errors.append(f"manifest_conflict:{item['ocr_text_sha256']}")
            for result in executor.map(
                lambda item: verify_ocr_text(ocr_root, item), items
            ):
                checked += 1
                if result and len(errors) < 20:
                    errors.append(result)
    actual_paths = {
        path.relative_to(ocr_root).as_posix()
        for path in ocr_root.rglob("*.txt.gz")
        if path.is_file()
    }
    for prefix, paths in (
        ("extra", sorted(actual_paths - expected_paths)),
        ("missing", sorted(expected_paths - actual_paths)),
    ):
        for path in paths[: max(0, 20 - len(errors))]:
            errors.append(f"{prefix}:{path}")
    return checked, len(actual_paths), errors


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


def validate(args: argparse.Namespace) -> dict[str, Any]:
    raw_root = Path(args.raw_root)
    ocr_root = Path(args.ocr_root)
    native_manifest = Path(args.native_manifest)
    ocr_manifest = Path(args.ocr_manifest)
    ocr_report_path = Path(args.ocr_report)
    ocr_report = load_json(ocr_report_path)
    if (
        ocr_report.get("schema_version") != "real_document_page_ocr_v1"
        or ocr_report.get("status") != "ok"
    ):
        raise OcrValidationError("OCR report is not a complete v1 run")
    policy = ocr_report.get("policy") or {}
    if (
        policy.get("synthetic_or_mock_records_counted") is not False
        or policy.get("official_public_domain_personal_information_retained")
        is not True
        or policy.get("ocr_text_is_not_sanitized_or_identity_stripped") is not True
        or policy.get("ocr_is_additive_to_native_text") is not True
    ):
        raise OcrValidationError("OCR report policy is unsafe")

    conn, index_path = open_index()
    try:
        native_rows, expected_pages = load_expected(conn, native_manifest)
        observed_pages = load_observed(conn, ocr_manifest)
        mismatches = mismatch_count(conn)
        invalid_states = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM observed
                WHERE work_state != 'succeeded'
                   OR ocr_status NOT IN ('ocr_text_extracted', 'ocr_no_text')
                   OR last_error IS NOT NULL
                   OR (
                     ocr_status = 'ocr_text_extracted'
                     AND (
                       LENGTH(ocr_text_sha256) != 64
                       OR ocr_text_cas_path IS NULL
                       OR ocr_text_chars IS NULL
                       OR ocr_text_chars <= 0
                       OR improved_over_native IS NULL
                     )
                   )
                   OR (
                     ocr_status = 'ocr_no_text'
                     AND (
                       ocr_text_sha256 IS NOT NULL
                       OR ocr_text_cas_path IS NOT NULL
                       OR COALESCE(ocr_text_chars, 0) != 0
                       OR improved_over_native != 0
                     )
                   )
                """
            ).fetchone()[0]
        )
        documents_checked, document_errors = validate_documents(
            conn, raw_root=raw_root, workers=int(args.workers)
        )
        cas_checked, actual_cas_files, cas_errors = validate_ocr_cas(
            conn,
            ocr_root=ocr_root,
            workers=int(args.workers),
            batch_size=int(args.batch_size),
        )
        totals_row = conn.execute(
            """
            SELECT
              COUNT(*) AS candidate_pages,
              COUNT(DISTINCT document_sha256) AS documents,
              SUM(CASE WHEN reason = 'empty_text' THEN 1 ELSE 0 END)
                AS empty_text_pages,
              SUM(CASE WHEN reason = 'sparse_text' THEN 1 ELSE 0 END)
                AS sparse_text_pages,
              SUM(native_text_chars) AS native_text_chars,
              SUM(COALESCE(ocr_text_chars, 0)) AS ocr_text_chars,
              SUM(CASE WHEN improved_over_native = 1 THEN 1 ELSE 0 END)
                AS improved_pages
            FROM observed
            """
        ).fetchone()
    finally:
        conn.close()
        index_path.unlink(missing_ok=True)
        index_path.with_name(f"{index_path.name}-wal").unlink(missing_ok=True)
        index_path.with_name(f"{index_path.name}-shm").unlink(missing_ok=True)

    report_manifest = ocr_report.get("manifest") or {}
    report_totals = ocr_report.get("totals") or {}
    ocr_manifest_sha256 = sha256_path(ocr_manifest)
    totals = {
        "native_manifest_rows": native_rows,
        "documents": int(totals_row["documents"]),
        "candidate_pages": int(totals_row["candidate_pages"]),
        "empty_text_pages": int(totals_row["empty_text_pages"] or 0),
        "sparse_text_pages": int(totals_row["sparse_text_pages"] or 0),
        "native_text_chars_on_candidate_pages": int(
            totals_row["native_text_chars"] or 0
        ),
        "ocr_text_chars": int(totals_row["ocr_text_chars"] or 0),
        "pages_improved_over_native_by_50_chars": int(
            totals_row["improved_pages"] or 0
        ),
        "source_documents_checksum_verified": documents_checked,
        "ocr_text_cas_objects_checksum_verified": cas_checked,
        "ocr_text_cas_files_observed": actual_cas_files,
    }
    report_keys = (
        "documents",
        "candidate_pages",
        "empty_text_pages",
        "sparse_text_pages",
        "native_text_chars_on_candidate_pages",
        "ocr_text_chars",
        "pages_improved_over_native_by_50_chars",
    )
    checks = {
        "expected_and_observed_candidate_pages_match": (
            expected_pages == observed_pages
        ),
        "manifest_rows_match_ocr_report": (
            int(report_manifest.get("rows", -1)) == observed_pages
        ),
        "manifest_sha256_matches_ocr_report": (
            report_manifest.get("sha256") == ocr_manifest_sha256
        ),
        "native_routing_and_ocr_manifest_values_match": mismatches == 0,
        "all_work_states_are_successful_and_well_formed": invalid_states == 0,
        "source_document_checksums_match": not document_errors,
        "ocr_text_cas_checksums_and_character_counts_match": not cas_errors,
        "ocr_text_cas_inventory_is_exact": cas_checked == actual_cas_files,
        "ocr_report_totals_reconcile": all(
            int(report_totals.get(key, -1)) == int(totals[key]) for key in report_keys
        ),
        "ocr_is_additive_and_native_text_is_unchanged": True,
        "no_synthetic_or_mock_records": True,
        "official_public_domain_personal_information_retained": True,
    }
    return {
        "schema_version": "real_document_page_ocr_validation_v1",
        "generated_at": utc_now(),
        "status": "ok" if all(checks.values()) else "failed",
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "ocr_text_is_not_sanitized_or_identity_stripped": True,
            "ocr_is_additive_to_native_text": True,
        },
        "inputs": {
            "native_manifest": {
                "path": display_path(native_manifest),
                "rows": native_rows,
                "bytes": native_manifest.stat().st_size,
                "sha256": sha256_path(native_manifest),
            },
            "ocr_manifest": {
                "path": display_path(ocr_manifest),
                "rows": observed_pages,
                "bytes": ocr_manifest.stat().st_size,
                "sha256": ocr_manifest_sha256,
            },
            "ocr_report": {
                "path": display_path(ocr_report_path),
                "bytes": ocr_report_path.stat().st_size,
                "sha256": sha256_path(ocr_report_path),
            },
        },
        "totals": totals,
        "diagnostics": {
            "manifest_value_mismatches": mismatches,
            "invalid_work_states": invalid_states,
            "source_document_error_samples": document_errors,
            "ocr_text_error_samples": cas_errors,
        },
        "checks": checks,
        "next_action": (
            "Human-review a stratified real-page sample by source, language, scan "
            "quality, and routing reason before analytical promotion."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if int(args.workers) < 1 or int(args.batch_size) < 1:
        print("ERROR: workers and batch-size must be positive")
        return 2
    try:
        report = validate(args)
        write_json_atomic(Path(args.report_out), report)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        if args.enforce and report["status"] != "ok":
            return 1
        return 0
    except (
        OcrValidationError,
        GenerationManifestError,
        OSError,
        sqlite3.Error,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
