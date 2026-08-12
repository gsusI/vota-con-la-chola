#!/usr/bin/env python3
"""Rebuild queryable SQLite tables from checksum-verified restored Parquet corpora."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.semantic_contracts import peak_rss_mb
from scripts.publicar_hf_scale_snapshot import (
    ARTIFACT_CONTRACT_SCHEMA_VERSION,
    CORPUS_ID_RE,
    SCHEMA_VERSION,
    ScaleOriginError,
    artifact_contract_sha256,
    load_json_object,
    safe_artifact_relative_path,
    safe_repo_path,
    sha256_file,
    write_json,
)

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def sql_identifier(value: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ScaleOriginError(f"unsafe SQLite identifier: {value!r}")
    return f'"{value}"'


def sqlite_type(arrow_type: Any) -> str:
    import pyarrow as pa

    if pa.types.is_integer(arrow_type) or pa.types.is_boolean(arrow_type):
        return "INTEGER"
    if pa.types.is_floating(arrow_type):
        return "REAL"
    if pa.types.is_binary(arrow_type) or pa.types.is_large_binary(arrow_type):
        return "BLOB"
    return "TEXT"


def sqlite_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if value is None or isinstance(value, (str, int, float, bytes)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
    return str(value)


def update_logical_hash(digest: Any, values: list[Any] | tuple[Any, ...]) -> None:
    normalized = [
        {"bytes_hex": value.hex()} if isinstance(value, bytes) else value
        for value in values
    ]
    digest.update(
        json.dumps(normalized, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    )
    digest.update(b"\n")


def restored_reference_path(root: Path) -> Path:
    explicit = root / "restore-reference.json"
    if explicit.is_file():
        return explicit
    return root / "remote-latest.json"


def validate_restored_release(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = root / "manifest.json"
    reference_path = restored_reference_path(root)
    manifest = load_json_object(manifest_path)
    reference = load_json_object(reference_path)
    manifest_sha256 = sha256_file(manifest_path)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ScaleOriginError("restored manifest schema is unsupported")
    if reference.get("schema_version") != SCHEMA_VERSION:
        raise ScaleOriginError("restored reference schema is unsupported")
    if reference.get("manifest_sha256") != manifest_sha256:
        raise ScaleOriginError("restored manifest checksum differs from reference")
    contract = manifest.get("artifact_contract")
    if (
        not isinstance(contract, dict)
        or contract.get("schema_version") != ARTIFACT_CONTRACT_SCHEMA_VERSION
    ):
        raise ScaleOriginError("restored artifact contract schema is unsupported")
    contract_sha256 = artifact_contract_sha256(manifest)
    if contract.get("sha256") != contract_sha256:
        raise ScaleOriginError("restored artifact contract checksum is invalid")
    if reference.get("artifact_contract_sha256") != contract_sha256:
        raise ScaleOriginError("restored reference artifact contract differs")
    policy = manifest.get("policy")
    if not isinstance(policy, dict) or any(
        policy.get(key) is not True
        for key in (
            "official_real_records_only",
            "synthetic_or_mock_records_forbidden",
            "official_public_domain_personal_information_retained",
        )
    ):
        raise ScaleOriginError("restored release fails mandatory real-data policy")
    return manifest, reference


def corpus_files(
    *, root: Path, manifest: dict[str, Any], corpus_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    corpora = {
        str(item.get("id") or ""): item
        for item in manifest.get("corpora", [])
        if isinstance(item, dict) and item.get("id")
    }
    corpus = corpora.get(corpus_id)
    if corpus is None:
        raise ScaleOriginError(f"unknown corpus ID: {corpus_id}")
    if corpus.get("kind") != "parquet_manifest":
        raise ScaleOriginError(
            f"SQLite rebuild currently requires a Parquet corpus: {corpus_id}"
        )
    entries = [
        item
        for item in manifest.get("files", [])
        if isinstance(item, dict)
        and item.get("kind") == "data"
        and item.get("corpus_id") == corpus_id
    ]
    entries.sort(key=lambda item: str(item.get("path") or ""))
    if len(entries) != int(corpus.get("files") or 0):
        raise ScaleOriginError(f"restored data-file count differs for {corpus_id}")
    for entry in entries:
        relative = safe_artifact_relative_path(str(entry.get("path") or ""))
        path = (root / relative).resolve()
        if root != path and root not in path.parents:
            raise ScaleOriginError(f"restored file escapes root: {relative}")
        expected_bytes = int(entry.get("bytes") or -1)
        expected_sha256 = str(entry.get("sha256") or "")
        if (
            not path.is_file()
            or int(path.stat().st_size) != expected_bytes
            or sha256_file(path) != expected_sha256
        ):
            raise ScaleOriginError(f"restored file checksum mismatch: {relative}")
    return corpus, entries


def create_metadata_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE rebuild_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE rebuild_files (
          corpus_id TEXT NOT NULL,
          path TEXT NOT NULL,
          bytes INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          rows INTEGER NOT NULL,
          PRIMARY KEY (corpus_id, path)
        );
        """
    )


def rebuild_parquet_corpus(
    *,
    root: Path,
    manifest: dict[str, Any],
    reference: dict[str, Any],
    corpus_id: str,
    output_path: Path,
    batch_rows: int,
    max_peak_rss_mb: float,
) -> dict[str, Any]:
    import pyarrow.parquet as pq

    corpus, entries = corpus_files(root=root, manifest=manifest, corpus_id=corpus_id)
    table_name = f"corpus_{corpus_id}"
    sql_table = sql_identifier(table_name)
    partial = output_path.with_name(f".{output_path.name}.partial-{os.getpid()}")
    if output_path.exists() or partial.exists():
        raise ScaleOriginError(f"output already exists: {output_path.name}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    imported_rows = 0
    imported_bytes = 0
    schema_names: list[str] | None = None
    identity_column = ""
    file_reports: list[dict[str, Any]] = []
    input_logical_hash = hashlib.sha256()
    connection = sqlite3.connect(partial)
    try:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA temp_store = MEMORY")
        create_metadata_tables(connection)
        connection.execute("BEGIN")
        for entry in entries:
            relative = safe_artifact_relative_path(str(entry["path"]))
            path = root / relative
            parquet = pq.ParquetFile(path)
            names = list(parquet.schema_arrow.names)
            if schema_names is None:
                schema_names = names
                if "row_ordinal" in schema_names:
                    raise ScaleOriginError("Parquet schema reserves row_ordinal")
                columns_sql = [
                    '"row_ordinal" INTEGER PRIMARY KEY',
                    *[
                        f"{sql_identifier(field.name)} {sqlite_type(field.type)}"
                        for field in parquet.schema_arrow
                    ],
                ]
                connection.execute(
                    f"CREATE TABLE {sql_table} ({', '.join(columns_sql)})"
                )
                identity_column = next(
                    (
                        candidate
                        for candidate in (
                            "mandate_id",
                            "fact_id",
                            "observation_id",
                            "ledger_entry_id",
                            "candidate_occurrence_id",
                        )
                        if candidate in schema_names
                    ),
                    "",
                )
            elif names != schema_names:
                raise ScaleOriginError(
                    f"Parquet schema drift in restored file: {relative.as_posix()}"
                )
            assert schema_names is not None
            quoted_columns = ", ".join(
                ['"row_ordinal"', *[sql_identifier(name) for name in schema_names]]
            )
            placeholders = ", ".join("?" for _ in range(len(schema_names) + 1))
            insert_sql = (
                f"INSERT INTO {sql_table} ({quoted_columns}) VALUES ({placeholders})"
            )
            file_rows = 0
            for batch in parquet.iter_batches(batch_size=batch_rows):
                rows = []
                for raw_row in batch.to_pylist():
                    imported_rows += 1
                    file_rows += 1
                    values = [sqlite_value(raw_row[name]) for name in schema_names]
                    update_logical_hash(input_logical_hash, values)
                    rows.append(
                        (
                            imported_rows,
                            *values,
                        )
                    )
                connection.executemany(insert_sql, rows)
            imported_bytes += int(entry["bytes"])
            connection.execute(
                "INSERT INTO rebuild_files(corpus_id,path,bytes,sha256,rows) "
                "VALUES (?,?,?,?,?)",
                (
                    corpus_id,
                    relative.as_posix(),
                    int(entry["bytes"]),
                    str(entry["sha256"]),
                    file_rows,
                ),
            )
            file_reports.append({"path": relative.as_posix(), "rows": file_rows})

        if schema_names is None:
            raise ScaleOriginError(f"restored corpus has no Parquet files: {corpus_id}")
        for column in (
            identity_column,
            "source_id" if "source_id" in schema_names else "",
            "source_record_id" if "source_record_id" in schema_names else "",
        ):
            if column:
                connection.execute(
                    f"CREATE INDEX {sql_identifier(f'idx_{table_name}_{column}')} "
                    f"ON {sql_table} ({sql_identifier(column)})"
                )
        metadata = {
            "schema_version": "restored_scale_sqlite_rebuild_v1",
            "corpus_id": corpus_id,
            "snapshot_date": str(manifest.get("snapshot_date") or ""),
            "release_id": str(reference.get("release_id") or ""),
            "manifest_sha256": str(reference.get("manifest_sha256") or ""),
            "artifact_contract_sha256": str(
                reference.get("artifact_contract_sha256") or ""
            ),
            "selection_mode": str(
                reference.get("selection_mode") or "legacy_latest_pointer"
            ),
            "official_real_records_only": "true",
            "synthetic_or_mock_records_forbidden": "true",
            "official_public_domain_personal_information_retained": "true",
        }
        connection.executemany(
            "INSERT INTO rebuild_metadata(key,value) VALUES (?,?)",
            sorted(metadata.items()),
        )
        connection.commit()
        actual_rows = int(
            connection.execute(f"SELECT COUNT(*) FROM {sql_table}").fetchone()[0]
        )
        rebuilt_logical_hash = hashlib.sha256()
        select_columns = ", ".join(sql_identifier(name) for name in schema_names)
        cursor = connection.execute(
            f"SELECT {select_columns} FROM {sql_table} ORDER BY row_ordinal"
        )
        while rows := cursor.fetchmany(batch_rows):
            for row in rows:
                update_logical_hash(rebuilt_logical_hash, row)
        distinct_identity = (
            int(
                connection.execute(
                    f"SELECT COUNT(DISTINCT {sql_identifier(identity_column)}) FROM {sql_table}"
                ).fetchone()[0]
            )
            if identity_column
            else None
        )
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_errors = list(connection.execute("PRAGMA foreign_key_check"))
    except BaseException:
        connection.close()
        partial.unlink(missing_ok=True)
        raise
    finally:
        try:
            connection.close()
        except sqlite3.Error:
            pass

    expected_rows = int(corpus.get("rows") or 0)
    expected_files = int(corpus.get("files") or 0)
    expected_bytes = int(corpus.get("bytes") or 0)
    peak_rss = peak_rss_mb()
    checks = {
        "rows_match_release": actual_rows == expected_rows,
        "files_match_release": len(entries) == expected_files,
        "bytes_match_release": imported_bytes == expected_bytes,
        "identity_unique_when_declared": distinct_identity in {None, actual_rows},
        "sqlite_integrity": integrity == "ok",
        "foreign_keys_valid": not foreign_key_errors,
        "logical_rows_exact": input_logical_hash.hexdigest()
        == rebuilt_logical_hash.hexdigest(),
        "bounded_peak_rss": peak_rss <= max_peak_rss_mb,
        "official_real_records_only": True,
        "synthetic_or_mock_records_forbidden": True,
        "official_public_domain_personal_information_retained": True,
    }
    if not all(checks.values()):
        partial.unlink(missing_ok=True)
        failed = ", ".join(key for key, value in checks.items() if not value)
        raise ScaleOriginError(f"rebuilt SQLite validation failed: {failed}")
    with partial.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(partial, output_path)
    return {
        "schema_version": "restored_scale_sqlite_rebuild_v1",
        "status": "ok",
        "corpus_id": corpus_id,
        "table": table_name,
        "output": output_path.name,
        "snapshot_date": manifest.get("snapshot_date"),
        "release_id": reference.get("release_id"),
        "selection_mode": reference.get("selection_mode", "legacy_latest_pointer"),
        "artifact_contract_sha256": reference.get("artifact_contract_sha256"),
        "totals": {
            "rows": actual_rows,
            "files": len(entries),
            "bytes": imported_bytes,
            "sqlite_bytes": int(output_path.stat().st_size),
            "distinct_identity": distinct_identity,
        },
        "checks": checks,
        "performance": {
            "batch_rows": batch_rows,
            "peak_rss_mb": peak_rss,
            "max_peak_rss_mb": max_peak_rss_mb,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        },
        "sqlite_sha256": sha256_file(output_path),
        "logical_rows_sha256": rebuilt_logical_hash.hexdigest(),
        "input_file_rows_total": sum(item["rows"] for item in file_reports),
        "public_domain_personal_information_retained": True,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-rows", type=int, default=10_000)
    parser.add_argument("--max-peak-rss-mb", type=float, default=1536.0)
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.batch_rows <= 0 or args.max_peak_rss_mb <= 0:
            raise ScaleOriginError("batch rows and RSS ceiling must be positive")
        if not CORPUS_ID_RE.fullmatch(args.corpus_id):
            raise ScaleOriginError(f"invalid corpus ID: {args.corpus_id!r}")
        root = safe_repo_path(REPO_ROOT, args.root, "restored root")
        output = safe_repo_path(REPO_ROOT, args.output, "SQLite output")
        manifest, reference = validate_restored_release(root)
        report = rebuild_parquet_corpus(
            root=root,
            manifest=manifest,
            reference=reference,
            corpus_id=args.corpus_id,
            output_path=output,
            batch_rows=args.batch_rows,
            max_peak_rss_mb=args.max_peak_rss_mb,
        )
        if args.report_out.strip():
            write_json(safe_repo_path(REPO_ROOT, args.report_out, "report"), report)
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    except (OSError, ScaleOriginError, sqlite3.Error, ValueError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
