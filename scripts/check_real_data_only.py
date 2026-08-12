#!/usr/bin/env python3
"""Fail closed when invented records can reach accountable data products."""

from __future__ import annotations

import argparse
import gzip
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


PROHIBITED_MARKERS: tuple[bytes, ...] = tuple(
    marker.casefold().encode("utf-8")
    for marker in (
        "example.invalid",
        "synthetic sample",
        "sample-metadatos",
        "EXP-2026-0001",
        "EXP-2026-0002",
        "EXP-2026-0003",
        "AND-2026-0001",
        "CAT-2026-0002",
        "BDNS-2026-1001",
        "BDNS-2026-1002",
        "BDNS-2026-1003",
        "AUTO-AND-2026-2001",
        "AUTO-CAT-2026-2002",
        "series:3feb2dae20867f4bf608324a",
        "series:4468f558922332ed237bf17f",
        "Real Decreto 123/2026, de 15 de febrero, por el que se actualizan medidas del regimen electoral general",
        "Orden INT/95/2026, de 12 de febrero, sobre administracion y censo electoral",
    )
)
TEXT_SUFFIXES = {".csv", ".html", ".json", ".jsonl", ".md", ".txt", ".xml"}


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file():
            yield path
            continue
        if not path.exists():
            continue
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file() and (
                candidate.suffix.casefold() in TEXT_SUFFIXES
                or candidate.name.casefold().endswith(".json.gz")
            ):
                yield candidate


def _read_scan_bytes(path: Path) -> bytes:
    if path.name.casefold().endswith(".json.gz"):
        with gzip.open(path, "rb") as handle:
            return handle.read()
    return path.read_bytes()


def scan_paths(paths: Iterable[Path]) -> tuple[int, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    files_scanned = 0
    for path in _iter_files(paths):
        files_scanned += 1
        try:
            folded = _read_scan_bytes(path).lower()
        except (OSError, EOFError) as exc:
            findings.append(
                {"kind": "unreadable_public_artifact", "path": str(path), "error": str(exc)}
            )
            continue
        for marker in PROHIBITED_MARKERS:
            if marker in folded:
                findings.append(
                    {
                        "kind": "prohibited_non_real_marker",
                        "path": str(path),
                        "marker": marker.decode("utf-8"),
                    }
                )
    return files_scanned, findings


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def scan_db(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return [{"kind": "database_missing", "path": str(path)}]
    findings: list[dict[str, Any]] = []
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        if _table_exists(conn, "source_records"):
            columns = _table_columns(conn, "source_records")
            searchable_columns = [
                column for column in ("raw_payload", "source_record_id") if column in columns
            ]
            if not searchable_columns:
                searchable_columns = []
            marker_sql = " OR ".join(
                "(" + " OR ".join(f"lower(CAST({column} AS TEXT)) LIKE ?" for column in searchable_columns) + ")"
                for _ in PROHIBITED_MARKERS
            )
            params = tuple(
                value
                for marker in PROHIBITED_MARKERS
                for value in [f"%{marker.decode('utf-8')}%"] * len(searchable_columns)
            )
            rows = (
                conn.execute(
                    f"""
                    SELECT source_id, COUNT(*)
                    FROM source_records
                    WHERE {marker_sql}
                    GROUP BY source_id
                    ORDER BY source_id
                    """,
                    params,
                ).fetchall()
                if marker_sql and "source_id" in columns
                else []
            )
            findings.extend(
                {
                    "kind": "prohibited_non_real_source_records",
                    "path": str(path),
                    "source_id": str(source_id),
                    "records": int(records),
                }
                for source_id, records in rows
            )
        if _table_exists(conn, "ingestion_runs"):
            rows = conn.execute(
                """
                SELECT source_id, COUNT(*)
                FROM ingestion_runs
                WHERE lower(COALESCE(message, '')) LIKE '%network-error-fallback%'
                   OR lower(COALESCE(message, '')) LIKE '%fallback-sample%'
                GROUP BY source_id
                ORDER BY source_id
                """
            ).fetchall()
            findings.extend(
                {
                    "kind": "implicit_fallback_ingestion_run",
                    "path": str(path),
                    "source_id": str(source_id),
                    "runs": int(runs),
                }
                for source_id, runs in rows
            )
    finally:
        conn.close()
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", action="append", default=[])
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--out", default="")
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_paths = [Path(value) for value in args.db] or [Path("etl/data/staging/politicos-es.db")]
    artifact_paths = [Path(value) for value in args.path] or [
        Path("etl/data/raw"),
        Path("etl/data/derived"),
        Path("etl/data/published"),
        Path("ui/gh-pages-next/public"),
    ]
    files_scanned, findings = scan_paths(artifact_paths)
    for db_path in db_paths:
        findings.extend(scan_db(db_path))
    report = {
        "schema_version": "real_data_only_validation_v1",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "policy": {
            "synthetic_or_mock_records_forbidden": True,
            "implicit_sample_fallback_forbidden": True,
            "official_public_domain_personal_information_retained": True,
        },
        "databases_scanned": [str(path) for path in db_paths],
        "artifact_roots_scanned": [str(path) for path in artifact_paths],
        "files_scanned": files_scanned,
        "findings_total": len(findings),
        "findings": findings,
        "ok": not findings,
    }
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if args.enforce and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
