#!/usr/bin/env python3
"""Prepare deterministic bounded cohorts of real official documents."""

from __future__ import annotations

import argparse
import fcntl
import gzip
import hashlib
import json
import os
import resource
import secrets
import shutil
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import parse_qs, urlparse


PIPELINE_ID = "real_document_fetch_scale_cohort_v2"
DEFAULT_BOE_DOCUMENT_ROWS = 800
DEFAULT_BOE_SUMMARY_ROWS = 114
EXPECTED_HOST_ROWS = {
    "www.boe.es": 914,
    "www.parlamentodeandalucia.es": 86,
}
KNOWN_BLOCKED_HOSTS = {
    "contrataciondelestado.es",
    "parlamentodenavarra.es",
    "www.congreso.es",
    "www.senado.es",
}
FORBIDDEN_HTML_MARKERS = [
    "cf-mitigated",
    "<title>just a moment...</title>",
    "attention required! | cloudflare",
    "access denied",
]
MAX_PARTITION_ROWS = 250_000
MAX_PARTITION_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_EMBEDDED_ROWS = 25_000
MAX_PROVENANCE_REFS_PER_DOCUMENT = 10_000
PLANNER_SCHEMA_VERSION = "real_document_fetch_disk_planner_v1"
LOCK_SCHEMA_VERSION = "real_document_fetch_prepare_lock_v2"
LOCK_ROOT = Path("etl/data/staging/.real-document-fetch-prepare-locks")
TRANSACTION_SCHEMA_VERSION = "real_document_fetch_prepare_transaction_v1"
TRANSACTION_ROOT = Path("etl/data/staging/.real-document-fetch-prepare-transactions")
RUN_ROOT = Path("etl/data/staging/.real-document-fetch-prepare-runs")


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def peak_rss_bytes() -> int:
    # Linux getrusage may retain a high-water value inherited across fork/exec.
    # VmHWM belongs to the current process memory map, so it measures this CLI
    # rather than the long-lived test or worker process that launched it.
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
                if line.startswith("VmHWM:"):
                    fields = line.split()
                    if len(fields) == 3 and fields[2] == "kB":
                        return int(fields[1]) * 1024
        except (OSError, UnicodeError, ValueError):
            pass
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repository: {path}") from exc


def source_descriptor(path: Path) -> dict[str, Any]:
    return {
        "path": repo_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def validate_unchanged_input(path: Path, expected: dict[str, Any]) -> None:
    actual = source_descriptor(path)
    if actual != expected:
        raise ValueError(f"input changed during cohort preparation: {repo_path(path)}")


def require_checkpointed_sqlite(path: Path) -> None:
    wal_path = Path(f"{path}-wal")
    if wal_path.exists() and wal_path.stat().st_size > 0:
        raise ValueError(
            "source SQLite has an uncheckpointed WAL; create a stable checkpoint "
            f"before cohort preparation: {repo_path(path)}"
        )


def read_only_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA temp_store = FILE")
    conn.execute("BEGIN")
    return conn


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def output_target_hash(path: Path) -> str:
    return hashlib.sha256(repo_path(path).encode("utf-8")).hexdigest()


def release_output_locks(locks: list[tuple[Path, int]]) -> None:
    for _lock_path, descriptor in reversed(locks):
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def acquire_output_locks(targets: list[Path]) -> list[tuple[Path, int]]:
    target_pairs = sorted(
        {(output_target_hash(path), path.resolve()) for path in targets},
        key=lambda row: row[0],
    )
    if len(target_pairs) != len(targets):
        raise ValueError("duplicate output targets are not allowed")
    LOCK_ROOT.mkdir(parents=True, exist_ok=True)
    owner_token = secrets.token_hex(16)
    acquired: list[tuple[Path, int]] = []
    try:
        for target_hash, _target in target_pairs:
            lock_path = LOCK_ROOT / f"{target_hash}.lock"
            payload = {
                "schema_version": LOCK_SCHEMA_VERSION,
                "mechanism": "kernel_advisory_flock",
                "pid": os.getpid(),
                "owner_token": owner_token,
                "created_at": utc_now(),
                "target_sha256": target_hash,
            }
            body = (
                json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                os.close(descriptor)
                raise ValueError(
                    f"output preparation target is actively locked: {target_hash}"
                ) from exc
            try:
                os.ftruncate(descriptor, 0)
                os.write(descriptor, body)
                os.fsync(descriptor)
                fsync_directory(LOCK_ROOT)
            except BaseException:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)
                raise
            acquired.append((lock_path, descriptor))
        return acquired
    except BaseException:
        release_output_locks(acquired)
        raise


def safe_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe repository path: {value}")
    resolved = (Path.cwd() / path).resolve()
    try:
        resolved.relative_to(Path.cwd().resolve())
    except ValueError as exc:
        raise ValueError(f"repository path escapes root: {value}") from exc
    return resolved


def directory_descriptor(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    files = 0
    total_bytes = 0
    for member in sorted(path.rglob("*")):
        if member.is_symlink():
            raise ValueError(f"transaction artifact contains symlink: {repo_path(member)}")
        if not member.is_file():
            continue
        relative = member.relative_to(path).as_posix()
        member_bytes = member.stat().st_size
        member_sha256 = sha256_path(member)
        digest.update(
            (
                json.dumps(
                    {
                        "path": relative,
                        "bytes": member_bytes,
                        "sha256": member_sha256,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        )
        files += 1
        total_bytes += member_bytes
    if files < 1:
        raise ValueError(f"transaction artifact directory is empty: {repo_path(path)}")
    return {
        "kind": "directory",
        "files": files,
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
    }


def artifact_descriptor(path: Path) -> dict[str, Any]:
    if path.is_file() and not path.is_symlink():
        return {
            "kind": "file",
            "bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }
    if path.is_dir() and not path.is_symlink():
        return directory_descriptor(path)
    raise ValueError(f"transaction artifact is missing or unsafe: {repo_path(path)}")


def artifact_matches(path: Path, expected: dict[str, Any]) -> bool:
    try:
        return artifact_descriptor(path) == expected
    except (OSError, ValueError):
        return False


def transaction_bundle_hash(targets: dict[str, Path]) -> str:
    payload = {
        role: repo_path(path) for role, path in sorted(targets.items())
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def transaction_journal_path(targets: dict[str, Path]) -> Path:
    return TRANSACTION_ROOT / f"{transaction_bundle_hash(targets)}.json"


def remove_transaction_artifact(path: Path, expected: dict[str, Any]) -> None:
    if not path.exists():
        return
    if not artifact_matches(path, expected):
        raise ValueError(
            "refusing to remove an incomplete transaction artifact whose content "
            f"does not match its ownership journal: {repo_path(path)}"
        )
    if expected.get("kind") == "directory":
        shutil.rmtree(path)
    else:
        path.unlink()


def recover_stale_transaction(
    *, journal_path: Path, targets: dict[str, Path]
) -> None:
    if not journal_path.exists():
        return
    journal = read_json(journal_path)
    if journal.get("schema_version") != TRANSACTION_SCHEMA_VERSION:
        raise ValueError(f"transaction journal schema mismatch: {journal_path}")
    expected_bundle_hash = transaction_bundle_hash(targets)
    if journal.get("bundle_sha256") != expected_bundle_hash:
        raise ValueError(f"transaction journal target mismatch: {journal_path}")
    expected_targets = {
        role: repo_path(path) for role, path in sorted(targets.items())
    }
    if journal.get("targets") != expected_targets:
        raise ValueError(f"transaction journal path mismatch: {journal_path}")
    artifacts = journal.get("artifacts") or {}
    manifest_path = targets["manifest"]
    manifest_expected = artifacts.get("manifest")
    if manifest_path.exists():
        if not isinstance(manifest_expected, dict) or not artifact_matches(
            manifest_path, manifest_expected
        ):
            raise ValueError(
                "completed-looking manifest does not match its transaction journal; "
                f"manual inspection required: {repo_path(manifest_path)}"
            )
        for role, path in targets.items():
            expected = artifacts.get(role)
            if not isinstance(expected, dict) or not artifact_matches(path, expected):
                raise ValueError(
                    "manifest was published but its transaction bundle is incomplete "
                    f"or changed: {repo_path(path)}"
                )
    else:
        for role in ("partitions", "database"):
            path = targets.get(role)
            if path is None or not path.exists():
                continue
            expected = artifacts.get(role)
            if not isinstance(expected, dict):
                raise ValueError(
                    "incomplete transaction artifact has no ownership descriptor; "
                    f"manual inspection required: {repo_path(path)}"
                )
            remove_transaction_artifact(path, expected)
    run_dir_value = str(journal.get("run_dir") or "")
    if run_dir_value:
        run_dir = safe_repo_path(run_dir_value)
        try:
            run_dir.relative_to(RUN_ROOT.resolve())
        except ValueError as exc:
            raise ValueError("transaction run directory escapes run root") from exc
        if not run_dir.name.startswith(f"{expected_bundle_hash[:20]}-"):
            raise ValueError("transaction run directory ownership mismatch")
        shutil.rmtree(run_dir, ignore_errors=True)
    journal_path.unlink(missing_ok=True)
    fsync_directory(journal_path.parent)


def begin_output_transaction(targets: dict[str, Path]) -> dict[str, Any]:
    TRANSACTION_ROOT.mkdir(parents=True, exist_ok=True)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    bundle_sha256 = transaction_bundle_hash(targets)
    journal_path = transaction_journal_path(targets)
    recover_stale_transaction(journal_path=journal_path, targets=targets)
    run_dir = RUN_ROOT / f"{bundle_sha256[:20]}-{secrets.token_hex(8)}"
    run_dir.mkdir(mode=0o700)
    journal: dict[str, Any] = {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "bundle_sha256": bundle_sha256,
        "pid": os.getpid(),
        "owner_token": secrets.token_hex(16),
        "created_at": utc_now(),
        "state": "preparing",
        "targets": {
            role: repo_path(path) for role, path in sorted(targets.items())
        },
        "run_dir": repo_path(run_dir),
        "artifacts": {},
        "published": [],
        "publish_pending": "",
    }
    try:
        write_json_atomic(journal_path, journal)
    except BaseException:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise
    return {
        "journal_path": journal_path,
        "journal": journal,
        "run_dir": run_dir,
        "targets": targets,
    }


def publish_transaction_artifact(
    transaction: dict[str, Any], *, role: str, staged_path: Path
) -> None:
    journal_path = transaction["journal_path"]
    journal = transaction["journal"]
    target = transaction["targets"][role]
    expected = artifact_descriptor(staged_path)
    journal["artifacts"][role] = expected
    journal["publish_pending"] = role
    write_json_atomic(journal_path, journal)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staged_path, target)
    fsync_directory(target.parent)
    journal["published"].append(role)
    journal["publish_pending"] = ""
    write_json_atomic(journal_path, journal)


def finish_output_transaction(transaction: dict[str, Any]) -> None:
    journal_path = transaction["journal_path"]
    journal = transaction["journal"]
    journal["state"] = "complete"
    write_json_atomic(journal_path, journal)
    shutil.rmtree(transaction["run_dir"], ignore_errors=True)
    journal_path.unlink(missing_ok=True)
    fsync_directory(journal_path.parent)


def rollback_output_transaction(transaction: dict[str, Any]) -> None:
    journal_path = transaction["journal_path"]
    if journal_path.exists():
        recover_stale_transaction(
            journal_path=journal_path,
            targets=transaction["targets"],
        )


def validate_host_health(path: Path) -> dict[str, Any]:
    report = read_json(path)
    if report.get("schema_version") != "real_document_host_health_v1":
        raise ValueError("host health schema mismatch")
    policy = report.get("policy") or {}
    if policy.get("official_real_documents_only") is not True:
        raise ValueError("host health real-document policy mismatch")
    if policy.get("synthetic_or_mock_records_counted") is not False:
        raise ValueError("host health synthetic-data policy mismatch")
    probes = {
        str(row.get("host") or ""): row for row in report.get("probes") or []
    }
    parliament = probes.get("www.parlamentodeandalucia.es") or {}
    if (
        parliament.get("eligible") is not True
        or int(parliament.get("http_status") or 0) != 200
        or parliament.get("validation_mode") != "official_html_semantic_contract"
    ):
        raise ValueError("Parlamento de Andalucia host is not probe-eligible")
    excluded = set(report.get("known_blocked_hosts_excluded_without_probe") or [])
    if not KNOWN_BLOCKED_HOSTS.issubset(excluded):
        raise ValueError("known blocked host exclusion set is incomplete")
    return report


def boe_validation_contract(
    *, source_id: str, expected_bytes: int
) -> dict[str, Any]:
    allowed_types = ["application/xml", "text/xml"]
    if source_id == "boe_daily_summaries":
        allowed_types.extend(["application/json", "text/json"])
    return {
        "require_https": True,
        "expected_host": "www.boe.es",
        "minimum_bytes": max(1, min(expected_bytes, 1024)),
        "allowed_content_types": allowed_types,
    }


def decile_quota(total: int) -> tuple[int, int]:
    if total < 0:
        raise ValueError("row quota cannot be negative")
    return divmod(total, 10)


def open_planner_store(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        PRAGMA journal_mode = DELETE;
        PRAGMA synchronous = FULL;
        PRAGMA temp_store = FILE;

        CREATE TABLE selected_rows (
          source_url TEXT PRIMARY KEY,
          source_pipeline_id TEXT NOT NULL,
          source_id TEXT NOT NULL,
          provenance_source_id TEXT,
          source_host TEXT NOT NULL,
          document_kind TEXT NOT NULL,
          validation_mode TEXT NOT NULL,
          size_decile INTEGER NOT NULL CHECK (size_decile BETWEEN 1 AND 10),
          expected_bytes INTEGER NOT NULL CHECK (expected_bytes > 0),
          expected_content_sha256 TEXT NOT NULL,
          captured_raw_path TEXT NOT NULL,
          partition_key TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );

        CREATE INDEX selected_rows_order_idx
          ON selected_rows(source_pipeline_id, size_decile, source_url);
        CREATE INDEX selected_rows_host_idx
          ON selected_rows(source_host);
        CREATE INDEX selected_rows_mode_idx
          ON selected_rows(validation_mode);

        CREATE TABLE parliament_candidates (
          source_url TEXT PRIMARY KEY,
          declared_bytes INTEGER NOT NULL,
          file_path TEXT NOT NULL,
          file_sha256 TEXT NOT NULL,
          match_basis TEXT NOT NULL,
          source_id TEXT NOT NULL
        );

        CREATE TABLE parliament_candidate_refs (
          source_url TEXT NOT NULL,
          db_ref TEXT NOT NULL,
          table_name TEXT NOT NULL,
          PRIMARY KEY (source_url, db_ref, table_name),
          FOREIGN KEY (source_url) REFERENCES parliament_candidates(source_url)
        );
        """
    )
    return conn


def insert_selected_row(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO selected_rows (
          source_url, source_pipeline_id, source_id, provenance_source_id,
          source_host, document_kind, validation_mode, size_decile,
          expected_bytes, expected_content_sha256, captured_raw_path,
          partition_key, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(row["source_url"]),
            str(row["source_pipeline_id"]),
            str(row["source_id"]),
            row.get("provenance_source_id"),
            str(row["source_host"]),
            str(row["document_kind"]),
            str(row["validation_mode"]),
            int(row["size_decile"]),
            int(row["expected_bytes"]),
            str(row["expected_content_sha256"]),
            str(row["captured_raw_path"]),
            str(row["partition_key"]),
            json.dumps(
                row["payload"],
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ),
        ),
    )


def selected_row_from_sql(
    raw: sqlite3.Row, *, include_reference_edges: bool = True
) -> dict[str, Any]:
    row = dict(raw)
    payload = json.loads(str(row.pop("payload_json")))
    if not isinstance(payload, dict):
        raise ValueError(f"stored queue payload is not an object: {row['source_url']}")
    if row.get("provenance_source_id") is None:
        row.pop("provenance_source_id", None)
    if not include_reference_edges:
        provenance = payload.get("provenance") or {}
        if isinstance(provenance, dict):
            provenance.pop("reference_edges", None)
    row["payload"] = payload
    return row


def iter_selected_rows(
    conn: sqlite3.Connection,
    *,
    include_queue_priority: bool = False,
    include_reference_edges: bool = True,
) -> Iterator[dict[str, Any]]:
    cursor = conn.execute(
        """
        SELECT *
        FROM selected_rows
        ORDER BY source_pipeline_id, size_decile, source_url
        """
    )
    host_ranks: dict[str, int] = {}
    for raw in cursor:
        row = selected_row_from_sql(
            raw,
            include_reference_edges=include_reference_edges,
        )
        if include_queue_priority:
            host = str(row["source_host"])
            host_rank = host_ranks.get(host, 0)
            row["queue_priority"] = -host_rank
            host_ranks[host] = host_rank + 1
        yield row


def grouped_selected_counts(
    conn: sqlite3.Connection, column: str
) -> dict[str, int]:
    allowed = {"source_host", "document_kind", "validation_mode"}
    if column not in allowed:
        raise ValueError(f"unsupported planner count column: {column}")
    return {
        str(row[0]): int(row[1])
        for row in conn.execute(
            f"SELECT {column}, COUNT(*) FROM selected_rows GROUP BY {column}"
        )
    }


def load_boe_rows(
    conn: sqlite3.Connection,
    planner: sqlite3.Connection,
    *,
    document_rows: int,
    summary_rows: int,
    queue_created_before: str,
) -> int:
    document_base, document_extra = decile_quota(document_rows)
    summary_base, summary_extra = decile_quota(summary_rows)
    rows = conn.execute(
        """
        WITH ranked AS (
          SELECT
            w.pipeline_id AS source_pipeline_id,
            w.item_key AS source_url,
            w.payload_json,
            f.source_id,
            f.content_type,
            f.content_sha256,
            f.bytes,
            f.raw_path,
            NTILE(10) OVER (
              PARTITION BY w.pipeline_id
              ORDER BY f.bytes, w.item_key
            ) AS size_decile
          FROM pipeline_work_items w
          JOIN document_fetches f ON f.doc_url = w.item_key
          WHERE w.pipeline_id IN ('boe_document_fetch', 'boe_summary_fetch')
            AND w.created_at <= ?
            AND w.state = 'succeeded'
            AND f.fetched_ok = 1
            AND f.last_http_status = 200
            AND f.doc_url LIKE 'https://www.boe.es/%'
            AND f.content_sha256 IS NOT NULL
            AND f.bytes > 0
            AND f.raw_path IS NOT NULL
        ), numbered AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY source_pipeline_id, size_decile
            ORDER BY source_url
          ) AS row_in_decile
          FROM ranked
        )
        SELECT *
        FROM numbered
        WHERE (
          source_pipeline_id = 'boe_document_fetch'
          AND row_in_decile <= ? + CASE WHEN size_decile <= ? THEN 1 ELSE 0 END
        ) OR (
          source_pipeline_id = 'boe_summary_fetch'
          AND row_in_decile <= ? + CASE WHEN size_decile <= ? THEN 1 ELSE 0 END
        )
        ORDER BY source_pipeline_id, size_decile, source_url
        """,
        (
            queue_created_before,
            document_base,
            document_extra,
            summary_base,
            summary_extra,
        ),
    )
    counts = {
        "boe_document_fetch": 0,
        "boe_summary_fetch": 0,
    }
    for raw in rows:
        row = dict(raw)
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, dict):
            raise ValueError(f"queue payload is not an object: {row['source_url']}")
        source_pipeline_id = str(row["source_pipeline_id"])
        expected_source_id = (
            "boe_document_xml"
            if source_pipeline_id == "boe_document_fetch"
            else "boe_daily_summaries"
        )
        source_url = str(row["source_url"])
        if str(row["source_id"]) != expected_source_id:
            raise ValueError(f"BOE source mismatch: {source_url}")
        if str(payload.get("document_source_id") or "") != expected_source_id:
            raise ValueError(f"BOE payload source mismatch: {source_url}")
        if payload.get("synthetic_or_mock_records_counted") is not False:
            raise ValueError(f"BOE real-data policy mismatch: {source_url}")
        if payload.get("official_public_domain_personal_information_retained") is not True:
            raise ValueError(f"BOE public-information policy mismatch: {source_url}")
        raw_path = Path(str(row["raw_path"]))
        expected_bytes = int(row["bytes"])
        expected_sha256 = str(row["content_sha256"])
        if not raw_path.is_file() or raw_path.stat().st_size != expected_bytes:
            raise ValueError(f"BOE captured raw size mismatch: {source_url}")
        if sha256_path(raw_path) != expected_sha256:
            raise ValueError(f"BOE captured raw hash mismatch: {source_url}")
        payload = {
            **payload,
            "validation_contract": boe_validation_contract(
                source_id=expected_source_id,
                expected_bytes=expected_bytes,
            ),
        }
        insert_selected_row(
            planner,
            {
                "source_pipeline_id": source_pipeline_id,
                "source_id": expected_source_id,
                "source_url": source_url,
                "source_host": "www.boe.es",
                "document_kind": (
                    "boe_document_xml"
                    if source_pipeline_id == "boe_document_fetch"
                    else "boe_daily_summary"
                ),
                "validation_mode": (
                    "boe_document_identifier"
                    if source_pipeline_id == "boe_document_fetch"
                    else "boe_summary_structure"
                ),
                "size_decile": int(row["size_decile"]),
                "expected_bytes": expected_bytes,
                "expected_content_sha256": expected_sha256,
                "captured_raw_path": repo_path(raw_path),
                "partition_key": f"{source_pipeline_id}:size_decile_{row['size_decile']}",
                "payload": payload,
            },
        )
        counts[source_pipeline_id] += 1
    expected = {
        "boe_document_fetch": document_rows,
        "boe_summary_fetch": summary_rows,
    }
    if counts != expected:
        raise ValueError(f"BOE row allocation mismatch: expected={expected} actual={counts}")
    planner.commit()
    return sum(counts.values())


def safe_capture_path(raw_root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe provenance capture path: {value}")
    path = (raw_root / relative).resolve()
    try:
        path.relative_to(raw_root.resolve())
    except ValueError as exc:
        raise ValueError(f"provenance capture escapes raw root: {value}") from exc
    return path


def parliament_validation_contract(
    *, source_url: str, document_kind: str
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "require_https": True,
        "expected_host": "www.parlamentodeandalucia.es",
        "minimum_bytes": 8192,
        "forbidden_ascii_casefolded": FORBIDDEN_HTML_MARKERS,
    }
    if document_kind == "pdf":
        return {
            **base,
            "required_ascii_casefolded": ["%pdf-"],
        }
    references = parse_qs(urlparse(source_url).query).get("numexp") or []
    if len(references) == 1 and str(references[0]).strip():
        required = ["<!doctype html", str(references[0]).lower()]
    elif "resultadosvotaciones.do" in urlparse(source_url).path:
        required = ["<!doctype html", "<title>sentido del voto", "votaciones"]
    elif "todaslasiniciativas/portipo.do" in urlparse(source_url).path:
        required = ["<!doctype html", "iniciativas", "legislatura"]
    else:
        raise ValueError(f"Parlamento HTML URL lacks a semantic contract: {source_url}")
    return {
        **base,
        "allowed_content_types": ["text/html"],
        "required_ascii_casefolded": required,
    }


def load_parliament_rows(
    edges_path: Path, raw_root: Path, planner: sqlite3.Connection
) -> int:
    with edges_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            edge = json.loads(line)
            if not isinstance(edge, dict):
                raise ValueError(f"edge line {line_number} is not an object")
            source_url = str(edge.get("source_url") or "")
            parsed = urlparse(source_url)
            if (
                edge.get("url_kind") != "public_https"
                or parsed.scheme != "https"
                or (parsed.hostname or "").lower() != "www.parlamentodeandalucia.es"
            ):
                continue
            candidate = (
                source_url,
                int(edge.get("declared_bytes") or 0),
                str(edge.get("file_path") or ""),
                str(edge.get("file_sha256") or ""),
                str(edge.get("match_basis") or ""),
                str(edge.get("source_id") or ""),
            )
            inserted = planner.execute(
                """
                INSERT OR IGNORE INTO parliament_candidates (
                  source_url, declared_bytes, file_path, file_sha256,
                  match_basis, source_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                candidate,
            ).rowcount
            if inserted == 0:
                previous = planner.execute(
                    """
                    SELECT source_url, declared_bytes, file_path, file_sha256,
                           match_basis, source_id
                    FROM parliament_candidates
                    WHERE source_url = ?
                    """,
                    (source_url,),
                ).fetchone()
                if previous is None or tuple(previous) != candidate:
                    raise ValueError(f"ambiguous provenance for URL: {source_url}")
            db_ref = str(edge.get("db_ref") or "")
            table_name = str(edge.get("table_name") or "")
            if not db_ref or not table_name:
                raise ValueError(f"edge line {line_number} lacks exact provenance pair")
            planner.execute(
                """
                INSERT OR IGNORE INTO parliament_candidate_refs (
                  source_url, db_ref, table_name
                ) VALUES (?, ?, ?)
                """,
                (
                    source_url,
                    db_ref,
                    table_name,
                ),
            )
    planner.commit()

    joined = planner.execute(
        """
        SELECT c.*, r.db_ref, r.table_name
        FROM parliament_candidates c
        JOIN parliament_candidate_refs r ON r.source_url = c.source_url
        ORDER BY c.source_url, r.db_ref, r.table_name
        """
    )
    inserted_rows = 0
    for source_url, member_rows in groupby(joined, key=lambda row: str(row["source_url"])):
        members = iter(member_rows)
        edge = dict(next(members))
        reference_edges = [
            {
                "db_ref": str(edge.pop("db_ref")),
                "table_name": str(edge.pop("table_name")),
            }
        ]
        for member in members:
            reference_edges.append(
                {
                    "db_ref": str(member["db_ref"]),
                    "table_name": str(member["table_name"]),
                }
            )
            if len(reference_edges) > MAX_PROVENANCE_REFS_PER_DOCUMENT:
                raise ValueError(
                    "document provenance exceeds bounded reference count: "
                    f"{source_url}"
                )
        db_refs = sorted({row["db_ref"] for row in reference_edges})
        table_names = sorted({row["table_name"] for row in reference_edges})
        if edge.get("match_basis") != "path_checksum":
            raise ValueError(f"weak provenance basis: {source_url}")
        file_path = str(edge.get("file_path") or "")
        captured = safe_capture_path(raw_root, file_path)
        expected_bytes = int(edge.get("declared_bytes") or 0)
        expected_sha256 = str(edge.get("file_sha256") or "")
        if expected_bytes <= 0 or len(expected_sha256) != 64:
            raise ValueError(f"invalid provenance size/hash: {source_url}")
        if not captured.is_file() or captured.stat().st_size != expected_bytes:
            raise ValueError(f"captured Parliament file size mismatch: {source_url}")
        if sha256_path(captured) != expected_sha256:
            raise ValueError(f"captured Parliament file hash mismatch: {source_url}")
        document_kind = "pdf" if captured.suffix.lower() == ".pdf" else "html"
        validation_mode = (
            "parliament_pdf_signature"
            if document_kind == "pdf"
            else "parliament_html_semantic"
        )
        validation_contract = parliament_validation_contract(
            source_url=source_url,
            document_kind=document_kind,
        )
        payload = {
            "doc_url": source_url,
            "document_source_id": "parl_initiative_docs",
            "official_public_domain_personal_information_retained": True,
            "synthetic_or_mock_records_counted": False,
            "provenance": {
                "source_id": str(edge.get("source_id") or ""),
                "reference_edges": reference_edges,
                "table_names": table_names,
                "db_refs": db_refs,
                "captured_raw_path": repo_path(captured),
                "captured_content_sha256": expected_sha256,
                "captured_bytes": expected_bytes,
            },
            "validation_contract": validation_contract,
        }
        insert_selected_row(
            planner,
            {
                "source_pipeline_id": "provenance_edges:parlamento_andalucia",
                "source_id": "parl_initiative_docs",
                "provenance_source_id": str(edge.get("source_id") or ""),
                "source_url": source_url,
                "source_host": "www.parlamentodeandalucia.es",
                "document_kind": f"parliament_{document_kind}",
                "validation_mode": validation_mode,
                "size_decile": 1,
                "expected_bytes": expected_bytes,
                "expected_content_sha256": expected_sha256,
                "captured_raw_path": repo_path(captured),
                "partition_key": f"parlamento_andalucia:{document_kind}",
                "payload": payload,
            },
        )
        inserted_rows += 1
    planner.commit()

    for document_kind in ("parliament_html", "parliament_pdf"):
        total = int(
            planner.execute(
                "SELECT COUNT(*) FROM selected_rows WHERE document_kind = ?",
                (document_kind,),
            ).fetchone()[0]
        )
        if total == 0:
            continue
        planner.execute(
            """
            WITH ranked AS (
              SELECT
                source_url,
                MIN(
                  10,
                  CAST(
                    ((ROW_NUMBER() OVER (ORDER BY expected_bytes, source_url) - 1) * 10)
                    / COUNT(*) OVER ()
                    AS INTEGER
                  ) + 1
                ) AS size_decile
              FROM selected_rows
              WHERE document_kind = ?
            )
            UPDATE selected_rows
            SET size_decile = (
              SELECT ranked.size_decile
              FROM ranked
              WHERE ranked.source_url = selected_rows.source_url
            )
            WHERE document_kind = ?
            """,
            (document_kind, document_kind),
        )
    planner.commit()
    return inserted_rows


def validate_planner_rows(
    planner: sqlite3.Connection,
    *,
    expected_rows: int,
    expected_host_rows: dict[str, int],
    expected_mode_rows: dict[str, int],
) -> None:
    actual_rows = int(planner.execute("SELECT COUNT(*) FROM selected_rows").fetchone()[0])
    if actual_rows != expected_rows:
        raise ValueError(f"expected {expected_rows:,} rows, got {actual_rows:,}")
    distinct_urls = int(
        planner.execute("SELECT COUNT(DISTINCT source_url) FROM selected_rows").fetchone()[0]
    )
    if distinct_urls != actual_rows:
        raise ValueError("cohort URLs are not unique")
    host_counts = {
        str(row[0]): int(row[1])
        for row in planner.execute(
            "SELECT source_host, COUNT(*) FROM selected_rows GROUP BY source_host"
        )
    }
    mode_counts = {
        str(row[0]): int(row[1])
        for row in planner.execute(
            "SELECT validation_mode, COUNT(*) FROM selected_rows GROUP BY validation_mode"
        )
    }
    if host_counts != expected_host_rows:
        raise ValueError(f"host allocation mismatch: {host_counts}")
    if mode_counts != expected_mode_rows:
        raise ValueError(f"validation-mode allocation mismatch: {mode_counts}")
    for row in iter_selected_rows(planner):
        host = str(row["source_host"])
        if host in KNOWN_BLOCKED_HOSTS:
            raise ValueError(f"known blocked host selected: {host}")
        payload = row["payload"]
        if payload.get("synthetic_or_mock_records_counted") is not False:
            raise ValueError(f"real-data policy mismatch: {row['source_url']}")
        if payload.get("official_public_domain_personal_information_retained") is not True:
            raise ValueError(f"public-information policy mismatch: {row['source_url']}")
    if str(planner.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
        raise ValueError("planner database integrity failed")
    if planner.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("planner database foreign-key check failed")


def semantic_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "source_pipeline_id",
        "source_id",
        "source_url",
        "source_host",
        "document_kind",
        "validation_mode",
        "size_decile",
        "expected_bytes",
        "expected_content_sha256",
    )
    return [{field: row.get(field) for field in fields} for row in rows]


def semantic_sha256(rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        semantic_projection(rows),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def partitioned_semantic_sha256(rows: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(
                semantic_projection([row])[0],
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def execution_contract_sha256(rows: Iterable[dict[str, Any]]) -> str:
    fields = (
        "source_pipeline_id",
        "source_id",
        "provenance_source_id",
        "source_url",
        "source_host",
        "document_kind",
        "validation_mode",
        "size_decile",
        "expected_bytes",
        "expected_content_sha256",
        "captured_raw_path",
        "partition_key",
        "queue_priority",
        "payload",
    )
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(
                {field: row.get(field) for field in fields},
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def partition_slug(
    source_pipeline_id: str, size_decile: int, *, shard_ordinal: int | None = None
) -> str:
    safe_pipeline = "".join(
        character if character.isalnum() else "-"
        for character in source_pipeline_id.lower()
    ).strip("-")
    if shard_ordinal is None:
        return f"{safe_pipeline}-size-decile-{size_decile:02d}.jsonl.gz"
    pipeline_hash = hashlib.sha256(source_pipeline_id.encode("utf-8")).hexdigest()[:10]
    return (
        f"{safe_pipeline}-{pipeline_hash}-size-decile-{size_decile:02d}-"
        f"part-{shard_ordinal:06d}.jsonl.gz"
    )


def write_partitioned_rows(
    *,
    partition_dir: Path,
    rows: Iterable[dict[str, Any]],
    bounded_shards: bool = False,
    manifest_partition_dir: Path | None = None,
    max_partition_rows: int = MAX_PARTITION_ROWS,
    max_partition_uncompressed_bytes: int = MAX_PARTITION_UNCOMPRESSED_BYTES,
) -> dict[str, Any]:
    if max_partition_rows < 1 or max_partition_uncompressed_bytes < 1:
        raise ValueError("manifest partition bounds must be positive")
    if partition_dir.exists():
        raise ValueError(f"manifest partition directory already exists: {partition_dir}")
    partition_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{partition_dir.name}.", dir=partition_dir.parent)
    )
    descriptors: list[dict[str, Any]] = []
    seen_filenames: set[str] = set()
    total_rows = 0
    manifest_partition_dir = manifest_partition_dir or partition_dir
    try:
        for (source_pipeline_id, size_decile), member_rows in groupby(
            rows,
            key=lambda row: (
                str(row["source_pipeline_id"]),
                int(row["size_decile"]),
            ),
        ):
            shard_ordinal = 0
            filename = ""
            temporary_path: Path | None = None
            uncompressed_bytes = 0
            member_count = 0
            first_source_url = ""
            last_source_url = ""
            raw_handle = None
            compressed = None

            def finish_shard() -> None:
                nonlocal raw_handle, compressed
                if raw_handle is None or compressed is None or temporary_path is None:
                    return
                compressed.close()
                compressed = None
                raw_handle.flush()
                os.fsync(raw_handle.fileno())
                raw_handle.close()
                raw_handle = None
                descriptor = {
                    "path": repo_path(manifest_partition_dir / filename),
                    "compression": "gzip",
                    "rows": member_count,
                    "bytes": temporary_path.stat().st_size,
                    "uncompressed_bytes": uncompressed_bytes,
                    "sha256": sha256_path(temporary_path),
                    "source_pipeline_id": source_pipeline_id,
                    "size_decile": size_decile,
                    "first_source_url": first_source_url,
                    "last_source_url": last_source_url,
                }
                if bounded_shards:
                    descriptor["shard_ordinal"] = shard_ordinal
                descriptors.append(descriptor)

            def start_shard() -> None:
                nonlocal shard_ordinal, filename, temporary_path
                nonlocal uncompressed_bytes, member_count
                nonlocal first_source_url, last_source_url, raw_handle, compressed
                shard_ordinal += 1
                filename = partition_slug(
                    source_pipeline_id,
                    size_decile,
                    shard_ordinal=shard_ordinal if bounded_shards else None,
                )
                if filename in seen_filenames:
                    raise ValueError(f"manifest partition filename collision: {filename}")
                seen_filenames.add(filename)
                temporary_path = temporary / filename
                uncompressed_bytes = 0
                member_count = 0
                first_source_url = ""
                last_source_url = ""
                raw_handle = temporary_path.open("wb")
                compressed = gzip.GzipFile(
                    filename="", mode="wb", fileobj=raw_handle, mtime=0
                )

            try:
                for row in member_rows:
                    line = (
                        json.dumps(
                            row,
                            ensure_ascii=True,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                    if len(line) > max_partition_uncompressed_bytes:
                        raise ValueError(
                            "manifest row exceeds expanded-byte partition bound: "
                            f"{row['source_url']}"
                        )
                    needs_rollover = member_count > 0 and (
                        member_count >= max_partition_rows
                        or uncompressed_bytes + len(line)
                        > max_partition_uncompressed_bytes
                    )
                    if needs_rollover:
                        if not bounded_shards:
                            raise ValueError(
                                "manifest partition exceeds configured bound: "
                                f"{source_pipeline_id} decile {size_decile}"
                            )
                        finish_shard()
                    if raw_handle is None:
                        start_shard()
                    source_url = str(row["source_url"])
                    if member_count == 0:
                        first_source_url = source_url
                    last_source_url = source_url
                    if compressed is None:
                        raise ValueError("manifest partition writer is not open")
                    compressed.write(line)
                    member_count += 1
                    total_rows += 1
                    uncompressed_bytes += len(line)
                finish_shard()
            finally:
                if compressed is not None:
                    compressed.close()
                if raw_handle is not None:
                    raw_handle.close()
        os.replace(temporary, partition_dir)
        fsync_directory(partition_dir.parent)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {
        "layout": (
            "partitioned_jsonl_gzip_v2"
            if bounded_shards
            else "partitioned_jsonl_gzip_v1"
        ),
        "semantic_identity_contract": (
            "sha256_concatenated_canonical_projection_jsonl_v1"
        ),
        "rows": total_rows,
        "partitions": descriptors,
    }


def build_queue_db(
    *,
    schema_path: Path,
    out_db: Path,
    rows: Iterable[dict[str, Any]],
    prepared_at: str,
) -> None:
    out_db.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{out_db.name}.", suffix=".tmp", dir=out_db.parent
    )
    os.close(descriptor)
    try:
        conn = sqlite3.connect(temporary)
        try:
            conn.executescript(schema_path.read_text(encoding="utf-8"))
            conn.executemany(
                """
                INSERT INTO pipeline_work_items (
                  pipeline_id, item_key, partition_key, priority, state,
                  payload_json, available_at, attempts, max_attempts,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, 0, 2, ?, ?)
                """,
                (
                    (
                        PIPELINE_ID,
                        row["source_url"],
                        row["partition_key"],
                        int(row["queue_priority"]),
                        json.dumps(
                            row["payload"],
                            ensure_ascii=True,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        prepared_at,
                        prepared_at,
                        prepared_at,
                    )
                    for row in rows
                ),
            )
            conn.commit()
            if str(conn.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
                raise ValueError("prepared database integrity failed")
        finally:
            conn.close()
        os.replace(temporary, out_db)
        fsync_directory(out_db.parent)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--schema", default="etl/load/sqlite_schema.sql")
    parser.add_argument(
        "--provenance-edges",
        default="etl/data/manifests/real-document-provenance-edges.jsonl",
    )
    parser.add_argument("--raw-root", default="etl/data/raw")
    parser.add_argument("--host-health", required=True)
    parser.add_argument("--out-db", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument(
        "--manifest-layout",
        choices=("embedded_v2", "partitioned_v3", "partitioned_v4"),
        default="embedded_v2",
    )
    parser.add_argument("--manifest-partition-dir", default="")
    parser.add_argument(
        "--boe-document-rows", type=int, default=DEFAULT_BOE_DOCUMENT_ROWS
    )
    parser.add_argument(
        "--boe-summary-rows", type=int, default=DEFAULT_BOE_SUMMARY_ROWS
    )
    parser.add_argument("--prepared-at", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_db = Path(args.source_db)
    schema_path = Path(args.schema)
    edges_path = Path(args.provenance_edges)
    raw_root = Path(args.raw_root)
    host_health_path = Path(args.host_health)
    out_db = Path(args.out_db)
    manifest_out = Path(args.manifest_out)
    v4_layout = args.manifest_layout == "partitioned_v4"
    partitioned_layout = args.manifest_layout in {"partitioned_v3", "partitioned_v4"}
    partition_dir = (
        Path(
            args.manifest_partition_dir
            or manifest_out.with_suffix("").as_posix() + "-rows"
        )
        if partitioned_layout
        else None
    )
    prepared_at = str(args.prepared_at or "").strip() or utc_now()
    planner: sqlite3.Connection | None = None
    planner_path: Path | None = None
    output_locks: list[tuple[Path, int]] = []
    transaction: dict[str, Any] | None = None
    selected_rows = 0
    cohort_sha256 = ""
    manifest: dict[str, Any] = {}
    input_descriptors: dict[str, dict[str, Any]] = {}
    try:
        prepared_datetime = datetime.fromisoformat(prepared_at.replace("Z", "+00:00"))
        if prepared_datetime.tzinfo is None:
            raise ValueError("prepared-at must include a timezone")
        queue_created_before = prepared_datetime.astimezone(UTC).isoformat()
        if (
            args.manifest_layout == "embedded_v2"
            and args.boe_document_rows + args.boe_summary_rows > MAX_EMBEDDED_ROWS
        ):
            raise ValueError(
                "embedded manifest exceeds bounded compatibility limit; "
                "use --manifest-layout partitioned_v4"
            )
        for required in (source_db, schema_path, edges_path, host_health_path):
            if not required.is_file():
                raise ValueError(f"required input missing: {required}")
        if not raw_root.is_dir():
            raise ValueError(f"raw root missing: {raw_root}")
        manifest_out.parent.mkdir(parents=True, exist_ok=True)
        targets = {"database": out_db, "manifest": manifest_out}
        if partition_dir is not None:
            targets["partitions"] = partition_dir
        output_locks = acquire_output_locks(list(targets.values()))
        recover_stale_transaction(
            journal_path=transaction_journal_path(targets),
            targets=targets,
        )
        for output in targets.values():
            if output is not None and output.exists():
                raise ValueError(f"output already exists: {output}")
        transaction = begin_output_transaction(targets)
        run_dir = transaction["run_dir"]
        staged_out_db = run_dir / "queue.db"
        staged_manifest = run_dir / "manifest.json"
        staged_partition_dir = run_dir / "rows" if partition_dir is not None else None
        require_checkpointed_sqlite(source_db)
        input_paths = {
            "producer": Path(__file__),
            "source_db": source_db,
            "schema": schema_path,
            "provenance_edges": edges_path,
            "host_health": host_health_path,
        }
        input_descriptors = {
            name: source_descriptor(path) for name, path in input_paths.items()
        }
        planner_path = run_dir / "planner.sqlite"
        planner = open_planner_store(planner_path)
        host_health = validate_host_health(host_health_path)
        source_conn = read_only_db(source_db)
        try:
            boe_rows = load_boe_rows(
                source_conn,
                planner,
                document_rows=args.boe_document_rows,
                summary_rows=args.boe_summary_rows,
                queue_created_before=queue_created_before,
            )
        finally:
            source_conn.rollback()
            source_conn.close()
        parliament_rows = load_parliament_rows(edges_path, raw_root, planner)
        parliament_mode_rows = {
            str(row[0]): int(row[1])
            for row in planner.execute(
                """
                SELECT validation_mode, COUNT(*)
                FROM selected_rows
                WHERE source_host = 'www.parlamentodeandalucia.es'
                GROUP BY validation_mode
                """
            )
        }
        expected_mode_rows = {
            "boe_document_identifier": args.boe_document_rows,
            "boe_summary_structure": args.boe_summary_rows,
            "parliament_html_semantic": parliament_mode_rows.get(
                "parliament_html_semantic", 0
            ),
            "parliament_pdf_signature": parliament_mode_rows.get(
                "parliament_pdf_signature", 0
            ),
        }
        expected_mode_rows = {
            key: value for key, value in expected_mode_rows.items() if value > 0
        }
        expected_host_rows = {
            "www.boe.es": boe_rows,
            "www.parlamentodeandalucia.es": parliament_rows,
        }
        expected_rows = sum(expected_host_rows.values())
        validate_planner_rows(
            planner,
            expected_rows=expected_rows,
            expected_host_rows=expected_host_rows,
            expected_mode_rows=expected_mode_rows,
        )
        selected_rows = int(
            planner.execute("SELECT COUNT(*) FROM selected_rows").fetchone()[0]
        )
        expected_prior_bytes = int(
            planner.execute(
                "SELECT COALESCE(SUM(expected_bytes), 0) FROM selected_rows"
            ).fetchone()[0]
        )
        host_counts = grouped_selected_counts(planner, "source_host")
        kind_counts = grouped_selected_counts(planner, "document_kind")
        mode_counts = grouped_selected_counts(planner, "validation_mode")
        selection_sha256 = partitioned_semantic_sha256(
            iter_selected_rows(planner)
        )
        if partitioned_layout:
            cohort_sha256 = selection_sha256
            embedded_rows: list[dict[str, Any]] | None = None
        else:
            if selected_rows > MAX_EMBEDDED_ROWS:
                raise ValueError(
                    "embedded manifest exceeds bounded compatibility limit; "
                    "use --manifest-layout partitioned_v4"
                )
            embedded_rows = list(
                iter_selected_rows(planner, include_reference_edges=False)
            )
            cohort_sha256 = semantic_sha256(embedded_rows)
        execution_sha256 = execution_contract_sha256(
            iter_selected_rows(
                planner,
                include_queue_priority=True,
                include_reference_edges=v4_layout,
            )
        )
        build_queue_db(
            schema_path=schema_path,
            out_db=staged_out_db,
            rows=iter_selected_rows(
                planner,
                include_queue_priority=True,
                include_reference_edges=v4_layout,
            ),
            prepared_at=prepared_at,
        )
        planner.commit()
        planner_store_bytes = planner_path.stat().st_size
        manifest = {
            "schema_version": (
                "real_document_fetch_scale_cohort_v4"
                if args.manifest_layout == "partitioned_v4"
                else (
                    "real_document_fetch_scale_cohort_v3"
                    if args.manifest_layout == "partitioned_v3"
                    else "real_document_fetch_scale_cohort_v2"
                )
            ),
            "prepared_at": prepared_at,
            "status": "ready",
            "cohort_id": f"real_document_fetch_scale_cohort_{cohort_sha256[:24]}",
            "cohort_semantic_sha256": cohort_sha256,
            "cohort_selection_sha256": selection_sha256,
            "selection_identity_contract": (
                "sha256_concatenated_canonical_projection_jsonl_v1"
            ),
            "pipeline_id": PIPELINE_ID,
            "policy": {
                "official_real_documents_only": True,
                "synthetic_or_mock_records_counted": False,
                "official_public_domain_personal_information_retained": True,
                "known_blocked_rows_selected": 0,
                "known_blocked_hosts_excluded": sorted(KNOWN_BLOCKED_HOSTS),
                "dynamic_official_html_requires_semantic_contract": True,
                "official_content_revisions_preserved_and_measured": True,
            },
            "selection": {
                "method": "deterministic_official_host_kind_and_captured_size_decile",
                "rows": selected_rows,
                "expected_prior_bytes": expected_prior_bytes,
                "hosts": dict(sorted(host_counts.items())),
                "document_kinds": dict(sorted(kind_counts.items())),
                "validation_modes": dict(sorted(mode_counts.items())),
                "size_deciles": 10,
                "source_queue_created_before": queue_created_before,
            },
            "planning": {
                "schema_version": PLANNER_SCHEMA_VERSION,
                "backend": "disk_backed_sqlite",
                "candidate_deduplication": "sqlite_primary_key",
                "selected_row_iteration": "ordered_sqlite_cursor",
                "source_query_temp_store": "file",
                "queue_insertion": "streamed_executemany",
                "queue_priority": "deterministic_negative_host_rank_db_only",
                "partition_writes": (
                    "streamed_bounded_shards"
                    if args.manifest_layout == "partitioned_v4"
                    else (
                        "streamed_group_cursor"
                        if partitioned_layout
                        else "bounded_embedded_compatibility"
                    )
                ),
                "full_cohort_materialized_in_memory": (
                    not partitioned_layout
                ),
                "partition_members_materialized_in_memory": False,
                "embedded_compatibility_max_rows": MAX_EMBEDDED_ROWS,
                "partition_max_rows": MAX_PARTITION_ROWS,
                "partition_max_uncompressed_bytes": (
                    MAX_PARTITION_UNCOMPRESSED_BYTES
                ),
                "output_locking": "sorted_per_target_kernel_flock_v1",
                "output_publication": "journaled_manifest_last_bundle_v1",
                "input_immutability": (
                    "sha256_before_after_checkpointed_sqlite_v1"
                ),
                "provenance_reference_edges": (
                    "exact_db_ref_table_name_pairs_bounded_10000_v1"
                ),
                "planner_store_bytes": planner_store_bytes,
            },
            "host_health": {
                "status": host_health.get("status"),
                "probe_requests": int(
                    (host_health.get("method") or {}).get("probe_requests") or 0
                ),
                "eligible_hosts": sorted(EXPECTED_HOST_ROWS),
            },
            "inputs": {
                **input_descriptors,
                "source_sqlite_snapshot": {
                    "transaction": "read_only_snapshot",
                    "wal_required_empty": True,
                },
            },
            "output_db": repo_path(out_db),
        }
        if args.manifest_layout == "partitioned_v4":
            manifest["execution_contract"] = {
                "schema_version": "real_document_fetch_execution_contract_v1",
                "sha256": execution_sha256,
                "includes_payload_and_queue_priority": True,
            }
        if partitioned_layout:
            if partition_dir is None or staged_partition_dir is None:
                raise ValueError("partition directory is required for partitioned manifest")
            manifest["row_manifest"] = write_partitioned_rows(
                partition_dir=staged_partition_dir,
                bounded_shards=v4_layout,
                manifest_partition_dir=partition_dir,
                rows=iter_selected_rows(
                    planner,
                    include_reference_edges=v4_layout,
                ),
            )
            if int(manifest["row_manifest"]["rows"]) != selected_rows:
                raise ValueError("partitioned manifest row balance failed")
        else:
            if embedded_rows is None:
                raise ValueError("embedded manifest rows were not prepared")
            manifest["rows"] = embedded_rows
        require_checkpointed_sqlite(source_db)
        for name, path in input_paths.items():
            validate_unchanged_input(path, input_descriptors[name])
        manifest["planning"]["peak_rss_bytes"] = peak_rss_bytes()
        write_json_atomic(staged_manifest, manifest)
        planner.close()
        planner = None
        planner_path.unlink()
        planner_path = None
        publish_transaction_artifact(
            transaction,
            role="database",
            staged_path=staged_out_db,
        )
        if staged_partition_dir is not None:
            publish_transaction_artifact(
                transaction,
                role="partitions",
                staged_path=staged_partition_dir,
            )
        publish_transaction_artifact(
            transaction,
            role="manifest",
            staged_path=staged_manifest,
        )
        finish_output_transaction(transaction)
        transaction = None
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR real document fetch scale cohort preparation: {exc}")
        return 2
    finally:
        if planner is not None:
            planner.close()
        if planner_path is not None:
            planner_path.unlink(missing_ok=True)
        if transaction is not None:
            try:
                rollback_output_transaction(transaction)
            except (OSError, ValueError, json.JSONDecodeError) as cleanup_exc:
                print(
                    "ERROR real document fetch transaction cleanup requires "
                    f"inspection: {cleanup_exc}"
                )
        release_output_locks(output_locks)
    print(
        "OK real document fetch scale cohort -> "
        f"{out_db} (rows={selected_rows} prior_bytes={manifest['selection']['expected_prior_bytes']} "
        f"sha256={cohort_sha256})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
