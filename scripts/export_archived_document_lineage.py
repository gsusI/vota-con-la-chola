#!/usr/bin/env python3
"""Recover exact document lineage from preserved read-only staging databases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY_ROOT = Path("etl/data/raw")
DEFAULT_INVENTORY_MANIFEST = Path(
    "etl/data/manifests/real-document-format-inventory.jsonl"
)
DEFAULT_QUEUE = Path("etl/data/manifests/document-provenance-gap-queue.jsonl")
# Preserve lineage from every repo-local legacy database, including historical
# root-level databases created before staging paths became canonical.
DEFAULT_DATABASE_ROOT = Path(".")
ACTIVE_DATABASES_ALREADY_AUDITED = {
    Path("etl/data/staging/politicos-es.db"),
}
DEFAULT_MANIFEST = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "archived-document-source-lineage.jsonl"
)
DEFAULT_REPORT = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "archived-document-source-lineage.json"
)
DISALLOWED_HOSTS = {
    "",
    "0.0.0.0",
    "127.0.0.1",
    "example.com",
    "example.invalid",
    "example.org",
    "localhost",
}
SHA256_RE_LENGTH = 64


class ArchivedLineageError(RuntimeError):
    """Raised when archived lineage inputs violate the recovery contract."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-root", default=str(DEFAULT_INVENTORY_ROOT))
    parser.add_argument(
        "--inventory-manifest",
        default=str(DEFAULT_INVENTORY_MANIFEST),
    )
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--database-root", default=str(DEFAULT_DATABASE_ROOT))
    parser.add_argument("--db", action="append", dest="databases")
    parser.add_argument("--manifest-out", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT))
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def safe_repo_path(value: str | Path) -> Path:
    candidate = (REPO_ROOT / value).resolve()
    try:
        candidate.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ArchivedLineageError(f"path escapes repository: {value}") from exc
    return candidate


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def public_url(value: Any) -> str | None:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or (parsed.hostname or "").lower() in DISALLOWED_HOSTS
    ):
        return None
    return url


def normalize_inventory_path(value: Any) -> str | None:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return None
    marker = "etl/data/raw/"
    if marker in raw:
        raw = raw.split(marker, 1)[1]
    elif raw.startswith("raw/"):
        raw = raw[len("raw/") :]
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix().removeprefix("./")


def load_queue(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ArchivedLineageError(
                    f"invalid queue JSON at line {line_number}: {exc}"
                ) from exc
            document_path = str(item.get("path") or "")
            sha256 = str(item.get("sha256") or "").lower()
            if not document_path or len(sha256) != SHA256_RE_LENGTH:
                raise ArchivedLineageError(
                    f"invalid queue contract at line {line_number}"
                )
            rows[document_path] = item
    return rows


def load_inventory_targets(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ArchivedLineageError(
                    f"invalid inventory JSON at line {line_number}: {exc}"
                ) from exc
            document_path = str(item.get("path") or "")
            sha256 = str(item.get("sha256") or "").lower()
            if (
                not document_path
                or len(sha256) != SHA256_RE_LENGTH
                or item.get("real_data_status") != "eligible_real_capture"
                or "samples" in PurePosixPath(document_path).parts
            ):
                raise ArchivedLineageError(
                    f"invalid real inventory contract at line {line_number}"
                )
            rows[document_path] = item
    return rows


def discover_databases(database_root: Path) -> list[Path]:
    excluded = {
        (REPO_ROOT / path).resolve() for path in ACTIVE_DATABASES_ALREADY_AUDITED
    }
    return sorted(
        path
        for path in database_root.rglob("politicos*.db")
        if path.is_file() and path.resolve() not in excluded
    )


def metadata_columns(
    connection: sqlite3.Connection, table: str
) -> tuple[str, str, str, str | None, str | None] | None:
    columns = {
        str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')
    }
    if "raw_path" not in columns or "content_sha256" not in columns:
        return None
    url_column = (
        "source_url"
        if "source_url" in columns
        else "doc_url"
        if "doc_url" in columns
        else None
    )
    if url_column is None:
        return None
    return (
        "raw_path",
        "content_sha256",
        url_column,
        "bytes" if "bytes" in columns else None,
        "source_id" if "source_id" in columns else None,
    )


def run_export(
    *,
    inventory_root: Path,
    inventory_manifest_path: Path,
    queue_path: Path,
    database_paths: list[Path],
    manifest_out: Path,
    report_out: Path,
) -> dict[str, Any]:
    inventory = load_inventory_targets(inventory_manifest_path)
    queue = load_queue(queue_path)
    counts: Counter[str] = Counter()
    candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    metadata_sources: dict[tuple[str, str, str], set[tuple[str, str]]] = defaultdict(
        set
    )
    database_statuses: list[dict[str, Any]] = []
    actual_sha_cache: dict[str, str] = {}
    for database_path in sorted(database_paths):
        db_ref = display_path(database_path)
        if not database_path.is_file():
            database_statuses.append({"path": db_ref, "status": "missing"})
            continue
        connection = sqlite3.connect(
            f"{database_path.resolve().as_uri()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        matched_in_database = 0
        try:
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            for table in (
                "raw_fetches",
                "run_fetches",
                "document_fetches",
                "text_documents",
            ):
                if table not in tables:
                    continue
                columns = metadata_columns(connection, table)
                if columns is None:
                    continue
                raw_column, sha_column, url_column, bytes_column, source_column = (
                    columns
                )
                select_bytes = f'"{bytes_column}"' if bytes_column else "NULL"
                select_source = f'"{source_column}"' if source_column else "NULL"
                query = (
                    f'SELECT "{raw_column}" AS raw_path, '
                    f'"{sha_column}" AS content_sha256, '
                    f'"{url_column}" AS source_url, '
                    f"{select_bytes} AS declared_bytes, "
                    f"{select_source} AS source_id "
                    f'FROM "{table}" WHERE "{raw_column}" IS NOT NULL'
                )
                for row in connection.execute(query):
                    counts["metadata_rows_scanned"] += 1
                    normalized_path = normalize_inventory_path(row["raw_path"])
                    inventory_item = inventory.get(normalized_path or "")
                    if inventory_item is None:
                        continue
                    counts["inventory_path_metadata_rows"] += 1
                    source_url = public_url(row["source_url"])
                    if source_url is None:
                        counts["skipped_non_public_url"] += 1
                        continue
                    observed_sha = str(row["content_sha256"] or "").lower()
                    expected_sha = str(inventory_item["sha256"])
                    declared_bytes = row["declared_bytes"]
                    expected_bytes = int(inventory_item["bytes"])
                    if observed_sha != expected_sha:
                        counts["skipped_sha_mismatch"] += 1
                        continue
                    if (
                        not isinstance(declared_bytes, int)
                        or declared_bytes != expected_bytes
                    ):
                        counts["skipped_bytes_mismatch"] += 1
                        continue
                    capture_path = inventory_root / str(normalized_path)
                    if not capture_path.is_file():
                        counts["skipped_missing_capture"] += 1
                        continue
                    if str(normalized_path) not in actual_sha_cache:
                        actual_sha_cache[str(normalized_path)] = sha256_file(
                            capture_path
                        )
                    actual_sha = actual_sha_cache[str(normalized_path)]
                    if (
                        actual_sha != expected_sha
                        or capture_path.stat().st_size != expected_bytes
                    ):
                        counts["skipped_capture_integrity_mismatch"] += 1
                        continue
                    key = (str(normalized_path), source_url, expected_sha)
                    if key not in candidates:
                        candidates[key] = {
                            "schema_version": "archived_document_source_lineage_v1",
                            "capture_status": "checksum_capture_present",
                            "capture": {
                                "path": f"etl/data/raw/{normalized_path}",
                                "bytes": expected_bytes,
                                "sha256": expected_sha,
                            },
                            "source_id": str(
                                row["source_id"] or inventory_item["source_group"]
                            ),
                            "source_url": source_url,
                            "was_pending_gap": normalized_path in queue,
                            "public_domain_personal_information_retained": True,
                            "synthetic_or_mock_records_counted": False,
                        }
                        metadata_sources[key].add((db_ref, table))
                    else:
                        counts["duplicate_exact_metadata_rows"] += 1
                    matched_in_database += 1
            database_statuses.append(
                {
                    "path": db_ref,
                    "status": "ok",
                    "accepted_metadata_rows": matched_in_database,
                }
            )
        finally:
            connection.close()
    accepted_database_refs = {
        db_ref for sources in metadata_sources.values() for db_ref, _table in sources
    }
    db_hashes = {
        display_path(path): sha256_file(path)
        for path in database_paths
        if path.is_file() and display_path(path) in accepted_database_refs
    }
    records: list[dict[str, Any]] = []
    for key in sorted(candidates):
        item = candidates[key]
        item["metadata_sources"] = [
            {
                "database": db_ref,
                "database_sha256": db_hashes[db_ref],
                "table": table,
            }
            for db_ref, table in sorted(metadata_sources[key])
        ]
        records.append(item)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(
        "".join(
            json.dumps(item, ensure_ascii=True, sort_keys=True) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
    counts["accepted_unique_relations"] = len(records)
    counts["accepted_unique_files"] = len({item["capture"]["path"] for item in records})
    counts["pending_gap_files_recovered"] = len(
        {item["capture"]["path"] for item in records if item["was_pending_gap"]}
    )
    report = {
        "schema_version": "archived_document_source_lineage_report_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok",
        "policy": {
            "exact_path_bytes_sha_and_public_url_required": True,
            "placeholder_hosts_rejected": True,
            "source_databases_opened_read_only": True,
            "synthetic_or_mock_records_counted": False,
            "public_domain_personal_information_retained": True,
        },
        "queue": {
            "path": display_path(queue_path),
            "rows": len(queue),
            "bytes": queue_path.stat().st_size,
            "sha256": sha256_file(queue_path),
        },
        "inventory": {
            "path": display_path(inventory_manifest_path),
            "rows": len(inventory),
            "bytes": inventory_manifest_path.stat().st_size,
            "sha256": sha256_file(inventory_manifest_path),
        },
        "databases": database_statuses,
        "counts": dict(sorted(counts.items())),
        "manifest": {
            "path": display_path(manifest_out),
            "rows": len(records),
            "bytes": manifest_out.stat().st_size,
            "sha256": sha256_file(manifest_out),
        },
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
        inventory_root = safe_repo_path(args.inventory_root)
        inventory_manifest_path = safe_repo_path(args.inventory_manifest)
        queue_path = safe_repo_path(args.queue)
        database_paths = (
            [safe_repo_path(value) for value in args.databases]
            if args.databases
            else discover_databases(safe_repo_path(args.database_root))
        )
        report = run_export(
            inventory_root=inventory_root,
            inventory_manifest_path=inventory_manifest_path,
            queue_path=queue_path,
            database_paths=database_paths,
            manifest_out=safe_repo_path(args.manifest_out),
            report_out=safe_repo_path(args.report_out),
        )
    except (ArchivedLineageError, OSError, sqlite3.DatabaseError, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps(report["counts"], ensure_ascii=True, sort_keys=True))
    if args.enforce and int(report["counts"].get("accepted_unique_files", 0)) < 1:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
