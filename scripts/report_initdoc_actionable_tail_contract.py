#!/usr/bin/env python3
"""Machine-readable actionable-tail contract report for initiative docs.

Focus:
- quantify missing initiative doc rows
- exclude known redundant Senado global_enmiendas rows
- report actionable queue size and strict gate outcome
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_source_ids(csv_value: str) -> list[str]:
    vals = [x.strip() for x in str(csv_value or "").split(",")]
    out: list[str] = []
    seen: set[str] = set()
    for v in vals:
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Initiative-doc actionable-tail contract report")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--initiative-source-ids",
        default="senado_iniciativas",
        help="CSV of parl_initiatives.source_id values",
    )
    p.add_argument(
        "--sample-limit",
        type=int,
        default=20,
        help="Actionable sample rows to include in output",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when actionable_missing > 0.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _load_redundant_senado_initiatives(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT pid.initiative_id
        FROM parl_initiative_documents pid
        JOIN parl_initiatives i ON i.initiative_id = pid.initiative_id
        JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
        WHERE i.source_id = 'senado_iniciativas'
          AND pid.doc_kind = 'bocg'
          AND td.source_id = 'parl_initiative_docs'
          AND (
            pid.doc_url LIKE '%/xml/INI-3-%'
            OR pid.doc_url LIKE '%/publicaciones/pdf/senado/bocg/%'
            OR pid.doc_url LIKE '%tipoFich=3%'
          )
        """
    ).fetchall()
    return {str(r["initiative_id"] or "") for r in rows if str(r["initiative_id"] or "")}


def _is_redundant_senado_global(row: sqlite3.Row, *, redundant_initiatives: set[str]) -> bool:
    initiative_source_id = str(row["initiative_source_id"] or "")
    initiative_id = str(row["initiative_id"] or "")
    doc_kind = str(row["doc_kind"] or "")
    doc_url = str(row["doc_url"] or "")
    return (
        initiative_source_id == "senado_iniciativas"
        and initiative_id in redundant_initiatives
        and doc_kind == "bocg"
        and "global_enmiendas_vetos_" in doc_url
    )


def build_actionable_report(
    conn: sqlite3.Connection,
    *,
    source_ids: list[str],
    sample_limit: int,
) -> dict[str, Any]:
    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"""
        SELECT
          i.source_id AS initiative_source_id,
          d.initiative_id,
          d.doc_kind,
          d.doc_url,
          COALESCE(df.last_http_status, 0) AS last_http_status,
          COALESCE(df.attempts, 0) AS attempts,
          COALESCE(df.last_attempt_at, '') AS last_attempt_at
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        LEFT JOIN document_fetches df ON df.doc_url = d.doc_url
        WHERE i.source_id IN ({placeholders})
          AND d.source_record_pk IS NULL
        ORDER BY
          COALESCE(df.last_http_status, 0) DESC,
          COALESCE(df.attempts, 0) DESC,
          d.initiative_id ASC,
          d.doc_kind ASC,
          d.doc_url ASC
        """,
        source_ids,
    ).fetchall()

    redundant_inits = _load_redundant_senado_initiatives(conn)
    redundant_rows: list[sqlite3.Row] = []
    actionable_rows: list[sqlite3.Row] = []
    for r in rows:
        if _is_redundant_senado_global(r, redundant_initiatives=redundant_inits):
            redundant_rows.append(r)
        else:
            actionable_rows.append(r)

    def _status_buckets(in_rows: list[sqlite3.Row]) -> list[dict[str, int]]:
        buckets: dict[int, int] = {}
        for r in in_rows:
            status = int(r["last_http_status"] or 0)
            buckets[status] = int(buckets.get(status, 0)) + 1
        out = [{"status": int(k), "count": int(v)} for k, v in buckets.items()]
        out.sort(key=lambda x: (-int(x["count"]), -int(x["status"])))
        return out

    actionable_sample: list[dict[str, Any]] = []
    for r in actionable_rows[: max(0, int(sample_limit))]:
        actionable_sample.append(
            {
                "initiative_source_id": str(r["initiative_source_id"] or ""),
                "initiative_id": str(r["initiative_id"] or ""),
                "doc_kind": str(r["doc_kind"] or ""),
                "doc_url": str(r["doc_url"] or ""),
                "last_http_status": int(r["last_http_status"] or 0),
                "attempts": int(r["attempts"] or 0),
                "last_attempt_at": str(r["last_attempt_at"] or ""),
            }
        )

    total_missing = len(rows)
    redundant_missing = len(redundant_rows)
    actionable_missing = len(actionable_rows)
    actionable_queue_empty = actionable_missing == 0

    return {
        "generated_at": now_utc_iso(),
        "initiative_source_ids": source_ids,
        "total_missing": int(total_missing),
        "redundant_missing": int(redundant_missing),
        "actionable_missing": int(actionable_missing),
        "redundant_missing_pct": round((redundant_missing / total_missing), 6) if total_missing > 0 else 0.0,
        "actionable_missing_pct": round((actionable_missing / total_missing), 6) if total_missing > 0 else 0.0,
        "checks": {
            "actionable_queue_empty": bool(actionable_queue_empty),
        },
        "status_buckets_total_missing": _status_buckets(list(rows)),
        "status_buckets_actionable_missing": _status_buckets(actionable_rows),
        "actionable_sample": actionable_sample,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    source_ids = parse_source_ids(args.initiative_source_ids)
    if not source_ids:
        print(json.dumps({"error": "initiative-source-ids empty"}, ensure_ascii=False))
        return 2

    try:
        with open_db(db_path) as conn:
            report = build_actionable_report(
                conn,
                source_ids=source_ids,
                sample_limit=int(args.sample_limit or 0),
            )
    except sqlite3.Error as exc:
        print(json.dumps({"error": f"sqlite error: {exc}"}, ensure_ascii=False))
        return 3

    report["db"] = str(db_path)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out or "").strip()) if str(args.out or "").strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    actionable_missing = int(report.get("actionable_missing") or 0)
    if bool(args.strict) and actionable_missing > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

