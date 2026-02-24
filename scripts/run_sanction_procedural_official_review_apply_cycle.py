#!/usr/bin/env python3
"""Run strict cycle: readiness -> apply -> lane status for official procedural metrics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.apply_sanction_procedural_official_review_metrics import apply_rows, _norm as _apply_norm
from scripts.report_sanction_procedural_official_review_apply_readiness import (
    build_report as build_readiness_report,
)
from scripts.report_sanction_procedural_official_review_apply_readiness import (
    _write_csv as write_readiness_queue_csv,
)
from scripts.report_sanction_procedural_official_review_status import (
    build_status_report as build_official_review_status_report,
)

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SOURCE_ID = "boe_api_legal"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Run readiness+apply cycle for official procedural-review metrics"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--in", dest="in_file", required=True, help="Input CSV")
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--readiness-tolerance", type=float, default=0.01)
    ap.add_argument("--readiness-queue-limit", type=int, default=0)
    ap.add_argument("--readiness-csv-out", default="")
    ap.add_argument("--readiness-out", default="")
    ap.add_argument("--strict-readiness", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status-queue-limit", type=int, default=0)
    ap.add_argument("--status-out", default="")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({str(k or ""): str(v or "") for k, v in row.items()})
    return rows


def _write_json(path: str, payload: dict[str, Any]) -> None:
    token = _apply_norm(path)
    if not token:
        return
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_cycle(
    *,
    db_path: Path,
    in_path: Path,
    source_id: str,
    snapshot_date: str,
    readiness_tolerance: float,
    readiness_queue_limit: int,
    readiness_csv_out: str,
    strict_readiness: bool,
    dry_run: bool,
    status_queue_limit: int,
) -> tuple[int, dict[str, Any]]:
    conn = open_db(db_path)
    try:
        readiness = build_readiness_report(
            conn,
            input_csv=in_path,
            tolerance=float(readiness_tolerance),
            queue_limit=int(readiness_queue_limit),
        )
        if _apply_norm(readiness_csv_out):
            write_readiness_queue_csv(Path(readiness_csv_out), list(readiness.get("queue") or []))

        status_before = build_official_review_status_report(conn, queue_limit=int(status_queue_limit))

        apply_report: dict[str, Any] = {
            "skipped": False,
            "skip_reason": "",
            "dry_run": bool(dry_run),
            "counts": {},
        }
        exit_code = 0
        if bool(strict_readiness) and str(readiness.get("status")) != "ok":
            apply_report = {
                "skipped": True,
                "skip_reason": "readiness_not_ok",
                "dry_run": bool(dry_run),
                "counts": {
                    "rows_seen": 0,
                    "rows_ready": 0,
                    "rows_upserted": 0,
                },
            }
            exit_code = 4
        else:
            csv_rows = _read_csv_rows(in_path)
            apply_report = apply_rows(
                conn,
                rows=csv_rows,
                default_source_id=_apply_norm(source_id) or DEFAULT_SOURCE_ID,
                snapshot_date=_apply_norm(snapshot_date) or today_utc_date(),
                dry_run=bool(dry_run),
            )
            apply_report["skipped"] = False
            apply_report["skip_reason"] = ""

        status_after = build_official_review_status_report(conn, queue_limit=int(status_queue_limit))
    finally:
        conn.close()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "input_csv": str(in_path),
        "strict_readiness": bool(strict_readiness),
        "dry_run": bool(dry_run),
        "readiness": readiness,
        "status_before": status_before,
        "apply": apply_report,
        "status_after": status_after,
    }
    return int(exit_code), payload


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    in_path = Path(args.in_file)

    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2
    if not in_path.exists():
        print(json.dumps({"error": f"input csv not found: {in_path}"}, ensure_ascii=False))
        return 2

    exit_code, payload = run_cycle(
        db_path=db_path,
        in_path=in_path,
        source_id=args.source_id,
        snapshot_date=args.snapshot_date,
        readiness_tolerance=float(args.readiness_tolerance),
        readiness_queue_limit=int(args.readiness_queue_limit),
        readiness_csv_out=args.readiness_csv_out,
        strict_readiness=bool(args.strict_readiness),
        dry_run=bool(args.dry_run),
        status_queue_limit=int(args.status_queue_limit),
    )
    _write_json(args.readiness_out, dict(payload.get("readiness") or {}))
    _write_json(args.status_out, dict(payload.get("status_after") or {}))
    _write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
