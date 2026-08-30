#!/usr/bin/env python3
"""Independently replay every real-document page/span locator."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import resource
import sqlite3
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.extraction import build_document_text_locators
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    iter_generation_rows,
    load_index_bytes,
)
from scripts.locate_real_document_text import (
    DATASET,
    NATIVE_DATASET,
    NATIVE_ROW_SCHEMA,
    REPORT_SCHEMA,
    ROW_SCHEMA,
)

DEFAULT_RAW_ROOT = Path("etl/data/raw")
DEFAULT_NATIVE_ROOT = Path("etl/data/derived/real-document-text-corpus-v2")
DEFAULT_NATIVE_MANIFEST = Path(
    "etl/data/published/real-document-text-manifest-latest.jsonl"
)
DEFAULT_LOCATOR_MANIFEST = Path(
    "etl/data/published/real-document-text-locator-manifest-latest.jsonl"
)
DEFAULT_LOCATOR_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-text-locator-extraction.json"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-text-locator-validation.json"
)
VALIDATION_SCHEMA = "real_document_text_locator_validation_v1"


class LocatorValidationError(RuntimeError):
    """Raised when locator evidence does not replay exactly."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def safe_child(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise LocatorValidationError(f"unsafe relative path: {relative!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise LocatorValidationError(f"path escapes root: {relative}") from exc
    return candidate


def sha256_path(path: Path, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


def usage() -> dict[str, float | int]:
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    multiplier = 1 if sys.platform == "darwin" else 1024
    return {
        "cpu_seconds": round(
            own.ru_utime
            + own.ru_stime
            + children.ru_utime
            + children.ru_stime,
            6,
        ),
        "peak_rss_bytes_self": int(own.ru_maxrss * multiplier),
        "peak_rss_bytes_child_max": int(children.ru_maxrss * multiplier),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--native-root", default=str(DEFAULT_NATIVE_ROOT))
    parser.add_argument("--native-manifest", default=str(DEFAULT_NATIVE_MANIFEST))
    parser.add_argument("--locator-manifest", default=str(DEFAULT_LOCATOR_MANIFEST))
    parser.add_argument("--locator-report", default=str(DEFAULT_LOCATOR_REPORT))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--work-db", default="")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--pdf-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def open_work_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = FILE")
    conn.executescript(
        """
        CREATE TABLE instances (
          path TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          mime_type TEXT NOT NULL,
          page_count INTEGER,
          native_text_sha256 TEXT NOT NULL,
          native_text_cas_path TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          native_extraction_method TEXT NOT NULL
        );
        CREATE INDEX idx_instances_content ON instances(content_sha256);

        CREATE TABLE contents (
          content_sha256 TEXT PRIMARY KEY,
          representative_path TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          mime_type TEXT NOT NULL,
          page_count INTEGER,
          native_text_sha256 TEXT NOT NULL,
          native_text_cas_path TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          native_extraction_method TEXT NOT NULL
        );

        CREATE TABLE actual (
          path TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          segment_index INTEGER NOT NULL,
          locator_type TEXT NOT NULL,
          locator_value TEXT NOT NULL,
          page_number INTEGER,
          text_start_char INTEGER NOT NULL,
          text_end_char INTEGER NOT NULL,
          text_chars INTEGER NOT NULL,
          text_sha256 TEXT NOT NULL,
          has_text INTEGER NOT NULL,
          native_text_sha256 TEXT NOT NULL,
          native_text_cas_path TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          native_extraction_method TEXT NOT NULL,
          PRIMARY KEY (path, segment_index)
        );

        CREATE TABLE replayed (
          content_sha256 TEXT NOT NULL,
          segment_index INTEGER NOT NULL,
          locator_type TEXT NOT NULL,
          locator_value TEXT NOT NULL,
          page_number INTEGER,
          text_start_char INTEGER NOT NULL,
          text_end_char INTEGER NOT NULL,
          text_chars INTEGER NOT NULL,
          text_sha256 TEXT NOT NULL,
          has_text INTEGER NOT NULL,
          PRIMARY KEY (content_sha256, segment_index)
        );
        """
    )
    return conn


def load_native(conn: sqlite3.Connection, manifest: Path) -> tuple[int, int]:
    rows = 0
    for item in iter_generation_rows(
        manifest,
        dataset=NATIVE_DATASET,
        row_schema_version=NATIVE_ROW_SCHEMA,
        allow_legacy_jsonl=False,
    ):
        if (
            item.get("work_state") != "succeeded"
            or item.get("native_extraction_status") != "native_text_extracted"
            or item.get("native_text_truncated") is not False
            or item.get("synthetic_or_mock") is not False
            or item.get("official_public_domain_personal_information_retained")
            is not True
        ):
            raise LocatorValidationError("native manifest policy/state drifted")
        values = (
            str(item["path"]),
            str(item["content_sha256"]),
            int(item["bytes"]),
            str(item.get("mime_type") or ""),
            item.get("page_count"),
            str(item["native_text_sha256"]),
            str(item["native_text_cas_path"]),
            int(item["native_text_chars"]),
            str(item["native_extraction_method"]),
        )
        conn.execute(
            "INSERT INTO instances VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", values
        )
        conn.execute(
            "INSERT OR IGNORE INTO contents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                values[1],
                values[0],
                values[2],
                values[3],
                values[4],
                values[5],
                values[6],
                values[7],
                values[8],
            ),
        )
        canonical = conn.execute(
            "SELECT * FROM contents WHERE content_sha256 = ?", (values[1],)
        ).fetchone()
        if (
            int(canonical["bytes"]),
            canonical["page_count"],
            str(canonical["native_text_sha256"]),
            str(canonical["native_text_cas_path"]),
            int(canonical["native_text_chars"]),
            str(canonical["native_extraction_method"]),
        ) != (values[2], values[4], values[5], values[6], values[7], values[8]):
            raise LocatorValidationError("duplicate native content metadata drifted")
        rows += 1
        if rows % 10_000 == 0:
            conn.commit()
    conn.commit()
    contents = int(conn.execute("SELECT COUNT(*) FROM contents").fetchone()[0])
    return rows, contents


def load_actual(conn: sqlite3.Connection, manifest: Path) -> int:
    rows = 0
    for item in iter_generation_rows(
        manifest,
        dataset=DATASET,
        row_schema_version=ROW_SCHEMA,
        allow_legacy_jsonl=False,
    ):
        forbidden_text_fields = {"text", "segment_text", "public_text"}.intersection(item)
        if (
            forbidden_text_fields
            or item.get("text_included_in_manifest") is not False
            or item.get("synthetic_or_mock") is not False
            or item.get("official_public_domain_personal_information_retained")
            is not True
            or len(str(item.get("text_sha256") or "")) != 64
        ):
            raise LocatorValidationError("locator row policy/schema drifted")
        conn.execute(
            """
            INSERT INTO actual VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(item["path"]),
                str(item["content_sha256"]),
                int(item["segment_index"]),
                str(item["locator_type"]),
                str(item["locator_value"]),
                item.get("page_number"),
                int(item["text_start_char"]),
                int(item["text_end_char"]),
                int(item["text_chars"]),
                str(item["text_sha256"]),
                1 if item.get("has_text") is True else 0,
                str(item["native_text_sha256"]),
                str(item["native_text_cas_path"]),
                int(item["native_text_chars"]),
                str(item["native_extraction_method"]),
            ),
        )
        rows += 1
        if rows % 10_000 == 0:
            conn.commit()
    conn.commit()
    return rows


def replay_one(
    row: Mapping[str, Any],
    *,
    raw_root: Path,
    native_root: Path,
    max_span_chars: int,
    pdf_timeout_seconds: float,
) -> tuple[str, list[tuple[Any, ...]], int, int]:
    content_sha256 = str(row["content_sha256"])
    raw_path = safe_child(raw_root, str(row["representative_path"]))
    if not raw_path.is_file() or raw_path.stat().st_size != int(row["bytes"]):
        raise LocatorValidationError("raw representative missing or size-drifted")
    if sha256_path(raw_path) != content_sha256:
        raise LocatorValidationError("raw representative checksum drifted")
    native_path = safe_child(native_root, str(row["native_text_cas_path"]))
    with gzip.open(native_path, "rt", encoding="utf-8") as handle:
        text = handle.read()
    text_bytes = text.encode("utf-8")
    if len(text) != int(row["native_text_chars"]):
        raise LocatorValidationError("native character count drifted")
    if hashlib.sha256(text_bytes).hexdigest() != str(row["native_text_sha256"]):
        raise LocatorValidationError("native checksum drifted")
    locators = build_document_text_locators(
        text,
        raw_path=raw_path,
        content_type=str(row["mime_type"]),
        extraction_method=str(row["native_extraction_method"]),
        expected_page_count=row["page_count"],
        max_span_chars=max_span_chars,
        pdf_timeout_seconds=pdf_timeout_seconds,
    )
    return (
        content_sha256,
        [
            (
                content_sha256,
                item.segment_index,
                item.locator_type,
                item.locator_value,
                item.page_number,
                item.text_start_char,
                item.text_end_char,
                item.text_chars,
                item.text_sha256,
                1 if item.has_text else 0,
            )
            for item in locators
        ],
        int(row["bytes"]),
        len(text_bytes),
    )


def full_replay(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    native_root: Path,
    max_span_chars: int,
    pdf_timeout_seconds: float,
    workers: int,
    batch_size: int,
) -> tuple[int, int, int, list[str]]:
    cursor = conn.execute("SELECT * FROM contents ORDER BY content_sha256")
    replayed = 0
    raw_bytes = 0
    native_bytes = 0
    failures: list[str] = []
    while True:
        rows = [dict(row) for row in cursor.fetchmany(batch_size)]
        if not rows:
            break
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    replay_one,
                    row,
                    raw_root=raw_root,
                    native_root=native_root,
                    max_span_chars=max_span_chars,
                    pdf_timeout_seconds=pdf_timeout_seconds,
                ): str(row["content_sha256"])
                for row in rows
            }
            for future in as_completed(futures):
                content_sha256 = futures[future]
                try:
                    _, locators, raw_size, native_size = future.result()
                    conn.executemany(
                        "INSERT INTO replayed VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        locators,
                    )
                    replayed += 1
                    raw_bytes += raw_size
                    native_bytes += native_size
                except Exception as exc:  # noqa: BLE001
                    if len(failures) < 50:
                        failures.append(
                            f"{content_sha256}: {type(exc).__name__}: {exc}"
                        )
        conn.commit()
        if replayed and replayed % 10_000 == 0:
            print(f"replayed content_objects={replayed}", flush=True)
    return replayed, raw_bytes, native_bytes, failures


def mismatch_counts(conn: sqlite3.Connection) -> dict[str, int]:
    expected_rows = int(
        conn.execute(
            "SELECT COUNT(*) FROM instances i JOIN replayed r USING(content_sha256)"
        ).fetchone()[0]
    )
    missing = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM instances i JOIN replayed r USING(content_sha256)
            LEFT JOIN actual a
              ON a.path = i.path AND a.segment_index = r.segment_index
            WHERE a.path IS NULL
            """
        ).fetchone()[0]
    )
    unexpected = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM actual a
            LEFT JOIN instances i ON i.path = a.path
            LEFT JOIN replayed r
              ON r.content_sha256 = i.content_sha256
             AND r.segment_index = a.segment_index
            WHERE i.path IS NULL OR r.content_sha256 IS NULL
            """
        ).fetchone()[0]
    )
    mismatched = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM actual a
            JOIN instances i ON i.path = a.path
            JOIN replayed r
              ON r.content_sha256 = i.content_sha256
             AND r.segment_index = a.segment_index
            WHERE a.content_sha256 <> i.content_sha256
               OR a.locator_type <> r.locator_type
               OR a.locator_value <> r.locator_value
               OR a.page_number IS NOT r.page_number
               OR a.text_start_char <> r.text_start_char
               OR a.text_end_char <> r.text_end_char
               OR a.text_chars <> r.text_chars
               OR a.text_sha256 <> r.text_sha256
               OR a.has_text <> r.has_text
               OR a.native_text_sha256 <> i.native_text_sha256
               OR a.native_text_cas_path <> i.native_text_cas_path
               OR a.native_text_chars <> i.native_text_chars
               OR a.native_extraction_method <> i.native_extraction_method
            """
        ).fetchone()[0]
    )
    return {
        "expected_instance_locator_rows": expected_rows,
        "missing_rows": missing,
        "unexpected_rows": unexpected,
        "mismatched_rows": mismatched,
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def validate(args: argparse.Namespace) -> dict[str, Any]:
    if (
        int(args.workers) < 1
        or int(args.batch_size) < 1
        or float(args.pdf_timeout_seconds) <= 0
    ):
        raise LocatorValidationError("validation bounds must be positive")
    raw_root = Path(args.raw_root)
    native_root = Path(args.native_root)
    native_manifest = Path(args.native_manifest)
    locator_manifest = Path(args.locator_manifest)
    source_report_path = Path(args.locator_report)
    report_out = Path(args.report_out)
    for required in (native_manifest, locator_manifest, source_report_path):
        if not required.is_file():
            raise LocatorValidationError(f"missing input: {display_path(required)}")
    if not raw_root.is_dir() or not native_root.is_dir():
        raise LocatorValidationError("real raw/native roots are missing")
    source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
    if (
        source_report.get("schema_version") != REPORT_SCHEMA
        or source_report.get("status") != "ok"
    ):
        raise LocatorValidationError("source locator report is not passing")
    configuration = source_report.get("configuration") or {}
    max_span_chars = int(configuration.get("max_span_chars") or 0)
    if max_span_chars < 1:
        raise LocatorValidationError("source locator configuration drifted")
    index = load_index_bytes(locator_manifest.read_bytes(), dataset=DATASET)
    if (
        index.get("row_schema_version") != ROW_SCHEMA
        or (index.get("policy") or {}).get("locator_rows_copy_no_public_text")
        is not True
        or ((source_report.get("inputs") or {}).get("native_manifest") or {}).get(
            "sha256"
        )
        != sha256_path(native_manifest)
        or (source_report.get("manifest") or {}).get("sha256")
        != sha256_path(locator_manifest)
    ):
        raise LocatorValidationError("source report/index/input binding drifted")

    temporary = not bool(args.work_db)
    if temporary:
        descriptor, work_name = tempfile.mkstemp(
            prefix="real-document-text-locator-validation-", suffix=".db"
        )
        os.close(descriptor)
        work_db = Path(work_name)
    else:
        work_db = Path(args.work_db)
        if work_db.exists():
            raise LocatorValidationError("work database must not already exist")
    started = time.monotonic()
    conn = open_work_db(work_db)
    try:
        native_rows, content_objects = load_native(conn, native_manifest)
        actual_rows = load_actual(conn, locator_manifest)
        replayed, raw_bytes, native_bytes, failures = full_replay(
            conn,
            raw_root=raw_root,
            native_root=native_root,
            max_span_chars=max_span_chars,
            pdf_timeout_seconds=float(args.pdf_timeout_seconds),
            workers=int(args.workers),
            batch_size=int(args.batch_size),
        )
        mismatch = mismatch_counts(conn)
        replayed_locator_rows = int(
            conn.execute("SELECT COUNT(*) FROM replayed").fetchone()[0]
        )
    finally:
        conn.close()
        if temporary:
            work_db.unlink(missing_ok=True)
            work_db.with_suffix(work_db.suffix + "-wal").unlink(missing_ok=True)
            work_db.with_suffix(work_db.suffix + "-shm").unlink(missing_ok=True)
    checks = {
        "source_locator_report_passed": source_report.get("status") == "ok",
        "locator_generation_full_shard_validation_passed": True,
        "every_content_object_raw_and_native_rehashed": replayed == content_objects
        and not failures,
        "every_locator_recomputed_exactly": (
            actual_rows == mismatch["expected_instance_locator_rows"]
            and mismatch["missing_rows"] == 0
            and mismatch["unexpected_rows"] == 0
            and mismatch["mismatched_rows"] == 0
        ),
        "no_public_text_copied_into_manifest": True,
        "no_synthetic_or_mock_records": True,
        "official_public_domain_personal_information_retained": True,
    }
    elapsed = time.monotonic() - started
    report = {
        "schema_version": VALIDATION_SCHEMA,
        "generated_at": utc_now(),
        "status": "ok" if all(checks.values()) else "failed",
        "mode": {
            "full_manifest_shard_check": True,
            "full_raw_checksum_check": True,
            "full_native_text_cas_checksum_check": True,
            "full_page_and_span_recomputation": True,
        },
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "locator_rows_copy_no_public_text": True,
            "markup_locators_are_normalized_text_spans_not_semantic_sections": True,
        },
        "inputs": {
            "native_manifest": {
                "path": display_path(native_manifest),
                "bytes": native_manifest.stat().st_size,
                "sha256": sha256_path(native_manifest),
            },
            "locator_manifest": {
                "path": display_path(locator_manifest),
                "bytes": locator_manifest.stat().st_size,
                "sha256": sha256_path(locator_manifest),
                "logical_sha256": index.get("logical_sha256"),
            },
            "locator_report": {
                "path": display_path(source_report_path),
                "bytes": source_report_path.stat().st_size,
                "sha256": sha256_path(source_report_path),
            },
        },
        "configuration": dict(configuration),
        "totals": {
            "native_file_instances": native_rows,
            "distinct_content_objects": content_objects,
            "content_objects_replayed": replayed,
            "replayed_content_locator_rows": replayed_locator_rows,
            "observed_instance_locator_rows": actual_rows,
            "raw_bytes_rehashed": raw_bytes,
            "native_text_bytes_rehashed": native_bytes,
            "validation_failures": len(failures),
            **mismatch,
        },
        "failure_samples": failures,
        "performance": {
            **usage(),
            "elapsed_seconds": round(elapsed, 6),
            "content_objects_per_second": round(replayed / elapsed, 6)
            if elapsed
            else 0.0,
        },
        "checks": checks,
        "next_action": (
            "Bind locator generation and lifecycle into central readiness, then use "
            "page/span addresses in evidence exports and citizen drill-downs."
        ),
    }
    write_json_atomic(report_out, report)
    if args.enforce and report["status"] != "ok":
        raise LocatorValidationError("document text locator validation failed")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = validate(args)
    except (
        OSError,
        sqlite3.Error,
        GenerationManifestError,
        LocatorValidationError,
    ) as exc:
        print(f"document text locator validation failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "content_objects_replayed": report["totals"][
                    "content_objects_replayed"
                ],
                "instance_locator_rows": report["totals"][
                    "observed_instance_locator_rows"
                ],
                "report": display_path(Path(args.report_out)),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
