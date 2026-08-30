#!/usr/bin/env python3
"""Independently rehash and replay every real language/encryption profile."""

from __future__ import annotations

import argparse
import json
import os
import resource
import sqlite3
import sys
import tempfile
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_docs.document_profile import (
    LANGUAGE_MODEL,
    LANGUAGE_MODEL_VERSION,
    PROFILE_ALGORITHM_VERSION,
    DocumentProfileError,
    profile_document_content,
    safe_child,
    sha256_path,
)
from publicdata_docs.generation_manifest import (
    GenerationManifestError,
    iter_generation_rows,
    load_index_bytes,
)
from scripts.classify_real_document_profiles import DATASET, REPORT_SCHEMA, ROW_SCHEMA

DEFAULT_RAW_ROOT = Path("etl/data/raw")
DEFAULT_NATIVE_ROOT = Path("etl/data/derived/real-document-text-corpus-v2")
DEFAULT_NATIVE_MANIFEST = Path(
    "etl/data/published/real-document-text-manifest-latest.jsonl"
)
DEFAULT_PROFILE_MANIFEST = Path(
    "etl/data/published/real-document-profile-manifest-latest.jsonl"
)
DEFAULT_PROFILE_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-language-encryption-profile.json"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-language-encryption-validation.json"
)
VALIDATION_SCHEMA = "real_document_language_encryption_validation_v2"
PROFILE_KEYS = (
    "machine_language_candidate",
    "machine_language_status",
    "machine_language_confidence",
    "machine_language_margin",
    "machine_language_runner_up",
    "source_declared_language",
    "language_evidence_status",
    "language_review_status",
    "encryption_status",
    "language_model",
    "language_model_version",
    "profile_algorithm_version",
    "language_sample_bytes",
    "language_sample_sha256",
    "language_sample_alphabetic_chars",
    "native_text_bytes",
    "native_text_sha256_verified",
)


class ProfileValidationError(RuntimeError):
    """Raised when independent profile validation fails closed."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def usage() -> dict[str, float | int]:
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
    parser.add_argument("--native-root", default=str(DEFAULT_NATIVE_ROOT))
    parser.add_argument("--native-manifest", default=str(DEFAULT_NATIVE_MANIFEST))
    parser.add_argument("--profile-manifest", default=str(DEFAULT_PROFILE_MANIFEST))
    parser.add_argument("--profile-report", default=str(DEFAULT_PROFILE_REPORT))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--work-db", default="")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileValidationError(f"cannot load {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProfileValidationError(f"{label} root is not an object")
    return payload


def profile_projection(item: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item.get(key) for key in PROFILE_KEYS}


def canonical_profile(item: Mapping[str, Any]) -> str:
    return json.dumps(
        profile_projection(item),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def open_work_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript(
        """
        CREATE TABLE expected (
          path TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          extension TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          source_group TEXT NOT NULL,
          native_text_sha256 TEXT NOT NULL,
          native_text_cas_path TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL
        );

        CREATE INDEX idx_expected_content ON expected(content_sha256);

        CREATE TABLE observed (
          path TEXT PRIMARY KEY,
          content_sha256 TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          extension TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          source_group TEXT NOT NULL,
          native_text_sha256 TEXT NOT NULL,
          native_text_chars INTEGER NOT NULL,
          profile_json TEXT NOT NULL
        );

        CREATE INDEX idx_observed_content ON observed(content_sha256);

        CREATE TABLE observed_content (
          content_sha256 TEXT PRIMARY KEY,
          profile_json TEXT NOT NULL
        );
        """
    )
    return conn


def load_expected(conn: sqlite3.Connection, native_manifest: Path) -> int:
    rows = 0
    try:
        iterator = iter_generation_rows(
            native_manifest,
            dataset="native_text",
            row_schema_version="real_document_text_manifest_row_v1",
            allow_legacy_jsonl=False,
        )
        for item in iterator:
            path = str(item.get("path") or "")
            if (
                item.get("synthetic_or_mock") is not False
                or item.get("official_public_domain_personal_information_retained")
                is not True
                or item.get("work_state") != "succeeded"
                or item.get("native_extraction_status") != "native_text_extracted"
                or item.get("native_text_truncated") is not False
                or not item.get("native_text_sha256")
                or not item.get("native_text_cas_path")
            ):
                raise ProfileValidationError(f"invalid native row: {path}")
            conn.execute(
                """
                INSERT INTO expected (
                  path, content_sha256, bytes, extension, mime_type, source_group,
                  native_text_sha256, native_text_cas_path, native_text_chars
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    path,
                    str(item.get("content_sha256") or ""),
                    int(item.get("bytes") or 0),
                    str(item.get("extension") or ""),
                    str(item.get("mime_type") or ""),
                    str(item.get("source_group") or ""),
                    str(item.get("native_text_sha256") or ""),
                    str(item.get("native_text_cas_path") or ""),
                    int(item.get("native_text_chars") or 0),
                ),
            )
            rows += 1
            if rows % 10_000 == 0:
                conn.commit()
    except (GenerationManifestError, sqlite3.IntegrityError) as exc:
        raise ProfileValidationError(f"cannot load native generation: {exc}") from exc
    conn.commit()
    return rows


def load_observed(conn: sqlite3.Connection, profile_manifest: Path) -> int:
    rows = 0
    try:
        iterator = iter_generation_rows(
            profile_manifest,
            dataset=DATASET,
            row_schema_version=ROW_SCHEMA,
            allow_legacy_jsonl=False,
        )
        for item in iterator:
            path = str(item.get("path") or "")
            profile_json = canonical_profile(item)
            if (
                item.get("synthetic_or_mock") is not False
                or item.get("official_public_domain_personal_information_retained")
                is not True
                or item.get("language_model") != LANGUAGE_MODEL
                or item.get("language_model_version") != LANGUAGE_MODEL_VERSION
                or item.get("profile_algorithm_version") != PROFILE_ALGORITHM_VERSION
                or item.get("machine_language_candidate") is None
                or item.get("machine_language_status") is None
                or item.get("language_evidence_status") is None
                or item.get("language_review_status") != "unreviewed"
                or item.get("encryption_status") is None
            ):
                raise ProfileValidationError(f"invalid profile row: {path}")
            conn.execute(
                """
                INSERT INTO observed (
                  path, content_sha256, bytes, extension, mime_type, source_group,
                  native_text_sha256, native_text_chars, profile_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    path,
                    str(item.get("content_sha256") or ""),
                    int(item.get("bytes") or 0),
                    str(item.get("extension") or ""),
                    str(item.get("mime_type") or ""),
                    str(item.get("source_group") or ""),
                    str(item.get("native_text_sha256") or ""),
                    int(item.get("native_text_chars") or 0),
                    profile_json,
                ),
            )
            conn.execute(
                """
                INSERT INTO observed_content (content_sha256, profile_json)
                VALUES (?, ?)
                ON CONFLICT(content_sha256) DO NOTHING
                """,
                (str(item.get("content_sha256") or ""), profile_json),
            )
            retained = conn.execute(
                "SELECT profile_json FROM observed_content WHERE content_sha256 = ?",
                (str(item.get("content_sha256") or ""),),
            ).fetchone()
            if retained is None or str(retained["profile_json"]) != profile_json:
                raise ProfileValidationError(
                    f"duplicate content has inconsistent profile: {path}"
                )
            rows += 1
            if rows % 10_000 == 0:
                conn.commit()
    except (GenerationManifestError, sqlite3.IntegrityError) as exc:
        raise ProfileValidationError(f"cannot load profile generation: {exc}") from exc
    conn.commit()
    return rows


def set_mismatch_count(conn: sqlite3.Connection) -> int:
    expected_missing_or_drifted = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM expected e
            LEFT JOIN observed o USING (path)
            WHERE o.path IS NULL
               OR o.content_sha256 != e.content_sha256
               OR o.bytes != e.bytes
               OR o.extension != e.extension
               OR o.mime_type != e.mime_type
               OR o.source_group != e.source_group
               OR o.native_text_sha256 != e.native_text_sha256
               OR o.native_text_chars != e.native_text_chars
            """
        ).fetchone()[0]
    )
    unexpected = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM observed o
            LEFT JOIN expected e USING (path)
            WHERE e.path IS NULL
            """
        ).fetchone()[0]
    )
    return expected_missing_or_drifted + unexpected


def unique_tasks(conn: sqlite3.Connection) -> sqlite3.Cursor:
    return conn.execute(
        """
        SELECT e.content_sha256, MIN(e.path) AS representative_path,
               MIN(e.extension) AS extension,
               MIN(e.native_text_sha256) AS native_text_sha256,
               MIN(e.native_text_cas_path) AS native_text_cas_path,
               MIN(o.profile_json) AS profile_json,
               COUNT(DISTINCT e.extension) AS extensions,
               COUNT(DISTINCT e.native_text_sha256) AS text_hashes,
               COUNT(DISTINCT e.native_text_cas_path) AS text_paths,
               COUNT(DISTINCT o.profile_json) AS profiles
        FROM expected e
        JOIN observed o USING (path, content_sha256)
        GROUP BY e.content_sha256
        ORDER BY e.content_sha256
        """
    )


def replay_one(
    row: Mapping[str, Any],
    *,
    raw_root: Path,
    native_root: Path,
    configuration: Mapping[str, Any],
) -> str | None:
    if (
        int(row["extensions"]) != 1
        or int(row["text_hashes"]) != 1
        or int(row["text_paths"]) != 1
        or int(row["profiles"]) != 1
    ):
        return f"dedup_contract:{row['content_sha256']}"
    try:
        raw_path = safe_child(raw_root, str(row["representative_path"]))
        text_path = safe_child(native_root, str(row["native_text_cas_path"]))
        replayed = profile_document_content(
            raw_path=raw_path,
            content_sha256=str(row["content_sha256"]),
            extension=str(row["extension"]),
            text_cas_path=text_path,
            text_sha256=str(row["native_text_sha256"]),
            sample_bytes=int(configuration["sample_bytes"]),
            min_alpha_chars=int(configuration["min_alpha_chars"]),
            min_confidence=float(configuration["min_confidence"]),
            min_margin=float(configuration["min_margin"]),
            pdf_timeout=float(configuration["pdf_timeout"]),
        )
    except Exception as exc:  # noqa: BLE001 - exact failure becomes evidence
        return f"{type(exc).__name__}:{row['content_sha256']}:{exc}"
    expected = str(row["profile_json"])
    actual = canonical_profile(replayed)
    if actual != expected:
        return f"profile_mismatch:{row['content_sha256']}"
    return None


def full_replay(
    conn: sqlite3.Connection,
    *,
    raw_root: Path,
    native_root: Path,
    configuration: Mapping[str, Any],
    workers: int,
    batch_size: int,
) -> tuple[int, list[str]]:
    cursor = unique_tasks(conn)
    verified = 0
    failures: list[str] = []
    while True:
        batch = [dict(row) for row in cursor.fetchmany(max(1, batch_size))]
        if not batch:
            break
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(
                    replay_one,
                    row,
                    raw_root=raw_root,
                    native_root=native_root,
                    configuration=configuration,
                ): row
                for row in batch
            }
            for future in as_completed(futures):
                failure = future.result()
                if failure is None:
                    verified += 1
                elif len(failures) < 100:
                    failures.append(failure)
        if verified and verified % 10_000 == 0:
            print(
                json.dumps(
                    {"stage": "document_profile_replay", "verified": verified},
                    sort_keys=True,
                ),
                file=sys.stderr,
                flush=True,
            )
    return verified, failures


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


def validate(args: argparse.Namespace) -> dict[str, Any]:
    raw_root = Path(args.raw_root)
    native_root = Path(args.native_root)
    native_manifest = Path(args.native_manifest)
    profile_manifest = Path(args.profile_manifest)
    profile_report_path = Path(args.profile_report)
    report_out = Path(args.report_out)
    if not raw_root.is_dir() or not native_root.is_dir():
        raise ProfileValidationError("raw/native roots are missing")
    for required in (native_manifest, profile_manifest, profile_report_path):
        if not required.is_file():
            raise ProfileValidationError(f"required profile input missing: {required}")
    source_report = load_json(profile_report_path, "profile report")
    configuration = source_report.get("configuration") or {}
    if (
        source_report.get("schema_version") != REPORT_SCHEMA
        or source_report.get("status") != "ok"
        or configuration.get("language_model") != LANGUAGE_MODEL
        or configuration.get("language_model_version") != LANGUAGE_MODEL_VERSION
        or configuration.get("profile_algorithm_version") != PROFILE_ALGORITHM_VERSION
    ):
        raise ProfileValidationError("profile report contract drifted")
    index = load_index_bytes(
        profile_manifest.read_bytes(),
        dataset=DATASET,
    )
    policy = index.get("policy") or {}
    if (
        index.get("row_schema_version") != ROW_SCHEMA
        or policy.get("official_public_domain_personal_information_retained")
        is not True
        or policy.get("synthetic_or_mock_records_counted") is not False
    ):
        raise ProfileValidationError("profile manifest contract drifted")
    report_manifest = source_report.get("manifest") or {}
    source_inputs = source_report.get("inputs") or {}
    if (
        report_manifest.get("sha256") != sha256_path(profile_manifest)
        or report_manifest.get("logical_sha256") != index.get("logical_sha256")
        or (source_inputs.get("native_manifest") or {}).get("sha256")
        != sha256_path(native_manifest)
    ):
        raise ProfileValidationError("profile report input binding drifted")
    temporary = not bool(args.work_db)
    if temporary:
        descriptor, work_name = tempfile.mkstemp(
            prefix="real-document-profile-validation-", suffix=".db"
        )
        os.close(descriptor)
        work_db = Path(work_name)
    else:
        work_db = Path(args.work_db)
        if work_db.exists():
            raise ProfileValidationError("work database must not already exist")
    started = time.monotonic()
    conn = open_work_db(work_db)
    try:
        expected_rows = load_expected(conn, native_manifest)
        observed_rows = load_observed(conn, profile_manifest)
        mismatches = set_mismatch_count(conn)
        distinct_content = int(
            conn.execute(
                "SELECT COUNT(DISTINCT content_sha256) FROM expected"
            ).fetchone()[0]
        )
        replayed, failures = full_replay(
            conn,
            raw_root=raw_root,
            native_root=native_root,
            configuration=configuration,
            workers=int(args.workers),
            batch_size=int(args.batch_size),
        )
    finally:
        conn.close()
        if temporary:
            work_db.unlink(missing_ok=True)
            work_db.with_suffix(work_db.suffix + "-wal").unlink(missing_ok=True)
            work_db.with_suffix(work_db.suffix + "-shm").unlink(missing_ok=True)
    checks = {
        "source_profile_report_passed": source_report.get("status") == "ok",
        "profile_generation_full_shard_validation_passed": True,
        "native_and_profile_file_sets_match": (
            expected_rows == observed_rows and mismatches == 0
        ),
        "every_distinct_content_object_rehashed_and_reclassified": (
            replayed == distinct_content and not failures
        ),
        "language_model_and_configuration_replayed_exactly": not failures,
        "every_pdf_encryption_status_reobserved_from_raw_bytes": not failures,
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
            "full_language_reclassification": True,
            "full_pdf_encryption_reinspection": True,
        },
        "policy": {
            "official_real_documents_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "unknown_language_is_retained_not_imputed": True,
            "probabilistic_language_is_not_human_ground_truth": True,
            "machine_language_candidates_are_explicitly_unreviewed": True,
        },
        "inputs": {
            "native_manifest": {
                "path": display_path(native_manifest),
                "bytes": native_manifest.stat().st_size,
                "sha256": sha256_path(native_manifest),
            },
            "profile_manifest": {
                "path": display_path(profile_manifest),
                "bytes": profile_manifest.stat().st_size,
                "sha256": sha256_path(profile_manifest),
                "logical_sha256": index.get("logical_sha256"),
            },
            "profile_report": {
                "path": display_path(profile_report_path),
                "bytes": profile_report_path.stat().st_size,
                "sha256": sha256_path(profile_report_path),
            },
        },
        "configuration": dict(configuration),
        "totals": {
            "native_file_instances": expected_rows,
            "profile_file_instances": observed_rows,
            "file_set_mismatches": mismatches,
            "distinct_content_objects": distinct_content,
            "content_objects_rehashed_and_reclassified": replayed,
            "validation_failures": len(failures),
        },
        "failure_samples": failures,
        "performance": {
            **usage(),
            "elapsed_seconds": round(elapsed, 6),
            "objects_per_second": round(replayed / elapsed, 6) if elapsed else 0.0,
        },
        "checks": checks,
        "next_action": (
            "Bind this independent validation and the generation lifecycle audit into "
            "central readiness, then use explicit language/encryption strata in DEC-01."
        ),
    }
    write_json_atomic(report_out, report)
    if args.enforce and report["status"] != "ok":
        raise ProfileValidationError("document profile validation failed")
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = validate(args)
    except (
        OSError,
        sqlite3.Error,
        GenerationManifestError,
        DocumentProfileError,
        ProfileValidationError,
    ) as exc:
        print(f"document profile validation failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "file_instances": report["totals"]["profile_file_instances"],
                "content_objects_replayed": report["totals"][
                    "content_objects_rehashed_and_reclassified"
                ],
                "report": display_path(Path(args.report_out)),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
