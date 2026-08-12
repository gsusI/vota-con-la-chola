#!/usr/bin/env python3
"""Remove known invented records and every derived row that depends on them."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_real_data_only import PROHIBITED_MARKERS


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _delete_by_ids(
    conn: sqlite3.Connection,
    *,
    table: str,
    column: str,
    values: list[Any],
) -> int:
    if not values or not _table_exists(conn, table):
        return 0
    placeholders = ",".join("?" for _ in values)
    cursor = conn.execute(
        f"DELETE FROM {_q(table)} WHERE {_q(column)} IN ({placeholders})", values
    )
    return max(0, int(cursor.rowcount))


def find_source_record_pks(conn: sqlite3.Connection) -> list[int]:
    marker_sql = " OR ".join(
        "(lower(raw_payload) LIKE ? OR lower(source_record_id) LIKE ?)"
        for _ in PROHIBITED_MARKERS
    )
    params = tuple(
        value
        for marker in PROHIBITED_MARKERS
        for value in (
            f"%{marker.decode('utf-8')}%",
            f"%{marker.decode('utf-8')}%",
        )
    )
    return [
        int(row[0])
        for row in conn.execute(
            f"SELECT source_record_pk FROM source_records WHERE {marker_sql}", params
        ).fetchall()
    ]


def purge(conn: sqlite3.Connection, *, apply: bool) -> dict[str, Any]:
    conn.execute("PRAGMA foreign_keys=ON")
    source_record_pks = find_source_record_pks(conn)
    placeholders = ",".join("?" for _ in source_record_pks) or "NULL"
    policy_event_ids = [
        str(row[0])
        for row in conn.execute(
            f"SELECT policy_event_id FROM policy_events WHERE source_record_pk IN ({placeholders})",
            source_record_pks,
        ).fetchall()
    ] if _table_exists(conn, "policy_events") else []
    issue_ids = [f"policy-event:{value}" for value in policy_event_ids]
    run_rows = conn.execute(
        """
        SELECT run_id, raw_path
        FROM ingestion_runs
        WHERE lower(COALESCE(message, '')) LIKE '%network-error-fallback%'
           OR lower(COALESCE(message, '')) LIKE '%fallback-sample%'
           OR lower(COALESCE(source_url, '')) LIKE 'file:%/samples/placsp_%'
           OR lower(COALESCE(source_url, '')) LIKE 'file:%/samples/bdns_%'
        ORDER BY run_id
        """
    ).fetchall() if _table_exists(conn, "ingestion_runs") else []
    run_ids = [int(row[0]) for row in run_rows]
    raw_paths = [str(row[1]) for row in run_rows if str(row[1] or "").strip()]
    report: dict[str, Any] = {
        "schema_version": "non_real_record_purge_v1",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "apply": bool(apply),
        "source_record_pks": source_record_pks,
        "policy_event_ids": policy_event_ids,
        "issue_ids": issue_ids,
        "ingestion_run_ids": run_ids,
        "raw_paths": raw_paths,
        "deleted": {},
    }
    if not apply:
        report["ok"] = True
        return report

    deleted: dict[str, int] = {}
    conn.execute("BEGIN IMMEDIATE")
    try:
        deleted["accountability_ledger_entries_by_issue"] = _delete_by_ids(
            conn, table="accountability_ledger_entries", column="issue_id", values=issue_ids
        )
        deleted["accountability_ledger_entries_by_policy_event"] = _delete_by_ids(
            conn,
            table="accountability_ledger_entries",
            column="policy_event_id",
            values=policy_event_ids,
        )
        deleted["accountability_issues"] = _delete_by_ids(
            conn, table="accountability_issues", column="issue_id", values=issue_ids
        )

        # Delete or detach every row with a declared FK to the affected source records.
        for table_row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall():
            table = str(table_row[0])
            if table == "source_records":
                continue
            for fk in conn.execute(f"PRAGMA foreign_key_list({_q(table)})").fetchall():
                referenced_table = str(fk[2])
                from_column = str(fk[3])
                on_delete = str(fk[6] or "NO ACTION").upper()
                if referenced_table != "source_records":
                    continue
                key = f"{table}.{from_column}"
                if on_delete == "CASCADE":
                    continue
                if on_delete == "SET NULL":
                    cursor = conn.execute(
                        f"UPDATE {_q(table)} SET {_q(from_column)}=NULL "
                        f"WHERE {_q(from_column)} IN ({placeholders})",
                        source_record_pks,
                    )
                    deleted[f"detached:{key}"] = max(0, int(cursor.rowcount))
                else:
                    deleted[key] = _delete_by_ids(
                        conn,
                        table=table,
                        column=from_column,
                        values=source_record_pks,
                    )

        deleted["source_records"] = _delete_by_ids(
            conn,
            table="source_records",
            column="source_record_pk",
            values=source_record_pks,
        )
        deleted["raw_fetches"] = _delete_by_ids(
            conn, table="raw_fetches", column="run_id", values=run_ids
        )
        deleted["ingestion_runs"] = _delete_by_ids(
            conn, table="ingestion_runs", column="run_id", values=run_ids
        )
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_rows:
            raise RuntimeError(f"foreign_key_check failed after purge: {fk_rows[:10]}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    report["deleted"] = deleted
    report["remaining_non_real_source_records"] = len(find_source_record_pks(conn))
    report["foreign_key_errors"] = 0
    report["ok"] = report["remaining_non_real_source_records"] == 0
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    db_path = Path(args.db)
    conn = sqlite3.connect(db_path)
    try:
        report = purge(conn, apply=bool(args.apply))
    finally:
        conn.close()
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
