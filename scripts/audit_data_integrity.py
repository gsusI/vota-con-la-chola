#!/usr/bin/env python3
"""Fail closed on physical, relational, and operational data corruption."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASES = (
    "etl/data/staging/politicos-es.db",
    "etl/data/staging/parlamentario-es.db",
    "etl/data/staging/eurostat-indicators-real-s2-20260811.db",
    "etl/data/staging/placsp-contracts-real-s1-20260811.db",
)
DEFAULT_TEXT_ROOT = "etl/data/derived/parl_initiative_doc_texts"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def stale_ingestion_runs(
    connection: sqlite3.Connection,
    *,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    if not table_exists(connection, "ingestion_runs"):
        return []
    rows = connection.execute(
        """
        SELECT run_id, source_id, started_at, records_seen, records_loaded
        FROM ingestion_runs
        WHERE status = 'running'
        ORDER BY run_id
        """
    ).fetchall()
    stale: list[dict[str, Any]] = []
    for row in rows:
        try:
            started_at = parse_timestamp(str(row["started_at"]))
        except (TypeError, ValueError):
            stale.append({**dict(row), "reason": "invalid_started_at"})
            continue
        if started_at <= cutoff:
            stale.append({**dict(row), "reason": "stale_running_status"})
    return stale


def audit_database(
    path: Path,
    *,
    stale_after_hours: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = now or utc_now()
    result: dict[str, Any] = {
        "path": display_path(path),
        "bytes": path.stat().st_size if path.is_file() else None,
        "checks": {},
        "issues": [],
    }
    if not path.is_file():
        result["checks"]["exists"] = False
        result["issues"].append("missing_database")
        return result
    result["checks"]["exists"] = True

    connection: sqlite3.Connection | None = None
    try:
        connection = open_read_only(path)
        quick_check_rows = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
        physical_ok = quick_check_rows == ["ok"]
        result["checks"]["sqlite_quick_check"] = physical_ok
        if not physical_ok:
            result["issues"].append("sqlite_physical_corruption")
            result["quick_check_errors"] = quick_check_rows[:20]
            return result

        foreign_key_violations = sum(
            1 for _row in connection.execute("PRAGMA foreign_key_check")
        )
        result["foreign_key_violations"] = foreign_key_violations
        result["checks"]["foreign_keys"] = foreign_key_violations == 0
        if foreign_key_violations:
            result["issues"].append("foreign_key_violations")

        lost_and_found_rows = 0
        if table_exists(connection, "lost_and_found"):
            lost_and_found_rows = int(
                connection.execute("SELECT COUNT(*) FROM lost_and_found").fetchone()[0]
            )
        result["lost_and_found_rows"] = lost_and_found_rows
        result["checks"]["no_recovery_residue"] = lost_and_found_rows == 0
        if lost_and_found_rows:
            result["issues"].append("sqlite_recovery_residue")

        stale = stale_ingestion_runs(
            connection,
            cutoff=observed_at - timedelta(hours=stale_after_hours),
        )
        result["stale_ingestion_runs"] = stale
        result["checks"]["no_stale_ingestion_runs"] = not stale
        if stale:
            result["issues"].append("stale_ingestion_runs")
    except sqlite3.DatabaseError as exc:
        result["checks"]["sqlite_quick_check"] = False
        result["issues"].append("sqlite_unreadable")
        result["sqlite_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if connection is not None:
            connection.close()

    return result


def audit_zero_byte_artifacts(root: Path) -> dict[str, Any]:
    paths: list[str] = []
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or "quarantine" in path.relative_to(root).parts:
                continue
            if path.stat().st_size == 0:
                paths.append(display_path(path))
    return {
        "root": display_path(root),
        "exists": root.is_dir(),
        "zero_byte_files": paths,
        "checks": {"no_zero_byte_artifacts": not paths},
        "issues": ["zero_byte_artifacts"] if paths else [],
    }


def staging_database_paths(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return ()
    candidates = set(root.glob("*.db")) | set(root.glob("*.db.*"))
    return tuple(
        sorted(
            path
            for path in candidates
            if path.is_file() and path.suffix not in {".shm", ".wal"}
        )
    )


def build_report(
    database_paths: Iterable[Path],
    *,
    text_root: Path,
    stale_after_hours: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = now or utc_now()
    databases = [
        audit_database(
            path,
            stale_after_hours=stale_after_hours,
            now=observed_at,
        )
        for path in database_paths
    ]
    artifacts = audit_zero_byte_artifacts(text_root)
    issue_count = sum(len(item["issues"]) for item in databases) + len(artifacts["issues"])
    return {
        "generated_at": iso_utc(observed_at),
        "status": "ok" if issue_count == 0 else "failed",
        "policy": {
            "stale_running_after_hours": stale_after_hours,
            "quarantine_directories_excluded": True,
        },
        "summary": {
            "databases_checked": len(databases),
            "databases_with_issues": sum(bool(item["issues"]) for item in databases),
            "issue_count": issue_count,
            "zero_byte_artifacts": len(artifacts["zero_byte_files"]),
        },
        "databases": databases,
        "derived_artifacts": artifacts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", action="append", dest="databases")
    parser.add_argument("--scan-staging", action="store_true")
    parser.add_argument("--staging-root", default="etl/data/staging")
    parser.add_argument("--text-root", default=DEFAULT_TEXT_ROOT)
    parser.add_argument("--stale-after-hours", type=int, default=24)
    parser.add_argument("--report-out")
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stale_after_hours < 1:
        raise SystemExit("--stale-after-hours must be at least 1")

    if args.scan_staging:
        database_paths = list(staging_database_paths(REPO_ROOT / args.staging_root))
    else:
        requested = args.databases or list(DEFAULT_DATABASES)
        database_paths = [REPO_ROOT / value for value in requested]

    report = build_report(
        database_paths,
        text_root=REPO_ROOT / args.text_root,
        stale_after_hours=args.stale_after_hours,
    )
    if args.report_out:
        output_path = REPO_ROOT / args.report_out
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 1 if args.enforce and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
