#!/usr/bin/env python3
"""Classify language and encryption for every current real document instance."""

from __future__ import annotations

import argparse
import json
import os
import resource
import sqlite3
import sys
import tempfile
import time
import uuid
from collections import Counter
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.document_profile import (
    DEFAULT_MIN_ALPHA_CHARS,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_MARGIN,
    DEFAULT_SAMPLE_BYTES,
    LANGUAGE_MODEL,
    LANGUAGE_MODEL_VERSION,
    PROFILE_ALGORITHM_VERSION,
    DocumentProfileError,
    profile_document_content,
    safe_child,
    sha256_path,
    validate_profile_runtime,
)
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    iter_generation_rows,
    publish_generation_manifest,
)

DEFAULT_RAW_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY = Path("etl/data/manifests/real-document-format-inventory.jsonl")
DEFAULT_NATIVE_MANIFEST = Path(
    "etl/data/published/real-document-text-manifest-latest.jsonl"
)
DEFAULT_NATIVE_ROOT = Path("etl/data/derived/real-document-text-corpus-v2")
DEFAULT_STATE_DB = Path("etl/data/staging/real-document-profile-v1.db")
DEFAULT_MANIFEST = Path(
    "etl/data/published/real-document-profile-manifest-latest.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-language-encryption-profile.json"
)
ROW_SCHEMA = "real_document_profile_manifest_row_v2"
REPORT_SCHEMA = "real_document_language_encryption_profile_v2"
DATASET = "document_profile"
OFFICE_DOCUMENT_EXTENSIONS = frozenset(
    {"doc", "docx", "odt", "rtf", "xls", "xlsx", "ods", "ppt", "pptx", "odp"}
)

_MACHINE_STATUS_ALIASES = {
    "detected": "candidate_threshold_passed",
    "low_confidence": "candidate_below_threshold",
    "insufficient_alphabetic_text": "insufficient_alphabetic_text",
}


def _machine_status(value: Any) -> str:
    status = str(value or "")
    return _MACHINE_STATUS_ALIASES.get(status, status)


def _language_evidence_status(
    machine_candidate: str,
    source_declared_language: str | None,
) -> str:
    if source_declared_language and machine_candidate != "und":
        return (
            "source_declared_model_agree"
            if source_declared_language == machine_candidate
            else "source_declared_model_conflict"
        )
    if source_declared_language:
        return "source_declared_only"
    if machine_candidate != "und":
        return "machine_candidate_only_unreviewed"
    return "unknown_unreviewed"


class ProfileRunError(RuntimeError):
    """Raised when the exact production profile cannot be built."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def process_usage() -> dict[str, float | int]:
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    multiplier = 1 if sys.platform == "darwin" else 1024
    return {
        "cpu_seconds": float(
            own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime
        ),
        "peak_rss_bytes_self": int(own.ru_maxrss * multiplier),
        "peak_rss_bytes_child_max": int(children.ru_maxrss * multiplier),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--native-manifest", default=str(DEFAULT_NATIVE_MANIFEST))
    parser.add_argument("--native-root", default=str(DEFAULT_NATIVE_ROOT))
    parser.add_argument("--state-db", default=str(DEFAULT_STATE_DB))
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--claim-size", type=int, default=64)
    parser.add_argument("--max-items", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--sample-bytes", type=int, default=DEFAULT_SAMPLE_BYTES)
    parser.add_argument("--min-alpha-chars", type=int, default=DEFAULT_MIN_ALPHA_CHARS)
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    parser.add_argument("--min-margin", type=float, default=DEFAULT_MIN_MARGIN)
    parser.add_argument("--pdf-timeout", type=float, default=60.0)
    parser.add_argument("--manifest-shard-max-rows", type=int, default=10_000)
    parser.add_argument(
        "--manifest-shard-max-uncompressed-bytes",
        type=int,
        default=64 * 1024 * 1024,
    )
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def open_state(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profile_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS document_instances (
          path TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          extension TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          source_group TEXT NOT NULL,
          native_seen INTEGER NOT NULL DEFAULT 0,
          native_text_sha256 TEXT,
          native_text_cas_path TEXT,
          native_text_chars INTEGER,
          CHECK (native_seen IN (0, 1)),
          CHECK (bytes >= 0)
        );

        CREATE INDEX IF NOT EXISTS idx_document_instances_content
          ON document_instances(content_sha256);
        CREATE INDEX IF NOT EXISTS idx_document_instances_source
          ON document_instances(source_group);

        CREATE TABLE IF NOT EXISTS document_profile_work (
          content_sha256 TEXT PRIMARY KEY,
          representative_path TEXT NOT NULL,
          extension TEXT NOT NULL,
          native_text_sha256 TEXT NOT NULL,
          native_text_cas_path TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending',
          attempts INTEGER NOT NULL DEFAULT 0,
          max_attempts INTEGER NOT NULL,
          lease_owner TEXT,
          lease_expires_at TEXT,
          started_at TEXT,
          finished_at TEXT,
          updated_at TEXT,
          detected_language TEXT,
          language_status TEXT,
          language_confidence REAL,
          language_margin REAL,
          language_runner_up TEXT,
          declared_language TEXT,
          language_reconciliation TEXT,
          encryption_status TEXT,
          language_sample_bytes INTEGER,
          language_sample_sha256 TEXT,
          language_sample_alphabetic_chars INTEGER,
          native_text_bytes INTEGER,
          native_text_sha256_verified TEXT,
          last_error TEXT,
          CHECK (state IN ('pending', 'leased', 'succeeded', 'dead')),
          CHECK (attempts >= 0),
          CHECK (max_attempts >= 1)
        );

        CREATE INDEX IF NOT EXISTS idx_document_profile_work_state
          ON document_profile_work(state, content_sha256);
        """
    )
    conn.commit()


def _metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row["key"]): str(row["value"])
        for row in conn.execute("SELECT key, value FROM profile_metadata")
    }


def _configuration(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "language_model": LANGUAGE_MODEL,
        "language_model_version": LANGUAGE_MODEL_VERSION,
        "profile_algorithm_version": PROFILE_ALGORITHM_VERSION,
        "sample_bytes": int(args.sample_bytes),
        "min_alpha_chars": int(args.min_alpha_chars),
        "min_confidence": float(args.min_confidence),
        "min_margin": float(args.min_margin),
        "pdf_timeout": float(args.pdf_timeout),
    }


def _load_inventory(conn: sqlite3.Connection, path: Path) -> int:
    rows = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProfileRunError(
                    f"invalid inventory row {line_number}: {exc}"
                ) from exc
            relative = str(item.get("path") or "")
            content_sha256 = str(item.get("sha256") or "").lower()
            if (
                not relative
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
                or len(content_sha256) != 64
                or item.get("status") != "ok"
                or item.get("real_data_status") != "eligible_real_capture"
                or item.get("accountability_eligible") is not True
            ):
                raise ProfileRunError(f"invalid real inventory row: {relative}")
            conn.execute(
                """
                INSERT INTO document_instances (
                  path, content_sha256, bytes, extension, mime_type, source_group
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    relative,
                    content_sha256,
                    int(item.get("bytes") or 0),
                    str(item.get("extension") or ""),
                    str(item.get("mime_type") or ""),
                    str(item.get("source_group") or ""),
                ),
            )
            rows += 1
            if rows % 10_000 == 0:
                conn.commit()
    conn.commit()
    return rows


def _load_native_manifest(conn: sqlite3.Connection, path: Path) -> int:
    rows = 0
    try:
        iterator = iter_generation_rows(
            path,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
            allow_legacy_jsonl=False,
        )
        for item in iterator:
            relative = str(item.get("path") or "")
            if (
                item.get("synthetic_or_mock") is not False
                or item.get("official_public_domain_personal_information_retained")
                is not True
                or item.get("work_state") != "succeeded"
                or item.get("native_extraction_status") != "native_text_extracted"
                or item.get("native_text_truncated") is not False
            ):
                raise ProfileRunError(f"native manifest row is not usable: {relative}")
            cursor = conn.execute(
                """
                UPDATE document_instances
                SET native_seen = 1, native_text_sha256 = ?,
                    native_text_cas_path = ?, native_text_chars = ?
                WHERE path = ? AND content_sha256 = ? AND bytes = ?
                  AND native_seen = 0
                """,
                (
                    str(item.get("native_text_sha256") or ""),
                    str(item.get("native_text_cas_path") or ""),
                    int(item.get("native_text_chars") or 0),
                    relative,
                    str(item.get("content_sha256") or ""),
                    int(item.get("bytes") or 0),
                ),
            )
            if cursor.rowcount != 1:
                raise ProfileRunError(f"native/inventory mismatch: {relative}")
            rows += 1
            if rows % 10_000 == 0:
                conn.commit()
    except GenerationManifestError as exc:
        raise ProfileRunError(f"invalid native generation: {exc}") from exc
    conn.commit()
    return rows


def seed_state(
    conn: sqlite3.Connection,
    *,
    inventory: Path,
    native_manifest: Path,
    args: argparse.Namespace,
) -> dict[str, int]:
    expected_metadata = {
        "inventory_sha256": sha256_path(inventory),
        "native_manifest_sha256": sha256_path(native_manifest),
        "configuration_json": json.dumps(
            _configuration(args), sort_keys=True, separators=(",", ":")
        ),
    }
    existing = _metadata(conn)
    if existing.get("seed_complete") == "1":
        if any(existing.get(key) != value for key, value in expected_metadata.items()):
            raise ProfileRunError(
                "classification inputs/configuration drifted; use a new state database"
            )
        return {
            "file_instances": int(
                conn.execute("SELECT COUNT(*) FROM document_instances").fetchone()[0]
            ),
            "content_objects": int(
                conn.execute("SELECT COUNT(*) FROM document_profile_work").fetchone()[0]
            ),
        }
    conn.execute("DELETE FROM document_profile_work")
    conn.execute("DELETE FROM document_instances")
    conn.execute("DELETE FROM profile_metadata")
    conn.executemany(
        "INSERT INTO profile_metadata (key, value) VALUES (?, ?)",
        [*expected_metadata.items(), ("seed_complete", "0")],
    )
    conn.commit()
    inventory_rows = _load_inventory(conn, inventory)
    native_rows = _load_native_manifest(conn, native_manifest)
    missing_native = int(
        conn.execute(
            "SELECT COUNT(*) FROM document_instances WHERE native_seen = 0"
        ).fetchone()[0]
    )
    if inventory_rows != native_rows or missing_native:
        raise ProfileRunError(
            "inventory/native manifest sets do not reconcile: "
            f"{inventory_rows}/{native_rows}/{missing_native}"
        )
    conn.execute(
        """
        INSERT INTO document_profile_work (
          content_sha256, representative_path, extension,
          native_text_sha256, native_text_cas_path, max_attempts, updated_at
        )
        SELECT content_sha256, MIN(path), MIN(extension),
               MIN(native_text_sha256), MIN(native_text_cas_path), ?, ?
        FROM document_instances
        GROUP BY content_sha256
        HAVING COUNT(DISTINCT extension) = 1
           AND COUNT(DISTINCT native_text_sha256) = 1
           AND COUNT(DISTINCT native_text_cas_path) = 1
        """,
        (int(args.max_attempts), utc_now()),
    )
    content_objects = int(
        conn.execute(
            "SELECT COUNT(DISTINCT content_sha256) FROM document_instances"
        ).fetchone()[0]
    )
    work_objects = int(
        conn.execute("SELECT COUNT(*) FROM document_profile_work").fetchone()[0]
    )
    if content_objects != work_objects:
        raise ProfileRunError("content deduplication contract drifted")
    conn.execute("UPDATE profile_metadata SET value = '1' WHERE key = 'seed_complete'")
    conn.commit()
    return {"file_instances": inventory_rows, "content_objects": content_objects}


def reclaim_expired(conn: sqlite3.Connection) -> int:
    now = utc_now()
    cursor = conn.execute(
        """
        UPDATE document_profile_work
        SET state = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'pending' END,
            lease_owner = NULL, lease_expires_at = NULL, updated_at = ?,
            last_error = COALESCE(last_error, 'expired_lease_reclaimed')
        WHERE state = 'leased' AND lease_expires_at < ?
        """,
        (now, now),
    )
    conn.commit()
    return int(cursor.rowcount)


def claim_work(
    conn: sqlite3.Connection,
    *,
    owner: str,
    limit: int,
    lease_seconds: int,
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows = conn.execute(
        """
        SELECT content_sha256, representative_path, extension,
               native_text_sha256, native_text_cas_path, attempts, max_attempts
        FROM document_profile_work
        WHERE state = 'pending' AND attempts < max_attempts
        ORDER BY content_sha256
        LIMIT ?
        """,
        (max(1, limit),),
    ).fetchall()
    if not rows:
        return []
    now_iso = now.isoformat().replace("+00:00", "Z")
    expires = (
        (now + timedelta(seconds=max(1, lease_seconds)))
        .isoformat()
        .replace("+00:00", "Z")
    )
    conn.executemany(
        """
        UPDATE document_profile_work
        SET state = 'leased', attempts = attempts + 1, lease_owner = ?,
            lease_expires_at = ?, started_at = COALESCE(started_at, ?),
            updated_at = ?
        WHERE content_sha256 = ? AND state = 'pending'
        """,
        [
            (owner, expires, now_iso, now_iso, str(row["content_sha256"]))
            for row in rows
        ],
    )
    conn.commit()
    return [dict(row) for row in rows]


def _profile_one(
    row: Mapping[str, Any],
    *,
    raw_root: Path,
    native_root: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    raw_path = safe_child(raw_root, str(row["representative_path"]))
    text_path = safe_child(native_root, str(row["native_text_cas_path"]))
    if not raw_path.is_file() or not text_path.is_file():
        raise ProfileRunError(f"profile input missing: {row['representative_path']}")
    result = profile_document_content(
        raw_path=raw_path,
        content_sha256=str(row["content_sha256"]),
        extension=str(row["extension"]),
        text_cas_path=text_path,
        text_sha256=str(row["native_text_sha256"]),
        sample_bytes=int(args.sample_bytes),
        min_alpha_chars=int(args.min_alpha_chars),
        min_confidence=float(args.min_confidence),
        min_margin=float(args.min_margin),
        pdf_timeout=float(args.pdf_timeout),
    )
    return {"content_sha256": str(row["content_sha256"]), **result}


def persist_result(
    conn: sqlite3.Connection,
    *,
    owner: str,
    content_sha256: str,
    result: Mapping[str, Any] | None,
    error: str | None,
) -> str:
    now = utc_now()
    row = conn.execute(
        "SELECT attempts, max_attempts FROM document_profile_work "
        "WHERE content_sha256 = ? AND state = 'leased' AND lease_owner = ?",
        (content_sha256, owner),
    ).fetchone()
    if row is None:
        raise ProfileRunError(f"lost profile lease: {content_sha256}")
    if result is None:
        state = (
            "dead" if int(row["attempts"]) >= int(row["max_attempts"]) else "pending"
        )
        conn.execute(
            """
            UPDATE document_profile_work
            SET state = ?, lease_owner = NULL, lease_expires_at = NULL,
                updated_at = ?, last_error = ?
            WHERE content_sha256 = ? AND lease_owner = ?
            """,
            (state, now, error, content_sha256, owner),
        )
        conn.commit()
        return state
    conn.execute(
        """
        UPDATE document_profile_work
        SET state = 'succeeded', lease_owner = NULL, lease_expires_at = NULL,
            finished_at = ?, updated_at = ?, detected_language = ?,
            language_status = ?, language_confidence = ?, language_margin = ?,
            language_runner_up = ?, declared_language = ?,
            language_reconciliation = ?, encryption_status = ?,
            language_sample_bytes = ?, language_sample_sha256 = ?,
            language_sample_alphabetic_chars = ?, native_text_bytes = ?,
            native_text_sha256_verified = ?, last_error = NULL
        WHERE content_sha256 = ? AND lease_owner = ?
        """,
        (
            now,
            now,
            result["machine_language_candidate"],
            result["machine_language_status"],
            result["machine_language_confidence"],
            result["machine_language_margin"],
            result["machine_language_runner_up"],
            result["source_declared_language"],
            result["language_evidence_status"],
            result["encryption_status"],
            result["language_sample_bytes"],
            result["language_sample_sha256"],
            result["language_sample_alphabetic_chars"],
            result["native_text_bytes"],
            result["native_text_sha256_verified"],
            content_sha256,
            owner,
        ),
    )
    conn.commit()
    return "succeeded"


def run_queue(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    native_root: Path,
    args: argparse.Namespace,
) -> dict[str, int]:
    owner = uuid.uuid4().hex
    totals: Counter[str] = Counter()
    totals["expired_leases_reclaimed"] = reclaim_expired(conn)
    processed = 0
    next_progress = 10_000
    while int(args.max_items) <= 0 or processed < int(args.max_items):
        remaining = (
            int(args.claim_size)
            if int(args.max_items) <= 0
            else min(int(args.claim_size), int(args.max_items) - processed)
        )
        claimed = claim_work(
            conn,
            owner=owner,
            limit=remaining,
            lease_seconds=int(args.lease_seconds),
        )
        if not claimed:
            break
        with ThreadPoolExecutor(max_workers=max(1, int(args.workers))) as executor:
            futures = {
                executor.submit(
                    _profile_one,
                    row,
                    raw_root=raw_root,
                    native_root=native_root,
                    args=args,
                ): row
                for row in claimed
            }
            for future in as_completed(futures):
                row = futures[future]
                content_sha256 = str(row["content_sha256"])
                try:
                    result = future.result()
                    state = persist_result(
                        conn,
                        owner=owner,
                        content_sha256=content_sha256,
                        result=result,
                        error=None,
                    )
                except Exception as exc:  # noqa: BLE001 - persisted exact failure
                    state = persist_result(
                        conn,
                        owner=owner,
                        content_sha256=content_sha256,
                        result=None,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                totals[state] += 1
                processed += 1
        if processed >= next_progress:
            print(
                json.dumps(
                    {"stage": "document_profile", "processed_this_run": processed},
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )
            while next_progress <= processed:
                next_progress += 10_000
    totals["processed"] = processed
    return dict(totals)


def iter_manifest_rows(conn: sqlite3.Connection) -> Iterator[dict[str, Any]]:
    cursor = conn.execute(
        """
        SELECT i.path, i.content_sha256, i.bytes, i.extension, i.mime_type,
               i.source_group, i.native_text_sha256, i.native_text_chars,
               w.detected_language, w.language_status, w.language_confidence,
               w.language_margin, w.language_runner_up, w.declared_language,
               w.language_reconciliation, w.encryption_status,
               w.language_sample_bytes, w.language_sample_sha256,
               w.language_sample_alphabetic_chars, w.native_text_bytes,
               w.native_text_sha256_verified
        FROM document_instances i
        JOIN document_profile_work w USING (content_sha256)
        WHERE w.state = 'succeeded'
        ORDER BY i.path
        """
    )
    for row in cursor:
        machine_candidate = str(row["detected_language"] or "und")
        source_declared_language = (
            str(row["declared_language"]) if row["declared_language"] else None
        )
        yield {
            "schema_version": ROW_SCHEMA,
            "path": row["path"],
            "source_group": row["source_group"],
            "extension": row["extension"],
            "mime_type": row["mime_type"],
            "bytes": int(row["bytes"]),
            "content_sha256": row["content_sha256"],
            "native_text_sha256": row["native_text_sha256"],
            "native_text_chars": int(row["native_text_chars"] or 0),
            "native_text_bytes": int(row["native_text_bytes"]),
            "native_text_sha256_verified": row["native_text_sha256_verified"],
            "machine_language_candidate": machine_candidate,
            "machine_language_status": _machine_status(row["language_status"]),
            "machine_language_confidence": row["language_confidence"],
            "machine_language_margin": row["language_margin"],
            "machine_language_runner_up": row["language_runner_up"],
            "source_declared_language": source_declared_language,
            "language_evidence_status": _language_evidence_status(
                machine_candidate,
                source_declared_language,
            ),
            "language_review_status": "unreviewed",
            "language_model": LANGUAGE_MODEL,
            "language_model_version": LANGUAGE_MODEL_VERSION,
            "profile_algorithm_version": PROFILE_ALGORITHM_VERSION,
            "language_sample_bytes": int(row["language_sample_bytes"]),
            "language_sample_sha256": row["language_sample_sha256"],
            "language_sample_alphabetic_chars": int(
                row["language_sample_alphabetic_chars"]
            ),
            "encryption_status": row["encryption_status"],
            "synthetic_or_mock": False,
            "official_public_domain_personal_information_retained": True,
        }


def _terminal(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN state = 'succeeded' THEN 1 ELSE 0 END) AS succeeded
        FROM document_profile_work
        """
    ).fetchone()
    return int(row["total"] or 0) > 0 and int(row["total"] or 0) == int(
        row["succeeded"] or 0
    )


def write_manifest(
    conn: sqlite3.Connection,
    *,
    path: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    manifest = publish_generation_manifest(
        manifest_path=path,
        rows=iter_manifest_rows(conn),
        dataset=DATASET,
        row_schema_version=ROW_SCHEMA,
        state_connection=conn,
        max_rows=int(args.manifest_shard_max_rows),
        max_uncompressed_bytes=int(args.manifest_shard_max_uncompressed_bytes),
        policy={
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "language_is_probabilistic_and_uncertainty_is_retained": True,
            "machine_language_candidates_are_not_human_ground_truth": True,
            "language_review_status_is_explicit": True,
            "encryption_is_observed_from_raw_bytes": True,
            "automatic_deletion_forbidden": True,
        },
    )
    manifest["path"] = display_path(path)
    return manifest


def _counts(conn: sqlite3.Connection, column: str) -> dict[str, int]:
    allowed = {
        "detected_language",
        "language_status",
        "declared_language",
        "language_reconciliation",
        "encryption_status",
        "state",
    }
    if column not in allowed:
        raise ProfileRunError(f"unsafe aggregation column: {column}")
    return {
        str(row["value"] if row["value"] is not None else "null"): int(row["total"])
        for row in conn.execute(
            f"SELECT {column} AS value, COUNT(*) AS total "
            f"FROM document_profile_work GROUP BY {column} ORDER BY {column}"
        )
    }


def build_report(
    conn: sqlite3.Connection,
    *,
    args: argparse.Namespace,
    inventory: Path,
    native_manifest: Path,
    state_db: Path,
    manifest: Mapping[str, Any] | None,
    seed: Mapping[str, int],
    run: Mapping[str, int],
    elapsed: float,
    usage: Mapping[str, Any],
) -> dict[str, Any]:
    state_counts = _counts(conn, "state")
    file_instances = int(
        conn.execute("SELECT COUNT(*) FROM document_instances").fetchone()[0]
    )
    content_objects = int(
        conn.execute("SELECT COUNT(*) FROM document_profile_work").fetchone()[0]
    )
    succeeded_objects = state_counts.get("succeeded", 0)
    profiled_instances = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM document_instances i
            JOIN document_profile_work w USING (content_sha256)
            WHERE w.state = 'succeeded'
            """
        ).fetchone()[0]
    )
    pdf_instances = int(
        conn.execute(
            "SELECT COUNT(*) FROM document_instances WHERE extension = 'pdf'"
        ).fetchone()[0]
    )
    encrypted_pdf_instances = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM document_instances i
            JOIN document_profile_work w USING (content_sha256)
            WHERE i.extension = 'pdf' AND w.encryption_status = 'encrypted'
            """
        ).fetchone()[0]
    )
    language_counts = {
        str(row["detected_language"]): int(row["total"])
        for row in conn.execute(
            """
            SELECT w.detected_language, COUNT(*) AS total
            FROM document_instances i
            JOIN document_profile_work w USING (content_sha256)
            WHERE w.state = 'succeeded'
            GROUP BY w.detected_language ORDER BY w.detected_language
            """
        )
    }
    machine_status_counts = {
        _machine_status(row["language_status"]): int(row["total"])
        for row in conn.execute(
            """
            SELECT w.language_status, COUNT(*) AS total
            FROM document_profile_work w
            GROUP BY w.language_status ORDER BY w.language_status
            """
        )
    }
    declared_language_counts = _counts(conn, "declared_language")
    language_evidence_counts: Counter[str] = Counter()
    for row in conn.execute(
        """
        SELECT detected_language, declared_language, COUNT(*) AS total
        FROM document_profile_work
        GROUP BY detected_language, declared_language
        """
    ):
        language_evidence_counts[
            _language_evidence_status(
                str(row["detected_language"] or "und"),
                str(row["declared_language"]) if row["declared_language"] else None,
            )
        ] += int(row["total"])
    encryption_counts = {
        str(row["encryption_status"]): int(row["total"])
        for row in conn.execute(
            """
            SELECT w.encryption_status, COUNT(*) AS total
            FROM document_instances i
            JOIN document_profile_work w USING (content_sha256)
            WHERE w.state = 'succeeded'
            GROUP BY w.encryption_status ORDER BY w.encryption_status
            """
        )
    }
    extension_counts = {
        str(row["extension"]): int(row["total"])
        for row in conn.execute(
            "SELECT extension, COUNT(*) AS total FROM document_instances "
            "GROUP BY extension ORDER BY extension"
        )
    }
    office_format_instances = sum(
        total
        for extension, total in extension_counts.items()
        if extension.casefold().lstrip(".") in OFFICE_DOCUMENT_EXTENSIONS
    )
    terminal = _terminal(conn)
    checks = {
        "inventory_and_native_generation_bound_by_sha256": (
            _metadata(conn).get("inventory_sha256") == sha256_path(inventory)
            and _metadata(conn).get("native_manifest_sha256")
            == sha256_path(native_manifest)
        ),
        "every_file_instance_profiled": profiled_instances == file_instances,
        "every_content_object_terminal_success": terminal,
        "manifest_contains_every_file_instance": (
            manifest is not None and int(manifest.get("rows") or 0) == file_instances
        ),
        "machine_language_status_explicit_for_every_profiled_instance": (
            sum(language_counts.values()) == profiled_instances
        ),
        "machine_language_candidates_not_promoted_to_human_ground_truth": True,
        "language_review_status_explicit_and_unreviewed": terminal,
        "encryption_status_explicit_for_every_profiled_instance": (
            sum(encryption_counts.values()) == profiled_instances
        ),
        "file_format_explicit_for_every_profiled_instance": (
            sum(extension_counts.values()) == profiled_instances
        ),
        "every_pdf_encryption_status_observed": (
            int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM document_instances i
                    JOIN document_profile_work w USING (content_sha256)
                    WHERE i.extension = 'pdf'
                      AND w.encryption_status IN ('encrypted', 'not_encrypted')
                    """
                ).fetchone()[0]
            )
            == pdf_instances
        ),
        "no_dead_work": state_counts.get("dead", 0) == 0,
        "no_synthetic_or_mock_records": True,
        "official_public_domain_personal_information_retained": True,
    }
    processed = int(run.get("processed", 0))
    return {
        "schema_version": REPORT_SCHEMA,
        "generated_at": utc_now(),
        "status": "ok" if all(checks.values()) else "partial",
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "public_identity_text_is_not_removed_or_sanitized": True,
            "language_is_probabilistic_not_ground_truth": True,
            "machine_language_candidate_is_not_an_authoritative_language_label": True,
            "all_language_profiles_are_explicitly_unreviewed": True,
            "unknown_language_is_retained_not_imputed": True,
            "classification_is_content_deduplicated": True,
            "raw_and_native_text_bytes_are_fully_rehashed": True,
            "unsupported_formats_are_not_claimed_from_absent_real_data": True,
        },
        "configuration": _configuration(args),
        "inputs": {
            "inventory": {
                "path": display_path(inventory),
                "bytes": inventory.stat().st_size,
                "sha256": sha256_path(inventory),
            },
            "native_manifest": {
                "path": display_path(native_manifest),
                "bytes": native_manifest.stat().st_size,
                "sha256": sha256_path(native_manifest),
            },
        },
        "state": {
            "database": display_path(state_db),
            "state_counts": state_counts,
        },
        "manifest": dict(manifest) if manifest is not None else None,
        "seed": dict(seed),
        "run": dict(run),
        "performance": {
            **dict(usage),
            "elapsed_seconds": round(elapsed, 6),
            "objects_per_second": round(processed / elapsed, 6) if elapsed else 0.0,
        },
        "totals": {
            "file_instances": file_instances,
            "distinct_content_objects": content_objects,
            "duplicate_file_instances": file_instances - content_objects,
            "profiled_file_instances": profiled_instances,
            "profiled_content_objects": succeeded_objects,
            "pdf_file_instances": pdf_instances,
            "office_format_file_instances": office_format_instances,
            "encrypted_pdf_file_instances": encrypted_pdf_instances,
            "machine_language_candidate_file_instances": profiled_instances
            - language_counts.get("und", 0),
            "unknown_language_file_instances": language_counts.get("und", 0),
        },
        "by_machine_language_candidate_file_instances": language_counts,
        "by_machine_language_status_content_objects": machine_status_counts,
        "by_source_declared_language_content_objects": declared_language_counts,
        "by_language_evidence_status_content_objects": dict(
            sorted(language_evidence_counts.items())
        ),
        "by_language_review_status_content_objects": {"unreviewed": succeeded_objects},
        "by_encryption_status_file_instances": encryption_counts,
        "by_format_file_instances": extension_counts,
        "format_coverage": {
            "observed_office_extensions": sorted(
                extension
                for extension in extension_counts
                if extension.casefold().lstrip(".") in OFFICE_DOCUMENT_EXTENSIONS
            ),
            "representative_office_format_cohort_present": office_format_instances > 0,
            "office_extraction_support_claimed": False,
            "reason": (
                "real_office_format_cohort_absent"
                if office_format_instances == 0
                else "real_office_cohort_present_but_not_yet_quality_promoted"
            ),
        },
        "checks": checks,
        "next_action": (
            "Run the independent full-row/full-byte validator, then use the versioned "
            "machine-language/encryption distribution as an input to DEC-01. Treat "
            "every machine-only language label as an unreviewed candidate; human "
            "review remains required before language-quality promotion. Acquire and "
            "validate a representative real office-format cohort before claiming "
            "office extraction support."
        ),
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def run(args: argparse.Namespace) -> dict[str, Any]:
    raw_root = Path(args.raw_root)
    inventory = Path(args.inventory)
    native_manifest = Path(args.native_manifest)
    native_root = Path(args.native_root)
    state_db = Path(args.state_db)
    manifest_path = Path(args.manifest_out)
    report_path = Path(args.report_out)
    if not raw_root.is_dir() or not native_root.is_dir():
        raise ProfileRunError("raw/native roots are missing")
    if not inventory.is_file() or not native_manifest.is_file():
        raise ProfileRunError("inventory/native manifest is missing")
    if int(args.workers) < 1 or int(args.claim_size) < 1:
        raise ProfileRunError("workers and claim-size must be positive")
    validate_profile_runtime()
    start = time.monotonic()
    conn = open_state(state_db)
    try:
        apply_schema(conn)
        seed = seed_state(
            conn,
            inventory=inventory,
            native_manifest=native_manifest,
            args=args,
        )
        queue_result = run_queue(
            conn,
            raw_root=raw_root,
            native_root=native_root,
            args=args,
        )
        manifest: dict[str, Any] | None = None
        if _terminal(conn):
            try:
                manifest = write_manifest(conn, path=manifest_path, args=args)
            except GenerationManifestError as exc:
                raise ProfileRunError(
                    f"cannot publish profile generation: {exc}"
                ) from exc
        report = build_report(
            conn,
            args=args,
            inventory=inventory,
            native_manifest=native_manifest,
            state_db=state_db,
            manifest=manifest,
            seed=seed,
            run=queue_result,
            elapsed=time.monotonic() - start,
            usage=process_usage(),
        )
    finally:
        conn.close()
    write_json_atomic(report_path, report)
    if args.enforce and report["status"] != "ok":
        raise ProfileRunError("document profile is not terminal and complete")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run(args)
    except (OSError, sqlite3.Error, ProfileRunError, DocumentProfileError) as exc:
        print(f"document profile failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "file_instances": report["totals"]["file_instances"],
                "content_objects": report["totals"]["distinct_content_objects"],
                "profiled_file_instances": report["totals"]["profiled_file_instances"],
                "report": display_path(Path(args.report_out)),
                "manifest": (
                    report["manifest"]["path"] if report["manifest"] else None
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
