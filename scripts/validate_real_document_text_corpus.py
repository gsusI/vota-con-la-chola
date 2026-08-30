#!/usr/bin/env python3
"""Independently validate the complete real-document native-text corpus."""

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
DEFAULT_TEXT_ROOT = Path("etl/data/derived/real-document-text-corpus-v2")
DEFAULT_INVENTORY = Path("etl/data/manifests/real-document-format-inventory.jsonl")
DEFAULT_PROVENANCE = Path("etl/data/manifests/real-document-provenance-files.jsonl")
DEFAULT_MANIFEST = Path("etl/data/published/real-document-text-manifest-latest.jsonl")
DEFAULT_EXTRACTION_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-text-extraction.json"
)
DEFAULT_VALIDATION_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-text-validation.json"
)
SHA256_HEX_LENGTH = 64


class CorpusValidationError(RuntimeError):
    """Raised when extracted corpus evidence fails exact validation."""


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
        raise CorpusValidationError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise CorpusValidationError(f"path escapes root: {relative}") from exc
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
    parser.add_argument("--text-root", default=str(DEFAULT_TEXT_ROOT))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--provenance", default=str(DEFAULT_PROVENANCE))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--extraction-report", default=str(DEFAULT_EXTRACTION_REPORT))
    parser.add_argument("--report-out", default=str(DEFAULT_VALIDATION_REPORT))
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument(
        "--full-raw-check",
        action="store_true",
        help="Hash every file instance, including duplicate-content paths.",
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        raise CorpusValidationError(f"missing JSONL input: {display_path(path)}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CorpusValidationError(
                    f"invalid JSONL at {display_path(path)}:{line_number}: {exc}"
                ) from exc
            if not isinstance(item, dict):
                raise CorpusValidationError(
                    f"JSONL row must be an object: {display_path(path)}:{line_number}"
                )
            yield item


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CorpusValidationError(f"missing JSON report: {display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusValidationError(
            f"invalid JSON report {display_path(path)}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise CorpusValidationError("extraction report must be a JSON object")
    return payload


def open_index() -> tuple[sqlite3.Connection, Path]:
    file_descriptor, name = tempfile.mkstemp(
        prefix="vota-real-document-text-validation-", suffix=".db"
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
          path TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          provenance_seen INTEGER NOT NULL DEFAULT 0,
          provenance_status TEXT,
          public_url_edges INTEGER NOT NULL DEFAULT 0,
          ocr_candidate_pages INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX idx_expected_sha256 ON expected(content_sha256);

        CREATE TABLE observed (
          path TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          provenance_status TEXT,
          public_url_edges INTEGER NOT NULL,
          ocr_candidate_pages INTEGER NOT NULL,
          work_state TEXT NOT NULL,
          extraction_status TEXT,
          text_sha256 TEXT,
          text_cas_path TEXT,
          text_chars INTEGER,
          text_truncated INTEGER,
          last_error TEXT
        );
        CREATE INDEX idx_observed_sha256 ON observed(content_sha256);
        CREATE INDEX idx_observed_text_sha256 ON observed(text_sha256);
        """
    )
    return conn, path


def load_expected(
    conn: sqlite3.Connection, inventory_path: Path, provenance_path: Path
) -> int:
    rows = 0
    for item in iter_jsonl(inventory_path):
        path = str(item.get("path") or "")
        sha256 = str(item.get("sha256") or "").lower()
        declared_bytes = item.get("bytes")
        if (
            item.get("accountability_eligible") is not True
            or item.get("status") != "ok"
            or len(sha256) != SHA256_HEX_LENGTH
            or not isinstance(declared_bytes, int)
            or declared_bytes < 0
        ):
            raise CorpusValidationError(f"invalid inventory row: {path}")
        page_quality = item.get("page_text_quality") or {}
        candidate_pages = (
            page_quality.get("ocr_candidate_pages")
            if isinstance(page_quality, dict)
            else []
        )
        conn.execute(
            """
            INSERT INTO expected (
              path, content_sha256, bytes, ocr_candidate_pages
            ) VALUES (?, ?, ?, ?)
            """,
            (path, sha256, declared_bytes, len(candidate_pages or [])),
        )
        rows += 1
        if rows % 5_000 == 0:
            conn.commit()
    conn.commit()

    provenance_rows = 0
    for item in iter_jsonl(provenance_path):
        path = str(item.get("path") or "")
        if (
            item.get("checksum_conflict") is not False
            or item.get("declared_bytes_conflict") is not False
        ):
            raise CorpusValidationError(f"conflicted provenance row: {path}")
        cursor = conn.execute(
            """
            UPDATE expected
            SET provenance_seen = 1, provenance_status = ?, public_url_edges = ?
            WHERE path = ? AND content_sha256 = ? AND bytes = ?
              AND provenance_seen = 0
            """,
            (
                str(item.get("provenance_status") or "unlinked"),
                int(item.get("public_url_edges") or 0),
                path,
                str(item.get("sha256") or "").lower(),
                int(item.get("bytes") or 0),
            ),
        )
        if cursor.rowcount != 1:
            raise CorpusValidationError(f"provenance mismatch: {path}")
        provenance_rows += 1
        if provenance_rows % 5_000 == 0:
            conn.commit()
    conn.commit()
    missing = conn.execute(
        "SELECT COUNT(*) FROM expected WHERE provenance_seen = 0"
    ).fetchone()[0]
    if provenance_rows != rows or int(missing):
        raise CorpusValidationError(
            "expected inventory/provenance sets do not reconcile"
        )
    return rows


def load_observed(conn: sqlite3.Connection, manifest_path: Path) -> int:
    rows = 0
    try:
        manifest_rows = iter_generation_rows(
            manifest_path,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
        )
        for item in manifest_rows:
            path = str(item.get("path") or "")
            if (
                item.get("schema_version") != "real_document_text_manifest_row_v1"
                or item.get("synthetic_or_mock") is not False
                or item.get("official_public_domain_personal_information_retained")
                is not True
            ):
                raise CorpusValidationError(f"invalid extraction manifest row: {path}")
            ocr_pages = item.get("ocr_candidate_pages")
            if not isinstance(ocr_pages, list):
                raise CorpusValidationError(f"invalid OCR candidate list: {path}")
            conn.execute(
                """
                INSERT INTO observed (
                  path, content_sha256, bytes, provenance_status,
                  public_url_edges, ocr_candidate_pages, work_state,
                  extraction_status, text_sha256, text_cas_path, text_chars,
                  text_truncated, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    path,
                    str(item.get("content_sha256") or "").lower(),
                    int(item.get("bytes") or 0),
                    str(item.get("provenance_status") or ""),
                    int(item.get("public_url_edges") or 0),
                    len(ocr_pages),
                    str(item.get("work_state") or ""),
                    str(item.get("native_extraction_status") or ""),
                    item.get("native_text_sha256"),
                    item.get("native_text_cas_path"),
                    item.get("native_text_chars"),
                    (
                        1
                        if item.get("native_text_truncated") is True
                        else 0
                        if item.get("native_text_truncated") is False
                        else None
                    ),
                    item.get("last_error"),
                ),
            )
            rows += 1
            if rows % 5_000 == 0:
                conn.commit()
    except GenerationManifestError as exc:
        raise CorpusValidationError(f"invalid extraction manifest: {exc}") from exc
    conn.commit()
    return rows


def _mismatch_count(conn: sqlite3.Connection) -> int:
    return int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM expected e
            LEFT JOIN observed o ON o.path = e.path
            WHERE o.path IS NULL
               OR o.content_sha256 != e.content_sha256
               OR o.bytes != e.bytes
               OR o.provenance_status != e.provenance_status
               OR o.public_url_edges != e.public_url_edges
               OR o.ocr_candidate_pages != e.ocr_candidate_pages
            """
        ).fetchone()[0]
    ) + int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM observed o
            LEFT JOIN expected e ON e.path = o.path
            WHERE e.path IS NULL
            """
        ).fetchone()[0]
    )


def _verify_raw_item(raw_root: Path, item: Mapping[str, Any]) -> str | None:
    relative = str(item["path"])
    try:
        path = safe_child(raw_root, relative)
        if not path.is_file():
            return f"missing:{relative}"
        if path.stat().st_size != int(item["bytes"]):
            return f"bytes:{relative}"
        if sha256_path(path) != str(item["content_sha256"]):
            return f"sha256:{relative}"
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}:{relative}:{exc}"


def validate_raw_files(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    workers: int,
    batch_size: int,
    full_raw_check: bool,
) -> tuple[int, list[str]]:
    if full_raw_check:
        cursor = conn.execute(
            "SELECT path, content_sha256, bytes FROM expected ORDER BY path"
        )
    else:
        cursor = conn.execute(
            """
            SELECT MIN(path) AS path, content_sha256, MIN(bytes) AS bytes
            FROM expected
            GROUP BY content_sha256
            ORDER BY content_sha256
            """
        )
    checked = 0
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        while rows := cursor.fetchmany(max(1, batch_size)):
            results = executor.map(
                lambda row: _verify_raw_item(raw_root, dict(row)), rows
            )
            for result in results:
                checked += 1
                if result and len(errors) < 20:
                    errors.append(result)
    return checked, errors


def _verify_text_item(text_root: Path, item: Mapping[str, Any]) -> str | None:
    text_sha256 = str(item["text_sha256"])
    relative = str(item["text_cas_path"])
    expected_relative = (
        Path(text_sha256[:2]) / text_sha256[2:4] / f"{text_sha256}.txt.gz"
    ).as_posix()
    if relative != expected_relative:
        return f"cas_path:{relative}"
    try:
        path = safe_child(text_root, relative)
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
        if chars != int(item["text_chars"]):
            return f"chars:{relative}:{chars}!={item['text_chars']}"
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}:{relative}:{exc}"


def validate_text_cas(
    conn: sqlite3.Connection,
    *,
    text_root: Path,
    workers: int,
    batch_size: int,
) -> tuple[int, int, list[str]]:
    cursor = conn.execute(
        """
        SELECT text_sha256, MIN(text_cas_path) AS text_cas_path,
               MIN(text_chars) AS text_chars,
               MAX(text_chars) AS max_text_chars,
               COUNT(DISTINCT text_cas_path) AS paths
        FROM observed
        WHERE extraction_status = 'native_text_extracted'
        GROUP BY text_sha256
        ORDER BY text_sha256
        """
    )
    checked = 0
    expected_paths: set[str] = set()
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        while rows := cursor.fetchmany(max(1, batch_size)):
            items = [dict(row) for row in rows]
            for item in items:
                expected_paths.add(str(item["text_cas_path"]))
                if (
                    int(item["paths"]) != 1
                    or int(item["text_chars"]) != int(item["max_text_chars"])
                ) and len(errors) < 20:
                    errors.append(f"manifest_conflict:{item['text_sha256']}")
            results = executor.map(
                lambda item: _verify_text_item(text_root, item), items
            )
            for result in results:
                checked += 1
                if result and len(errors) < 20:
                    errors.append(result)
    actual_paths = {
        path.relative_to(text_root).as_posix()
        for path in text_root.rglob("*.txt.gz")
        if path.is_file()
    }
    extras = sorted(actual_paths - expected_paths)
    missing = sorted(expected_paths - actual_paths)
    for prefix, paths in (("extra", extras), ("missing", missing)):
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
    text_root = Path(args.text_root)
    inventory_path = Path(args.inventory)
    provenance_path = Path(args.provenance)
    manifest_path = Path(args.manifest)
    extraction_report_path = Path(args.extraction_report)
    extraction_report = load_json(extraction_report_path)
    if (
        extraction_report.get("schema_version") != "real_document_text_extraction_v1"
        or extraction_report.get("status") != "ok"
    ):
        raise CorpusValidationError("extraction report is not a complete v1 run")
    policy = extraction_report.get("policy") or {}
    if (
        policy.get("synthetic_or_mock_records_counted") is not False
        or policy.get("official_public_domain_personal_information_retained")
        is not True
        or policy.get("native_text_is_not_sanitized_or_identity_stripped") is not True
    ):
        raise CorpusValidationError("extraction report policy is unsafe")

    conn, index_path = open_index()
    try:
        expected_rows = load_expected(conn, inventory_path, provenance_path)
        observed_rows = load_observed(conn, manifest_path)
        mismatch_rows = _mismatch_count(conn)
        invalid_states = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM observed
                WHERE work_state != 'succeeded'
                   OR extraction_status NOT IN (
                     'native_text_extracted', 'native_no_text'
                   )
                   OR last_error IS NOT NULL
                   OR (
                     extraction_status = 'native_text_extracted'
                     AND (
                       LENGTH(text_sha256) != 64
                       OR text_cas_path IS NULL
                       OR text_chars IS NULL
                       OR text_chars <= 0
                     )
                   )
                   OR (
                     extraction_status = 'native_no_text'
                     AND (
                       text_sha256 IS NOT NULL
                       OR text_cas_path IS NOT NULL
                       OR COALESCE(text_chars, 0) != 0
                     )
                   )
                """
            ).fetchone()[0]
        )
        raw_checked, raw_errors = validate_raw_files(
            conn,
            raw_root=raw_root,
            workers=int(args.workers),
            batch_size=int(args.batch_size),
            full_raw_check=bool(args.full_raw_check),
        )
        text_checked, actual_cas_files, text_errors = validate_text_cas(
            conn,
            text_root=text_root,
            workers=int(args.workers),
            batch_size=int(args.batch_size),
        )
        totals_row = conn.execute(
            """
            SELECT
              COUNT(DISTINCT content_sha256) AS distinct_content_objects,
              SUM(CASE WHEN public_url_edges > 0 THEN 1 ELSE 0 END)
                AS public_url_instances,
              SUM(CASE WHEN public_url_edges = 0 THEN 1 ELSE 0 END)
                AS provenance_gap_instances,
              SUM(ocr_candidate_pages) AS ocr_candidate_pages
            FROM observed
            """
        ).fetchone()
        extraction_row = conn.execute(
            """
            SELECT
              COUNT(*) AS distinct_content_objects,
              SUM(CASE WHEN extraction_status = 'native_no_text' THEN 1 ELSE 0 END)
                AS no_text_objects,
              SUM(CASE WHEN text_truncated = 1 THEN 1 ELSE 0 END)
                AS truncated_objects,
              SUM(COALESCE(text_chars, 0)) AS native_text_chars
            FROM (
              SELECT content_sha256, MAX(extraction_status) AS extraction_status,
                     MAX(text_truncated) AS text_truncated,
                     MAX(text_chars) AS text_chars
              FROM observed
              GROUP BY content_sha256
            )
            """
        ).fetchone()
    finally:
        conn.close()
        index_path.unlink(missing_ok=True)
        index_path.with_name(f"{index_path.name}-wal").unlink(missing_ok=True)
        index_path.with_name(f"{index_path.name}-shm").unlink(missing_ok=True)

    report_manifest = extraction_report.get("manifest") or {}
    report_totals = extraction_report.get("totals") or {}
    manifest_sha256 = sha256_path(manifest_path)
    totals = {
        "file_instances": observed_rows,
        "distinct_content_objects": int(totals_row["distinct_content_objects"]),
        "public_url_instances": int(totals_row["public_url_instances"] or 0),
        "provenance_gap_instances": int(totals_row["provenance_gap_instances"] or 0),
        "native_text_chars": int(extraction_row["native_text_chars"] or 0),
        "native_no_text_objects": int(extraction_row["no_text_objects"] or 0),
        "native_truncated_objects": int(extraction_row["truncated_objects"] or 0),
        "ocr_candidate_pages": int(totals_row["ocr_candidate_pages"] or 0),
        "raw_files_checksum_verified": raw_checked,
        "text_cas_objects_checksum_verified": text_checked,
        "text_cas_files_observed": actual_cas_files,
    }
    reconciled_report_keys = (
        "file_instances",
        "distinct_content_objects",
        "public_url_instances",
        "provenance_gap_instances",
        "native_text_chars",
        "native_no_text_objects",
        "native_truncated_objects",
        "ocr_candidate_pages",
    )
    report_totals_match = all(
        int(report_totals.get(key, -1)) == int(totals[key])
        for key in reconciled_report_keys
    )
    checks = {
        "expected_and_observed_rows_match": expected_rows == observed_rows,
        "manifest_rows_match_extraction_report": (
            int(report_manifest.get("rows", -1)) == observed_rows
        ),
        "manifest_sha256_matches_extraction_report": (
            report_manifest.get("sha256") == manifest_sha256
        ),
        "inventory_provenance_and_manifest_values_match": mismatch_rows == 0,
        "all_work_states_are_successful_and_well_formed": invalid_states == 0,
        "raw_checksums_match": not raw_errors,
        "text_cas_checksums_and_character_counts_match": not text_errors,
        "text_cas_inventory_is_exact": text_checked == actual_cas_files,
        "extraction_report_totals_reconcile": report_totals_match,
        "no_native_text_truncation": totals["native_truncated_objects"] == 0,
        "no_synthetic_or_mock_records": True,
        "official_public_domain_personal_information_retained": True,
    }
    return {
        "schema_version": "real_document_text_validation_v1",
        "generated_at": utc_now(),
        "status": "ok" if all(checks.values()) else "failed",
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "native_text_is_not_sanitized_or_identity_stripped": True,
        },
        "inputs": {
            "inventory": {
                "path": display_path(inventory_path),
                "sha256": sha256_path(inventory_path),
            },
            "provenance": {
                "path": display_path(provenance_path),
                "sha256": sha256_path(provenance_path),
            },
            "manifest": {
                "path": display_path(manifest_path),
                "rows": observed_rows,
                "bytes": manifest_path.stat().st_size,
                "sha256": manifest_sha256,
            },
            "extraction_report": {
                "path": display_path(extraction_report_path),
                "bytes": extraction_report_path.stat().st_size,
                "sha256": sha256_path(extraction_report_path),
            },
        },
        "validation_scope": {
            "full_raw_file_instance_checksums": bool(args.full_raw_check),
            "workers": int(args.workers),
            "batch_size": int(args.batch_size),
        },
        "totals": totals,
        "diagnostics": {
            "manifest_value_mismatches": mismatch_rows,
            "invalid_work_states": invalid_states,
            "raw_error_samples": raw_errors,
            "text_error_samples": text_errors,
        },
        "checks": checks,
        "next_action": (
            "Run bounded page-level OCR for every distinct empty or sparse PDF "
            "page and publish it as additive evidence beside native text."
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
        CorpusValidationError,
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
