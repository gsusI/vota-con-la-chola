#!/usr/bin/env python3
"""Reconcile the real document inventory with durable source metadata."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY_MANIFEST = Path(
    "etl/data/manifests/real-document-format-inventory.jsonl"
)
DEFAULT_FILE_MANIFEST = Path("etl/data/manifests/real-document-provenance-files.jsonl")
DEFAULT_EDGE_MANIFEST = Path("etl/data/manifests/real-document-provenance-edges.jsonl")
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "real-document-provenance-audit.json"
)
DEFAULT_DATABASES = (
    Path("etl/data/staging/politicos-es.db"),
    Path("etl/data/staging/parlamentario-es.db"),
    Path("etl/data/staging/placsp-contracts-real-s1-20260811.db"),
)
SUPPORTED_SUFFIXES = {".pdf", ".html", ".htm", ".xml"}
DISALLOWED_PUBLIC_HOSTS = {
    "",
    "0.0.0.0",
    "127.0.0.1",
    "example.com",
    "example.org",
    "localhost",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ProvenanceAuditError(RuntimeError):
    """Raised when an input or output violates the audit contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", default=str(DEFAULT_INVENTORY_ROOT))
    parser.add_argument("--inventory-manifest", default=str(DEFAULT_INVENTORY_MANIFEST))
    parser.add_argument("--db", action="append", dest="databases")
    parser.add_argument("--file-manifest-out", default=str(DEFAULT_FILE_MANIFEST))
    parser.add_argument("--edge-manifest-out", default=str(DEFAULT_EDGE_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce-integrity", action="store_true")
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text_artifact(path: Path) -> str:
    digest = hashlib.sha256()
    opener = gzip.open if path.suffix.lower() == ".gz" else Path.open
    with opener(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path, *, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.name


def safe_repo_path(value: str | Path, *, repo_root: Path) -> Path:
    candidate = (repo_root / value).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ProvenanceAuditError(f"path escapes repository: {value}") from exc
    return candidate


def normalize_repo_path(value: Any, *, repo_root: Path) -> str | None:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            marker = "/etl/"
            if marker not in raw:
                return None
            raw = "etl/" + raw.split(marker, 1)[1]
    normalized = PurePosixPath(raw)
    if normalized.is_absolute() or ".." in normalized.parts:
        return None
    return normalized.as_posix().removeprefix("./")


def normalize_inventory_path(
    value: Any,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> str | None:
    repo_path = normalize_repo_path(value, repo_root=repo_root)
    if repo_path is None:
        return None
    try:
        root_relative = (
            inventory_root.resolve().relative_to(repo_root.resolve()).as_posix()
        )
    except ValueError as exc:
        raise ProvenanceAuditError("inventory root must be inside repository") from exc
    prefix = root_relative.rstrip("/") + "/"
    if repo_path.startswith(prefix):
        return repo_path[len(prefix) :]
    if repo_path == root_relative:
        return None
    return repo_path


def public_url_kind(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host in DISALLOWED_PUBLIC_HOSTS:
        return "missing_or_non_public"
    return "public_https" if parsed.scheme == "https" else "public_http"


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def select_expression(columns: set[str], column: str) -> str:
    return f'"{column}"' if column in columns else "NULL"


def iter_metadata_rows(
    connection: sqlite3.Connection,
    table: str,
) -> Iterator[sqlite3.Row]:
    columns = table_columns(connection, table)
    if "raw_path" not in columns:
        return
    fetched_column = "fetched_at"
    if fetched_column not in columns and "last_attempt_at" in columns:
        fetched_column = "last_attempt_at"
    select = {
        "raw_path": select_expression(columns, "raw_path"),
        "content_sha256": select_expression(columns, "content_sha256"),
        "source_id": select_expression(columns, "source_id"),
        "source_url": select_expression(columns, "source_url"),
        "fetched_at": select_expression(columns, fetched_column),
        "bytes": select_expression(columns, "bytes"),
        "text_path": select_expression(columns, "text_path"),
        "text_sha256": select_expression(columns, "text_sha256"),
    }
    query = "SELECT " + ", ".join(
        f"{expression} AS {name}" for name, expression in select.items()
    )
    conditions = ['"raw_path" IS NOT NULL']
    if "text_path" in columns:
        conditions.append('"text_path" IS NOT NULL')
    query += f' FROM "{table}" WHERE ' + " OR ".join(conditions)
    yield from connection.execute(query)


def create_work_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = FILE;
        CREATE TABLE inventory (
          file_id INTEGER PRIMARY KEY,
          path TEXT NOT NULL UNIQUE,
          source_group TEXT NOT NULL,
          extension TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          item_status TEXT NOT NULL
        );
        CREATE INDEX inventory_sha_idx ON inventory(sha256);

        CREATE TABLE provenance (
          provenance_id INTEGER PRIMARY KEY,
          edge_key TEXT NOT NULL UNIQUE,
          db_ref TEXT NOT NULL,
          table_name TEXT NOT NULL,
          raw_path TEXT NOT NULL,
          normalized_path TEXT,
          content_sha256 TEXT,
          source_id TEXT,
          source_url TEXT,
          fetched_at TEXT,
          declared_bytes INTEGER,
          url_kind TEXT NOT NULL
        );
        CREATE INDEX provenance_path_idx ON provenance(normalized_path);
        CREATE INDEX provenance_sha_idx ON provenance(content_sha256);

        CREATE TABLE matches (
          file_id INTEGER NOT NULL,
          provenance_id INTEGER NOT NULL,
          match_basis TEXT NOT NULL,
          PRIMARY KEY(file_id, provenance_id)
        ) WITHOUT ROWID;
        CREATE INDEX matches_provenance_idx ON matches(provenance_id);

        CREATE TABLE text_refs (
          text_ref_id INTEGER PRIMARY KEY,
          ref_key TEXT NOT NULL UNIQUE,
          db_ref TEXT NOT NULL,
          source_id TEXT,
          source_url TEXT,
          text_path TEXT NOT NULL,
          text_sha256 TEXT
        );
        """
    )
    return connection


def load_inventory(
    work: sqlite3.Connection,
    manifest_path: Path,
) -> int:
    if not manifest_path.is_file():
        raise ProvenanceAuditError(f"inventory manifest missing: {manifest_path}")
    batch: list[tuple[str, str, str, int, str, str]] = []
    rows = 0
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProvenanceAuditError(
                    f"invalid inventory JSON at line {line_number}: {exc}"
                ) from exc
            path = str(item.get("path") or "")
            sha256 = str(item.get("sha256") or "").lower()
            if (
                not path
                or Path(path).is_absolute()
                or ".." in PurePosixPath(path).parts
            ):
                raise ProvenanceAuditError(
                    f"unsafe inventory path at line {line_number}: {path!r}"
                )
            if not SHA256_RE.fullmatch(sha256):
                raise ProvenanceAuditError(
                    f"invalid inventory SHA-256 at line {line_number}: {sha256!r}"
                )
            batch.append(
                (
                    path,
                    str(item.get("source_group") or "unknown"),
                    str(item.get("extension") or "unknown"),
                    int(item.get("bytes") or 0),
                    sha256,
                    str(item.get("status") or "unknown"),
                )
            )
            rows += 1
            if len(batch) >= 2_000:
                work.executemany(
                    """
                    INSERT INTO inventory(path, source_group, extension, bytes, sha256, item_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    batch,
                )
                batch.clear()
    if batch:
        work.executemany(
            """
            INSERT INTO inventory(path, source_group, extension, bytes, sha256, item_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
    work.commit()
    return rows


def metadata_edge_key(values: Iterable[Any]) -> str:
    encoded = "\x1f".join(str(value or "") for value in values).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_database_metadata(
    work: sqlite3.Connection,
    database_path: Path,
    *,
    repo_root: Path,
    inventory_root: Path,
) -> dict[str, Any]:
    db_ref = display_path(database_path, repo_root=repo_root)
    result: dict[str, Any] = {
        "path": db_ref,
        "bytes": database_path.stat().st_size if database_path.is_file() else None,
        "status": "ok",
        "raw_metadata_rows": 0,
        "text_metadata_rows": 0,
        "tables": {},
    }
    if not database_path.is_file():
        result["status"] = "missing"
        return result
    source = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        available_tables = {
            str(row[0])
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table in (
            "raw_fetches",
            "run_fetches",
            "ingestion_runs",
            "text_documents",
            "document_fetches",
        ):
            if table not in available_tables:
                continue
            table_raw_rows = 0
            table_text_rows = 0
            for row in iter_metadata_rows(source, table):
                normalized_path = normalize_inventory_path(
                    row["raw_path"],
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                if (
                    normalized_path
                    and Path(normalized_path).suffix.lower() in SUPPORTED_SUFFIXES
                ):
                    content_sha256 = str(row["content_sha256"] or "").lower() or None
                    if content_sha256 and not SHA256_RE.fullmatch(content_sha256):
                        content_sha256 = None
                    values = (
                        db_ref,
                        table,
                        normalized_path,
                        content_sha256,
                        row["source_id"],
                        row["source_url"],
                        row["fetched_at"],
                    )
                    work.execute(
                        """
                        INSERT OR IGNORE INTO provenance(
                          edge_key, db_ref, table_name, raw_path, normalized_path,
                          content_sha256, source_id, source_url, fetched_at,
                          declared_bytes, url_kind
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            metadata_edge_key(values),
                            db_ref,
                            table,
                            str(row["raw_path"] or ""),
                            normalized_path,
                            content_sha256,
                            row["source_id"],
                            row["source_url"],
                            row["fetched_at"],
                            row["bytes"],
                            public_url_kind(row["source_url"]),
                        ),
                    )
                    table_raw_rows += 1
                text_path = normalize_repo_path(row["text_path"], repo_root=repo_root)
                if text_path:
                    text_sha256 = str(row["text_sha256"] or "").lower() or None
                    if text_sha256 and not SHA256_RE.fullmatch(text_sha256):
                        text_sha256 = None
                    values = (
                        db_ref,
                        table,
                        text_path,
                        text_sha256,
                        row["source_id"],
                        row["source_url"],
                    )
                    work.execute(
                        """
                        INSERT OR IGNORE INTO text_refs(
                          ref_key, db_ref, source_id, source_url, text_path, text_sha256
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            metadata_edge_key(values),
                            db_ref,
                            row["source_id"],
                            row["source_url"],
                            text_path,
                            text_sha256,
                        ),
                    )
                    table_text_rows += 1
            result["tables"][table] = {
                "raw_metadata_rows": table_raw_rows,
                "text_metadata_rows": table_text_rows,
            }
            result["raw_metadata_rows"] += table_raw_rows
            result["text_metadata_rows"] += table_text_rows
        work.commit()
    except sqlite3.DatabaseError as exc:
        result["status"] = "unreadable"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        source.close()
    return result


def build_matches(work: sqlite3.Connection) -> None:
    work.executescript(
        """
        INSERT OR IGNORE INTO matches(file_id, provenance_id, match_basis)
        SELECT
          f.file_id,
          p.provenance_id,
          CASE
            WHEN p.content_sha256 = f.sha256 THEN 'path_checksum'
            WHEN p.content_sha256 IS NULL THEN 'path_only'
            ELSE 'path_checksum_conflict'
          END
        FROM inventory AS f
        JOIN provenance AS p ON p.normalized_path = f.path;

        INSERT OR IGNORE INTO matches(file_id, provenance_id, match_basis)
        SELECT f.file_id, p.provenance_id, 'content_checksum'
        FROM inventory AS f
        JOIN provenance AS p ON p.content_sha256 = f.sha256;
        """
    )
    work.commit()


FILE_SUMMARY_QUERY = """
SELECT
  f.file_id,
  f.path,
  f.source_group,
  f.extension,
  f.bytes,
  f.sha256,
  f.item_status,
  COUNT(m.provenance_id) AS provenance_edges,
  COUNT(DISTINCT CASE WHEN p.source_id IS NOT NULL THEN p.source_id END) AS source_ids,
  SUM(CASE WHEN p.url_kind IN ('public_http', 'public_https') THEN 1 ELSE 0 END) AS public_url_edges,
  SUM(CASE WHEN p.url_kind = 'public_https' THEN 1 ELSE 0 END) AS public_https_edges,
  MAX(CASE WHEN m.match_basis = 'path_checksum' THEN 1 ELSE 0 END) AS has_path_checksum,
  MAX(CASE WHEN m.match_basis = 'content_checksum' THEN 1 ELSE 0 END) AS has_content_checksum,
  MAX(CASE WHEN m.match_basis = 'path_only' THEN 1 ELSE 0 END) AS has_path_only,
  MAX(CASE WHEN m.match_basis = 'path_checksum_conflict' THEN 1 ELSE 0 END) AS has_conflict
FROM inventory AS f
LEFT JOIN matches AS m ON m.file_id = f.file_id
LEFT JOIN provenance AS p ON p.provenance_id = m.provenance_id
GROUP BY f.file_id
ORDER BY f.file_id
"""


def classification(row: sqlite3.Row) -> str:
    if int(row["has_path_checksum"] or 0):
        return "verified_path_checksum"
    if int(row["has_content_checksum"] or 0):
        return "verified_content_checksum"
    if int(row["has_path_only"] or 0):
        return "path_only_checksum_unverified"
    if int(row["has_conflict"] or 0):
        return "checksum_conflict"
    return "unlinked"


def write_file_manifest(
    work: sqlite3.Connection,
    output_path: Path,
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    totals: Counter[str] = Counter()
    by_source_group: dict[str, Counter[str]] = defaultdict(Counter)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in work.execute(FILE_SUMMARY_QUERY):
            status = classification(row)
            has_conflict = bool(row["has_conflict"])
            item = {
                "path": row["path"],
                "source_group": row["source_group"],
                "extension": row["extension"],
                "bytes": int(row["bytes"]),
                "sha256": row["sha256"],
                "inventory_status": row["item_status"],
                "provenance_status": status,
                "provenance_edges": int(row["provenance_edges"] or 0),
                "source_ids": int(row["source_ids"] or 0),
                "public_url_edges": int(row["public_url_edges"] or 0),
                "public_https_edges": int(row["public_https_edges"] or 0),
                "checksum_conflict": has_conflict,
            }
            handle.write(json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n")
            totals["files"] += 1
            totals["bytes"] += int(row["bytes"])
            totals[status] += 1
            totals["files_with_public_url"] += int(item["public_url_edges"] > 0)
            totals["files_with_public_https_url"] += int(item["public_https_edges"] > 0)
            totals["files_with_checksum_conflict"] += int(has_conflict)
            totals["inventory_non_ok_files"] += int(row["item_status"] != "ok")
            group = by_source_group[str(row["source_group"])]
            group["files"] += 1
            group["bytes"] += int(row["bytes"])
            group[status] += 1
            group["files_with_public_url"] += int(item["public_url_edges"] > 0)
    return dict(totals), {
        key: dict(sorted(value.items()))
        for key, value in sorted(by_source_group.items())
    }


def write_edge_manifest(work: sqlite3.Connection, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    query = """
    SELECT
      f.path AS file_path,
      f.sha256 AS file_sha256,
      p.db_ref,
      p.table_name,
      p.normalized_path AS metadata_path,
      p.content_sha256 AS metadata_sha256,
      p.source_id,
      p.source_url,
      p.fetched_at,
      p.declared_bytes,
      p.url_kind,
      m.match_basis
    FROM matches AS m
    JOIN inventory AS f ON f.file_id = m.file_id
    JOIN provenance AS p ON p.provenance_id = m.provenance_id
    ORDER BY f.file_id, p.provenance_id
    """
    with output_path.open("w", encoding="utf-8") as handle:
        for row in work.execute(query):
            handle.write(
                json.dumps(dict(row), ensure_ascii=True, sort_keys=True) + "\n"
            )
            rows += 1
    return rows


def audit_text_artifacts(
    work: sqlite3.Connection,
    *,
    repo_root: Path,
) -> dict[str, Any]:
    refs = int(work.execute("SELECT COUNT(*) FROM text_refs").fetchone()[0])
    unique_paths = int(
        work.execute("SELECT COUNT(DISTINCT text_path) FROM text_refs").fetchone()[0]
    )
    existing = 0
    missing = 0
    checksum_verified = 0
    checksum_conflicts = 0
    checksum_missing = 0
    missing_samples: list[str] = []
    conflict_samples: list[str] = []
    for row in work.execute(
        """
        SELECT text_path, GROUP_CONCAT(DISTINCT text_sha256) AS expected_hashes
        FROM text_refs
        GROUP BY text_path
        ORDER BY text_path
        """
    ):
        path = safe_repo_path(str(row["text_path"]), repo_root=repo_root)
        if not path.is_file():
            missing += 1
            if len(missing_samples) < 20:
                missing_samples.append(str(row["text_path"]))
            continue
        existing += 1
        expected = {
            value
            for value in str(row["expected_hashes"] or "").split(",")
            if SHA256_RE.fullmatch(value)
        }
        if not expected:
            checksum_missing += 1
            continue
        observed = sha256_text_artifact(path)
        if observed in expected:
            checksum_verified += 1
        else:
            checksum_conflicts += 1
            if len(conflict_samples) < 20:
                conflict_samples.append(str(row["text_path"]))
    return {
        "metadata_edges": refs,
        "unique_paths": unique_paths,
        "existing": existing,
        "missing": missing,
        "checksum_verified": checksum_verified,
        "checksum_unavailable": checksum_missing,
        "checksum_conflicts": checksum_conflicts,
        "missing_samples": missing_samples,
        "checksum_conflict_samples": conflict_samples,
    }


def artifact_reference(path: Path, *, repo_root: Path, rows: int) -> dict[str, Any]:
    return {
        "path": display_path(path, repo_root=repo_root),
        "rows": rows,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def unmatched_metadata_summary(work: sqlite3.Connection) -> dict[str, Any]:
    total = int(work.execute("SELECT COUNT(*) FROM provenance").fetchone()[0])
    matched = int(
        work.execute("SELECT COUNT(DISTINCT provenance_id) FROM matches").fetchone()[0]
    )
    samples = [
        {
            "path": row["normalized_path"],
            "source_id": row["source_id"],
            "table": row["table_name"],
        }
        for row in work.execute(
            """
            SELECT p.normalized_path, p.source_id, p.table_name
            FROM provenance AS p
            LEFT JOIN matches AS m ON m.provenance_id = p.provenance_id
            WHERE m.provenance_id IS NULL
            ORDER BY p.normalized_path
            LIMIT 20
            """
        )
    ]
    return {
        "metadata_edges": total,
        "matched_metadata_edges": matched,
        "unmatched_metadata_edges": total - matched,
        "unmatched_samples": samples,
    }


def run_audit(
    *,
    repo_root: Path,
    inventory_root: Path,
    inventory_manifest: Path,
    database_paths: list[Path],
    file_manifest_out: Path,
    edge_manifest_out: Path,
    report_out: Path,
) -> dict[str, Any]:
    if not inventory_root.is_dir():
        raise ProvenanceAuditError(f"inventory root missing: {inventory_root}")
    with tempfile.TemporaryDirectory(prefix="vota-document-provenance-") as temp_dir:
        work = create_work_database(Path(temp_dir) / "audit.sqlite")
        try:
            inventory_rows = load_inventory(work, inventory_manifest)
            databases = [
                load_database_metadata(
                    work,
                    path,
                    repo_root=repo_root,
                    inventory_root=inventory_root,
                )
                for path in database_paths
            ]
            build_matches(work)
            file_totals, by_source_group = write_file_manifest(
                work,
                file_manifest_out,
            )
            edge_rows = write_edge_manifest(work, edge_manifest_out)
            text_artifacts = audit_text_artifacts(work, repo_root=repo_root)
            metadata = unmatched_metadata_summary(work)
        finally:
            work.close()

    verified_files = int(file_totals.get("verified_path_checksum", 0)) + int(
        file_totals.get("verified_content_checksum", 0)
    )
    files_total = int(file_totals.get("files", 0))
    files_with_public_url = int(file_totals.get("files_with_public_url", 0))
    database_inputs_ok = all(item["status"] == "ok" for item in databases)
    integrity_passed = (
        files_total > 0
        and inventory_rows == files_total
        and database_inputs_ok
        and int(file_totals.get("inventory_non_ok_files", 0)) == 0
        and int(file_totals.get("files_with_checksum_conflict", 0)) == 0
        and int(text_artifacts["missing"]) == 0
        and int(text_artifacts["checksum_conflicts"]) == 0
    )
    complete_provenance = (
        files_total > 0
        and verified_files == files_total
        and files_with_public_url == files_total
    )
    report: dict[str, Any] = {
        "schema_version": "real_document_provenance_audit_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": (
            "failed"
            if not integrity_passed
            else "ok"
            if complete_provenance
            else "partial"
        ),
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_counted": False,
            "public_domain_personal_information_retained": True,
            "workstation_paths_forbidden_in_outputs": True,
            "checksum_or_content_address_required_for_verified_file": True,
        },
        "inventory": artifact_reference(
            inventory_manifest,
            repo_root=repo_root,
            rows=inventory_rows,
        ),
        "databases": databases,
        "file_manifest": artifact_reference(
            file_manifest_out,
            repo_root=repo_root,
            rows=files_total,
        ),
        "edge_manifest": artifact_reference(
            edge_manifest_out,
            repo_root=repo_root,
            rows=edge_rows,
        ),
        "totals": {
            **file_totals,
            "verified_checksum_files": verified_files,
            "verified_checksum_coverage": (
                round(verified_files / files_total, 6) if files_total else 0.0
            ),
            "public_url_coverage": (
                round(files_with_public_url / files_total, 6) if files_total else 0.0
            ),
            "provenance_edges": edge_rows,
        },
        "metadata": metadata,
        "text_artifacts": text_artifacts,
        "by_source_group": by_source_group,
        "checks": {
            "inventory_rows_reconciled": inventory_rows == files_total,
            "database_inputs_readable": database_inputs_ok,
            "inventory_files_parse_clean": int(
                file_totals.get("inventory_non_ok_files", 0)
            )
            == 0,
            "no_document_checksum_conflicts": int(
                file_totals.get("files_with_checksum_conflict", 0)
            )
            == 0,
            "all_referenced_text_artifacts_exist": int(text_artifacts["missing"]) == 0,
            "no_text_checksum_conflicts": int(text_artifacts["checksum_conflicts"])
            == 0,
            "integrity_passed": integrity_passed,
            "complete_checksum_provenance": verified_files == files_total,
            "complete_public_url_provenance": files_with_public_url == files_total,
            "promotion_ready": complete_provenance and integrity_passed,
        },
        "limitations": [
            "The audit covers only the declared inventory manifest and SQLite metadata inputs.",
            "Unlinked files remain real local bytes but do not count as fully traceable evidence until an official URL and checksum-backed metadata edge are recovered.",
            "A public HTTP(S) URL proves a public locator, not institutional completeness or long-term availability.",
            "This reconciliation does not increase the document corpus row count or prove extraction accuracy.",
        ],
        "next_action": (
            "Recover source URL, retrieval, and checksum metadata for every unlinked source group; regenerate the inventory and audit; then require promotion_ready before durable publication."
        ),
    }
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        repo_root = REPO_ROOT
        databases = [Path(value) for value in (args.databases or DEFAULT_DATABASES)]
        report = run_audit(
            repo_root=repo_root,
            inventory_root=safe_repo_path(args.inventory_root, repo_root=repo_root),
            inventory_manifest=safe_repo_path(
                args.inventory_manifest,
                repo_root=repo_root,
            ),
            database_paths=[
                safe_repo_path(path, repo_root=repo_root) for path in databases
            ],
            file_manifest_out=safe_repo_path(
                args.file_manifest_out,
                repo_root=repo_root,
            ),
            edge_manifest_out=safe_repo_path(
                args.edge_manifest_out,
                repo_root=repo_root,
            ),
            report_out=safe_repo_path(args.report_out, repo_root=repo_root),
        )
    except (OSError, sqlite3.DatabaseError, ProvenanceAuditError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "files": report["totals"]["files"],
                "verified_checksum_files": report["totals"]["verified_checksum_files"],
                "files_with_public_url": report["totals"]["files_with_public_url"],
                "checksum_conflicts": report["totals"]["files_with_checksum_conflict"],
                "promotion_ready": report["checks"]["promotion_ready"],
                "report": display_path(
                    safe_repo_path(args.report_out, repo_root=REPO_ROOT),
                    repo_root=REPO_ROOT,
                ),
            },
            sort_keys=True,
        )
    )
    return (
        1 if args.enforce_integrity and not report["checks"]["integrity_passed"] else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
